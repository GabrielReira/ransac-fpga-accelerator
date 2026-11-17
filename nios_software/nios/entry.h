#ifndef NIOS_LANE_ENTRY_H
#define NIOS_LANE_ENTRY_H

#include "board_config.h"
#include "lane.h"

extern uint8_t nios_rgb[3 * LANE_IMAGE_WIDTH * LANE_IMAGE_HEIGHT];
extern uint8_t nios_lane_mask[LANE_IMAGE_WIDTH * LANE_IMAGE_HEIGHT];
extern LaneConfig nios_lane_config;
extern LaneResult nios_lane_result;
extern size_t nios_point_count;

/* O produtor preenche nios_rgb antes da chamada. O RGB vira o debug em lugar.
   O proximo frame deve repor todo o RGB, sem as marcacoes anteriores. */
LaneStatus nios_process_rgb(void);

#endif
