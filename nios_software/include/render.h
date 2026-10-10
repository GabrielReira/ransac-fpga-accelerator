#ifndef RENDER_H
#define RENDER_H

#include "ransac.h"

/* Reutiliza a mascara do filtro. thickness define a largura horizontal em pixels.
   false indica argumentos invalidos. */
bool render_lane_mask(const LaneResult *result, BinaryMask *mask, size_t thickness);
/* Desenha a mascara e os inliers em vermelho, alterando a imagem RGB em lugar. */
void render_debug(Image *image, const BinaryMask *mask, const Point *points,
                  const size_t *inlier_ids, const LaneResult *result);

#endif
