#ifndef LANE_TYPES_H
#define LANE_TYPES_H

#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Aritmetica do pipeline: double por padrao, float com -DLANE_REAL_FLOAT
   O float casa com a FPU de precisao simples do Nios II (Floating Point Hardware 2) */
// Builds em float tambem usam -fsingle-precision-constant, senao 0.5 promove a conta a double
#ifdef LANE_REAL_FLOAT
typedef float lane_real;
#define LANE_REAL_EPSILON FLT_EPSILON
#define lane_fabs fabsf
#define lane_fmin fminf
#define lane_fmax fmaxf
#define lane_floor floorf
#define lane_round roundf
#else
typedef double lane_real;
#define LANE_REAL_EPSILON DBL_EPSILON
#define lane_fabs fabs
#define lane_fmin fmin
#define lane_fmax fmax
#define lane_floor floor
#define lane_round round
#endif

typedef struct {
    lane_real x;
    lane_real y;
} Point;

/* x(y) = a*y*y + b*y + c, em coordenadas da imagem. */
typedef struct {
    lane_real a;
    lane_real b;
    lane_real c;
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
