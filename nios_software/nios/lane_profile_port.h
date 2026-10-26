#ifndef LANE_PROFILE_PORT_H
#define LANE_PROFILE_PORT_H

// Marcadores sobre o perf_counter do Platform Designer
// Cada um e uma escrita no barramento, entao custa poucos ciclos
#include "altera_avalon_performance_counter.h"
#include "system.h"

#define LANE_PROFILE_BEGIN(section) PERF_BEGIN(PERF_COUNTER_BASE, (section))
#define LANE_PROFILE_END(section) PERF_END(PERF_COUNTER_BASE, (section))

#endif
