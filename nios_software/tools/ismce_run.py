"""Roda o pipeline no Nios II pelo In-System Memory Content Editor e compara
com a mesma implementacao C no computador

Requer a placa com o .sof da P1 e o ransac_ismce.elf rodando (nios2-download -g)
Sai com 0 em PASS e 1 em FAIL
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import cv2

TOOLS = Path(__file__).resolve().parent
SW = TOOLS.parent
SECTIONS = ["Pre-processamento", "Amostragem", "Estimativa modelo", "Consenso",
            "Refinamento", "Erro/selecao", "Renderizacao"]


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def mailbox_layout():
    """Le os #define MBOX_* de nios/mailbox.h, fonte unica do layout"""
    text = (SW / "nios" / "mailbox.h").read_text()
    return {name: int(value.rstrip("U"), 0) for name, value in
            re.findall(r"#define\s+MBOX_(\w+)\s+(0x[0-9A-Fa-f]+U?|\d+U?)", text)}


def rgb_to_words(rgb):
    """Empacota o RGB em palavras little-endian, na ordem em que o Nios le a IMG"""
    padded = rgb + bytes(-len(rgb) % 4)
    return [int.from_bytes(padded[i:i + 4], "little") for i in range(0, len(padded), 4)]


def words_to_u64(words, index):
    return words[index] | (words[index + 1] << 32)


def words_to_double(words, index):
    return struct.unpack("<d", struct.pack("<Q", words_to_u64(words, index)))[0]


def find_quartus_stp(explicit):
    if explicit:
        return explicit
    root = os.environ.get("QUARTUS_ROOTDIR")
    if root:
        return str(Path(root) / "bin" / "quartus_stp")
    found = shutil.which("quartus_stp")
    if not found:
        sys.exit("quartus_stp nao encontrado; defina QUARTUS_ROOTDIR ou --quartus-stp")
    return found


def host_reference(rgb_path, args, threshold, out_prefix):
    lane_detect = SW / "build" / "lane_detect"
    subprocess.run(["make", "-C", str(SW), "host"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([str(lane_detect), str(rgb_path), str(args.width), str(args.height),
                    str(out_prefix), "--iterations", str(args.iterations),
                    "--threshold", repr(threshold), "--min-inliers", str(args.min_inliers),
                    "--seed", str(args.seed), "--thickness", str(args.thickness)],
                   check=True, stdout=subprocess.DEVNULL)
    model = json.loads(Path(f"{out_prefix}_model.json").read_text())
    model["mask_hash"] = fnv1a(Path(f"{out_prefix}_mask.bin").read_bytes())
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="JPEG de entrada")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--threshold", type=float, default=1.0, help="pixels (resolucao 0.001)")
    parser.add_argument("--min-inliers", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--thickness", type=int, default=3)
    parser.add_argument("--clock-hz", type=float, default=50e6, help="clock do Nios")
    parser.add_argument("--timeout", type=int, default=900, help="segundos")
    parser.add_argument("--skip-image", action="store_true",
                        help="reutiliza a imagem ja carregada em IMG (mesmas dimensoes)")
    parser.add_argument("--cable", default="", help='ex.: "USB-Blaster [1-1]"')
    parser.add_argument("--quartus-stp")
    parser.add_argument("--work", type=Path, default=SW / "build" / "ismce")
    args = parser.parse_args()

    layout = mailbox_layout()
    args.work.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.image))
    if image is None:
        parser.error(f"Nao foi possivel ler {args.image}.")
    image = cv2.resize(image, (args.width, args.height), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).tobytes()
    rgb_path = args.work / "frame.rgb"
    rgb_path.write_bytes(rgb)

    # A MBOX leva o threshold em milesimos, entao a referencia usa o valor ja arredondado
    threshold_milli = round(args.threshold * 1000)
    threshold = threshold_milli / 1000
    img_words = args.work / "img_words.txt"
    img_words.write_text("" if args.skip_image else
                         "\n".join(f"{w:08X}" for w in rgb_to_words(rgb)) + "\n")
    inputs = {"WIDTH": args.width, "HEIGHT": args.height, "ITERATIONS": args.iterations,
              "THRESHOLD_MILLI": threshold_milli, "MIN_INLIERS": args.min_inliers,
              "SEED": args.seed, "THICKNESS": args.thickness}
    mbox_in = args.work / "mbox_in.txt"
    mbox_in.write_text("".join(f"{layout[name]} {value:08X}\n" for name, value in inputs.items()))
    mbox_out = args.work / "mbox_out.txt"
    mbox_out.unlink(missing_ok=True)

    print(f"Nios II: {args.image.name} {args.width}x{args.height}, "
          f"{len(rgb)} bytes, {args.iterations} iteracoes", flush=True)
    subprocess.run([find_quartus_stp(args.quartus_stp), "-t", str(TOOLS / "ismce_run.tcl"),
                    str(img_words), str(mbox_in), str(mbox_out), str(layout["WORDS"]),
                    str(layout["MAGIC_VALUE"]), str(layout["COMMAND_RUN"]),
                    str(args.timeout), args.cable], check=True)
    words = [int(line, 16) for line in mbox_out.read_text().split()]

    def word(name):
        return words[layout[name]]

    nios = {
        "status": word("STATUS"), "found": bool(word("FOUND")), "points": word("POINTS"),
        "inliers": word("INLIERS"), "a": words_to_double(words, layout["A"]),
        "b": words_to_double(words, layout["B"]), "c": words_to_double(words, layout["C"]),
        "mse": words_to_double(words, layout["MSE"]), "mask_hash": word("MASK_HASH"),
        "rgb_hash": word("RGB_HASH"),
    }
    reference = host_reference(rgb_path, args, threshold, args.work / "reference")

    checks = [
        ("status", nios["status"], 0),
        ("rgb_fnv1a", f"0x{nios['rgb_hash']:08x}", f"0x{fnv1a(rgb):08x}"),
        ("found", nios["found"], reference["found"]),
        ("points", nios["points"], reference["points"]),
        ("inliers", nios["inliers"], reference["inliers"]),
        ("a", nios["a"], reference["poly"]["a"]),
        ("b", nios["b"], reference["poly"]["b"]),
        ("c", nios["c"], reference["poly"]["c"]),
        ("mse", nios["mse"], reference["mse"]),
        ("mask_fnv1a", f"0x{nios['mask_hash']:08x}", f"0x{reference['mask_hash']:08x}"),
    ]
    print(f"\n{'campo':<11} {'Nios II':>24} {'computador':>24}")
    passed = True
    for name, got, expected in checks:
        ok = got == expected
        passed &= ok
        print(f"{name:<11} {got!s:>24} {expected!s:>24}{'' if ok else '  <-- DIFERENTE'}")

    total = words_to_u64(words, layout["CYCLES"])
    print(f"\nTotal: {total} ciclos = {total * 1000 / args.clock_hz:.3f} ms "
          f"a {args.clock_hz / 1e6:g} MHz")
    for index, name in enumerate(SECTIONS, start=1):
        cycles = words_to_u64(words, layout["CYCLES"] + 2 * index)
        share = 100 * cycles / total if total else 0
        print(f"  {index}. {name:<18} {cycles:>14} ciclos {cycles * 1000 / args.clock_hz:>12.3f} ms"
              f" {share:6.2f}%")
    print("\nPASS" if passed else "\nFAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
