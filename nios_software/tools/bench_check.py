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
# Pontos, inliers e mascara sao exatos; os coeficientes valem pela curva que descrevem
# O FPH2 arredonda alguns bits finais diferente do float do PC (~1e-4 px na curva),
# entao a curva tolera 0,01 px no trecho detectado e o mse 1e-4 relativo
CURVE_TOLERANCE_PX = 0.01
MSE_TOLERANCE = 1e-4


def parse_reference(path):
    reference = {}
    name, json_lines = None, []
    for line in path.read_text().splitlines():
        if line.startswith("image="):
            fields = dict(item.split("=", 1) for item in line.split())
            name, json_lines = (fields["image"], fields.get("size", "")), []
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
            current = {"image": (fields["image"], fields.get("size", "")),
                       "run": int(fields["run"])}
            runs.append(current)
        elif current is None:
            continue
        elif re.match(r"(status|a|mask_fnv1a|total_cycles)=", line):
            current.update(item.split("=", 1) for item in line.split())
        elif line.startswith("|Consenso"):
            current["consensus_pct"] = float(line.split("|")[2])
    return runs


def curve_deviation(got, model):
    """Maior |dx| em pixels entre as duas parabolas, de y_min a y_max"""
    poly = model["poly"]
    da, db, dc = (got[key] - poly[key] for key in ("a", "b", "c"))
    return max(abs((da * y + db) * y + dc)
               for y in range(int(model["y_min"]), int(model["y_max"]) + 1))


def check(run, model):
    expected = [
        ("status", run.get("status") == "0"),
        ("found", run.get("found") == str(int(model["found"]))),
        ("points", run.get("points") == str(model["points"])),
        ("inliers", run.get("inliers") == str(model["inliers"])),
        ("mask_fnv1a", int(run.get("mask_fnv1a", "0"), 16) == model["mask_hash"]),
    ]
    if model["found"]:
        got = {key: float(run[key]) for key in ("a", "b", "c")}
        expected.append(("curva", curve_deviation(got, model) <= CURVE_TOLERANCE_PX))
        expected.append(("mse", math.isclose(float(run["mse"]), model["mse"],
                                             rel_tol=MSE_TOLERANCE, abs_tol=1e-12)))
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

    print(f"\n{'imagem':<30} {'exec':>4} {'resultado':<10} {'total (ms)':>12} {'consenso':>9}")
    passed = True
    for run in runs:
        model = reference.get(run["image"])
        failed = ["sem referencia"] if model is None else check(run, model)
        passed &= not failed
        total_ms = float(run.get("total_ms", "nan"))
        consensus = run.get("consensus_pct")
        label = " ".join(part for part in run["image"] if part)
        print(f"{label:<30} {run['run']:>4} {'PASS' if not failed else 'FAIL':<10} "
              f"{total_ms:>12.1f} {consensus if consensus is not None else '?':>8}%"
              + (f"  diferente: {', '.join(failed)}" if failed else ""))
    missing = sorted(set(reference) - {run["image"] for run in runs})
    if missing:
        passed = False
        print("sem execucao no log: " + ", ".join(" ".join(key).strip() for key in missing))
    print("\nPASS" if passed else "\nFAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
