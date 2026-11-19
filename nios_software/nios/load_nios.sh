#!/usr/bin/env bash
# Carrega um .elf no Nios da P1 e inicia a execucao (nios2-download -g)
#
# Uso: load_nios.sh <elf>
# Variaveis: QUARTUS_ROOTDIR, CABLE (ex.: "USB-Blaster [1-1]"),
#            RANSAC_WORK (padrao: ~/.cache/ransac-fpga)
#
# O nios2-download converte o .elf em .srec com caminhos sem aspas, entao um
# espaco no caminho quebra a conversao e o rm do .srec temporario
# Por isso o .elf vai antes para RANSAC_WORK/download
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    echo "Uso: $0 <elf>" >&2
    exit 1
fi
if [[ -z "${QUARTUS_ROOTDIR:-}" ]]; then
    quartus_sh="$(command -v quartus_sh)" || { echo "Defina QUARTUS_ROOTDIR" >&2; exit 1; }
    QUARTUS_ROOTDIR="$(dirname "$(dirname "$quartus_sh")")"
fi
export QUARTUS_ROOTDIR
export SOPC_KIT_NIOS2="$(dirname "$QUARTUS_ROOTDIR")/nios2eds"
# nios2-download chama o nios2-elf-objcopy do toolchain GNU do Nios
export PATH="$SOPC_KIT_NIOS2/bin:$SOPC_KIT_NIOS2/bin/gnu/H-x86_64-pc-linux-gnu/bin:$QUARTUS_ROOTDIR/bin:$PATH"
stage="${RANSAC_WORK:-$HOME/.cache/ransac-fpga}/download"
case "$stage" in
    *[[:space:]]*) echo "RANSAC_WORK nao pode conter espacos: $stage" >&2; exit 1 ;;
esac
mkdir -p "$stage"
elf="$stage/$(basename "$1")"
cp "$1" "$elf"

cable_args=()
if [[ -n "${CABLE:-}" ]]; then
    cable_args=(-c "$CABLE")
fi
nios2-download "${cable_args[@]}" -g "$elf"
