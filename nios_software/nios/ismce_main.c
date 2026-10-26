/* Estrutura de teste pelo In-System Memory Content Editor (tools/ismce_run.py): 
o PC grava o frame em IMG e os parametros na MBOX, escreve MBOX_COMMAND = 1 e le os
resultados quando o comando volta a zero
Dimensoes vem da MBOX*/
#include "altera_avalon_performance_counter.h"
#include "altera_avalon_pio_regs.h"
#include "board_config.h"
#include "fnv1a.h"
#include "io.h"
#include "lane.h"
#include "lane_profile.h"
#include "mailbox.h"
#include "sys/alt_cache.h"
#include "system.h"
#include <string.h>

#define IMG_CAPACITY IMG_BUF_SPAN

static uint8_t rgb[IMG_CAPACITY];
static uint8_t mask[IMG_CAPACITY / 3];
static Point points[LANE_MAX_POINTS];
static size_t candidate_ids[LANE_MAX_POINTS];
static size_t best_ids[LANE_MAX_POINTS];

// IORD/IOWR passam por fora do cache de dados, o que importa no Nios II/f
static uint32_t mbox_read(unsigned word)
{
    return IORD_32DIRECT(MAILBOX_BASE, 4 * word);
}

static void mbox_write(unsigned word, uint32_t value)
{
    IOWR_32DIRECT(MAILBOX_BASE, 4 * word, value);
}

static void mbox_write_u64(unsigned word, uint64_t value)
{
    mbox_write(word, (uint32_t)value);
    mbox_write(word + 1, (uint32_t)(value >> 32));
}

static void mbox_write_double(unsigned word, double value)
{
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    mbox_write_u64(word, bits);
}

static void run_command(void)
{
    for (unsigned word = MBOX_STATUS; word < MBOX_WORDS; ++word) {
        mbox_write(word, 0);
    }
    mbox_write(MBOX_STATUS, MBOX_STATUS_RUNNING);

    size_t width = mbox_read(MBOX_WIDTH);
    size_t height = mbox_read(MBOX_HEIGHT);
    if (width == 0 || height == 0 || width > IMG_CAPACITY / 3 / height) {
        mbox_write(MBOX_STATUS, MBOX_STATUS_BAD_INPUT);
        return;
    }
    size_t size = 3 * width * height;
    // O JTAG escreveu o frame direto na memoria, por fora do cache do Nios
    alt_dcache_flush_all();
    memcpy(rgb, (const void *)IMG_BUF_BASE, size);
    mbox_write(MBOX_RGB_HASH, fnv1a(rgb, size));

    LaneConfig config = lane_default_config();
    config.ransac.iterations = mbox_read(MBOX_ITERATIONS);
    config.ransac.threshold = mbox_read(MBOX_THRESHOLD_MILLI) / 1000.0;
    config.ransac.min_inliers = mbox_read(MBOX_MIN_INLIERS);
    config.ransac.seed = mbox_read(MBOX_SEED);
    config.thickness = mbox_read(MBOX_THICKNESS);

    Image image = {width, height, rgb};
    BinaryMask binary_mask = {width, height, mask};
    LaneWorkspace workspace = {
        points, LANE_MAX_POINTS,
        {candidate_ids, best_ids, LANE_MAX_POINTS}
    };
    LaneResult result;
    size_t point_count;

    // debug=true como no benchmark, para a secao de renderizacao incluir o debug
    PERF_RESET(PERF_COUNTER_BASE);
    PERF_START_MEASURING(PERF_COUNTER_BASE);
    LaneStatus status = lane_detect_rgb(&image, &binary_mask, &config, &workspace, true,
                                        &result, &point_count);
    PERF_STOP_MEASURING(PERF_COUNTER_BASE);

    mbox_write(MBOX_FOUND, result.found);
    mbox_write(MBOX_POINTS, point_count);
    mbox_write(MBOX_INLIERS, result.inlier_count);
    mbox_write_double(MBOX_A, result.poly.a);
    mbox_write_double(MBOX_B, result.poly.b);
    mbox_write_double(MBOX_C, result.poly.c);
    mbox_write_double(MBOX_MSE, result.mean_squared_error);
    mbox_write(MBOX_MASK_HASH, fnv1a(mask, width * height));
    mbox_write_u64(MBOX_CYCLES, perf_get_total_time((void *)PERF_COUNTER_BASE));
    for (int section = 1; section <= LANE_SECTION_COUNT; ++section) {
        mbox_write_u64(MBOX_CYCLES + 2 * section,
                       perf_get_section_time((void *)PERF_COUNTER_BASE, section));
    }
    mbox_write(MBOX_STATUS, status);
}

int main(void)
{
    mbox_write(MBOX_COMMAND, 0);
    mbox_write(MBOX_SEQUENCE, 0);
    mbox_write(MBOX_VERSION, MBOX_VERSION_VALUE);
    mbox_write(MBOX_IMG_CAPACITY, IMG_CAPACITY);
    mbox_write(MBOX_MAGIC, MBOX_MAGIC_VALUE); // por ultimo: o PC so confia na MBOX depois disso

    uint32_t heartbeat = 0;
    while (1) {
        mbox_write(MBOX_HEARTBEAT, ++heartbeat);
        if (mbox_read(MBOX_COMMAND) == MBOX_COMMAND_RUN) {
            IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, 0x80);
            run_command();
            uint32_t sequence = mbox_read(MBOX_SEQUENCE) + 1;
            mbox_write(MBOX_SEQUENCE, sequence);
            IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, sequence & 0x7F);
            mbox_write(MBOX_COMMAND, 0); // ultimo passo, libera o PC para ler
        }
    }
}
