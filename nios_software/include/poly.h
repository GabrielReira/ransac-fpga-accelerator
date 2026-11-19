#ifndef POLY_H
#define POLY_H

#include "lane_types.h"

lane_real poly_predict(const Poly *poly, lane_real y);
/* indices == NULL seleciona os primeiros count pontos. Exige 3 alturas distintas. */
bool poly_fit(const Point *points, const size_t *indices, size_t count, Poly *poly);

#endif
