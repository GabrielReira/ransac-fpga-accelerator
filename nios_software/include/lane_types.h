#ifndef LANE_TYPES_H
#define LANE_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    double x;
    double y;
} Point;

/* x(y) = a*y*y + b*y + c, em coordenadas da imagem. */
typedef struct {
    double a;
    double b;
    double c;
} Poly;

typedef struct {
    size_t width;
    size_t height;
    uint8_t *pixels; /* RGB intercalado: 3 bytes por pixel. */
} Image;

typedef struct {
    size_t width;
    size_t height;
    uint8_t *pixels; /* Ordem de linhas: pixels[y * width + x], valores 0/1. */
} BinaryMask;

#endif
