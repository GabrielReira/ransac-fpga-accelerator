/* PPMs (P6) do benchmark, concatenados e embutidos no .elf
   build_nios.sh gera bench_images.ppm antes de compilar; nios/bench_frames.c percorre */
    .section .rodata
    .balign 4
    .global bench_ppm
    .global bench_ppm_end
bench_ppm:
    .incbin "bench_images.ppm"
bench_ppm_end:
