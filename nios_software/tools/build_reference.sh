#!/usr/bin/env bash
# Compila o lane_detect do computador numa pasta propria, em double ou float
#
# Uso: build_reference.sh <saida> <double|float>
# O build_nios.sh e o ismce_run.py usam esta referencia para comparar com a placa
# Pasta separada evita misturar objetos double e float no build/ do Makefile
set -euo pipefail

out="$1"
real="$2"
sw_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
flags=(-O2 -std=c11 -Wall -Wextra -Wpedantic -Werror -I"$sw_dir/include")
case "$real" in
    double) ;;
    float) flags+=(-DLANE_REAL_FLOAT -fsingle-precision-constant) ;;
    *) echo "aritmetica deve ser double ou float: $real" >&2; exit 1 ;;
esac
mkdir -p "$out"
cc "${flags[@]}" "$sw_dir"/src/*.c "$sw_dir"/host/*.c -lm -o "$out/lane_detect"
