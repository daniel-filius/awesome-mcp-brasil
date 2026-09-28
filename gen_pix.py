"""Gera o Pix "copia-e-cola" estático (BR Code / EMVCo) de DOAÇÃO, sem valor fixo,
e grava em data/pix.txt (lido por scripts/build_readme.py).

A chave Pix é lida de control-panel/finance_config.py do Agentic OS (nunca
hardcoded aqui). O payload resultante é público por natureza (é um QR de
recebimento) — é a única saída deste script. Só roda na sandbox do Agentic OS;
no repositório público basta o data/pix.txt já gerado.

Uso:  python3 gen_pix.py
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "control-panel"))


def _strip(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _tlv(id_: str, value: str) -> str:
    return f"{id_}{len(value):02d}{value}"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build(pix_key: str, name: str, city: str, txid: str = "AWESOMEMCPBR") -> str:
    mai = _tlv("26", _tlv("00", "br.gov.bcb.pix") + _tlv("01", pix_key))
    body = (_tlv("00", "01") + _tlv("01", "12") + mai + _tlv("52", "0000") + _tlv("53", "986")
            + _tlv("58", "BR") + _tlv("59", _strip(name).upper()[:25]) + _tlv("60", _strip(city).upper()[:15])
            + _tlv("62", _tlv("05", txid[:25])) + "6304")
    return body + _crc16(body)


if __name__ == "__main__":
    import finance_config  # noqa: E402

    key = finance_config.reveal().get("pix_key")
    if not key:
        sys.exit("sem chave Pix configurada em /finance")
    out = HERE / "data" / "pix.txt"
    out.write_text(build(key, "Daniel Filius", "Sao Paulo") + "\n", encoding="utf-8")
    print(f"pix.txt gravado ({out.stat().st_size} bytes)")
