"""
Salva diagnosticos visuais de cada etapa do pre-processamento: mascara de
tinta branca/amarela, ROI e nuvem de pontos enviada ao RANSAC.

Uso:
    python debug_preprocessing.py caminho/da/imagem.jpg

O resultado eh salvo em test_images/debug_outputs/<nome_imagem>_<timestamp>/
"""

import argparse
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from ransac import default_roi_vertices, extract_lane_points

DEFAULT_OUTPUT_DIR = Path("test_images/debug_outputs")
ROI_COLOR = (0, 255, 0)    # verde (BGR)
POINT_COLOR = (255, 0, 0)  # azul (BGR)


def save_diagnostics(image_path, output_dir=DEFAULT_OUTPUT_DIR):
    """Salva a mascara de tinta, o overlay da ROI e a nuvem de pontos."""
    image_path = Path(image_path)
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Nao foi possivel abrir '{image_path}'")
    height, width = image_bgr.shape[:2]

    # O debug mostra exatamente o que o RANSAC recebe
    paint_mask, roi_mask, points = extract_lane_points(image_bgr)
    roi_vertices = default_roi_vertices(width, height)

    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    output_dir = Path(output_dir) / f"{image_path.stem}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    paint_path = output_dir / f"{image_path.stem}_paint_mask.png"
    roi_path = output_dir / f"{image_path.stem}_roi_overlay.png"
    points_path = output_dir / f"{image_path.stem}_ransac_points.png"

    # Mascara de tinta branca/amarela na imagem inteira, antes da ROI
    cv2.imwrite(str(paint_path), paint_mask)

    # ROI: regiao colorida e contorno sobre a imagem original
    polygon_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(polygon_mask, roi_vertices, 255)
    color_layer = np.zeros_like(image_bgr)
    color_layer[:] = ROI_COLOR
    tinted_image = cv2.addWeighted(image_bgr, 0.72, color_layer, 0.28, 0)
    roi_overlay = image_bgr.copy()
    roi_overlay[polygon_mask > 0] = tinted_image[polygon_mask > 0]
    cv2.polylines(roi_overlay, roi_vertices, isClosed=True, color=ROI_COLOR, thickness=3)
    cv2.imwrite(str(roi_path), roi_overlay)

    # Nuvem de pontos enviada ao RANSAC (um ponto por corrida horizontal de tinta)
    point_overlay = image_bgr.copy()
    for x, y in points:
        cv2.circle(point_overlay, (int(round(x)), int(round(y))), 1, POINT_COLOR, -1)
    cv2.imwrite(str(points_path), point_overlay)

    print(f"Tamanho da imagem: {width}x{height}")
    print(f"Pixels de tinta antes da ROI: {int(np.count_nonzero(paint_mask))}")
    print(f"Pixels de tinta dentro da ROI: {int(np.count_nonzero(roi_mask))}")
    print(f"Pontos enviados ao RANSAC: {len(points)}")
    print(f"Salvo em: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    args = parser.parse_args()

    save_diagnostics(args.image)