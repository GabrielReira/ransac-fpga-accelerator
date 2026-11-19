"""Compara o log do benchmark no Nios II com a referencia do computador

Le o log gravado por nios/run_bench.sh e o reference.txt gerado por
nios/build_nios.sh, uma linha por imagem e execucao. Sai com 0 se todas
batem e 1 caso contrario
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent.parent
# a placa imprime %.9g, entao a tolerancia relativa cobre so o arredondamento do printf
FLOAT_TOLERANCE = 1e-8


def parse_reference(path):
    reference = {}
    name, json_lines = None, []
    for line in path.read_text().splitlines():
        if line.startswith("image="):
            name, json_lines = line.split("=", 1)[1], []
        elif line.startswith("mask_fnv1a="):
            model = json.loads("\n".join(json_lines))
            model["mask_hash"] = int(line.split("=", 1)[1], 16)
            reference[name] = model
        else:
            json_lines.append(line)
    return reference


def parse_log(path):
    runs = []
    current = None
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("image="):
            fields = dict(item.split("=", 1) for item in line.split())
            current = {"image": fields["image"], "run": int(fields["run"])}
            runs.append(current)
        elif current is None:
            continue
        elif re.match(r"(status|a|mask_fnv1a|total_cycles)=", line):
            current.update(item.split("=", 1) for item in line.split())
        elif line.startswith("|Consenso"):
            current["consensus_pct"] = float(line.split("|")[2])
    return runs


def close(got, expected):
    return math.isclose(float(got), expected, rel_tol=FLOAT_TOLERANCE, abs_tol=1e-12)


def check(run, model):
    expected = [
        ("status", run.get("status") == "0"),
        ("found", run.get("found") == str(int(model["found"]))),
        ("points", run.get("points") == str(model["points"])),
        ("inliers", run.get("inliers") == str(model["inliers"])),
        ("mask_fnv1a", int(run.get("mask_fnv1a", "0"), 16) == model["mask_hash"]),
    ]
    if model["found"]:
        expected += [(key, close(run[key], model["poly"][key])) for key in ("a", "b", "c")]
        expected.append(("mse", close(run["mse"], model["mse"])))
    return [name for name, ok in expected if not ok]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path)
    parser.add_argument("--reference", type=Path,
                        default=SW / "build" / "nios" / "reference.txt")
    args = parser.parse_args()

    reference = parse_reference(args.reference)
    runs = parse_log(args.log)
    if not runs:
        sys.exit(f"Nenhuma execucao encontrada em {args.log}")

    print(f"\n{'imagem':<22} {'exec':>4} {'resultado':<10} {'total (ms)':>12} {'consenso':>9}")
    passed = True
    for run in runs:
        model = reference.get(run["image"])
        failed = ["sem referencia"] if model is None else check(run, model)
        passed &= not failed
        total_ms = float(run.get("total_ms", "nan"))
        consensus = run.get("consensus_pct")
        print(f"{run['image']:<22} {run['run']:>4} {'PASS' if not failed else 'FAIL':<10} "
              f"{total_ms:>12.1f} {consensus if consensus is not None else '?':>8}%"
              + (f"  diferente: {', '.join(failed)}" if failed else ""))
    missing = sorted(set(reference) - {run["image"] for run in runs})
    if missing:
        passed = False
        print(f"sem execucao no log: {', '.join(missing)}")
    print("\nPASS" if passed else "\nFAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
