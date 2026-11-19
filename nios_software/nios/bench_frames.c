#include "bench_frames.h"
#include <stdio.h>
#include <string.h>

extern const uint8_t bench_ppm[];
extern const uint8_t bench_ppm_end[];

PpmImage bench_frames[BENCH_IMAGE_COUNT];

bool bench_frames_load(void)
{
    size_t size = (size_t)(bench_ppm_end - bench_ppm);
    size_t at = 0;
    for (int i = 0; i < BENCH_IMAGE_COUNT; ++i) {
        size_t used = ppm_parse(&bench_ppm[at], size - at, &bench_frames[i]);
        const BenchReference *ref = &bench_references[i];
        if (used == 0) {
            printf("ERRO: PPM %d invalido no offset %lu\n", i, (unsigned long)at);
            return false;
        }
        if (bench_frames[i].name_length != strlen(ref->name) ||
            memcmp(bench_frames[i].name, ref->name, strlen(ref->name)) != 0 ||
            bench_frames[i].width != ref->width || bench_frames[i].height != ref->height) {
            printf("ERRO: PPM %d nao bate com a referencia %s %ux%u\n", i, ref->name,
                   ref->width, ref->height);
            return false;
        }
        at += used;
    }
    return true;
}
