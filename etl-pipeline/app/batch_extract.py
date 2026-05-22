import json
import time
from datetime import datetime
from pathlib import Path

import structlog

from app.extractor import Extractor

log = structlog.get_logger()

RAW_DIR = Path("data/raw")
latest = sorted(RAW_DIR.glob("places_enriched_*.json"))[-1]
log.info("reading", file=str(latest))
data = json.loads(latest.read_text())

shops = data if isinstance(data, list) else data.get("shops", [])
log.info("total_shops", count=len(shops))

extractor = Extractor()
existing_results_by_id = {}
previous_extracted_files = sorted(RAW_DIR.glob("places_extracted_*.json"))
if previous_extracted_files:
    latest_extracted = previous_extracted_files[-1]
    previous = json.loads(latest_extracted.read_text())
    existing_results_by_id = {
        shop["place_id"]: shop for shop in previous.get("shops", []) if shop.get("place_id")
    }
    log.info(
        "resume_found",
        file=str(latest_extracted),
        completed=len(existing_results_by_id),
    )

remaining_shops = [shop for shop in shops if shop["place_id"] not in existing_results_by_id]
log.info("remaining_shops", count=len(remaining_shops))

results = list(existing_results_by_id.values())
failed = []

for i, shop in enumerate(remaining_shops):
    name = shop["display_name"]
    try:
        log.info("extracting", idx=i + 1, total=len(remaining_shops), name=name)
        extracted = extractor.extract(shop)
        enriched_shop = {**shop, "ai_extracted": extracted}
        results.append(enriched_shop)
        time.sleep(4.5)
    except Exception as exc:
        log.error("extract_failed", name=name, error=str(exc))
        failed.append({"name": name, "error": str(exc)})
        continue

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out = RAW_DIR / f"places_extracted_{ts}.json"
result_by_id = {shop["place_id"]: shop for shop in results if shop.get("place_id")}
ordered_results = [result_by_id[shop["place_id"]] for shop in shops if shop["place_id"] in result_by_id]
out.write_text(
    json.dumps(
        {
            "timestamp": ts,
            "total": len(shops),
            "success": len(ordered_results),
            "failed": len(failed),
            "failures": failed,
            "shops": ordered_results,
        },
        ensure_ascii=False,
        indent=2,
    )
)

log.info("done", success=len(ordered_results), failed=len(failed), out=str(out))
