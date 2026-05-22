import json
from pathlib import Path

from app.extractor import Extractor

RAW_DIR = Path("data/raw")
latest = sorted(RAW_DIR.glob("places_enriched_*.json"))[-1]
print(f"reading: {latest}")
data = json.loads(latest.read_text())

ichiran = next((shop for shop in data if shop["display_name"] == "一蘭拉麵台灣台北本店"), None)

if not ichiran:
    ichiran = next((shop for shop in data if shop["display_name"] == "ICHIRAN Taipei"), None)

if not ichiran:
    print("ICHIRAN not found")
    raise SystemExit(1)

print(f"extracting: {ichiran['display_name']} ({len(ichiran['reviews'])} reviews)")

extractor = Extractor()
result = extractor.extract(ichiran)

print(json.dumps(result, ensure_ascii=False, indent=2))
