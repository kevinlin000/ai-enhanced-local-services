#!/usr/bin/env python3
"""
One-shot script: dedup reviews inside places_extracted_*.json files.
Keeps first occurrence of (author, normalized_text) per shop per file.
Backs up each modified file as <filename>.bak before overwriting.
"""
import json, re, shutil
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def dedup_file(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    total_removed = 0
    shops_changed = 0

    for shop in payload.get("shops", []):
        reviews = shop.get("reviews")
        if not reviews:
            continue
        seen: set[str] = set()
        kept = []
        for r in reviews:
            key = f"{r.get('author_name', r.get('author', ''))}||{normalize(r.get('text', ''))}"
            if key in seen:
                total_removed += 1
            else:
                seen.add(key)
                kept.append(r)
        if len(kept) < len(reviews):
            shop["reviews"] = kept
            shops_changed += 1

    if total_removed > 0:
        bak = path.with_suffix(".json.bak")
        shutil.copy2(path, bak)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.name}: removed {total_removed} dups across {shops_changed} shops  (backup: {bak.name})")
    else:
        print(f"  {path.name}: clean")

    return total_removed, shops_changed

if __name__ == "__main__":
    files = sorted(RAW_DIR.glob("places_extracted_*.json"))
    print(f"Processing {len(files)} files in {RAW_DIR}\n")
    grand_total = 0
    for f in files:
        removed, _ = dedup_file(f)
        grand_total += removed
    print(f"\nDone. Total duplicate rows removed: {grand_total}")
