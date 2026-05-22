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
results = []
failed = []

for i, shop in enumerate(shops):
    name = shop["display_name"]
    try:
        log.info("extracting", idx=i + 1, total=len(shops), name=name)
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
out.write_text(
    json.dumps(
        {
            "timestamp": ts,
            "total": len(shops),
            "success": len(results),
            "failed": len(failed),
            "failures": failed,
            "shops": results,
        },
        ensure_ascii=False,
        indent=2,
    )
)

log.info("done", success=len(results), failed=len(failed), out=str(out))
