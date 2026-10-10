#include "lane.h"

#include "preprocess.h"
#include <limits.h>

LaneConfig lane_default_config(void)
{
    return (LaneConfig){ransac_default_config(), 3};
}

LaneStatus lane_detect_rgb(Image *image, BinaryMask *mask, const LaneConfig *config,
                           LaneWorkspace *workspace, bool debug,
                           LaneResult *result, size_t *point_count)
{
    if (result != NULL) {
        *result = (LaneResult){0};
    }
    if (point_count != NULL) {
        *point_count = 0;
    }
    if (image == NULL || mask == NULL || config == NULL || workspace == NULL ||
        result == NULL || point_count == NULL || image->pixels == NULL ||
        mask->pixels == NULL || image->pixels == mask->pixels ||
        image->width == 0 || image->height == 0 ||
        image->width > INT_MAX || image->height > INT_MAX ||
        image->width > SIZE_MAX / image->height / 3 ||
        image->width != mask->width || image->height != mask->height ||
        config->thickness == 0 || config->thickness > (size_t)INT_MAX) {
        return LANE_INVALID_ARGUMENT;
    }
    extract_paint_mask(image, mask);
    apply_default_roi(mask);
    if (!mask_to_points(mask, workspace->points, workspace->point_capacity, point_count)) {
        return LANE_POINTS_CAPACITY_EXCEEDED;
    }
    if (!ransac_fit(workspace->points, *point_count, &config->ransac,
                    &workspace->ransac, result)) {
        return LANE_RANSAC_INVALID_ARGUMENT;
    }
    if (!render_lane_mask(result, mask, config->thickness)) {
        return LANE_INVALID_ARGUMENT;
    }
    if (debug) {
        render_debug(image, mask, workspace->points, workspace->ransac.best_ids, result);
    }
    return LANE_OK;
}
