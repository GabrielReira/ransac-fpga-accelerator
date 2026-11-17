#ifndef LANE_H
#define LANE_H

#include "render.h"

typedef struct {
    RansacConfig ransac;
    size_t thickness; /* Largura horizontal da curva, em pixels; pelo menos 1. */
} LaneConfig;

typedef struct {
    Point *points;
    size_t point_capacity;
    RansacWorkspace ransac;
} LaneWorkspace;

typedef enum {
    LANE_OK = 0, /* Consulte result.found para saber se existe modelo. */
    LANE_INVALID_ARGUMENT,
    LANE_POINTS_CAPACITY_EXCEEDED,
    LANE_RANSAC_INVALID_ARGUMENT
} LaneStatus;

LaneConfig lane_default_config(void);
/* RGB ja decodificado. Sem E/S ou alocacoes. Buffers RGB e mascara distintos.
   debug=true altera o buffer RGB em lugar. */
LaneStatus lane_detect_rgb(Image *image, BinaryMask *mask, const LaneConfig *config,
                           LaneWorkspace *workspace, bool debug,
                           LaneResult *result, size_t *point_count);

#endif
