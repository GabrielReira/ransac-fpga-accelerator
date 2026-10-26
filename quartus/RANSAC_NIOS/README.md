# P1 — RANSAC somente-software no Nios II (DE2-115)

Sistema base reproduzível gerado por scripts a partir dos arquivos
deste diretório diretamente por CLI.

## Sistema

| Componente | Configuração |
| --- | --- |
| `cpu` | Nios II Gen2 **/e** (`Tiny`, sem licença); `/f` com `CPU_IMPL=Fast` |
| `sdram` | 128 MB em `0x0000_0000`, código, dados e buffers |
| `jtag_uart` | `stdout`/`stdin` (`nios2-terminal`) |
| `sys_timer` | timer de sistema do HAL, 1 ms |
| `perf_counter` | 7 seções + total (profiling) |
| `sysid` | `0x20260201` |
| `led_pio` | `LEDG[7:0]` |
| `mailbox` | 1 KiB on-chip, ISMCE `MBOX`: comandos e resultados |
| `img_buf` | 192 KiB on-chip, ISMCE `IMG`: frame RGB888 (até 320×200) |

Clock de 50 MHz por um PLL no top-level (`ransac_nios_top.v`): `c0` para o
sistema e `c1` defasado −3 ns para `DRAM_CLK`. `KEY[0]` é o reset e `LEDG[8]`
indica PLL travado.

Pinos e padrões de I/O conferidos com o `DE2_115.qsf` do Altera University
Program (71 pinos, sem diferenças) e com o manual da DE2-115 (a confirmar com o kit físico). 
`LEDG` é fixo em 2,5 V; `KEY` segue o jumper **JP7** (bancos 5/6, padrão 2,5 V). 
Se a placa estiver com JP7 em outra tensão, ajustar o padrão de
`KEY` em `ransac_nios_project.tcl`.

O `/f` sem licença gera um `.sof` *time-limited* (OpenCore Plus): o sistema só
funciona com o cabo JTAG conectado. O `/e` não tem multiplicador em hardware
nem FPU; as operações em `double` são emuladas em software, o que afeta o
profiling.

## Requisitos

- Quartus Prime Lite 17.0 com Nios II EDS (Linux).
- OpenCV no Python do computador (`pip install opencv-python-headless`),
  somente para converter o JPEG.
- USB-Blaster com permissão de acesso. No Linux, crie
  `/etc/udev/rules.d/51-usbblaster.rules` com
  `SUBSYSTEM=="usb", ATTR{idVendor}=="09fb", ATTR{idProduct}=="6001", MODE="0666"`,
  recarregue as regras e verifique com `jtagconfig`.

Os scripts compilam na pasta padrão `~/.cache/ransac-fpga` (`RANSAC_WORK`), porque os makefiles do Nios não aceitam espaços no caminho do repositório
(pasta modificável).

## Uso

```bash
export QUARTUS_ROOTDIR=/caminho/para/Quartus/quartus
# Só para os comandos diretos (quartus_pgm, nios2-download, jtagconfig); os
# scripts ajustam o PATH sozinhos
export PATH="$QUARTUS_ROOTDIR/bin:$QUARTUS_ROOTDIR/../nios2eds/bin:$PATH"
jtagconfig      # deve listar o USB-Blaster e o EP4CE115

# 1. Hardware: gera Qsys, cria o projeto e compila (~1 min).
quartus/RANSAC_NIOS/build_hw.sh     # .sof e .sopcinfo em output/

# 2. Software: BSP + benchmark com a imagem embutida e a referência do computador.
nios_software/nios/build_nios.sh      # padrão: solidWhiteCurve, 960x540
WIDTH=480 HEIGHT=270 BENCH_ITERATIONS=200 nios_software/nios/build_nios.sh

# 3. Placa: programa, carrega, imprime o relatório e grava o log.
nios_software/nios/run_bench.sh
CABLE="USB-Blaster [1-1]" nios_software/nios/run_bench.sh     # com mais de um cabo
```

`output/` guarda só o último build: depois de `CPU_IMPL=Fast`, rodar
`build_hw.sh` de novo antes de voltar ao `/e`. Com `/f`, o script avisa que o
`.sof` é *time-limited* e o salva como `output/ransac_nios.sof` mesmo assim.

O benchmark aguarda o `nios2-terminal` conectar (`LEDG7` aceso), executa e
encerra o terminal ao final (`LEDG[7:0]` todos acesos). Para validar a
execução, compare `a=`, `b=`, `c=`, `inliers=` e `mask_fnv1a=` do log com
`nios_software/build/nios/reference.txt`, gerado pelo mesmo código C no
computador.

## Estrutura de teste pelo In-System Memory Content Editor

Alternativa ao terminal para testes automatizados: o PC grava o frame em
`IMG` e os parâmetros em `MBOX` pelo JTAG, dispara a execução e lê os
resultados. O layout da `MBOX` está em `nios_software/nios/mailbox.h`, lido
diretamente pelo script Python.

```bash
APP=ismce nios_software/nios/build_nios.sh      # gera ransac_ismce.elf
quartus_pgm -m JTAG -o "p;quartus/RANSAC_NIOS/output/ransac_nios.sof"
nios2-download -g nios_software/build/nios/ransac_ismce.elf
python3 nios_software/tools/ismce_run.py python/test_images/solidWhiteCurve.jpg \
    --width 320 --height 180 --iterations 1000
```

Com mais de um cabo, passe `-c "USB-Blaster [1-1]"` ao `quartus_pgm` e ao
`nios2-download`, e `--cable "USB-Blaster [1-1]"` ao `ismce_run.py`.

O script redimensiona o JPEG, grava `IMG` e `MBOX` com `quartus_stp`
(`tools/ismce_run.tcl`), espera o Nios zerar `MBOX_COMMAND` e compara status,
hash do RGB recebido, pontos, inliers, coeficientes, MSE e hash da máscara com
a mesma implementação C no computador. Imprime os ciclos por seção e
termina com `PASS` (código 0) ou `FAIL` (código 1). Com o programa já
carregado, novas imagens e parâmetros não exigem recompilar nem regravar a
placa. `--skip-image` reutiliza o frame já carregado.

Também é possível usar a interface gráfica (*Tools -> In-System Memory Content
Editor*): `MBOX` palavra 0 = `0x5253434E` indica o Nios pronto, palavra 4
(heartbeat) aumenta continuamente, e escrever 1 na palavra 2 dispara uma
execução com o conteúdo atual de `IMG` e `MBOX`.

Para o Nios II/f, o código já acessa `MBOX` com `IORD`/`IOWR` (sem cache) e
faz `alt_dcache_flush_all()` antes de copiar `IMG`.

## Seções do profiling

Definidas em `nios_software/include/lane_profile.h`. Sem `-DLANE_PROFILE`
(build do computador), os marcadores não geram código.

| Seção | Etapa |
| --- | --- |
| 1 | Pré-processamento: filtro de cor, ROI, extração de pontos |
| 2 | Amostragem dos três índices |
| 3 | Estimativa do modelo candidato |
| 4 | Avaliação de consenso, O(k·N) |
| 5 | Refinamento sobre o consenso |
| 6 | Erro (MSE) e seleção do melhor modelo |
| 7 | Renderização da máscara e do debug |

As seções 2–6 correspondem às categorias do profiling em Python.
