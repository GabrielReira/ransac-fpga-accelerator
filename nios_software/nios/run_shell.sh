#!/usr/bin/env bash
# Programa a DE2-115 com o .sof da P1, carrega o shell e abre o nios2-terminal
#
# Uso: run_shell.sh [--no-program]   (--no-program: so carrega o .elf, sem regravar o .sof)
# Variaveis: QUARTUS_ROOTDIR, SOF (padrao: quartus/RANSAC_NIOS/output/ransac_nios.sof),
#            ELF (padrao: nios_software/build/nios/ransac_shell.elf), CABLE (ex.: "USB-Blaster [1-1]")
# Para reabrir o terminal sem recarregar nada: nios2-terminal
set -euo pipefail

nios_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$(dirname "$nios_dir")")"
sof="${SOF:-$repo/quartus/RANSAC_NIOS/output/ransac_nios.sof}"
elf="${ELF:-$repo/nios_software/build/nios/ransac_shell.elf}"

if [[ -n "${QUARTUS_ROOTDIR:-}" ]]; then
    export PATH="$QUARTUS_ROOTDIR/bin:$QUARTUS_ROOTDIR/../nios2eds/bin:$PATH"
fi
cable_args=()
if [[ -n "${CABLE:-}" ]]; then
    cable_args=(-c "$CABLE")
fi

if [[ "${1:-}" != --no-program ]]; then
    quartus_pgm "${cable_args[@]}" -m JTAG -o "p;$sof"
fi
"$nios_dir/load_nios.sh" "$elf"
nios2-terminal "${cable_args[@]}"
