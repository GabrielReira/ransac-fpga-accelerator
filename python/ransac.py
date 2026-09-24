"""
Deteccao de faixa de rodovia via extracao de bordas (Canny) + RANSAC.

Pipeline:
    imagem (BGR) -> escala de cinza -> bordas (Canny) -> ROI (remove
    ceu/horizonte/fundo) -> nuvem de pontos (x, y) -> RANSAC (ajuste de
    reta a*x + b*y + c = 0) -> imagem original com a faixa marcada em
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
# 2. Modelo geometrico de reta: a*x + b*y + c = 0  (a^2 + b^2 = 1)
#    Ajuste por minimos quadrados totais (TLS via SVD) -> funciona
#    tambem para retas verticais, ao contrario de y = b0 + b1*x.
# ----------------------------------------------------------------------
class LineModel:
    def __init__(self):
        self.a = self.b = self.c = None
        self.point = None       # um ponto sobre a reta (centroide do ajuste)
        self.direction = None   # vetor unitario na direcao da reta

    def fit(self, points):
        centroid = points.mean(axis=0)
        _, _, vt = np.linalg.svd(points - centroid)
        direction = vt[0]
        normal = np.array([-direction[1], direction[0]])
        self.a, self.b = normal / np.linalg.norm(normal)
        self.c = -(self.a * centroid[0] + self.b * centroid[1])
        self.point = centroid
        self.direction = direction
        return self

    def distance(self, points):
        return np.abs(points @ np.array([self.a, self.b]) + self.c)

    def angle_deg(self):
        """Inclinacao da reta em relacao a horizontal, em graus.
        0 = horizontal (ex: horizonte); 90 = vertical."""
        return np.degrees(np.arctan2(abs(self.a), abs(self.b) + 1e-12))

    def segment_from_inliers(self, inlier_points):
        """Extremos do segmento coberto pelos proprios pontos inliers
        (projecao sobre a direcao da reta) -- nao extrapola alem do
        que foi realmente detectado."""
        t = (inlier_points - self.point) @ self.direction
        return self.point + t.min() * self.direction, self.point + t.max() * self.direction


# ----------------------------------------------------------------------
# 3. RANSAC (adaptado do esqueleto da Wikipedia para pontos 2D)
#    https://en.wikipedia.org/wiki/Random_sample_consensus
# ----------------------------------------------------------------------
class RANSAC:
    def __init__(self, n=2, k=100, t=0.05, d=50, model=None, filter=None, seed=SEED):
        self.n = n            # pontos minimos para instanciar o modelo (2 para reta)
        self.k = k            # numero maximo de iteracoes
        self.t = t            # limiar de distancia (px) para considerar inlier
        self.d = d            # minimo de inliers para o modelo ser considerado valido
        self.model = model    # modelo para explicar os pontos observados
        self.filter = filter  # descarta modelos implausiveis (ex: quase horizontais)
        self.seed = seed      # fixa o resultado entre execucoes
        self.best_fit = None
        self.best_inliers = None
        self.best_score = -1

    def fit(self, points):
        rng = default_rng(self.seed)
        n_points = points.shape[0]
        if n_points < self.n:
            return self

        for _ in range(self.k):
            ids = rng.permutation(n_points)
            sample_ids, rest_ids = ids[: self.n], ids[self.n:]

            maybe_model = copy(self.model).fit(points[sample_ids])
            if self.filter and not self.filter(maybe_model):
                continue  # descarta modelos sem calcular inliers

            inlier_ids = rest_ids[maybe_model.distance(points[rest_ids]) < self.t]
            if inlier_ids.size + self.n < self.d:
                continue

            all_ids = np.concatenate([sample_ids, inlier_ids])
            refined_model = copy(self.model).fit(points[all_ids])
            if self.filter and not self.filter(refined_model):
                continue  # refit pode puxar angulo pra fora da faixa aceita pelo filter

            if all_ids.size > self.best_score:
                self.best_score = all_ids.size
                self.best_fit = refined_model
                self.best_inliers = all_ids

        return self


# ----------------------------------------------------------------------
# 4. Pipeline completo
# ----------------------------------------------------------------------
def detect_lane(
        image_path, out_path, method_canny=(50, 150), ransac_k=100, ransac_t=0.05,
        ransac_d=50, ransac_seed=SEED, min_angle_deg=15, max_angle_deg=90
    ):
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Nao foi possivel abrir '{image_path}'")
    h, w = image_bgr.shape[:2]

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = extract_edges(gray, *method_canny)
    edges = apply_roi(edges, default_roi_vertices(w, h))
    points = edges_to_points(edges)

    model_filter = lambda m: min_angle_deg <= m.angle_deg() <= max_angle_deg
    ransac = RANSAC(
        k=ransac_k, t=ransac_t, d=ransac_d, model=LineModel(),
        filter=model_filter, seed=ransac_seed
    )
    ransac.fit(points)

    if ransac.best_fit is None:
        print(f"Nenhuma faixa identificada em '{image_path}'")
        cv2.imwrite(str(out_path), image_bgr)
        return

    inliers = points[ransac.best_inliers]
    p1, p2 = ransac.best_fit.segment_from_inliers(inliers)

    result = image_bgr.copy()
    for x, y in inliers:
        cv2.circle(result, (int(round(x)), int(round(y))), 1, RED, -1)
    cv2.line(result, tuple(map(round, p1)), tuple(map(round, p2)), RED, thickness=3)

    m = ransac.best_fit
    print(
        f"Faixa detectada: {m.a:.4f}*x + {m.b:.4f}*y + {m.c:.4f} = 0\n"
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

    detect_lane(input_image, output_path, ransac_k=5000, ransac_t=0.1, ransac_d=60)
