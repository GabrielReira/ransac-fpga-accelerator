#ifndef IMAGE_IO_H
#define IMAGE_IO_H

#include "lane.h"

/* Ferramenta host: arquivos RGB/binarios e PPM; somente biblioteca C padrao. */
bool image_read_rgb(const char *path, size_t width, size_t height, Image *image);
bool image_write_ppm(const char *path, const Image *image);
bool mask_write_binary(const char *path, const BinaryMask *mask);
bool result_write_json(const char *path, const BinaryMask *mask,
                       size_t point_count, const LaneConfig *config,
                       const LaneResult *result);

#endif
