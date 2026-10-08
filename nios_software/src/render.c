#include "render.h"

#include "poly.h"
#include <limits.h>
#include <math.h>
#include <string.h>

bool render_lane_mask(const LaneResult *result, BinaryMask *mask, size_t thickness)
{
    if (result == NULL || mask == NULL || mask->pixels == NULL ||
        mask->width == 0 || mask->height == 0 ||
        mask->width > INT_MAX || mask->height > INT_MAX ||
        mask->width > SIZE_MAX / mask->height ||
        thickness == 0 || thickness > (size_t)INT_MAX) {
        return false;
    }
    memset(mask->pixels, 0, mask->width * mask->height);
    if (!result->found) {
        return true;
    }
    for (size_t y = 0; y < mask->height; ++y) {
        if ((double)y < result->y_min || (double)y > result->y_max) {
            continue;
        }
        double x = round(poly_predict(&result->poly, (double)y));
        /* O polinomio retorna double e pode produzir valores negativos, enormes
           ou nao finitos. Validamos/recortamos antes do cast para size_t;
           double nao impede a curva de sair da imagem. */
        if (!isfinite(x)) {
            continue;
        }
        double left = fmax(0, x - (double)((thickness - 1) / 2));
        double right = fmin((double)mask->width - 1, x + (double)(thickness / 2));
        if (left > right) {
            continue;
        }
        for (size_t pixel_x = (size_t)left; pixel_x <= (size_t)right; ++pixel_x) {
            mask->pixels[y * mask->width + pixel_x] = 1;
        }
    }
    return true;
}

static void red_pixel(Image *image, double x, double y)
{
    if (!isfinite(x) || !isfinite(y) || x < 0 || y < 0 ||
        x >= (double)image->width || y >= (double)image->height) {
        return;
    }
    uint8_t *pixel = &image->pixels[3 * ((size_t)y * image->width + (size_t)x)];
    pixel[0] = 255;
    pixel[1] = pixel[2] = 0;
}

void render_debug(Image *image, const BinaryMask *mask, const Point *points,
                  const size_t *inlier_ids, const LaneResult *result)
{
    for (size_t y = 0; y < mask->height; ++y) {
        for (size_t x = 0; x < mask->width; ++x) {
            if (mask->pixels[y * mask->width + x]) {
                red_pixel(image, (double)x, (double)y);
            }
        }
    }
    for (size_t i = 0; i < result->inlier_count; ++i) {
        Point point = points[inlier_ids[i]];
        double x = round(point.x), y = round(point.y);
        red_pixel(image, x, y);
        red_pixel(image, x - 1, y);
        red_pixel(image, x + 1, y);
        red_pixel(image, x, y - 1);
        red_pixel(image, x, y + 1);
    }
}
