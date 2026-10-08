#include "image_io.h"

#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *program)
{
    fprintf(stderr,
        "Uso: %s imagem.rgb largura altura prefixo_saida [opcoes]\n"
        "  --iterations N   tentativas RANSAC (padrao 1000)\n"
        "  --threshold T    limiar do residuo horizontal em pixels (padrao 1)\n"
        "  --min-inliers M  minimo de inliers (padrao 50, pelo menos 3)\n"
        "  --seed S         seed de 32 bits (padrao 42)\n"
        "  --thickness E    espessura horizontal em pixels (padrao 3)\n", program);
}

static bool parse_integer(const char *text, size_t *value)
{
    char *end;
    errno = 0;
    if (*text < '0' || *text > '9') {
        return false;
    }
    unsigned long long parsed = strtoull(text, &end, 10);
    if (errno != 0 || *end != '\0' || parsed > SIZE_MAX) {
        return false;
    }
    *value = (size_t)parsed;
    return true;
}

static bool parse_options(int argc, char **argv, LaneConfig *config)
{
    for (int i = 5; i < argc; i += 2) {
        if (i + 1 == argc) {
            return false;
        }
        if (strcmp(argv[i], "--threshold") == 0) {
            char *end;
            errno = 0;
            config->ransac.threshold = strtod(argv[i + 1], &end);
            if (errno != 0 || end == argv[i + 1] || *end != '\0' ||
                !isfinite(config->ransac.threshold) || config->ransac.threshold <= 0) {
                return false;
            }
            continue;
        }
        size_t value;
        if (!parse_integer(argv[i + 1], &value)) {
            return false;
        }
        if (strcmp(argv[i], "--iterations") == 0 && value > 0) {
            config->ransac.iterations = value;
        } else if (strcmp(argv[i], "--min-inliers") == 0 && value >= 3) {
            config->ransac.min_inliers = value;
        } else if (strcmp(argv[i], "--seed") == 0 && value <= UINT32_MAX) {
            config->ransac.seed = (uint32_t)value;
        } else if (strcmp(argv[i], "--thickness") == 0 && value > 0 && value <= INT_MAX) {
            config->thickness = value;
        } else {
            return false;
        }
    }
    return true;
}

typedef struct {
    Image image;
    BinaryMask mask;
    Point *points;
    size_t *indices;
    size_t capacity;
} HostBuffers;

static void free_buffers(HostBuffers *buffers)
{
    free(buffers->indices);
    free(buffers->points);
    free(buffers->mask.pixels);
    free(buffers->image.pixels);
}

static bool allocate_workspace(HostBuffers *buffers)
{
    size_t width = buffers->image.width;
    size_t height = buffers->image.height;
    /* Pior caso: ceil(width/2) corridas em cada linha dentro da ROI. */
    size_t capacity = ((width + 1) / 2) * (height - (size_t)(0.55 * (double)height));
    if (capacity > UINT32_MAX || capacity > SIZE_MAX / sizeof(*buffers->points) ||
        capacity > SIZE_MAX / (2 * sizeof(*buffers->indices))) {
        return false;
    }
    buffers->capacity = capacity;
    buffers->mask = (BinaryMask){width, height, malloc(width * height)};
    buffers->points = malloc(capacity * sizeof(*buffers->points));
    buffers->indices = malloc(2 * capacity * sizeof(*buffers->indices));
    return buffers->mask.pixels != NULL && buffers->points != NULL && buffers->indices != NULL;
}

static bool write_outputs(const char *prefix, const HostBuffers *buffers,
                           const LaneConfig *config, const LaneResult *result, size_t count)
{
    size_t prefix_length = strlen(prefix);
    if (prefix_length > SIZE_MAX - 32) {
        fprintf(stderr, "Prefixo de saida excede a capacidade.\n");
        return false;
    }
    char *path = malloc(prefix_length + 32);
    if (path == NULL) {
        fprintf(stderr, "Memoria insuficiente para o caminho de saida.\n");
        return false;
    }
    snprintf(path, prefix_length + 32, "%s_mask.bin", prefix);
    bool written = mask_write_binary(path, &buffers->mask);
    if (written) {
        snprintf(path, prefix_length + 32, "%s_debug.ppm", prefix);
        written = image_write_ppm(path, &buffers->image);
    }
    if (written) {
        snprintf(path, prefix_length + 32, "%s_model.json", prefix);
        written = result_write_json(path, &buffers->mask, count, config, result);
    }
    if (!written) {
        fprintf(stderr, "Falha ao gravar %s. O diretorio de saida deve existir.\n", path);
    }
    free(path);
    return written;
}

static bool process_image(HostBuffers *buffers, const LaneConfig *config, const char *prefix)
{
    if (!allocate_workspace(buffers)) {
        fprintf(stderr, "Memoria insuficiente ou dimensoes excedem a capacidade.\n");
        return false;
    }
    size_t capacity = buffers->capacity;
    LaneWorkspace workspace = {
        buffers->points, capacity,
        {buffers->indices, buffers->indices + capacity, capacity}
    };
    LaneResult result;
    size_t count;
    LaneStatus pipeline_status = lane_detect_rgb(&buffers->image, &buffers->mask, config,
                                                &workspace, true, &result, &count);
    if (pipeline_status != LANE_OK) {
        fprintf(stderr, "Falha no pipeline RGB (status %d).\n", (int)pipeline_status);
        return false;
    }
    if (!write_outputs(prefix, buffers, config, &result, count)) {
        return false;
    }

    printf("Imagem: %zux%zu; pontos: %zu; inliers: %zu; espessura: %zu px\n",
           buffers->image.width, buffers->image.height, count, result.inlier_count, config->thickness);
    if (result.found) {
        printf("x = %.9g*y^2 + %.9g*y + %.9g; MSE = %.6g px^2\n",
               result.poly.a, result.poly.b, result.poly.c, result.mean_squared_error);
    } else {
        printf("Nenhuma faixa identificada; mascara preenchida com zeros.\n");
    }
    printf("Saidas: %s_{mask.bin,debug.ppm,model.json}\n", prefix);
    return true;
}

int main(int argc, char **argv)
{
    LaneConfig config = lane_default_config();
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(argv[0]);
        return EXIT_SUCCESS;
    }
    size_t width, height;
    if (argc < 5 || !parse_integer(argv[2], &width) || !parse_integer(argv[3], &height) ||
        !parse_options(argc, argv, &config)) {
        usage(argv[0]);
        return EXIT_FAILURE;
    }
    HostBuffers buffers = {0};
    if (!image_read_rgb(argv[1], width, height, &buffers.image)) {
        fprintf(stderr, "Nao foi possivel ler o buffer RGB.\n");
        return EXIT_FAILURE;
    }
    bool success = process_image(&buffers, &config, argv[4]);
    free_buffers(&buffers);
    return success ? EXIT_SUCCESS : EXIT_FAILURE;
}
