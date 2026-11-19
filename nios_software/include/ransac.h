#ifndef RANSAC_H
#define RANSAC_H

#include "lane_types.h"

typedef struct {
    size_t iterations;
    lane_real threshold; /* Residuo horizontal maximo em pixels; limite estrito. */
    size_t min_inliers;
    uint32_t seed;
} RansacConfig;

typedef struct {
    size_t *candidate_ids;
    size_t *best_ids;
    size_t capacity; /* Cada buffer possui capacity elementos. Nao podem se sobrepor. */
} RansacWorkspace;

typedef struct {
    bool found;
    Poly poly;
    size_t inlier_count;
    lane_real mean_squared_error;
    lane_real y_min;
    lane_real y_max;
} LaneResult;

RansacConfig ransac_default_config(void);
/* false indica parametros/buffers invalidos. found == false e uma execucao valida. */
bool ransac_fit(const Point *points, size_t count, const RansacConfig *config,
                RansacWorkspace *workspace, LaneResult *result);

#endif
