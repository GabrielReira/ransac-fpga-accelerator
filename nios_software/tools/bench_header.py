"""Gera nios/bench_images.h com a referencia do computador para cada frame embutido

Uso: bench_header.py <dir_referencia> <bench_set> <double|float> <nome:LxA>...
Le <dir_referencia>/<nome>_<L>x<A>_model.json e _mask.bin, gerados pelo lane_detect
A ordem dos argumentos e a ordem dos PPMs em bench_images.ppm
"""

import json
import sys
from pathlib import Path


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    reference_dir, bench_set, real = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    rows = []
    for entry in sys.argv[4:]:
        name, size = entry.split(":")
        width, height = (int(v) for v in size.split("x"))
        stem = reference_dir / f"{name}_{size}"
        model = json.loads(Path(f"{stem}_model.json").read_text())
        mask_hash = fnv1a(Path(f"{stem}_mask.bin").read_bytes())
        rows.append(f'    {{"{name}", {width}U, {height}U, {int(model["found"])}, '
                    f'{model["points"]}UL, {model["inliers"]}UL, 0x{mask_hash:08X}U}},')
    print(f"""// Gerado por tools/bench_header.py (BENCH_SET={bench_set}, {real})
#ifndef BENCH_IMAGES_H
#define BENCH_IMAGES_H

#include <stdint.h>

#define BENCH_IMAGE_COUNT {len(rows)}
#define BENCH_REAL_NAME "{real}"

// lane_detect no computador com a configuracao do build; so vale se ela nao mudou
typedef struct {{
    const char *name;
    unsigned width;
    unsigned height;
    int found;
    unsigned long points;
    unsigned long inliers;
    uint32_t mask_hash;
}} BenchReference;

static const BenchReference bench_references[BENCH_IMAGE_COUNT] = {{
{chr(10).join(rows)}
}};

#endif""")


if __name__ == "__main__":
    main()
