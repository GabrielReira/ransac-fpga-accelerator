/* Terminal de comandos da P1 pela JTAG UART (nios2-terminal): roda o pipeline
   sobre os PPMs embutidos em bench_image.S, com parametros ajustaveis */
// Comandos: help, list, show, set, reset, run, profile, quit
#include "altera_avalon_jtag_uart_regs.h"
#include "altera_avalon_performance_counter.h"
#include "altera_avalon_pio_regs.h"
#include "bench_frames.h"
#include "entry.h"
#include "fnv1a.h"
#include "lane_profile.h"
#include "system.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef BENCH_FPU
#define BENCH_FPU 0
#endif

static LaneConfig build_config;
static int last_image = -1;

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

// O nios2-terminal deixa o terminal do PC sem eco e manda '\r' ou '\n' no Enter,
// entao o eco e a edicao basica ficam aqui
static size_t read_line(char *line, size_t size)
{
    size_t length = 0;
    for (;;) {
        int c = getchar();
        if (c == EOF || c == '\r' || c == '\n') {
            if (length == 0 && c != EOF) {
                continue;
            }
            putchar('\n');
            break;
        }
        if ((c == '\b' || c == 0x7F) && length > 0) {
            --length;
            fputs("\b \b", stdout);
        } else if (c >= ' ' && length + 1 < size) {
            line[length++] = (char)c;
            putchar(c);
        }
        fflush(stdout);
    }
    line[length] = '\0';
    return length;
}

static bool config_is_build(void)
{
    const RansacConfig *now = &nios_lane_config.ransac;
    const RansacConfig *built = &build_config.ransac;
    return now->iterations == built->iterations && now->threshold == built->threshold &&
           now->min_inliers == built->min_inliers && now->seed == built->seed &&
           nios_lane_config.thickness == build_config.thickness;
}

static void show_config(void)
{
    printf("iterations=%lu threshold=%g min_inliers=%lu seed=%lu thickness=%lu%s\n",
           (unsigned long)nios_lane_config.ransac.iterations,
           (double)nios_lane_config.ransac.threshold,
           (unsigned long)nios_lane_config.ransac.min_inliers,
           (unsigned long)nios_lane_config.ransac.seed,
           (unsigned long)nios_lane_config.thickness,
           config_is_build() ? "  (configuracao do build)" : "");
}

// Indice da lista ou -1; nomes sao tratados em run_command porque podem ter varios tamanhos
static int find_index(const char *arg)
{
    char *end;
    long index = strtol(arg, &end, 10);
    return *end == '\0' && index >= 0 && index < BENCH_IMAGE_COUNT ? (int)index : -1;
}

// Retorna 1 em PASS, 0 em FAIL e -1 quando a referencia nao se aplica
static int run_image(int image)
{
    const PpmImage *frame = &bench_frames[image];
    size_t pixels = frame->width * frame->height;
    IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, image + 1);
    // A copia restaura o RGB que o debug sobrescreve e fica fora da medicao
    memcpy(nios_rgb, frame->pixels, 3 * pixels);

    PERF_RESET(PERF_COUNTER_BASE);
    PERF_START_MEASURING(PERF_COUNTER_BASE);
    LaneStatus status = nios_process_rgb_size(frame->width, frame->height);
    PERF_STOP_MEASURING(PERF_COUNTER_BASE);
    last_image = image;

    unsigned long long total = perf_get_total_time((void *)PERF_COUNTER_BASE);
    unsigned long long consensus =
        perf_get_section_time((void *)PERF_COUNTER_BASE, LANE_SECTION_CONSENSUS);
    uint32_t mask_hash = fnv1a(nios_lane_mask, pixels);
    printf("[%d] %s %lux%lu\n", image, bench_references[image].name,
           (unsigned long)frame->width, (unsigned long)frame->height);
    printf("  status=%d found=%d points=%lu inliers=%lu\n", (int)status,
           (int)nios_lane_result.found, (unsigned long)nios_point_count,
           (unsigned long)nios_lane_result.inlier_count);
    printf("  a=%.9g b=%.9g c=%.9g mse=%.9g\n", (double)nios_lane_result.poly.a,
           (double)nios_lane_result.poly.b, (double)nios_lane_result.poly.c,
           (double)nios_lane_result.mean_squared_error);
    printf("  mask_fnv1a=0x%08lx total_ms=%.1f consenso=%.1f%%\n", (unsigned long)mask_hash,
           (double)total * 1000.0 / (double)ALT_CPU_FREQ,
           total ? 100.0 * (double)consensus / (double)total : 0.0);

    if (!config_is_build()) {
        puts("  referencia: n/a (parametros diferentes do build)");
        return -1;
    }
    const BenchReference *ref = &bench_references[image];
    bool ok = status == LANE_OK && (int)nios_lane_result.found == ref->found &&
              nios_point_count == ref->points && nios_lane_result.inlier_count == ref->inliers &&
              mask_hash == ref->mask_hash;
    printf("  referencia: %s\n", ok ? "PASS" : "FAIL");
    return ok ? 1 : 0;
}

static void run_command(char *arg)
{
    if (arg == NULL) {
        puts("uso: run <indice|nome|all>");
        return;
    }
    int index = find_index(arg);
    if (index >= 0) {
        run_image(index);
        return;
    }
    // "all" roda tudo; um nome roda todos os tamanhos embutidos dele
    bool all = strcmp(arg, "all") == 0;
    int passed = 0, failed = 0, total = 0;
    for (int image = 0; image < BENCH_IMAGE_COUNT; ++image) {
        if (all || strcmp(arg, bench_references[image].name) == 0) {
            int result = run_image(image);
            passed += result == 1;
            failed += result == 0;
            ++total;
        }
    }
    if (total == 0) {
        printf("imagem desconhecida: %s (veja list)\n", arg);
    } else if (total > 1) {
        printf("%s: %d PASS, %d FAIL, %d sem referencia\n", arg, passed, failed,
               total - passed - failed);
    }
}

static void set_command(char *key, char *value)
{
    if (key == NULL || value == NULL) {
        puts("uso: set <iterations|threshold|min_inliers|seed|thickness> <valor>");
        return;
    }
    char *end;
    if (strcmp(key, "threshold") == 0) {
        double threshold = strtod(value, &end);
        if (*end != '\0' || !(threshold > 0)) {
            puts("threshold precisa ser um numero positivo");
            return;
        }
        nios_lane_config.ransac.threshold = threshold;
    } else {
        unsigned long number = strtoul(value, &end, 10);
        if (*end != '\0') {
            printf("valor invalido: %s\n", value);
            return;
        }
        if (strcmp(key, "iterations") == 0 && number > 0) {
            nios_lane_config.ransac.iterations = number;
        } else if (strcmp(key, "min_inliers") == 0 && number >= 3) {
            nios_lane_config.ransac.min_inliers = number;
        } else if (strcmp(key, "seed") == 0) {
            nios_lane_config.ransac.seed = (uint32_t)number;
        } else if (strcmp(key, "thickness") == 0 && number > 0) {
            nios_lane_config.thickness = number;
        } else {
            printf("parametro ou valor invalido: %s %s\n", key, value);
            return;
        }
    }
    show_config();
}

static void help(void)
{
    puts("  list                       imagens embutidas e referencia do computador");
    puts("  show                       parametros atuais");
    puts("  set <param> <valor>        iterations, threshold, min_inliers, seed, thickness");
    puts("  reset                      volta aos parametros do build");
    puts("  run <indice|nome|all>      processa e confere com a referencia");
    puts("  profile                    relatorio por secao da ultima execucao");
    puts("  quit                       fecha o nios2-terminal (o programa segue esperando)");
}

int main(void)
{
#ifdef BENCH_ITERATIONS
    nios_lane_config.ransac.iterations = BENCH_ITERATIONS;
#endif
    build_config = nios_lane_config;
    // sem buffer no stdin, cada tecla chega ao read_line assim que o PC envia
    setvbuf(stdin, NULL, _IONBF, 0);
    char line[96];

    for (;;) {
        wait_for_terminal();
        IOWR_ALTERA_AVALON_PIO_DATA(LED_PIO_BASE, 0);
        printf("\nRANSAC shell %d imagem(ns), %s, FPU %s, CPU %lu Hz (help para comandos)\n",
               BENCH_IMAGE_COUNT, BENCH_REAL_NAME, BENCH_FPU ? "sim" : "nao",
               (unsigned long)ALT_CPU_FREQ);
        bool images_ok = bench_frames_load();
        show_config();

        for (;;) {
            fputs("ransac> ", stdout);
            fflush(stdout);
            read_line(line, sizeof(line));
            char *command = strtok(line, " \t");
            char *arg1 = strtok(NULL, " \t");
            char *arg2 = strtok(NULL, " \t");
            if (command == NULL) {
                continue;
            } else if (strcmp(command, "help") == 0) {
                help();
            } else if (strcmp(command, "list") == 0) {
                for (int i = 0; i < BENCH_IMAGE_COUNT; ++i) {
                    printf("  %d %-20s %4ux%-4u ref: points=%lu inliers=%lu mask=0x%08lx\n", i,
                           bench_references[i].name, bench_references[i].width,
                           bench_references[i].height, bench_references[i].points,
                           bench_references[i].inliers,
                           (unsigned long)bench_references[i].mask_hash);
                }
            } else if (strcmp(command, "show") == 0) {
                show_config();
            } else if (strcmp(command, "set") == 0) {
                set_command(arg1, arg2);
            } else if (strcmp(command, "reset") == 0) {
                nios_lane_config = build_config;
                show_config();
            } else if (strcmp(command, "run") == 0) {
                if (images_ok) {
                    run_command(arg1);
                }
            } else if (strcmp(command, "profile") == 0) {
                if (last_image < 0) {
                    puts("nenhuma execucao ainda");
                } else {
                    printf("ultima execucao: [%d] %s\n", last_image,
                           bench_references[last_image].name);
                    perf_print_formatted_report((void *)PERF_COUNTER_BASE, ALT_CPU_FREQ,
                                                LANE_SECTION_COUNT, "Pre-processamento",
                                                "Amostragem", "Estimativa modelo", "Consenso",
                                                "Refinamento", "Erro/selecao", "Renderizacao");
                }
            } else if (strcmp(command, "quit") == 0 || strcmp(command, "exit") == 0) {
                puts("ate mais");
                putchar(0x04); // Ctrl-D fecha o nios2-terminal
                fflush(stdout);
                break;
            } else {
                printf("comando desconhecido: %s (help para a lista)\n", command);
            }
        }
    }
}
