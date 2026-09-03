"""Katalog SHA-256 + mesaj/sinyal sayısı doğrulaması (scout)."""

import hashlib
import json
import sys
from pathlib import Path
from random import Random

import cantools

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

data_dir = PROJECT_ROOT / "data" / "dbc"
catalog = json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))

sha_ok = sha_bad = 0
size_ok = size_bad = 0
bad_examples = []
for cat in catalog["categories"].values():
    for f in cat["files"]:
        rel = (
            f["relative_path"][len("curated/"):]
            if f["relative_path"].startswith("curated/")
            else f["relative_path"]
        )
        p = data_dir / rel
        if not p.exists():
            bad_examples.append(f"MISSING {rel}")
            sha_bad += 1
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h == f["sha256"]:
            sha_ok += 1
        else:
            sha_bad += 1
            bad_examples.append(f"SHA MISMATCH {rel}: cat={f['sha256'][:12]}… disk={h[:12]}…")
        if p.stat().st_size == f["size_bytes"]:
            size_ok += 1
        else:
            size_bad += 1
            bad_examples.append(f"SIZE MISMATCH {rel}: cat={f['size_bytes']} disk={p.stat().st_size}")

print(f"sha256 match: {sha_ok}/{sha_ok+sha_bad}   size match: {size_ok}/{size_ok+size_bad}")
for b in bad_examples[:10]:
    print(" ", b)

# Örnek: katalogdaki messages_count iddialarından 5'ini cantools ile doğrula
rnd = Random(42)
checked = mism = 0
all_files = [(_cat_name, f) for _cat_name, cat in catalog["categories"].items() for f in cat["files"]]
for _cat_name, f in rnd.sample(all_files, 5):
    rel = (
        f["relative_path"][len("curated/"):]
        if f["relative_path"].startswith("curated/")
        else f["relative_path"]
    )
    p = data_dir / rel
    if not p.exists():
        continue
    try:
        db = cantools.database.load_file(p)
        n_msg = len(db.messages)
        n_sig = sum(len(m.signals) for m in db.messages)
        checked += 1
        ok = n_msg == f["messages_count"]
        if not ok:
            mism += 1
            print(f"  COUNT MISMATCH {rel}: cat={f['messages_count']}/{f['signals_count']} actual={n_msg}/{n_sig}")
    except Exception as e:  # noqa: BLE001
        print(f"  LOAD FAIL {rel}: {e}")
print(f"sampled message-count check: {checked-mism}/{checked} match")
