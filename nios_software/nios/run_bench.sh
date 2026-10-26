#!/usr/bin/env bash
# Programa a DE2-115 com o .sof da P1, carrega o benchmark e grava a saida
#
# Uso: run_bench.sh [log]   (padrao: nios_software/build/nios/bench_<data>.log)
# Variaveis: QUARTUS_ROOTDIR, SOF (padrao: quartus/RANSAC_NIOS/output/ransac_nios.sof),
#            ELF (padrao: nios_software/build/nios/ransac_bench.elf), CABLE (ex.: "USB-Blaster [1-1]")
set -euo pipefail

nios_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$(dirname "$nios_dir")")"
out="$repo/nios_software/build/nios"
sof="${SOF:-$repo/quartus/RANSAC_NIOS/output/ransac_nios.sof}"
elf="${ELF:-$out/ransac_bench.elf}"
log="${1:-$out/bench_$(date +%Y%m%d_%H%M%S).log}"

if [[ -n "${QUARTUS_ROOTDIR:-}" ]]; then
    # nios2-download fica no nios2eds, ao lado do quartus/
    export PATH="$QUARTUS_ROOTDIR/bin:$QUARTUS_ROOTDIR/../nios2eds/bin:$PATH"
fi
cable_args=()
if [[ -n "${CABLE:-}" ]]; then
    cable_args=(-c "$CABLE")
fi

jtagconfig
quartus_pgm "${cable_args[@]}" -m JTAG -o "p;$sof"
nios2-download "${cable_args[@]}" -g "$elf"
#o benchmark so imprime depois que o terminal conecta e fecha com Ctrl-D
nios2-terminal "${cable_args[@]}" -q | tee "$log"
echo "Log: $log"
echo "Referencia do computador: $out/reference.txt"
