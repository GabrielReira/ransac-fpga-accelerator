#include "entry.h"

_Static_assert(LANE_IMAGE_WIDTH > 0 && LANE_IMAGE_HEIGHT > 0,
               "Dimensoes RGB precisam ser positivas");
_Static_assert(LANE_MAX_POINTS >= 3, "Reserve capacidade para pelo menos tres pontos");

_Alignas(8) uint8_t nios_rgb[3 * LANE_IMAGE_WIDTH * LANE_IMAGE_HEIGHT];
_Alignas(8) uint8_t nios_lane_mask[LANE_IMAGE_WIDTH * LANE_IMAGE_HEIGHT];
LaneConfig nios_lane_config = {{1000, 1.0, 50, 42}, 3};
LaneResult nios_lane_result;
size_t nios_point_count;

static Point points[LANE_MAX_POINTS];
static size_t candidate_ids[LANE_MAX_POINTS];
static size_t best_ids[LANE_MAX_POINTS];

LaneStatus nios_process_rgb(void)
{
    Image image = {LANE_IMAGE_WIDTH, LANE_IMAGE_HEIGHT, nios_rgb};
    BinaryMask mask = {LANE_IMAGE_WIDTH, LANE_IMAGE_HEIGHT, nios_lane_mask};
    LaneWorkspace workspace = {
        points, LANE_MAX_POINTS,
        {candidate_ids, best_ids, LANE_MAX_POINTS}
    };
    return lane_detect_rgb(&image, &mask, &nios_lane_config, &workspace, true,
                           &nios_lane_result, &nios_point_count);
}
