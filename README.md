# RANSAC FPGA ACCELERATOR - FPGA DE2-115 (Nios II + Verilog)

Projeto hardware/software desenvolvido para a disciplina de **Laboratório Integrado IV-A**, com aceleração em FPGA do algoritmo **RANSAC (Random Sample Consensus)** aplicado à detecção de retas em imagens.

## Sobre o projeto

O objetivo é acelerar em hardware dedicado (Verilog) a etapa mais custosa do algoritmo RANSAC, mantendo o restante da aplicação rodando em software (processador soft-core **Nios II**), e comprovar o ganho de desempenho obtido.

**Aplicação escolhida:** detecção de faixas de pista (retas) em imagens de pistas — a partir de pontos de borda extraídos da imagem (via Canny/Sobel), o algoritmo descarta outliers (ruído, sombras, marcações irregulares) e ajusta uma reta apenas aos pontos consistentes com a faixa (inliers).

**Etapa acelerada:** avaliação de consenso — para cada modelo candidato, calcular a distância de todos os pontos à reta e contar quantos estão dentro do limiar de aceitação. É a etapa de maior complexidade computacional ($O(k \cdot N)$) e a mais facilmente paralelizável, já que o cálculo de cada ponto é independente dos demais.

## Metodologia / Roadmap

Estrutura definida para realização do projeto:

- [ ] **1. Aplicação em Python** — implementação de referência do RANSAC para validar o algoritmo
- [ ] **2. Profiling em Python** — identificar os gargalos computacionais
- [ ] **3. Python para C** — reimplementação para rodar no Nios II
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
├── nios_software/         # Código C para o Nios II (versão somente-software)
├── verilog/               # Módulo acelerador (RTL) e testbench
│   ├── rtl/
│   └── tb/
├── quartus/               # Projetos Quartus / Platform Designer
│   ├── RANSAC_NIOS/       # P1 — versão somente-software
│   └── RANSAC_Acelerado/  # P2 — versão híbrida hardware/software
├── docs/                  # Relatório, imagens de teste, resultados e gráficos
└── README.md
```

## Licença

MIT
