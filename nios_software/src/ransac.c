#include "ransac.h"

#include "poly.h"
#include <math.h>
#include <string.h>

/* PRNG local e deterministico. Nao depende de rand() nem de estado global. */
static uint32_t random_u32(uint32_t *state)
{
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static size_t random_index(uint32_t *state, size_t count)
{
    uint32_t bound = (uint32_t)count;
    uint32_t cutoff = (uint32_t)(-bound) % bound;
    uint32_t value;
    do {
        value = random_u32(state);
    } while (value < cutoff);
    return value % bound;
}

RansacConfig ransac_default_config(void)
{
    return (RansacConfig){1000, 1.0, 50, 42};
}

bool ransac_fit(const Point *points, size_t count, const RansacConfig *config,
                RansacWorkspace *workspace, LaneResult *result)
{
    if (result == NULL) {
        return false;
    }
    *result = (LaneResult){0};
    if (config == NULL || workspace == NULL || config->iterations == 0 ||
        config->min_inliers < 3 || !isfinite(config->threshold) ||
        config->threshold <= 0 || count > UINT32_MAX ||
        (count > 0 && points == NULL)) {
        return false;
    }
    /* Configuracao em pixels; calcula o quadrado apenas uma vez por chamada. */
    double threshold_squared = config->threshold * config->threshold;
    if (!isfinite(threshold_squared) || threshold_squared == 0) {
        return false;
    }
    if (count < 3 || count < config->min_inliers) {
        return true;
    }
    if (workspace->capacity < count || workspace->candidate_ids == NULL ||
        workspace->best_ids == NULL || workspace->candidate_ids == workspace->best_ids) {
        return false;
    }
    for (size_t i = 0; i < count; ++i) {
        if (!isfinite(points[i].x) || !isfinite(points[i].y)) {
            return false;
        }
    }

    uint32_t state = config->seed == 0 ? UINT32_C(0x6d2b79f5) : config->seed;
    for (size_t iteration = 0; iteration < config->iterations; ++iteration) {
        size_t sample[3];
        sample[0] = random_index(&state, count);
        do {
            sample[1] = random_index(&state, count);
        } while (sample[1] == sample[0]);
        do {
            sample[2] = random_index(&state, count);
        } while (sample[2] == sample[0] || sample[2] == sample[1]);

        Poly candidate;
        if (!poly_fit(points, sample, 3, &candidate)) {
            continue;
        }
        size_t inliers = 3;
        memcpy(workspace->candidate_ids, sample, sizeof(sample));
        /* Gargalo O(k*N): pode ser substituido pelo acelerador em Verilog. */
        for (size_t i = 0; i < count; ++i) {
            if (i == sample[0] || i == sample[1] || i == sample[2]) {
                continue;
            }
            double dx = points[i].x - poly_predict(&candidate, points[i].y);
            if (dx * dx < threshold_squared) {
                workspace->candidate_ids[inliers++] = i;
            }
        }
        if (inliers < config->min_inliers) {
            continue;
        }
        /* Como no Python: ajusta uma vez sobre o consenso, sem reclassifica-lo. */
        Poly consensus_model;
        if (!poly_fit(points, workspace->candidate_ids, inliers, &consensus_model)) {
            continue;
        }
        double error = 0;
        double low = INFINITY, high = -INFINITY;
        for (size_t i = 0; i < inliers; ++i) {
            Point point = points[workspace->candidate_ids[i]];
            double dx = point.x - poly_predict(&consensus_model, point.y);
            error += dx * dx;
            low = fmin(low, point.y);
            high = fmax(high, point.y);
        }
        error /= (double)inliers;
        if (isfinite(error) && (!result->found || inliers > result->inlier_count ||
            (inliers == result->inlier_count && error < result->mean_squared_error))) {
            *result = (LaneResult){true, consensus_model, inliers, error, low, high};
            memcpy(workspace->best_ids, workspace->candidate_ids,
                   inliers * sizeof(*workspace->best_ids));
        }
    }
    return true;
}
