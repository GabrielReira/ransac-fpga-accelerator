#ifndef NIOS_BENCH_FRAMES_H
#define NIOS_BENCH_FRAMES_H

#include "bench_images.h"
#include "ppm.h"
#include <stdbool.h>

// Frames de bench_images.ppm, na ordem de bench_references
extern PpmImage bench_frames[BENCH_IMAGE_COUNT];

// Percorre os PPMs embutidos e confere nome e tamanho com bench_references
// Imprime o primeiro problema e retorna false se algo nao bate
bool bench_frames_load(void);

#endif
