#include "poly.h"

#include <float.h>
#include <math.h>

double poly_predict(const Poly *poly, double y)
{
    return (poly->a * y + poly->b) * y + poly->c;
}

bool poly_fit(const Point *points, const size_t *indices, size_t count, Poly *poly)
{
    if (points == NULL || poly == NULL || count < 3) {
        return false;
    }
    double low = points[indices == NULL ? 0 : indices[0]].y;
    double high = low;
    for (size_t i = 0; i < count; ++i) {
        Point point = points[indices == NULL ? i : indices[i]];
        if (!isfinite(point.x) || !isfinite(point.y)) {
            return false;
        }
        low = fmin(low, point.y);
        high = fmax(high, point.y);
    }
    if (high == low) {
        return false;
    }

    /* Normalizar y evita potencias da altura da imagem mal condicionadas.
       So acumulamos escalares: nao existe uma matriz de projeto N x 3. */
    double center = low + (high - low) * 0.5;
    double scale = (high - low) * 0.5;
    double s1 = 0, s2 = 0, s3 = 0, s4 = 0;
    double sx = 0, stx = 0, st2x = 0;
    for (size_t i = 0; i < count; ++i) {
        Point point = points[indices == NULL ? i : indices[i]];
        double t = (point.y - center) / scale;
        double t2 = t * t;
        s1 += t;
        s2 += t2;
        s3 += t2 * t;
        s4 += t2 * t2;
        sx += point.x;
        stx += t * point.x;
        st2x += t2 * point.x;
    }

    /* Sistema fixo 3 x 3 de minimos quadrados; pivotamento parcial. */
    double equations[3][4] = {
        {s4, s3, s2, st2x},
        {s3, s2, s1, stx},
        {s2, s1, (double)count, sx}
    };
    for (size_t column = 0; column < 3; ++column) {
        size_t pivot = column;
        for (size_t row = column + 1; row < 3; ++row) {
            if (fabs(equations[row][column]) > fabs(equations[pivot][column])) {
                pivot = row;
            }
        }
        if (fabs(equations[pivot][column]) <= 64 * DBL_EPSILON * (double)count) {
            return false;
        }
        for (size_t j = column; j < 4; ++j) {
            double tmp = equations[column][j];
            equations[column][j] = equations[pivot][j];
            equations[pivot][j] = tmp;
        }
        for (size_t row = column + 1; row < 3; ++row) {
            double factor = equations[row][column] / equations[column][column];
            for (size_t j = column; j < 4; ++j) {
                equations[row][j] -= factor * equations[column][j];
            }
        }
    }
    double c = equations[2][3] / equations[2][2];
    double b = (equations[1][3] - equations[1][2] * c) / equations[1][1];
    double a = (equations[0][3] - equations[0][2] * c - equations[0][1] * b) /
               equations[0][0];
    *poly = (Poly){a / (scale * scale),
                   b / scale - 2 * a * center / (scale * scale),
                   c - b * center / scale + a * center * center / (scale * scale)};
    return isfinite(poly->a) && isfinite(poly->b) && isfinite(poly->c);
}
