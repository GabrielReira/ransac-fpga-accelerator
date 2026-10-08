# Detecção de uma faixa no Nios II

O Nios II recebe uma imagem **RGB888 já decodificada**. Todo o processamento
é executado em C dentro da placa: filtro branco/amarelo, ROI trapezoidal,
centros das corridas horizontais, RANSAC, ajuste de uma única parábola e
geração da máscara binária.

```text
buffer RGB -> filtro de cor -> ROI -> Point[] -> RANSAC -> Poly
             -> máscara 0/1 + buffer RGB de debug
```

O código embarcado usa somente a biblioteca C e a matemática padrão
fornecidas pelo toolchain/BSP do Nios II. Não exige codecs ou bibliotecas
de imagem. Não usa arquivos, heap, OpenCV ou Python. O computador é
responsável pela decodificação prévia do JPEG e por transportar o RGB.

## Fontes para a aplicação na DE2-115

Inclua no projeto de aplicação associado ao BSP:

- `src/preprocess.c`, `src/poly.c`, `src/ransac.c`, `src/render.c` e `src/lane.c`.
- `nios/entry.c` e `nios/main.c`.
- Os diretórios de include `include/` e `nios/`.

Use C11 e habilite a biblioteca matemática padrão (`-lm`). Os arquivos
`host/`, `tools/` e `tests/` são exclusivos da validação no computador.

Em `nios/board_config.h`, configure:

```c
#define LANE_IMAGE_WIDTH 320
#define LANE_IMAGE_HEIGHT 180
#define LANE_MAX_POINTS 4096
```

Esses valores precisam corresponder ao frame RGB recebido e à memória
definida no BSP. Para cada frame:

1. Preencha `nios_rgb` com exatamente `3 * width * height` bytes.
2. Ajuste `nios_lane_config`, se necessário.
3. Escreva `1` em `nios_request`.
4. Aguarde `nios_request` voltar a zero e consulte `nios_status`.
5. Com status `LANE_OK`, consulte `nios_lane_result.found` e os buffers.

Também é possível chamar `nios_process_rgb()` diretamente depois de
receber o frame na sua própria rotina de UART/JTAG. Essa função devolve
`LaneStatus`; não imprime ou grava arquivos.

`nios_lane_mask` contém a matriz de saída. `nios_rgb` contém a imagem
de debug com marcações vermelhas. O RGB é alterado em lugar, então cada
novo frame deve repor todos os pixels originais. `nios_lane_result`
contém os coeficientes, quantidade de inliers, MSE e intervalo vertical;
`nios_point_count` contém a quantidade de pontos extraídos.

Se os buffers e a flag forem escritos por outro dispositivo ou pelo
editor de memória, a integração precisa garantir coerência de cache:
use uma região sem cache ou a manutenção apropriada de cache do BSP.
`volatile` na flag, sozinho, não resolve a visibilidade de memória.
Os endereços/linker script, transporte UART e configuração de memória
são específicos do sistema criado no Platform Designer e continuam
pendentes de validação na placa.

## API do pipeline

Para usar buffers de outro produtor, inclua `lane.h`:

```c
Image image = {width, height, rgb_buffer};
BinaryMask mask = {width, height, mask_buffer};
LaneConfig config = lane_default_config();
config.ransac.min_inliers = 50;
config.ransac.seed = 42;
config.thickness = 7;

LaneWorkspace workspace = {
    points, MAX_POINTS,
    {candidate_ids, best_ids, MAX_POINTS}
};
LaneResult result;
size_t point_count;
LaneStatus status = lane_detect_rgb(&image, &mask, &config, &workspace,
                                   true, &result, &point_count);
```

O chamador reserva todos os buffers. RGB e máscara devem ter dimensões
iguais, com pelo menos `3 * width * height` e `width * height` bytes,
respectivamente, e não podem se sobrepor. Os dois buffers de índices
precisam da capacidade declarada e também não podem se sobrepor.
Falta de capacidade de pontos retorna `LANE_POINTS_CAPACITY_EXCEEDED`.
Após qualquer erro, os buffers não representam um resultado válido.

## Matriz e espessura

A máscara representa **uma faixa pintada ajustada**, não toda a área
trafegável da rodovia. Tem as dimensões originais do buffer RGB, um byte
por pixel e valores exatos `0/1`. O acesso é:

```c
uint8_t detected = mask.pixels[y * mask.width + x];
```

O modelo é `x(y) = a*y² + b*y + c`. Avaliamos esse polinômio em cada
linha inteira entre `y_min` e `y_max` dos inliers. A espessura padrão é
três pixels, alterável em `config.thickness`; aceitamos qualquer valor
positivo que caiba em `int`.

A espessura é **horizontal**: com 5, marcamos `x-2` até `x+2`; com 2,
marcamos `x` e `x+1`. A largura visível pode diminuir nas bordas devido
ao recorte. Essa mudança só altera a rasterização, não os coeficientes
ou os inliers do modelo. Os inliers são desenhados no debug, mas não
acrescentam pontos isolados à máscara final.

As coordenadas calculadas permanecem em `double`. A parábola pode
produzir valores negativos, enormes ou não finitos; verificamos e
recortamos esses valores **antes** de converter para um índice
`size_t`. Usar `double` não mantém a curva dentro da imagem: é o teste
de limites que impede o acesso fora do buffer.

Sem modelo, a matriz é zerada e o RGB de debug permanece sem marcações.

## Ajuste da curva

O filtro reproduz os intervalos RGB inclusivos do Python: branco entre
`(165,165,165)` e `(255,255,255)`, amarelo entre `(170,165,80)` e
`(240,205,170)`. A ROI tem os mesmos vértices proporcionais. As bordas
interpoladas por linha podem diferir da rasterização do OpenCV em um
pixel. Cada corrida horizontal gera um `Point` no seu centro, que pode
ser fracionário.

O ajuste normaliza a altura para `[-1,1]`, acumula somas escalares e
resolve um sistema fixo `3 × 3`, com pivotamento parcial. Não cria
matrizes de projeto `N × 3`. Amostras degeneradas são descartadas.

Cada tentativa do RANSAC sorteia três índices distintos, usando um
xorshift32 local. A mesma seed reproduz o resultado em C; o NumPy usa
outro gerador, então a mesma seed não produz as mesmas amostras.
O threshold da configuração está em pixels. Seu quadrado é calculado
uma única vez por chamada ao RANSAC, antes das tentativas; a comparação
interna é `dx² < threshold²`. Assim, `threshold = 2.0` aceita resíduos
horizontais estritamente menores que dois pixels. Priorizamos mais
inliers, usando menor MSE como desempate. Na referência Python, o
parâmetro `t` continua em pixels ao quadrado: para comparar as versões,
use `t = threshold * threshold`.

Como no Python, ajustamos uma vez sobre o consenso de cada tentativa,
sem reclassificar os pontos depois desse ajuste.

O resultado continua sendo **uma única parábola**. Na imagem
`solidWhiteCurve`, a marcação fica quase reta na maior parte visível e
muda de curvatura perto do horizonte. Uma única parábola e o limiar de
um pixel privilegiam
o trecho quase reto. Aumentar a espessura não recupera essa curvatura.
É possível testar `threshold = 2.0`, aceitando resíduos menores
que dois pixels; isso admite mais pontos, mas também aumenta a tolerância
a outliers e não garante reproduzir a mudança local de curvatura.

## Memória

Em `nios/entry.c`, todos os buffers são estáticos e reutilizados:

- RGB: `3 * width * height` bytes, reutilizado para o debug.
- Máscara: `width * height` bytes, reutilizada entre filtro, ROI e saída.
- Pontos: `LANE_MAX_POINTS * sizeof(Point)` bytes.
- Índices: `2 * LANE_MAX_POINTS * sizeof(size_t)` bytes.

O núcleo não aloca memória durante o processamento e reutiliza os mesmos
buffers de consenso. A configuração padrão de
320 × 180 e 4096 pontos usa aproximadamente 321 KiB nesses buffers
quando `double` tem 8 bytes e `size_t` tem 4 bytes, além de código, pilha
e estruturas pequenas. Escolha a memória e o tamanho reduzido de acordo
com o sistema configurado no BSP. O custo de `double` no Nios II ainda
precisa ser medido.

## Validação no computador

Compilador C11, `make` e biblioteca C/matemática padrão são suficientes
para compilar **todo o C**, incluindo a ferramenta host:

```bash
make -C nios_software
make -C nios_software host
```

O primeiro comando gera a biblioteca e compila as fontes da entrada
embarcada usando o compilador local; isso não é uma validação do BSP
nem uma execução na placa. Não é necessário `pkg-config` ou instalar
bibliotecas adicionais.

Prepare o RGB no computador com o OpenCV já usado pela referência:

```bash
mkdir -p nios_software/results
python3 nios_software/tools/prepare_rgb.py python/test_images/solidWhiteCurve.jpg nios_software/results/frame.rgb --width 320 --height 180
nios_software/build/lane_detect nios_software/results/frame.rgb 320 180 nios_software/results/frame --min-inliers 50 --seed 42 --thickness 7
```

O arquivo RGB não tem cabeçalho: contém bytes RGBRGB..., em linhas
consecutivas. O script também grava `frame.rgb.json` com as dimensões.
Na CLI, os parâmetros opcionais são:

```text
--iterations N   tentativas RANSAC (padrão 1000)
--threshold T    limiar horizontal em pixels (padrão 1.0)
--min-inliers M  mínimo de inliers (padrão 50, pelo menos 3)
--seed S         seed de 32 bits (padrão 42, inclusive zero)
--thickness E    espessura horizontal em pixels (padrão 3)
```

O prefixo de saída pode incluir um diretório, que deve existir. Saídas
com o mesmo prefixo são sobrescritas:

| Sufixo | Conteúdo |
| --- | --- |
| `_mask.bin` | Matriz `height × width`, sem cabeçalho, valores `0/1` |
| `_debug.ppm` | Imagem RGB de debug em PPM P6, gravada diretamente em C |
| `_model.json` | Dimensões, espessura, seed, coeficientes, inliers e MSE |

PPM contém apenas um cabeçalho textual e os bytes RGB, sem codec.
Se quiser visualizar o debug em JPEG, converta no computador:

```bash
python3 nios_software/tools/debug_to_jpg.py nios_software/results/frame_debug.ppm nios_software/results/frame_debug.jpg
```

Para gerar o exemplo nas dimensões originais da imagem, com espessura 7:

```bash
python3 nios_software/tools/prepare_rgb.py python/test_images/solidWhiteCurve.jpg nios_software/results/solidWhiteCurve.rgb
nios_software/build/lane_detect nios_software/results/solidWhiteCurve.rgb 960 540 nios_software/results/solidWhiteCurve_thickness7 --thickness 7
python3 nios_software/tools/debug_to_jpg.py nios_software/results/solidWhiteCurve_thickness7_debug.ppm nios_software/results/solidWhiteCurve_thickness7_debug.jpg
```

Os scripts Python e a suíte de integração dependem de NumPy/OpenCV
somente no computador; o executável C e a aplicação Nios II não.

## Testes

```bash
make -C nios_software test
make -C nios_software integration
make -C nios_software sanitize SANITIZERS=undefined
```

Os testes cobrem filtro, ROI, degeneração, consenso, determinismo,
espessuras pares/ímpares, recorte, resultados negativos/enormes/não
finitos e a função embarcada com os próprios buffers estáticos.
A integração converte as seis imagens JPEG para RGB, valida as saídas,
compara pontos com o Python, testa uma parábola conhecida e erros de
dimensão, arquivo e argumentos. O build usa `-Wall -Wextra -Wpedantic -Werror`.

O alvo `sanitize` também permite `SANITIZERS=address,undefined`. O
AddressSanitizer do compilador Apple ficou preso na inicialização do
runtime neste computador, antes de `main`; sua validação está pendente.
Depois da instrumentação, use `make clean` seguido de `make host` dentro
de `nios_software/` para
voltar ao binário normal.
