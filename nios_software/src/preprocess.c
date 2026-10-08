#include "preprocess.h"

#include <math.h>
#include <string.h>

void extract_paint_mask(const Image *image, BinaryMask *mask)
{
    size_t size = image->width * image->height;
    for (size_t i = 0; i < size; ++i) {
        const uint8_t *rgb = &image->pixels[3 * i];
        bool white = rgb[0] >= 165 && rgb[1] >= 165 && rgb[2] >= 165;
        bool yellow = rgb[0] >= 170 && rgb[0] <= 240 &&
                      rgb[1] >= 165 && rgb[1] <= 205 &&
                      rgb[2] >= 80 && rgb[2] <= 170;
        mask->pixels[i] = (uint8_t)(white || yellow);
    }
}

void apply_default_roi(BinaryMask *mask)
{
    if (mask->width == 0 || mask->height == 0) {
        return;
    }
    size_t top = (size_t)(0.55 * (double)mask->height);
    size_t bottom = mask->height - 1;
    double top_left = floor(0.40 * (double)mask->width);
    double top_right = floor(0.60 * (double)mask->width);
    double bottom_left = floor(0.02 * (double)mask->width);
    double bottom_right = floor(0.98 * (double)mask->width);

    for (size_t y = 0; y < mask->height; ++y) {
        if (y < top) {
            memset(&mask->pixels[y * mask->width], 0, mask->width);
            continue;
        }
        double fraction = bottom == top ? 0.0 :
                          ((double)y - (double)top) / (double)(bottom - top);
        size_t left = (size_t)floor(top_left + fraction * (bottom_left - top_left) + 0.5);
        size_t right = (size_t)floor(top_right + fraction * (bottom_right - top_right) + 0.5);
        for (size_t x = 0; x < mask->width; ++x) {
            if (x < left || x > right) {
                mask->pixels[y * mask->width + x] = 0;
            }
        }
    }
}

size_t count_mask_points(const BinaryMask *mask)
{
    size_t count = 0;
    for (size_t y = 0; y < mask->height; ++y) {
        bool previous = false;
        for (size_t x = 0; x < mask->width; ++x) {
            bool current = mask->pixels[y * mask->width + x] != 0;
            count += current && !previous;
            previous = current;
        }
    }
    return count;
}

bool mask_to_points(const BinaryMask *mask, Point *points, size_t capacity,
                    size_t *count)
{
    *count = 0;
    for (size_t y = 0; y < mask->height; ++y) {
        size_t x = 0;
        while (x < mask->width) {
            if (mask->pixels[y * mask->width + x] == 0) {
                ++x;
                continue;
            }
            size_t start = x;
            do {
                ++x;
            } while (x < mask->width && mask->pixels[y * mask->width + x] != 0);
            if (*count == capacity || points == NULL) {
                return false;
            }
            points[(*count)++] = (Point){0.5 * ((double)start + (double)x - 1.0),
                                       (double)y};
        }
    }
    return true;
}
