"""
UUIDv7 — монотонно-возрастающий UUID на основе Unix timestamp (мс).
Используется как Request-ID и первичный ключ для трассируемости.
"""
import os
import time


def uuid7() -> str:
    """Генерирует UUIDv7-совместимый идентификатор (RFC 9562 draft)."""
    ts_ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF

    # Компоновка 128-бит: 48 бит ts | 4 бит ver=7 | 12 бит rand_a | 2 бит var=0b10 | 62 бит rand_b
    hi = (ts_ms << 16) | (0x7 << 12) | rand_a
    lo = (0b10 << 62) | rand_b

    hex_str = f"{hi:016x}{lo:016x}"
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"


def uuid7_str() -> str:
    return uuid7()
