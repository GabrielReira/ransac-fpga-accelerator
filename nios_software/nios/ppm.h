#ifndef NIOS_PPM_H
#define NIOS_PPM_H

#include <stddef.h>
#include <stdint.h>

/* PPM binario (P6, maxval 255): cabecalho em texto e depois RGB888 em ordem de linhas,
   o mesmo layout de nios_rgb */
// build_nios.sh grava o nome da imagem no primeiro comentario ("# nome")
typedef struct {
    const char *name; // aponta para dentro do cabecalho, sem '\0': use name_length
    size_t name_length;
    size_t width;
    size_t height;
    const uint8_t *pixels;
} PpmImage;

static inline size_t ppm_skip_space(const uint8_t *data, size_t size, size_t at, PpmImage *image)
{
    while (at < size) {
        if (data[at] == '#') {
            size_t start = at + 1;
            while (start < size && data[start] == ' ') {
                ++start;
            }
            while (at < size && data[at] != '\n') {
                ++at;
            }
            if (image->name == NULL) {
                image->name = (const char *)&data[start];
                image->name_length = at > start ? at - start : 0;
            }
        } else if (data[at] == ' ' || data[at] == '\t' || data[at] == '\n' || data[at] == '\r') {
            ++at;
        } else {
            break;
        }
    }
    return at;
}

static inline size_t ppm_read_number(const uint8_t *data, size_t size, size_t at, size_t *value)
{
    size_t start = at;
    *value = 0;
    while (at < size && data[at] >= '0' && data[at] <= '9' && *value <= 100000) {
        *value = *value * 10 + (size_t)(data[at++] - '0');
    }
    return at > start ? at : 0;
}

// Le o PPM no inicio de data e retorna quantos bytes ele ocupa; 0 se o formato nao bate
// PPMs concatenados sao validos: o proximo comeca logo depois do retorno
static inline size_t ppm_parse(const uint8_t *data, size_t size, PpmImage *image)
{
    size_t fields[3];
    *image = (PpmImage){0};
    if (size < 2 || data[0] != 'P' || data[1] != '6') {
        return 0;
    }
    size_t at = 2;
    for (int i = 0; i < 3; ++i) {
        at = ppm_skip_space(data, size, at, image);
        at = ppm_read_number(data, size, at, &fields[i]);
        if (at == 0) {
            return 0;
        }
    }
    // Exatamente um espaco separa o maxval dos pixels
    if (fields[0] == 0 || fields[1] == 0 || fields[2] != 255 || at >= size) {
        return 0;
    }
    ++at;
    size_t bytes = 3 * fields[0] * fields[1];
    if (bytes > size - at) {
        return 0;
    }
    image->width = fields[0];
    image->height = fields[1];
    image->pixels = &data[at];
    return at + bytes;
}

#endif
