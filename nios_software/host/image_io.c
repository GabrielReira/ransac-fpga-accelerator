#include "image_io.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

bool image_read_rgb(const char *path, size_t width, size_t height, Image *image)
{
    *image = (Image){0};
    if (width == 0 || height == 0 || width > INT_MAX || height > INT_MAX ||
        width > SIZE_MAX / height / 3) {
        return false;
    }
    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        perror(path);
        return false;
    }
    size_t size = 3 * width * height;
    uint8_t *pixels = malloc(size);
    if (pixels == NULL) {
        fclose(file);
        return false;
    }
    bool ok = fread(pixels, 1, size, file) == size;
    int extra = fgetc(file);
    ok = ok && extra == EOF && !ferror(file);
    bool closed = fclose(file) == 0;
    if (ok && closed) {
        *image = (Image){width, height, pixels};
        return true;
    }
    free(pixels);
    fprintf(stderr, "%s: esperado exatamente %zu bytes RGB.\n", path, size);
    return false;
}

bool image_write_ppm(const char *path, const Image *image)
{
    FILE *file = fopen(path, "wb");
    if (file == NULL) {
        perror(path);
        return false;
    }
    size_t size = 3 * image->width * image->height;
    bool ok = fprintf(file, "P6\n%zu %zu\n255\n", image->width, image->height) >= 0;
    ok = ok && fwrite(image->pixels, 1, size, file) == size;
    bool closed = fclose(file) == 0;
    return ok && closed;
}

bool mask_write_binary(const char *path, const BinaryMask *mask)
{
    FILE *file = fopen(path, "wb");
    if (file == NULL) {
        perror(path);
        return false;
    }
    size_t size = mask->width * mask->height;
    bool ok = fwrite(mask->pixels, 1, size, file) == size;
    return fclose(file) == 0 && ok;
}

bool result_write_json(const char *path, const BinaryMask *mask,
                       size_t point_count, const LaneConfig *config,
                       const LaneResult *result)
{
    FILE *file = fopen(path, "w");
    if (file == NULL) {
        perror(path);
        return false;
    }
    int written = fprintf(file,
        "{\n"
        "  \"width\": %zu,\n"
        "  \"height\": %zu,\n"
        "  \"thickness\": %zu,\n"
        "  \"seed\": %u,\n"
        "  \"found\": %s,\n"
        "  \"points\": %zu,\n"
        "  \"inliers\": %zu,\n",
        mask->width,
        mask->height,
        config->thickness,
        (unsigned)config->ransac.seed,
        result->found ? "true" : "false",
        point_count,
        result->inlier_count);
    if (written >= 0 && result->found) {
        written = fprintf(file,
            "  \"poly\": {\n"
            "    \"a\": %.17g,\n"
            "    \"b\": %.17g,\n"
            "    \"c\": %.17g\n"
            "  },\n"
            "  \"y_min\": %.17g,\n"
            "  \"y_max\": %.17g,\n"
            "  \"mse\": %.17g\n"
            "}\n",
            result->poly.a,
            result->poly.b,
            result->poly.c,
            result->y_min,
            result->y_max,
            result->mean_squared_error);
    } else if (written >= 0) {
        written = fprintf(file,
            "  \"poly\": null,\n"
            "  \"y_min\": null,\n"
            "  \"y_max\": null,\n"
            "  \"mse\": null\n"
            "}\n");
    }
    bool closed = fclose(file) == 0;
    return written >= 0 && closed;
}
