#ifndef PREPROCESS_H
#define PREPROCESS_H

#include "lane_types.h"

/* Buffers e dimensoes devem ser validos e coincidir; nenhuma alocacao interna. */
void extract_paint_mask(const Image *image, BinaryMask *mask);
void apply_default_roi(BinaryMask *mask);
size_t count_mask_points(const BinaryMask *mask);
/* Um Point no centro de cada corrida horizontal; retorna false se faltar espaco. */
bool mask_to_points(const BinaryMask *mask, Point *points, size_t capacity,
                    size_t *count);

#endif
