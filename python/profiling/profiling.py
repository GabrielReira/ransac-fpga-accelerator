
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ransac import (
    RED,
    SEED,
    PolynomialRegressor,
    apply_roi,
    default_roi_vertices,
    extract_paint_mask,
    mask_to_points,
    mean_square_error,
    square_error_loss,
)

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

        tAmostragem = 0;
        tEstimativaModelo = 0;
        tAvaliacaoConsenso = 0;
        tRefinamento = 0;
        tCalculoErro = 0;
        tSelecaoMelhorModelo = 0;

        iterations = self.k if n_points >= self.n else 0
        for _ in range(iterations):

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
        image_path, out_path, ransac_k=100,
        ransac_t=0.5, ransac_d=50, ransac_seed=SEED, loss=square_error_loss,
        metric=mean_square_error,
        max_points=None
    ):

    profile = {}

    t0 = perf_counter()
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Nao foi possivel abrir {image_path}")
    h, w = image_bgr.shape[:2]
    t1 = perf_counter()
    profile["Carregamento imagem"] = (t1 - t0) * 1000

    t0 = perf_counter()
    paint_mask = extract_paint_mask(image_bgr)
    profile["Mascara de tinta"] = (perf_counter() - t0) * 1000

    t0 = perf_counter()
    roi_mask = apply_roi(paint_mask, default_roi_vertices(w, h))
    points = mask_to_points(roi_mask)

    if max_points is not None and max_points < points.shape[0]:
        rng_points = default_rng(SEED)

        selected_ids = rng_points.choice(
            points.shape[0],
            size=max_points,
            replace=False
        )

        points = points[selected_ids]
    X, y = points[:, [1]], points[:, 0]

    t1 = perf_counter()
    profile["Extracao de pontos"] = (t1 - t0) * 1000
    profile["N"] = points.shape[0]

    t0 = perf_counter()
    ransac = RANSAC(
        n=PolynomialRegressor.degree + 1, k=ransac_k, t=ransac_t, d=ransac_d,
        model=PolynomialRegressor(), seed=ransac_seed, loss=loss, metric=metric,
    )
    ransac.fit(X, y)
    t1 = perf_counter()
    profile.update(ransac.profile)
    profile["RANSAC TOTAL"] = (t1 - t0) * 1000

    t0 = perf_counter()
    best_model = ransac.best_fit
    if best_model is not None:
        inliers = points[ransac.best_inliers]
        curve = best_model.curve_from_inliers(inliers)
    profile["Geracao resultado"] = (perf_counter() - t0) * 1000

    result = image_bgr
    profile["Geracao imagem resultado"] = 0.0
    if best_model is not None:
        t0 = perf_counter()
        result = image_bgr.copy()
        for x_values, y_values in inliers:
            cv2.circle(result, (int(round(x_values)), int(round(y_values))), 1, RED, -1)
        curve = np.rint(curve).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(result, [curve], isClosed=False, color=RED, thickness=3)
        profile["Geracao imagem resultado"] = (perf_counter() - t0) * 1000

    t0 = perf_counter()
    if best_model is None:
        print(f"Nenhuma faixa identificada em '{image_path}'")
    else:
        print(
            f"Faixa detectada: x = {best_model.a:.4f}*y^2 + "
            f"{best_model.b:.4f}*y + {best_model.c:.4f} "
            f"({ransac.best_score}/{points.shape[0]} inliers)"
        )
    cv2.imwrite(str(out_path), result)
    profile["Exibicao e salvamento do resultado"] = (perf_counter() - t0) * 1000

    return profile

def imprimir_log(titulo, resultado):

    print(f"\n==== {titulo} ====")
    print(f"=> Pipeline ")
    print(f"Carregamento imagem: {resultado['Carregamento imagem']:.3f} ms")
    print(f"Mascara de tinta: {resultado['Mascara de tinta']:.3f} ms")
    print(f"Extracao de pontos: {resultado['Extracao de pontos']:.3f} ms")
    
    print(f"\n=> Parametros")
    print(f"Iterações (k): {resultado['K']}")
    print(f"Threshold (t): {resultado['T']}")
    print(f"Inliers (d): {resultado['D']}")
    print(f"Quantidade de pontos (n): {resultado['N']}")

    print(f"\n=> RANSAC")
    print(f"Amostragem: {resultado['Amostragem']:.3f} ms - {(resultado['Amostragem']*100/resultado['RANSAC TOTAL']):.3f}%")
    print(f"Estimativa do modelo: {resultado['Estimativa do modelo']:.3f} ms - {(resultado['Estimativa do modelo']*100/resultado['RANSAC TOTAL']):.3f}%")
    print(f"Avaliacao de consenso: {resultado['Avaliacao de consenso']:.3f} ms - {(resultado['Avaliacao de consenso']*100/resultado['RANSAC TOTAL']):.3f}%")
    print(f"Refinamento: {resultado['Refinamento']:.3f} ms - {(resultado['Refinamento']*100/resultado['RANSAC TOTAL']):.3f}%")
    print(f"Calculo do erro: {resultado['Calculo do erro']:.3f} ms - {(resultado['Calculo do erro']*100/resultado['RANSAC TOTAL']):.3f}%")
    print(f"Selecao do melhor modelo: {resultado['Selecao do melhor modelo']:.3f} ms - {(resultado['Selecao do melhor modelo']*100/resultado['RANSAC TOTAL']):.3f}%")
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
        "Mascara de tinta": mean(
            result["Mascara de tinta"]
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
    parser = argparse.ArgumentParser(description="Deteccao de faixa via filtro de cor + RANSAC")
    parser.add_argument("image", help="Caminho da imagem de entrada")
    args = parser.parse_args()

    input_image = Path(args.image).resolve()

    # Diretório python/profiling, independente de onde o script foi executado
    script_dir = Path(__file__).resolve().parent
    profiling_dir = script_dir / "results"
    profiling_dir.mkdir(parents=True, exist_ok=True)
    profiling_path = profiling_dir / f"{input_image.stem}.txt" # Nome do arquivo de profiling

    with open(profiling_path, "w", encoding="utf-8") as log_file:
        tee = Tee(sys.stdout, log_file)
        
        with redirect_stdout(tee):

            print(f"==== INICIO PREPARACAO DA EXECUCAO ==== ")
            t0 = perf_counter()
            timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
            output_path = script_dir.parent / "test_images" / "profiling" / "results"
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / f"{input_image.stem}_result_{timestamp}{input_image.suffix}"
            t1 = perf_counter()
            print(f"Tempo PREPARACAO DA EXECUCAO : {(t1 - t0) * 1000:.3f} ms")

            default_k = 3000
            default_d = 50

            t0 = perf_counter()
            profiling = detect_lane(input_image, output_path, ransac_k=default_k, ransac_t=1.0, ransac_d=default_d, max_points=None)
            t1 = perf_counter()
            profiling["PIPELINE TOTAL"] = (t1 - t0) * 1000

            default_n = profiling["N"]

            imprimir_log(f"Cenário padrão (K = 3000 | N = {default_n} | D = {default_d})", profiling)

            exec_media(k=1500, d=default_d, n=None, repeticoes=10)
            exec_media(k=6000, d=default_d, n=None, repeticoes=10)
            exec_media(k=9000, d=default_d, n=None, repeticoes=10)

            if default_n == 0:
                print("Nenhum ponto extraído. Cenários de redução de pontos ignorados.")
                sys.exit(0)

            n = round(default_n*0.25)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

            n = round(default_n*0.5)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

            n = round(default_n*0.75)
            d = round(default_d/default_n*n)
            exec_media(k=default_k, d=d, n=n, repeticoes=10)

