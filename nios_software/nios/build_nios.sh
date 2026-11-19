#!/usr/bin/env bash
# Gera BSP + aplicacao para o sistema da P1
#   APP=bench (padrao): benchmark com as imagens embutidas (bench_main.c) e a
#                       referencia do computador com os mesmos parametros
#   APP=shell:          terminal de comandos pela JTAG UART (shell_main.c), com as
#                       mesmas imagens embutidas e a referencia do computador
#   APP=ismce:          estrutura de teste do In-System Memory Content Editor (ismce_main.c)
#                       Imagem e parametros chegam por tools/ismce_run.py, que
#                       assume o papel de IMAGE/WIDTH/HEIGHT/BENCH_*
#
# Variaveis (todas opcionais):
#   QUARTUS_ROOTDIR   .../Quartus/quartus (padrao: deduzido do quartus_sh no PATH)
#   SOPCINFO          padrao: quartus/RANSAC_NIOS/output/ransac_nios.sopcinfo
#   BENCH_SET         simple (padrao): so IMAGE
#                     full: todos os JPEG de python/test_images, em ordem alfabetica
#   IMAGE             JPEG do conjunto simple (padrao: python/test_images/solidWhiteCurve.jpg)
#   WIDTH, HEIGHT     dimensoes do frame (padrao: 960x540)
#   SIZES             varios tamanhos no mesmo .elf, ex.: "320x180 960x540" (padrao: WIDTHxHEIGHT)
#   REAL              double (padrao) ou float; float usa a FPU quando o sistema tem FPH2
#   BENCH_ITERATIONS  iteracoes do RANSAC (padrao: as de nios/entry.c, 1000)
#   BENCH_RUNS        repeticoes na placa (padrao: 1)
#   PYTHON            interpretador com OpenCV (padrao: python3)
#   RANSAC_WORK       diretorio de trabalho sem espacos (padrao: ~/.cache/ransac-fpga)
set -euo pipefail

nios_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sw_dir="$(dirname "$nios_dir")"
repo="$(dirname "$sw_dir")"
work="${RANSAC_WORK:-$HOME/.cache/ransac-fpga}/sw"
sopcinfo="${SOPCINFO:-$repo/quartus/RANSAC_NIOS/output/ransac_nios.sopcinfo}"
image="${IMAGE:-$repo/python/test_images/solidWhiteCurve.jpg}"
width="${WIDTH:-960}"
height="${HEIGHT:-540}"
runs="${BENCH_RUNS:-1}"
python="${PYTHON:-python3}"
app="${APP:-bench}"
bench_set="${BENCH_SET:-simple}"
sizes="${SIZES:-${width}x${height}}"
real="${REAL:-double}"

if [[ -z "${QUARTUS_ROOTDIR:-}" ]]; then
    quartus_sh="$(command -v quartus_sh)" || { echo "Defina QUARTUS_ROOTDIR" >&2; exit 1; }
    QUARTUS_ROOTDIR="$(dirname "$(dirname "$quartus_sh")")"
fi
export QUARTUS_ROOTDIR
export SOPC_KIT_NIOS2="$(dirname "$QUARTUS_ROOTDIR")/nios2eds"
export PATH="$SOPC_KIT_NIOS2/bin:$SOPC_KIT_NIOS2/bin/gnu/H-x86_64-pc-linux-gnu/bin:$SOPC_KIT_NIOS2/sdk2/bin:$QUARTUS_ROOTDIR/bin:$QUARTUS_ROOTDIR/sopc_builder/bin:$PATH"

case "$work" in
    *[[:space:]]*) echo "RANSAC_WORK nao pode conter espacos: $work" >&2; exit 1 ;;
esac
[[ -f "$sopcinfo" ]] || { echo "sopcinfo nao encontrado: $sopcinfo (rode build_hw.sh)" >&2; exit 1; }
case "$app" in
    bench|ismce|shell) ;;
    *) echo "APP deve ser bench, ismce ou shell: $app" >&2; exit 1 ;;
esac
case "$real" in
    double) real_flags="" ;;
    float) real_flags="-DLANE_REAL_FLOAT -fsingle-precision-constant" ;;
    *) echo "REAL deve ser double ou float: $real" >&2; exit 1 ;;
esac
# O BSP le o FPH2 do .sopcinfo e acrescenta os -mcustom-*; aqui so registramos para o log
fpu=0
if grep -q altera_nios_custom_instr_floating_point_2 "$sopcinfo"; then
    fpu=1
fi
case "$bench_set" in
    simple) images=("$image") ;;
    full) LC_COLLATE=C; images=("$repo"/python/test_images/*.jpg) ;;
    *) echo "BENCH_SET deve ser simple ou full: $bench_set" >&2; exit 1 ;;
esac

out="$repo/nios_software/build/nios"
rm -rf "$work"
mkdir -p "$work" "$out"
cp -r "$sw_dir/src" "$sw_dir/include" "$sw_dir/nios" "$work/"
cp "$sopcinfo" "$work/system.sopcinfo"

core_sources="src/preprocess.c src/poly.c src/ransac.c src/render.c src/lane.c"
if [[ "$app" == ismce ]]; then
    sources="$core_sources nios/ismce_main.c"
    defines="-DLANE_PROFILE -DBENCH_FPU=$fpu"
else
    # O buffer do entry.c cobre o maior tamanho; cada frame leva o proprio tamanho no PPM
    max_width=0
    max_height=0
    for size in $sizes; do
        [[ "$size" =~ ^[0-9]+x[0-9]+$ ]] || { echo "tamanho invalido em SIZES: $size" >&2; exit 1; }
        (( ${size%x*} > max_width )) && max_width=${size%x*}
        (( ${size#*x} > max_height )) && max_height=${size#*x}
    done
    host_args=()
    defines="-DLANE_PROFILE -DLANE_IMAGE_WIDTH=$max_width -DLANE_IMAGE_HEIGHT=$max_height"
    defines+=" -DBENCH_RUNS=$runs -DBENCH_FPU=$fpu"
    if [[ -n "${BENCH_ITERATIONS:-}" ]]; then
        defines+=" -DBENCH_ITERATIONS=$BENCH_ITERATIONS"
        host_args+=(--iterations "$BENCH_ITERATIONS")
    fi
    # Cada frame vira um PPM com o nome no comentario; os PPMs ficam em sequencia num unico .incbin
    # A referencia do computador usa o mesmo RGB, os mesmos parametros e a mesma aritmetica:
    # tools/bench_check.py compara com o log e a placa confere direto pelo bench_images.h
    "$sw_dir/tools/build_reference.sh" "$work/reference_bin" "$real"
    rm -rf "$out/reference" "$out"/reference_* "$out/reference.txt"
    mkdir -p "$work/frames" "$out/reference"
    : > "$work/bench_images.ppm"
    entries=()
    for img in "${images[@]}"; do
        name="$(basename "${img%.*}")"
        for size in $sizes; do
            frame="$work/frames/${name}_$size"
            "$python" "$sw_dir/tools/prepare_rgb.py" "$img" "$frame.rgb" \
                --width "${size%x*}" --height "${size#*x}"
            printf 'P6\n# %s\n%s %s\n255\n' "$name" "${size%x*}" "${size#*x}" > "$frame.ppm"
            cat "$frame.rgb" >> "$frame.ppm"
            cat "$frame.ppm" >> "$work/bench_images.ppm"
            "$work/reference_bin/lane_detect" "$frame.rgb" "${size%x*}" "${size#*x}" \
                "$out/reference/${name}_$size" "${host_args[@]}" >/dev/null
            {
                echo "image=$name size=$size"
                cat "$out/reference/${name}_${size}_model.json"
                "$python" "$sw_dir/tools/mask_hash.py" "$out/reference/${name}_${size}_mask.bin"
            } >> "$out/reference.txt"
            entries+=("$name:$size")
        done
    done
    "$python" "$sw_dir/tools/bench_header.py" "$out/reference" "$bench_set" "$real" \
        "${entries[@]}" > "$work/nios/bench_images.h"
    sources="$core_sources nios/entry.c nios/bench_frames.c nios/${app}_main.c nios/bench_image.S"
fi
elf="ransac_$app.elf"

# O Makefile gerado so compila fontes dentro do diretorio da aplicacao, por
# isso o proprio $work e a aplicacao (src/, include/, nios/) e o BSP fica em bsp/
cd "$work"
nios2-bsp hal bsp system.sopcinfo \
    --set hal.enable_small_c_library false \
    --set hal.make.bsp_cflags_optimization -O2
# shellcheck disable=SC2086
nios2-app-generate-makefile --bsp-dir bsp --app-dir . --elf-name "$elf" \
    --src-files $sources \
    --set APP_INCLUDE_DIRS "include nios" \
    --set APP_CFLAGS_DEFINED_SYMBOLS "$defines" \
    --set APP_CFLAGS_OPTIMIZATION -O2 \
    --set APP_CFLAGS_USER_FLAGS "-std=gnu11 $real_flags"
make -j"$(nproc)"
nios2-elf-size "$elf"

cp "$elf" "$out/"
case "$app" in
    ismce) echo "ELF: $out/$elf  (carregue com nios/load_nios.sh e rode tools/ismce_run.py)" ;;
    shell) echo "ELF: $out/$elf (${#entries[@]} frame(s), $real, FPU=$fpu; abra com nios/run_shell.sh)" ;;
    *) echo "ELF: $out/$elf (${#entries[@]} frame(s), $real, FPU=$fpu)"
       echo "Referencia: $out/reference.txt" ;;
esac
