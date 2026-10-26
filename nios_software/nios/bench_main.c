/* Benchmark da P1: processa a imagem de bench_image.S e imprime modelo, hash
   da mascara e relatorio do performance counter pela JTAG UART */
// Ocupa o lugar de nios/main.c no build de benchmark
#include "altera_avalon_jtag_uart_regs.h"
#include "altera_avalon_performance_counter.h"
#include "altera_avalon_pio_regs.h"
#include "entry.h"
#include "fnv1a.h"
#include "lane_profile.h"
#include "system.h"
#include <stdio.h>
#include <string.h>

#ifndef BENCH_RUNS
#define BENCH_RUNS 1
#endif

extern const uint8_t bench_rgb[];
extern const uint8_t bench_rgb_end[];

// Sem terminal conectado o driver da JTAG UART descarta a saida
// AC e limpo aqui e o hardware so volta a liga-lo quando o nios2-terminal le
static void wait_for_terminal(void)
{
    IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, 0x80);
    IOWR_ALTERA_AVALON_JTAG_UART_CONTROL(JTAG_UART_BASE, ALTERA_AVALON_JTAG_UART_CONTROL_AC_MSK);
    while (!(IORD_ALTERA_AVALON_JTAG_UART_CONTROL(JTAG_UART_BASE) &
             ALTERA_AVALON_JTAG_UART_CONTROL_AC_MSK)) {
    }
}

int main(void)
{
    wait_for_terminal();
    size_t image_size = (size_t)(bench_rgb_end - bench_rgb);
    printf("\nRANSAC_BENCH %dx%d, %d execucao(oes), CPU %lu Hz\n", LANE_IMAGE_WIDTH,
           LANE_IMAGE_HEIGHT, BENCH_RUNS, (unsigned long)ALT_CPU_FREQ);
    if (image_size != sizeof(nios_rgb)) {
        printf("ERRO: imagem embutida tem %lu bytes, esperado %lu\n",
               (unsigned long)image_size, (unsigned long)sizeof(nios_rgb));
        return 1;
    }
#ifdef BENCH_ITERATIONS
    nios_lane_config.ransac.iterations = BENCH_ITERATIONS;
#endif
    printf("iterations=%lu threshold=%g min_inliers=%lu seed=%lu thickness=%lu\n",
           (unsigned long)nios_lane_config.ransac.iterations,
           nios_lane_config.ransac.threshold,
           (unsigned long)nios_lane_config.ransac.min_inliers,
           (unsigned long)nios_lane_config.ransac.seed,
           (unsigned long)nios_lane_config.thickness);

    for (int run = 1; run <= BENCH_RUNS; ++run) {
        IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, run);
        // A copia restaura o RGB que o debug sobrescreve e fica fora da medicao
        memcpy(nios_rgb, bench_rgb, sizeof(nios_rgb));

        PERF_RESET(PERF_COUNTER_BASE);
        PERF_START_MEASURING(PERF_COUNTER_BASE);
        LaneStatus status = nios_process_rgb();
        PERF_STOP_MEASURING(PERF_COUNTER_BASE);

        unsigned long long cycles = perf_get_total_time((void *)PERF_COUNTER_BASE);
        printf("\n== Execucao %d ==\n", run);
        printf("status=%d found=%d points=%lu inliers=%lu\n", (int)status,
               (int)nios_lane_result.found, (unsigned long)nios_point_count,
               (unsigned long)nios_lane_result.inlier_count);
        printf("a=%.9g b=%.9g c=%.9g mse=%.9g\n", nios_lane_result.poly.a,
               nios_lane_result.poly.b, nios_lane_result.poly.c,
               nios_lane_result.mean_squared_error);
        printf("mask_fnv1a=0x%08lx\n",
               (unsigned long)fnv1a(nios_lane_mask, sizeof(nios_lane_mask)));
        printf("total_cycles=%llu total_ms=%.3f\n", cycles,
               (double)cycles * 1000.0 / (double)ALT_CPU_FREQ);
        perf_print_formatted_report((void *)PERF_COUNTER_BASE, ALT_CPU_FREQ,
                                    LANE_SECTION_COUNT, "Pre-processamento",
                                    "Amostragem", "Estimativa modelo", "Consenso",
                                    "Refinamento", "Erro/selecao", "Renderizacao");
    }
    IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, 0xFF);
    printf("RANSAC_BENCH_DONE\n");
    putchar(0x04); // Ctrl-D fecha o nios2-terminal
    fflush(stdout);
    return 0;
}
