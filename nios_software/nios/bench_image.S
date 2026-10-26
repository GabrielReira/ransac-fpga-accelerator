/* RGB888 cru do benchmark, embutido no .elf
   build_nios.sh copia a imagem escolhida para bench_image.rgb antes de compilar */
    .section .rodata
    .balign 4
    .global bench_rgb
    .global bench_rgb_end
bench_rgb:
    .incbin "bench_image.rgb"
bench_rgb_end:
