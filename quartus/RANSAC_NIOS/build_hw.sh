#!/usr/bin/env bash
# Gera o Qsys, cria o projeto e compila o hardware da P1
#
# Variaveis:
#   QUARTUS_ROOTDIR  .../Quartus/quartus (padrao: quartus_sh no PATH)
#   CPU_IMPL         Tiny (Nios II/e, padrao) ou Fast (Nios II/f)
#   RANSAC_WORK      diretorio de trabalho sem espacos (padrao: ~/.cache/ransac-fpga)
#
# As ferramentas do Quartus se perdem com espacos e acentos no caminho, entao
# tudo e copiado e compilado em RANSAC_WORK/hw
# .sof e .sopcinfo voltam para output/ ao lado deste script
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work="${RANSAC_WORK:-$HOME/.cache/ransac-fpga}/hw"
cpu_impl="${CPU_IMPL:-Tiny}"

if [[ -n "${QUARTUS_ROOTDIR:-}" ]]; then
    export PATH="$QUARTUS_ROOTDIR/bin:$QUARTUS_ROOTDIR/sopc_builder/bin:$PATH"
fi
for tool in quartus_sh qsys-script qsys-generate; do
    command -v "$tool" >/dev/null || { echo "$tool nao encontrado; defina QUARTUS_ROOTDIR" >&2; exit 1; }
done
case "$work" in
    *[[:space:]]*) echo "RANSAC_WORK nao pode conter espacos: $work" >&2; exit 1 ;;
esac

rm -rf "$work"
mkdir -p "$work"
cp "$here"/ransac_nios_qsys.tcl "$here"/ransac_nios_project.tcl \
   "$here"/ransac_nios_top.v "$here"/ransac_nios.sdc "$work"/
cd "$work"

qsys-script --script=ransac_nios_qsys.tcl --cmd="set cpu_impl $cpu_impl"
qsys-generate ransac_nios.qsys --synthesis=VERILOG --output-directory=ransac_nios \
    --family="Cyclone IV E" --part=EP4CE115F29C7
quartus_sh -t ransac_nios_project.tcl
quartus_sh --flow compile ransac_nios

rm -rf "$here/output"
mkdir -p "$here/output"
cp ransac_nios.qsys ransac_nios.sopcinfo "$here/output/"
# Sem licenca o /f so gera ransac_nios_time_limited.sof
# O nome fixo mantem run_bench.sh e os comandos do README iguais para os dois CPUs
if [[ -f output_files/ransac_nios_time_limited.sof ]]; then
    cp output_files/ransac_nios_time_limited.sof "$here/output/ransac_nios.sof"
    echo "AVISO: .sof time-limited (OpenCore Plus), mantenha o cabo JTAG conectado" >&2
else
    cp output_files/ransac_nios.sof "$here/output/"
fi
# Folga de setup/hold no pior caso (slow 85C)
#folga negativa = timing violado
awk '/^; Slow 1200mV 85C Model (Setup|Hold) Summary/{n=6} n-->0' output_files/ransac_nios.sta.rpt
echo "Hardware pronto em $here/output (projeto completo em $work)"
