"""
Deteccao de faixa de rodovia via extracao de bordas (Canny) + RANSAC.

Pipeline:
    imagem (BGR) -> escala de cinza -> bordas (Canny) -> ROI (remove
    ceu/horizonte/fundo) -> nuvem de pontos (x, y) -> RANSAC (ajuste de
    reta y = m*x + b) -> imagem original com a faixa marcada em
    vermelho, restrita ao trecho coberto pelos pontos inliers.

Uso:
    python ransac.py caminho/da/imagem.jpg

O resultado eh salvo em test_images/results/<nome_imagem>_result_<timestamp>.png
"""

import argparse
from copy import copy
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from numpy.random import default_rng
from time import perf_counter
import sys
from contextlib import redirect_stdout
from statistics import mean

SEED = 42
RED = (0, 0, 255)
RESULT_PATH = Path("test_images/results")

DEFAULT_K = 3000
DEFAULT_D = 200
DEFAULT_N = None

# ----------------------------------------------------------------------
# 0. Documenta terminal
# ----------------------------------------------------------------------
class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()

# ----------------------------------------------------------------------
# 1. Extracao de bordas (Canny) e conversao para nuvem de pontos
# ----------------------------------------------------------------------
def extract_edges(gray, canny_low=50, canny_high=150):
    """Aplica Canny e retorna a mascara binaria de bordas (mesma
    resolucao da imagem de entrada)."""
    return cv2.Canny(gray, canny_low, canny_high)


def edges_to_points(edges):
    """Converte uma mascara binaria de bordas num array (N, 2) de
    coordenadas (x, y) dos pixels de borda."""
    ys, xs = np.nonzero(edges)
    return np.column_stack([xs, ys]).astype(np.float64)


# ----------------------------------------------------------------------
# 1b. Region of interest (ROI)
# ----------------------------------------------------------------------
def default_roi_vertices(w, h):
    """Vertices de um trapezio cobrindo a parte inferior da imagem: da
    altura h*0.55 ate a base, estreitando nas laterais. Representa a
    regiao da pista. Tudo FORA desse trapezio (ceu, horizonte,
    arvores, muros ao fundo) fica fora do ROI."""
    return np.array([[
        (int(0.02 * w), h - 1),
        (int(0.40 * w), int(0.55 * h)),
        (int(0.60 * w), int(0.55 * h)),
        (int(0.98 * w), h - 1),
    ]], dtype=np.int32)


def apply_roi(edges, vertices):
    """Zera todo pixel de 'edges' que esta FORA do poligono 'vertices'.
    So o que sobra dentro do poligono alimenta o RANSAC."""
    mask = np.zeros_like(edges)
    cv2.fillPoly(mask, vertices, 255)
    return cv2.bitwise_and(edges, mask)


# ----------------------------------------------------------------------
# 2. Modelo de regressao linear (y = m*x + b)
# ----------------------------------------------------------------------
class LinearRegressor:
    def __init__(self):
        self.params = None
        self.m = self.b = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        rows = X.shape[0]
        X = np.hstack([np.ones((rows, 1)), X])
        # Rejeita amostras em que nao eh possivel estimar uma reta
        # Ex: quando os 2 pontos sorteados possuem exatamente o mesmo x
        if np.linalg.matrix_rank(X) < X.shape[1]:
            raise ValueError("Nao foi possivel estimar uma reta a partir da amostra")
        self.params = np.linalg.inv(X.T @ X) @ X.T @ y
        self.b = self.params[0]
        self.m = self.params[1]
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        rows = X.shape[0]
        X = np.hstack([np.ones((rows, 1)), X])
        return X @ self.params

    def angle_deg(self):
        """Inclinacao da reta em relacao a horizontal, em graus.
        0 = horizontal, 90 = vertical."""
        slope = self.params[1]
        return np.degrees(np.arctan(abs(slope)))

    def segment_from_inliers(self, inlier_points):
        """
        Retorna o segmento entre o menor e o maior x dos pontos inliers.
        Nao extrapola alem da evidencia encontrada pelo RANSAC.
        """
        x_min = np.min(inlier_points[:, 0])
        x_max = np.max(inlier_points[:, 0])
        y_min = self.predict(np.array([[x_min]]))[0]
        y_max = self.predict(np.array([[x_max]]))[0]
        return (x_min, y_min), (x_max, y_max)


# ----------------------------------------------------------------------
# 2b. Funcoes de perda e metrica
# ----------------------------------------------------------------------
def square_error_loss(y_true, y_pred):
    return (y_true - y_pred) ** 2


def mean_square_error(y_true, y_pred):
    return np.sum(square_error_loss(y_true, y_pred)) / y_true.shape[0]


# ----------------------------------------------------------------------
# 3. RANSAC (adaptado do esqueleto da Wikipedia para pontos 2D)
#    https://en.wikipedia.org/wiki/Random_sample_consensus
# ----------------------------------------------------------------------
class RANSAC:
    def __init__(self,n=2,k=100,t=0.5,d=50,model=None,filter=None,loss=None,metric=None,seed=SEED):
        self.n = n            # pontos minimos para instanciar o modelo (2 para reta)
        self.k = k            # numero maximo de iteracoes
        self.t = t            # limiar de distancia (px) para considerar inlier
        self.d = d            # minimo de inliers para o modelo ser considerado valido
        self.model = model    # modelo para explicar os pontos observados
        self.filter = filter  # descarta modelos implausiveis (ex: quase horizontais)
        self.loss = loss      # funcao de perda para avaliar a qualidade do modelo 
        self.metric = metric  # metrica para avaliar a qualidade do modelo
        self.seed = seed      # fixa o resultado entre execucoes
        self.best_fit = None
        self.best_inliers = None
        self.best_score = -1
        self.best_error = np.inf

    def fit(self, X, y):
        rng = default_rng(self.seed)
        X = np.asarray(X)
        y = np.asarray(y)
        n_points = X.shape[0]

        tAmostragem = 0;
        tEstimativaModelo = 0;
        tAvaliacaoConsenso = 0;
        tRefinamento = 0;
        tCalculoErro = 0;
        tSelecaoMelhorModelo = 0;

        if n_points < self.n:
            return self
        
        for _ in range(self.k):

            t0 = perf_counter(); # Amostragem
            ids = rng.permutation(n_points)
            sample_ids = ids[: self.n]
            rest_ids = ids[self.n :]

            tAmostragem += perf_counter() - t0

            t1 = perf_counter(); # Estimativa do modelo candidato
            try:
                maybe_model = copy(self.model).fit(
                    X[sample_ids], y[sample_ids]
                )
            except (np.linalg.LinAlgError, ValueError):
                tEstimativaModelo += perf_counter() - t1
                continue  # amostra nao permite estimar uma reta

            if self.filter and not self.filter(maybe_model):
                tEstimativaModelo += perf_counter() - t1
                continue  # descarta modelos sem calcular inliers

            tEstimativaModelo += perf_counter() - t1

            t2 = perf_counter(); # Avaliação de consenso
            predictions = maybe_model.predict(X[rest_ids])
            residuals = self.loss(y[rest_ids], predictions)
            inlier_ids = rest_ids[residuals < self.t]

            if inlier_ids.size + self.n < self.d:
                tAvaliacaoConsenso += perf_counter() - t2
                continue

            all_ids = np.concatenate([sample_ids, inlier_ids])
            
            tAvaliacaoConsenso += perf_counter() - t2

            t3 = perf_counter(); # Refinamento
            try:
                refined_model = copy(self.model).fit(X[all_ids], y[all_ids])
            except (np.linalg.LinAlgError, ValueError):
                tRefinamento += perf_counter() - t3
                continue

            if self.filter and not self.filter(refined_model):
                tRefinamento += perf_counter() - t3
                continue  # refit pode puxar angulo pra fora da faixa aceita pelo filter

            tRefinamento += perf_counter() - t3

            t4 = perf_counter(); # Calculo de erro
            this_error = self.metric(y[all_ids], refined_model.predict(X[all_ids]))
            # Primeiro prioriza quantidade de inliers
            # empate -> escolhe o modelo com menor erro
            
            tCalculoErro += perf_counter() - t4

            t5 = perf_counter(); # Escolha melhor modelo
            if (
                all_ids.size > self.best_score
                or (
                    all_ids.size == self.best_score
                    and this_error < self.best_error
                )
            ):
                self.best_score = all_ids.size
                self.best_error = this_error
                self.best_fit = refined_model
                self.best_inliers = all_ids

            tSelecaoMelhorModelo += perf_counter() - t5

        self.profile = {
            "Amostragem": tAmostragem * 1000,
            "Estimativa do modelo": tEstimativaModelo * 1000,
            "Avaliacao de consenso": tAvaliacaoConsenso * 1000,
            "Refinamento": tRefinamento * 1000,
            "Calculo do erro": tCalculoErro * 1000,
            "Selecao do melhor modelo": tSelecaoMelhorModelo * 1000,
            "K": self.k,
            "T": self.t,
            "D": self.d,
        }

        return self

    def predict(self, X):
        return self.best_fit.predict(X)


# ----------------------------------------------------------------------
# 4. Pipeline completo
# ----------------------------------------------------------------------
def detect_lane(
        image_path, out_path, method_canny=(50, 150), ransac_k=100,
        ransac_t=0.5, ransac_d=50, ransac_seed=SEED, loss=square_error_loss,
        metric=mean_square_error, min_angle_deg=15, max_angle_deg=89, 
        max_points=None
    ):

    profile = {}

    t0 = perf_counter()
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Nao foi possivel abrir '{image_path}'")
    h, w = image_bgr.shape[:2]
    t1 = perf_counter()
    profile["Carregamento imagem"] = (t1 - t0) * 1000

    t0 = perf_counter()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    t1 = perf_counter()
    profile["Conversao GRAYSCALE"] = (t1 - t0) * 1000

    t0 = perf_counter()
    edges = extract_edges(gray, *method_canny)
    edges = apply_roi(edges, default_roi_vertices(w, h))
    points = edges_to_points(edges)
    if max_points is not None and max_points < points.shape[0]:
        rng_points = default_rng(SEED)

        selected_ids = rng_points.choice(
            points.shape[0],
            size=max_points,
            replace=False
        )

        points = points[selected_ids]
    X, y = points[:, [0]], points[:, 1]

    model_filter = lambda m: min_angle_deg <= m.angle_deg() <= max_angle_deg
    t1 = perf_counter()
    profile["Extracao de pontos"] = (t1 - t0) * 1000
    profile["N"] = points.shape[0]

    t0 = perf_counter()
    ransac = RANSAC(
        k=ransac_k, t=ransac_t, d=ransac_d, model=LinearRegressor(),
        filter=model_filter, seed=ransac_seed, loss=loss, metric=metric
    )
    ransac.fit(X, y)
    t1 = perf_counter()
    profile.update(ransac.profile)
    profile["RANSAC TOTAL"] = (t1 - t0) * 1000

    t0 = perf_counter()
    if ransac.best_fit is None:
        print(f"Nenhuma faixa identificada em '{image_path}'")
        cv2.imwrite(str(out_path), image_bgr)
        return
    t1 = perf_counter()
    profile["Geracao resultado"] = (t1 - t0) * 1000

    t0 = perf_counter()
    inliers = points[ransac.best_inliers]
    p1, p2 = ransac.best_fit.segment_from_inliers(inliers)

    result = image_bgr.copy()
    for x_values, y_values in inliers:
        cv2.circle(result, (int(round(x_values)), int(round(y_values))), 1, RED, -1)
    cv2.line(result, tuple(map(round, p1)), tuple(map(round, p2)), RED, thickness=3)
    t1 = perf_counter()
    profile["Geracao imagem resultado"] = (t1 - t0) * 1000


    t0 = perf_counter()
    best_model = ransac.best_fit
    print(
        f"Faixa detectada: y = {best_model.m:.4f}*x + {best_model.b:.4f} "
        f"({ransac.best_score}/{points.shape[0]} inliers)"
    )
    cv2.imwrite(str(out_path), result)
    t1 = perf_counter()
    profile["Exibicao e salvamento do resultado"] = (t1 - t0) * 1000

    return profile

def imprimir_log(titulo, resultado):

    print(f"\n==== {titulo} ====")
    print(f"=> Pipeline ")
    print(f"Carregamento imagem: {resultado['Carregamento imagem']:.3f} ms")
    print(f"Conversao GRAYSCALE: {resultado['Conversao GRAYSCALE']:.3f} ms")
    print(f"Extracao de pontos: {resultado['Extracao de pontos']:.3f} ms")
    
    print(f"\n=> Parametros")
    print(f"Iterações (k): {resultado['K']}")
    print(f"Threshold (t): {resultado['T']}")
    print(f"Inliers (d): {resultado['D']}")
    print(f"Quantidade de pontos (n): {resultado['N']}")

    print(f"\n=> RANSAC")
    print(f"Amostragem: {resultado['Amostragem']:.3f} ms")
    print(f"Estimativa do modelo: {resultado['Estimativa do modelo']:.3f} ms")
    print(f"Avaliacao de consenso: {resultado['Avaliacao de consenso']:.3f} ms")
    print(f"Refinamento: {resultado['Refinamento']:.3f} ms")
    print(f"Calculo do erro: {resultado['Calculo do erro']:.3f} ms")
    print(f"Selecao do melhor modelo: {resultado['Selecao do melhor modelo']:.3f} ms")
    print(f"RANSAC TOTAL: {resultado['RANSAC TOTAL']:.3f} ms")

    print(f"\n=> Pos processamento")
    print(f"Geracao resultado: {resultado['Geracao resultado']:.3f} ms")
    print(f"Geracao imagem resultado: {resultado['Geracao imagem resultado']:.3f} ms")
    print(f"Exibicao e salvamento do resultado: {resultado['Exibicao e salvamento do resultado']:.3f} ms")
    print(f"\nPIPELINE TOTAL: {resultado['PIPELINE TOTAL']:.3f} ms")

def exec_media(k, d, n, repeticoes):

    result_list = []
    for i in range(repeticoes):
        t0 = perf_counter()
        result = detect_lane(input_image, output_path, ransac_k=k, ransac_t=1.0, ransac_d=d, max_points=n)
        t1 = perf_counter()
        result["PIPELINE TOTAL"] = (t1 - t0) * 1000
        result_list.append(result)

    profiling = {
        "Carregamento imagem": mean(
            result["Carregamento imagem"]
            for result in result_list
        ),
        "Conversao GRAYSCALE": mean(
            result["Conversao GRAYSCALE"]
            for result in result_list
        ),
        "Extracao de pontos": mean(
            result["Extracao de pontos"]
            for result in result_list
        ),
        "K": k,
        "T": mean(
            result["T"]
            for result in result_list
        ),
        "D": d,
        "N": result["N"],
        "Amostragem": mean(
            result["Amostragem"]
            for result in result_list
        ),
        "Estimativa do modelo": mean(
            result["Estimativa do modelo"]
            for result in result_list
        ),
        "Avaliacao de consenso": mean(
            result["Avaliacao de consenso"]
            for result in result_list
        ),
        "Refinamento": mean(
            result["Refinamento"]
            for result in result_list
        ),
        "Calculo do erro": mean(
            result["Calculo do erro"]
            for result in result_list
        ),
        "Selecao do melhor modelo": mean(
            result["Selecao do melhor modelo"]
            for result in result_list
        ),
        "RANSAC TOTAL": mean(
            result["RANSAC TOTAL"]
            for result in result_list
        ),
        "Geracao resultado": mean(
            result["Geracao resultado"]
            for result in result_list
        ),
        "Geracao imagem resultado": mean(
            result["Geracao imagem resultado"]
            for result in result_list
        ),
        "Exibicao e salvamento do resultado": mean(
            result["Exibicao e salvamento do resultado"]
            for result in result_list
        ),
        "PIPELINE TOTAL": mean(
            result["PIPELINE TOTAL"]
            for result in result_list
        ),
    }

    imprimir_log(f"MEDIA {repeticoes} repeticoes (K = {k} | N = {n} | D = {d})", profiling)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deteccao de faixa via bordas + RANSAC")
    parser.add_argument("image", help="Caminho da imagem de entrada")
    args = parser.parse_args()

    input_image = Path(args.image)

    # Diretório python/profiling, independente de onde o script foi executado
    script_dir = Path(__file__).resolve().parent
    profiling_dir = script_dir / "profiling"
    profiling_dir.mkdir(parents=True, exist_ok=True)
    profiling_path = profiling_dir / f"{input_image.stem}.txt" # Nome do arquivo de profiling

    with open(profiling_path, "w", encoding="utf-8") as log_file:
        tee = Tee(sys.stdout, log_file)
        
        with redirect_stdout(tee):

            print(f"==== INICIO PREPARACAO DA EXECUCAO ==== ")
            t0 = perf_counter()
            timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
            output_path = Path(RESULT_PATH)
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / f"{input_image.stem}_result_{timestamp}{input_image.suffix}"
            t1 = perf_counter()
            print(f"Tempo PREPARACAO DA EXECUCAO : {(t1 - t0) * 1000:.3f} ms")

            default_k = 3000
            default_d = 200

            t0 = perf_counter()
            profiling = detect_lane(input_image, output_path, ransac_k=default_k, ransac_t=1.0, ransac_d=default_d, max_points=None)
            t1 = perf_counter()
            profiling["PIPELINE TOTAL"] = (t1 - t0) * 1000

            default_n = profiling["N"]

            imprimir_log(f"Cenário padrão (K = 3000 | N = {default_n} | D = 200)", profiling)

            exec_media(k=1500, d=default_d, n=None, repeticoes=10)
            exec_media(k=6000, d=default_d, n=None, repeticoes=10)
            exec_media(k=9000, d=default_d, n=None, repeticoes=10)

            n = round(default_n*0.25)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

            n = round(default_n*0.5)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

            n = round(default_n*0.75)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

