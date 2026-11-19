"""Gera nios/bench_images.h com os nomes das imagens embutidas e a referencia do computador

Uso: bench_header.py <dir_referencia> <bench_set> <nome>...
Le <dir_referencia>/<nome>_model.json e <nome>_mask.bin, gerados pelo lane_detect
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
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    reference_dir, bench_set, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    rows = []
    for name in names:
        model = json.loads((reference_dir / f"{name}_model.json").read_text())
        mask_hash = fnv1a((reference_dir / f"{name}_mask.bin").read_bytes())
        rows.append(f"    {{{int(model['found'])}, {model['points']}UL, {model['inliers']}UL, "
                    f"0x{mask_hash:08X}U}}, // {name}")
    print(f"""// Gerado por tools/bench_header.py (BENCH_SET={bench_set})
#ifndef BENCH_IMAGES_H
#define BENCH_IMAGES_H

#include <stdint.h>

#define BENCH_IMAGE_COUNT {len(names)}

static const char *const bench_image_names[BENCH_IMAGE_COUNT] = {{
{chr(10).join(f'    "{name}",' for name in names)}
}};

#ifdef BENCH_REFERENCES
// lane_detect no computador com a configuracao do build; so vale se ela nao mudou
typedef struct {{
    int found;
    unsigned long points;
    unsigned long inliers;
    uint32_t mask_hash;
}} BenchReference;

static const BenchReference bench_references[BENCH_IMAGE_COUNT] = {{
{chr(10).join(rows)}
}};
#endif

#endif""")


if __name__ == "__main__":
    main()
