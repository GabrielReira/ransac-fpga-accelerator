"""
Deteccao de faixa de rodovia via extracao de bordas (Canny) + RANSAC.

Pipeline:
    imagem (RGB) -> escala de cinza -> bordas (Canny) -> ROI (remove
    ceu/horizonte/fundo) -> nuvem de pontos (x, y) -> RANSAC (ajuste de
    curva x = a*y^2 + b*y + c) -> imagem original com a faixa marcada em
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

SEED = 42
RED = (0, 0, 255)
RESULT_PATH = Path("test_images/results")


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
# 2. Modelo quadrático de regressão (x = a*y^2 + b*y + c)
# ----------------------------------------------------------------------
class PolynomialRegressor:
    degree = 2

    def __init__(self):
        self.params = None
        self.a = self.b = self.c = None
        self.y_min = self.y_max = None

    def _design_matrix(self, y):
        y = np.asarray(y, dtype=np.float64).reshape(-1)
        return np.column_stack([y ** 2, y, np.ones_like(y)])

    def fit(self, X, y):
        y_values = np.asarray(X, dtype=np.float64).reshape(-1)
        x_values = np.asarray(y, dtype=np.float64).reshape(-1)
        design = self._design_matrix(y_values)
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise ValueError("Nao foi possivel estimar uma parábola a partir da amostra")
        self.params = np.linalg.lstsq(design, x_values, rcond=None)[0]
        self.a, self.b, self.c = self.params
        self.y_min = float(np.min(y_values))
        self.y_max = float(np.max(y_values))
        return self

    def predict(self, X):
        return self._design_matrix(X) @ self.params

    def curve_from_inliers(self, inlier_points, samples=100):
        """Retorna pixels da curva entre o menor e o maior y dos pontos inliers."""
        y_min = np.min(inlier_points[:, 1])
        y_max = np.max(inlier_points[:, 1])
        y_values = np.linspace(y_min, y_max, samples)
        x_values = self.predict(y_values)
        return np.column_stack([x_values, y_values])


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
    def __init__(self,n=2,k=100,t=0.5,d=50,model=None,loss=None,metric=None,seed=SEED):
        self.n = n            # pontos minimos para instanciar o modelo (2 para reta)
        self.k = k            # numero maximo de iteracoes
        self.t = t            # limiar de distancia (px) para considerar inlier
        self.d = d            # minimo de inliers para o modelo ser considerado valido
        self.model = model    # modelo para explicar os pontos observados
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

        if n_points < self.n:
            return self

        for _ in range(self.k):
            ids = rng.permutation(n_points)
            sample_ids = ids[: self.n]
            rest_ids = ids[self.n :]

            try:
                maybe_model = copy(self.model).fit(
                    X[sample_ids], y[sample_ids]
                )
            except (np.linalg.LinAlgError, ValueError):
                continue  # amostra nao permite estimar uma parábola

            predictions = maybe_model.predict(X[rest_ids])
            residuals = self.loss(y[rest_ids], predictions)
            inlier_ids = rest_ids[residuals < self.t]
            if inlier_ids.size + self.n < self.d:
                continue

            all_ids = np.concatenate([sample_ids, inlier_ids])
            try:
                refined_model = copy(self.model).fit(X[all_ids], y[all_ids])
            except (np.linalg.LinAlgError, ValueError):
                continue

            this_error = self.metric(y[all_ids], refined_model.predict(X[all_ids]))
            # Primeiro prioriza quantidade de inliers
            # empate -> escolhe o modelo com menor erro
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

        return self

    def predict(self, X):
        return self.best_fit.predict(X)


# ----------------------------------------------------------------------
# 4. Pipeline completo
# ----------------------------------------------------------------------
def detect_lane(
        image_path, out_path, method_canny=(50, 150), ransac_k=100,
        ransac_t=0.5, ransac_d=50, ransac_seed=SEED, 
        loss=square_error_loss, metric=mean_square_error
    ):
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Nao foi possivel abrir '{image_path}'")
    h, w = image_bgr.shape[:2]

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = extract_edges(gray, *method_canny)
    edges = apply_roi(edges, default_roi_vertices(w, h))
    points = edges_to_points(edges)
    X, y = points[:, [1]], points[:, 0]  # X é o eixo vertical (y)

    ransac = RANSAC(
        n = PolynomialRegressor.degree + 1,  # minimo de pontos para instanciar o modelo
        k=ransac_k, t=ransac_t, d=ransac_d, model=PolynomialRegressor(),
        seed=ransac_seed, loss=loss, metric=metric
    )
    ransac.fit(X, y)

    if ransac.best_fit is None:
        print(f"Nenhuma faixa identificada em '{image_path}'")
        cv2.imwrite(str(out_path), image_bgr)
        return

    inliers = points[ransac.best_inliers]
    curve = ransac.best_fit.curve_from_inliers(inliers)

    result = image_bgr.copy()
    for x_values, y_values in inliers:
        cv2.circle(result, (int(round(x_values)), int(round(y_values))), 1, RED, -1)
    curve = np.rint(curve).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(result, [curve], isClosed=False, color=RED, thickness=3)

    best_model = ransac.best_fit
    print(
        f"Faixa detectada: x = {best_model.a:.4f}*y^2 + "
        f"{best_model.b:.4f}*y + {best_model.c:.4f}\n"
        f"({ransac.best_score}/{points.shape[0]} inliers)"
    )
    cv2.imwrite(str(out_path), result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deteccao de faixa via bordas + RANSAC")
    parser.add_argument("image", help="Caminho da imagem de entrada")
    args = parser.parse_args()

    input_image = Path(args.image)
    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    output_path = Path(RESULT_PATH)
    output_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path / f"{input_image.stem}_result_{timestamp}{input_image.suffix}"

    detect_lane(input_image, output_path, ransac_k=10000, ransac_t=0.3, ransac_d=200)
