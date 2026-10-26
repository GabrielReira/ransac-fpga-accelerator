#!/usr/bin/env bash
# Gera BSP + aplicacao para o sistema da P1
#   APP=bench (padrao): benchmark com a imagem embutida (bench_main.c) e a
#                       referencia do computador com os mesmos parametros
#   APP=ismce:          estrutura de teste do In-System Memory Content Editor (ismce_main.c)
#                       Imagem e parametros chegam por tools/ismce_run.py, que
#                       assume o papel de IMAGE/WIDTH/HEIGHT/BENCH_*
#
# Variaveis (todas opcionais):
#   QUARTUS_ROOTDIR   .../Quartus/quartus (padrao: deduzido do quartus_sh no PATH)
#   SOPCINFO          padrao: quartus/RANSAC_NIOS/output/ransac_nios.sopcinfo
#   IMAGE             JPEG de entrada (padrao: python/test_images/solidWhiteCurve.jpg)
#   WIDTH, HEIGHT     dimensoes do frame (padrao: 960x540)
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
    bench|ismce) ;;
    *) echo "APP deve ser bench ou ismce: $app" >&2; exit 1 ;;
esac

rm -rf "$work"
mkdir -p "$work" "$repo/nios_software/build/nios"
cp -r "$sw_dir/src" "$sw_dir/include" "$sw_dir/nios" "$work/"
cp "$sopcinfo" "$work/system.sopcinfo"

core_sources="src/preprocess.c src/poly.c src/ransac.c src/render.c src/lane.c"
host_args=()
if [[ "$app" == bench ]]; then
    "$python" "$sw_dir/tools/prepare_rgb.py" "$image" "$work/bench_image.rgb" \
        --width "$width" --height "$height"
    sources="$core_sources nios/entry.c nios/bench_main.c nios/bench_image.S"
    defines="-DLANE_PROFILE -DLANE_IMAGE_WIDTH=$width -DLANE_IMAGE_HEIGHT=$height -DBENCH_RUNS=$runs"
    if [[ -n "${BENCH_ITERATIONS:-}" ]]; then
        defines+=" -DBENCH_ITERATIONS=$BENCH_ITERATIONS"
        host_args+=(--iterations "$BENCH_ITERATIONS")
    fi
else
    sources="$core_sources nios/ismce_main.c"
    defines="-DLANE_PROFILE"
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
    --set APP_CFLAGS_USER_FLAGS "-std=gnu11"
make -j"$(nproc)"
nios2-elf-size "$elf"

out="$repo/nios_software/build/nios"
cp "$elf" "$out/"
if [[ "$app" == ismce ]]; then
    echo "ELF: $out/$elf  (carregue com nios2-download -g e rode tools/ismce_run.py)"
    exit 0
fi

# Referencia no computador com o mesmo RGB e os mesmos parametros
# Deve bater com as linhas a=, b=, c=, inliers= e mask_fnv1a= impressas pela placa
make -C "$sw_dir" host >/dev/null
"$sw_dir/build/lane_detect" bench_image.rgb "$width" "$height" "$out/reference" \
    "${host_args[@]}" >/dev/null
{
    cat "$out/reference_model.json"
    "$python" "$sw_dir/tools/mask_hash.py" "$out/reference_mask.bin"
} | tee "$out/reference.txt"
echo "ELF: $out/ransac_bench.elf  Referencia: $out/reference.txt"
