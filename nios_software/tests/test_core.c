#include "poly.h"
#include "lane.h"
#include "entry.h"
#include "preprocess.h"
#include "render.h"

#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void test_preprocessing(void)
{
    uint8_t rgb[] = {
        165, 165, 165, 255, 255, 255, 164, 255, 255,
        170, 165, 80, 240, 205, 170, 241, 185, 125
    };
    uint8_t pixels[6];
    Image image = {6, 1, rgb};
    BinaryMask mask = {6, 1, pixels};
    extract_paint_mask(&image, &mask);
    const uint8_t expected[] = {1, 1, 0, 1, 1, 0};
    assert(memcmp(pixels, expected, sizeof(expected)) == 0);

    uint8_t runs[] = {1, 1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0};
    mask = (BinaryMask){8, 2, runs};
    Point points[3];
    size_t count;
    assert(count_mask_points(&mask) == 3);
    assert(mask_to_points(&mask, points, 3, &count));
    assert(count == 3);
    assert(points[0].x == 0.5 && points[1].x == 4.0 && points[2].x == 7.0);
    assert(points[0].y == 0 && points[2].y == 0);
    assert(!mask_to_points(&mask, points, 2, &count));

    uint8_t roi_pixels[100];
    memset(roi_pixels, 1, sizeof(roi_pixels));
    mask = (BinaryMask){10, 10, roi_pixels};
    apply_default_roi(&mask);
    for (size_t i = 0; i < 50; ++i) {
        assert(roi_pixels[i] == 0);
    }
    assert(roi_pixels[5 * 10 + 3] == 0);
    assert(roi_pixels[5 * 10 + 4] == 1 && roi_pixels[5 * 10 + 6] == 1);
    assert(roi_pixels[5 * 10 + 7] == 0);
    uint8_t single = 1;
    mask = (BinaryMask){1, 1, &single};
    apply_default_roi(&mask);
    assert(single == 1);
}

static void test_polynomial(void)
{
    Poly truth = {0.003, -0.4, 200};
    Point points[80];
    for (size_t i = 0; i < 80; ++i) {
        double y = 300 + (double)i * 5;
        points[i] = (Point){poly_predict(&truth, y), y};
    }
    Poly fitted;
    assert(poly_fit(points, NULL, 80, &fitted));
    for (size_t i = 0; i < 80; ++i) {
        assert(fabs(poly_predict(&fitted, points[i].y) - points[i].x) < 1e-8);
    }
    size_t ids[] = {0, 40, 79};
    assert(poly_fit(points, ids, 3, &fitted));
    assert(fabs(fitted.a - truth.a) < 1e-10);
    Point degenerate[] = {{1, 10}, {2, 10}, {3, 20}, {4, 20}};
    assert(!poly_fit(degenerate, NULL, 4, &fitted));
    assert(!poly_fit(points, NULL, 2, &fitted));
    points[0].x = NAN;
    assert(!poly_fit(points, NULL, 80, &fitted));
}

static void test_ransac_and_render(void)
{
    enum {N = 240, INLIERS = 180};
    Point points[N];
    Poly truth = {0.001, -0.3, 200};
    for (size_t i = 0; i < N; ++i) {
        double y = 200 + (double)i;
        double x = i < INLIERS ? poly_predict(&truth, y) :
                   500 + (double)((i * 37) % 113);
        points[i] = (Point){x, y};
    }
    size_t candidate_ids[N], best_ids[N], saved_ids[N];
    RansacWorkspace workspace = {candidate_ids, best_ids, N};
    RansacConfig config = ransac_default_config();
    LaneResult result, repeated;
    assert(ransac_fit(points, N, &config, &workspace, &result));
    assert(result.found && result.inlier_count == INLIERS);
    assert(result.mean_squared_error < 1e-16);
    assert(result.y_min == 200 && result.y_max == 379);
    memcpy(saved_ids, best_ids, sizeof(saved_ids));
    assert(ransac_fit(points, N, &config, &workspace, &repeated));
    assert(result.poly.a == repeated.poly.a && result.poly.b == repeated.poly.b &&
           result.poly.c == repeated.poly.c);
    assert(memcmp(saved_ids, best_ids, INLIERS * sizeof(*best_ids)) == 0);

    uint8_t pixels[500 * 400];
    BinaryMask mask = {500, 400, pixels};
    assert(render_lane_mask(&result, &mask, 3));
    size_t marked = 0;
    for (size_t y = 0; y < mask.height; ++y) {
        size_t row_count = 0;
        for (size_t x = 0; x < mask.width; ++x) {
            assert(pixels[y * mask.width + x] <= 1);
            row_count += pixels[y * mask.width + x];
        }
        assert(row_count == (y >= 200 && y <= 379 ? 3 : 0));
        marked += row_count;
    }
    assert(marked == 3 * INLIERS);

    config.min_inliers = N + 1;
    assert(ransac_fit(points, N, &config, &workspace, &result));
    assert(!result.found);
    assert(render_lane_mask(&result, &mask, 3));
    for (size_t i = 0; i < sizeof(pixels); ++i) {
        assert(pixels[i] == 0);
    }
    config = ransac_default_config();
    assert(ransac_fit(NULL, 0, &config, &workspace, &result));
    assert(!result.found);
    workspace.capacity = N - 1;
    assert(!ransac_fit(points, N, &config, &workspace, &result));
    workspace.capacity = N;
    config.threshold = NAN;
    assert(!ransac_fit(points, N, &config, &workspace, &result));
    config = ransac_default_config();
    for (size_t i = 0; i < N; ++i) {
        points[i].y = 10;
    }
    assert(ransac_fit(points, N, &config, &workspace, &result));
    assert(!result.found);
    config.seed = 0;
    config.min_inliers = 3;
    Point small[] = {{1, 0}, {2, 1}, {5, 2}};
    assert(ransac_fit(small, 3, &config, &workspace, &result));
    assert(result.found && result.inlier_count == 3);
}

static void test_threshold_in_pixels(void)
{
    /* Seed 6 seleciona os tres pontos de x=0 nesta unica tentativa.
       O quarto ponto tem residuo de 1.5 pixels. */
    Point points[] = {{0, 0}, {0, 1}, {0, 2}, {1.5, 3}};
    size_t candidate_ids[4], best_ids[4];
    RansacWorkspace workspace = {candidate_ids, best_ids, 4};
    RansacConfig config = {1, 2.0, 4, 6};
    LaneResult result;
    assert(ransac_fit(points, 4, &config, &workspace, &result));
    assert(result.found && result.inlier_count == 4);

    /* O limite e estrito: residuo igual ao threshold fica de fora. */
    config.threshold = 1.5;
    assert(ransac_fit(points, 4, &config, &workspace, &result));
    assert(!result.found);

    config.threshold = DBL_MAX;
    assert(!ransac_fit(points, 4, &config, &workspace, &result));
    config.threshold = DBL_MIN;
    assert(!ransac_fit(points, 4, &config, &workspace, &result));
}

static void test_thickness_and_bounds(void)
{
    uint8_t pixels[100];
    BinaryMask mask = {10, 10, pixels};
    LaneResult result = {.found = true, .poly = {0, 0, 5}, .y_min = 2, .y_max = 7};
    const size_t thicknesses[] = {1, 2, 3, 6, 7};
    for (size_t i = 0; i < sizeof(thicknesses) / sizeof(*thicknesses); ++i) {
        size_t thickness = thicknesses[i];
        assert(render_lane_mask(&result, &mask, thickness));
        size_t marked = 0;
        for (size_t j = 0; j < sizeof(pixels); ++j) {
            marked += pixels[j];
        }
        assert(marked == thickness * 6);
    }
    result.poly.c = -1;
    assert(render_lane_mask(&result, &mask, 3));
    assert(pixels[2 * 10] == 1 && pixels[2 * 10 + 1] == 0);
    result.poly.c = 10;
    assert(render_lane_mask(&result, &mask, 3));
    assert(pixels[2 * 10 + 9] == 1 && pixels[2 * 10 + 8] == 0);
    const double invalid[] = {-1e100, 1e100, NAN, INFINITY};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
        result.poly.c = invalid[i];
        assert(render_lane_mask(&result, &mask, 3));
        for (size_t j = 0; j < sizeof(pixels); ++j) {
            assert(pixels[j] == 0);
        }
    }
    assert(!render_lane_mask(&result, &mask, 0));
}

static void test_embedded_pipeline(void)
{
    /* Executa a mesma entrada/buffers estaticos usados no Nios II. */
    memset(nios_rgb, 0, sizeof(nios_rgb));
    nios_lane_config = lane_default_config();
    assert(nios_process_rgb() == LANE_OK);
    assert(!nios_lane_result.found && nios_point_count == 0);
    for (size_t i = 0; i < sizeof(nios_lane_mask); ++i) {
        assert(nios_lane_mask[i] == 0);
    }
    for (size_t y = LANE_IMAGE_HEIGHT * 6 / 10; y < LANE_IMAGE_HEIGHT; ++y) {
        size_t x = LANE_IMAGE_WIDTH / 2 + (y * y) / (8 * LANE_IMAGE_HEIGHT);
        for (size_t dx = 0; dx < 3; ++dx) {
            for (size_t channel = 0; channel < 3; ++channel) {
                nios_rgb[3 * (y * LANE_IMAGE_WIDTH + x + dx) + channel] = 255;
            }
        }
    }
    assert(nios_process_rgb() == LANE_OK);
    assert(nios_lane_result.found);
    assert(nios_lane_result.inlier_count >= 50);
    nios_lane_config.thickness = 0;
    assert(nios_process_rgb() == LANE_INVALID_ARGUMENT);
    nios_lane_config = lane_default_config();
}

int main(void)
{
    test_preprocessing();
    test_polynomial();
    test_ransac_and_render();
    test_threshold_in_pixels();
    test_thickness_and_bounds();
    test_embedded_pipeline();
    puts("OK: filtro, ROI, ajuste, RANSAC, espessura, limites e entrada embarcada.");
    return 0;
}
