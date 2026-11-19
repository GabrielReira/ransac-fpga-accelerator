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
        if ((lane_real)y < result->y_min || (lane_real)y > result->y_max) {
            continue;
        }
        lane_real x = lane_round(poly_predict(&result->poly, (lane_real)y));
        /* O polinomio retorna lane_real e pode produzir valores negativos, enormes
           ou nao finitos. Validamos/recortamos antes do cast para size_t;
           lane_real nao impede a curva de sair da imagem. */
        if (!isfinite(x)) {
            continue;
        }
        lane_real left = lane_fmax(0, x - (lane_real)((thickness - 1) / 2));
        lane_real right = lane_fmin((lane_real)mask->width - 1, x + (lane_real)(thickness / 2));
        if (left > right) {
            continue;
        }
        for (size_t pixel_x = (size_t)left; pixel_x <= (size_t)right; ++pixel_x) {
            mask->pixels[y * mask->width + pixel_x] = 1;
        }
    }
    return true;
}

static void red_pixel(Image *image, lane_real x, lane_real y)
{
    if (!isfinite(x) || !isfinite(y) || x < 0 || y < 0 ||
        x >= (lane_real)image->width || y >= (lane_real)image->height) {
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
                red_pixel(image, (lane_real)x, (lane_real)y);
            }
        }
    }
    for (size_t i = 0; i < result->inlier_count; ++i) {
        Point point = points[inlier_ids[i]];
        lane_real x = lane_round(point.x), y = lane_round(point.y);
        red_pixel(image, x, y);
        red_pixel(image, x - 1, y);
        red_pixel(image, x + 1, y);
        red_pixel(image, x, y - 1);
        red_pixel(image, x, y + 1);
    }
}
