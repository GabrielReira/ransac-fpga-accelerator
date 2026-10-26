#ifndef LANE_PROFILE_H
#define LANE_PROFILE_H

// Secoes de profiling: as etapas do profiling em Python mais pre-processamento
// e renderizacao
// Comecam em 1 porque a secao 0 do performance counter do Nios II e o tempo total
typedef enum {
    LANE_SECTION_PREPROCESS = 1, // filtro de cor, ROI e extracao de pontos
    LANE_SECTION_SAMPLE,         // sorteio dos tres indices
    LANE_SECTION_MODEL,          // ajuste da parabola candidata
    LANE_SECTION_CONSENSUS,      // residuo de todos os pontos (O(k*N))
    LANE_SECTION_REFINE,         // ajuste sobre o consenso
    LANE_SECTION_ERROR,          // MSE e selecao do melhor modelo
    LANE_SECTION_RENDER,         // mascara e debug
    LANE_SECTION_COUNT = LANE_SECTION_RENDER
} LaneProfileSection;

// No build do computador (sem LANE_PROFILE) os marcadores viram ((void)0)
// Com LANE_PROFILE, a plataforma fornece lane_profile_port.h, como em nios/
#ifdef LANE_PROFILE
#include "lane_profile_port.h"
#else
#define LANE_PROFILE_BEGIN(section) ((void)0)
#define LANE_PROFILE_END(section) ((void)0)
#endif

#endif
