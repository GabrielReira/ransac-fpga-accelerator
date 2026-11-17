"""Converte no computador o debug PPM gerado em C em uma imagem JPEG."""

import argparse
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("debug", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.debug.suffix.lower() != ".ppm" or args.output.suffix.lower() not in {".jpg", ".jpeg"}:
        parser.error("Informe um debug .ppm e uma saida .jpg/.jpeg.")
    image = cv2.imread(str(args.debug))
    if image is None or not cv2.imwrite(str(args.output), image, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        parser.error("Nao foi possivel converter a imagem de debug.")


if __name__ == "__main__":
    main()
