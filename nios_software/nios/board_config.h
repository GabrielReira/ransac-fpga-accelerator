#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H

/* Ajuste ao buffer RGB recebido e a memoria configurada no BSP. */
#ifndef LANE_IMAGE_WIDTH
#define LANE_IMAGE_WIDTH 960
#endif
#ifndef LANE_IMAGE_HEIGHT
#define LANE_IMAGE_HEIGHT 540
#endif
#ifndef LANE_MAX_POINTS
#define LANE_MAX_POINTS 4096
#endif

#endif
