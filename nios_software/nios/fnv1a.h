#ifndef NIOS_FNV1A_H
#define NIOS_FNV1A_H

#include <stddef.h>
#include <stdint.h>

// FNV-1a 32 bits, o mesmo de tools/mask_hash.py e tools/ismce_run.py
static inline uint32_t fnv1a(const uint8_t *data, size_t size)
{
    uint32_t hash = UINT32_C(2166136261);
    for (size_t i = 0; i < size; ++i) {
        hash = (hash ^ data[i]) * UINT32_C(16777619);
    }
    return hash;
}

#endif
