"""FNV-1a 32 bits de uma mascara _mask.bin

Compare com a linha mask_fnv1a impressa pelo benchmark no Nios II
"""

import argparse
from pathlib import Path


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mask", type=Path)
    args = parser.parse_args()
    print(f"mask_fnv1a=0x{fnv1a(args.mask.read_bytes()):08x}")


if __name__ == "__main__":
    main()
