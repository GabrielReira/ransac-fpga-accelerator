# RANSAC FPGA ACCELERATOR - FPGA DE2-115 (Nios II + Verilog)

Projeto hardware/software desenvolvido para a disciplina de **Laboratório Integrado IV-A**, com aceleração em FPGA do algoritmo **RANSAC (Random Sample Consensus)** aplicado à detecção de faixas em imagens.

## Sobre o projeto

O objetivo é acelerar em hardware dedicado (Verilog) a etapa mais custosa do algoritmo RANSAC, mantendo o restante da aplicação rodando em software (processador soft-core **Nios II**), e comprovar o ganho de desempenho obtido.

**Aplicação escolhida:** detecção de uma faixa pintada de pista por imagem. A implementação atual filtra tinta branca/amarela, restringe os pixels a uma região de interesse (ROI) trapezoidal e extrai um ponto no centro de cada corrida horizontal de tinta. O RANSAC descarta outliers e ajusta a curva quadrática `x = a*y² + b*y + c` aos pontos consistentes com a faixa (inliers).

**Etapa prevista para aceleração:** avaliação de consenso — para cada modelo candidato, calcular o resíduo horizontal de todos os pontos em relação à curva e contar quantos estão dentro do threshold. Na versão C, o threshold é configurado em pixels e seu quadrado é calculado uma vez, antes das tentativas, para comparar `dx² < threshold²`. Essa etapa tem complexidade $O(k \cdot N)$ e permite paralelizar o cálculo de cada ponto. O profiling ainda deve confirmar seu custo na plataforma alvo.

## Metodologia / Roadmap

Estrutura definida para realização do projeto:

- [X] **1. Aplicação em Python** — implementação de referência do RANSAC para validar o algoritmo
- [ ] **2. Profiling em Python** — identificar os gargalos computacionais
- [X] **3. Python para C** — entrada RGB, buffers estáticos e aplicação para o Nios II; validação com o BSP e na placa pendente
- [ ] **4. Validação do C no Nios II** — leitura de memória via *In-System Memory Content Editor* (Quartus); usa-se uma imagem reduzida para caber nas memórias internas da FPGA
- [ ] **5. Acelerador em Verilog** — implementação do gargalo identificado, integrado ao sistema via Platform Designer (Nios II + módulo acelerador)
- [ ] **6. Revalidação + medição de desempenho** — repete a validação do passo 4 na versão acelerada e mede o ganho obtido
- [ ] **7. Comunicação UART** — integração entre o host Python e o sistema embarcado (Nios II + Verilog) via Platform Designer
- [ ] **8. Algoritmo comparador (Python)** — validação final comparando as imagens produzidas pelo algoritmo Python de referência com as imagens obtidas da implementação completa em FPGA

## Estrutura do repositório

```
.
├── python/                # Implementação de referência, profiling e algoritmo comparador
│   ├── ransac.py
│   ├── profiling/
│   └── comparator/
├── nios_software/         # Aplicação C para o Nios II, sem bibliotecas externas
│   ├── include/           # Point, Poly, Image, BinaryMask e APIs
│   ├── src/               # Filtro/ROI, ajuste, RANSAC e rasterização
│   ├── nios/              # main, configuração e buffers estáticos da placa
│   ├── host/              # Teste no computador: RGB e saída binária/PPM/JSON
│   ├── tools/             # Preparação de RGB e conversão do debug no computador
│   └── tests/             # Testes do núcleo e integração com a referência Python
├── verilog/               # Módulo acelerador (RTL) e testbench
│   ├── rtl/
│   └── tb/
├── quartus/               # Projetos Quartus / Platform Designer
│   ├── RANSAC_NIOS/       # P1 — versão somente-software
│   └── RANSAC_Acelerado/  # P2 — versão híbrida hardware/software
├── docs/                  # Relatório, imagens de teste, resultados e gráficos
└── README.md
```

## Executar a implementação em C

O Nios II recebe **RGB já decodificado** e produz uma matriz `0/1` e um buffer RGB de debug. Todo o processamento em C está em `nios_software/`, usando apenas a biblioteca C e a matemática padrão do toolchain/BSP. Não é necessário instalar bibliotecas de imagem.

Para compilar o núcleo e verificar as fontes da aplicação embarcada no computador:

```bash
make -C nios_software
```

Para testar a mesma implementação no computador, prepare o RGB a partir de um JPEG e execute a ferramenta host:

```bash
make -C nios_software host
mkdir -p nios_software/results
python3 nios_software/tools/prepare_rgb.py python/test_images/solidWhiteCurve.jpg nios_software/results/solidWhiteCurve.rgb
nios_software/build/lane_detect nios_software/results/solidWhiteCurve.rgb 960 540 nios_software/results/solidWhiteCurve --min-inliers 50 --seed 42 --thickness 3
```

O teste host grava a matriz (`_mask.bin`, um byte `0/1` por pixel), a imagem de debug (`_debug.ppm`, sem compressão) e os metadados (`_model.json`). A espessura é configurável; o modelo continua sendo uma única parábola entre a menor e a maior altura dos inliers. Os scripts Python são ferramentas do computador, usando o OpenCV já empregado pela referência, e não são executados no Nios II.

Veja [nios_software/README.md](nios_software/README.md) para a organização dos módulos, parâmetros, testes e uso dos buffers no Nios II.

## Licença

MIT
