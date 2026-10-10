"""Ferramenta do computador: JPEG -> RGB intercalado para carregar no Nios II."""

import argparse
import json
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    args = parser.parse_args()
    if args.image.suffix.lower() not in {".jpg", ".jpeg"}:
        parser.error("A entrada deve ser JPEG (.jpg/.jpeg).")
    if (args.width is None) != (args.height is None):
        parser.error("Informe --width e --height juntos.")
    if args.width is not None and (args.width <= 0 or args.height <= 0):
        parser.error("As dimensoes precisam ser positivas.")
    image = cv2.imread(str(args.image))
    if image is None:
        parser.error(f"Nao foi possivel ler {args.image}.")
    if args.width is not None:
        image = cv2.resize(image, (args.width, args.height), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rgb.tofile(args.output)
    height, width = rgb.shape[:2]
    metadata = {"width": width, "height": height, "format": "RGB888", "bytes": rgb.size}
    Path(f"{args.output}.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"{args.output}: {width}x{height}, {rgb.size} bytes RGB888")


if __name__ == "__main__":
    main()
