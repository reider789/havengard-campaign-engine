"""Build a deterministic, offline-only chat payload. No script is fetched by the chat widget."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "current-chat-battle.html"
TARGET = ROOT / "current-chat-battle.gzip.b64"
META = ROOT / "inline-payload-manifest.json"

def build():
    html = SOURCE.read_bytes()
    if b'data-hg-runtime' not in html or b'class CombatDiceRoller' not in html or b'class CombatSpellResolver' not in html or b'class CombatReactionResolver' not in html or b'v21NewScenario' not in html:
        raise RuntimeError("Not the self-contained modular v23 bundle")
    compressed = gzip.compress(html, compresslevel=9, mtime=0)
    if gzip.decompress(compressed) != html:
        raise RuntimeError("Round-trip mismatch")
    payload = base64.b64encode(compressed).decode("ascii")
    TARGET.write_text(payload + "\n", encoding="ascii")
    metadata = {
        "schema": 1, "encoding": "gzip+base64", "engine": "v23",
        "bytes_original": len(html), "bytes_gzip": len(compressed),
        "bytes_base64": len(payload),
        "sha256_original": hashlib.sha256(html).hexdigest(),
        "sha256_gzip": hashlib.sha256(compressed).hexdigest(),
        "same_as_source": True,
        "runtime_network_requests": 0,
    }
    META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(metadata))

if __name__ == "__main__":
    build()
