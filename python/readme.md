# Aplicação de referência em Python

Esta etapa consiste na implementação em software do algoritmo **RANSAC** e da extração de características visuais para detecção de faixas de pista. O objetivo principal é validar a lógica do algoritmo e o pipeline de processamento de imagens antes de realizar o *profiling* e a migração para C/hardware (Nios II e Verilog).

## Referências

- RANSAC: https://en.wikipedia.org/wiki/Random_sample_consensus
- Filtro Canny (Código-fonte de referência em C++ do OpenCV): https://github.com/opencv/opencv/blob/5.x/modules/imgproc/src/canny.cpp
- Vídeo sobre o Canny: https://www.youtube.com/watch?v=17cOHpSaqi0

## Base de dados

- Imagens de pistas (CarND-LaneLines-P1 Test Images): https://github.com/udacity/CarND-LaneLines-P1/tree/master/test_images

## Ambiente e dependências

- **Python:** 3.14.7
- **NumPy:** 2.5.3
- **OpenCV:** 5.0.0

# Como executar

Configure um ambiente virtual primeiro e instale as dependências acima. Após isso, basta executar no seu terminal:

```bash
    python ransac.py caminho/da/imagem.jpg
```

O resultado é salvo em `test_images/results/<nome_imagem>_result_<timestamp>.png`.
