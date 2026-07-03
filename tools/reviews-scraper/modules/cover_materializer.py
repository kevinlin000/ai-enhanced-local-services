"""Materialize remote shop covers as bounded local WebP assets."""

from __future__ import annotations

import argparse
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "web" / "data" / "shop-media.json"
DEFAULT_OUTPUT_DIR = ROOT / "web" / "public" / "images" / "shops"
DEFAULT_OVERVIEW_DB = ROOT / "tools" / "reviews-scraper" / "reviews.db"
DEFAULT_RAW_DIR = ROOT / "etl-pipeline" / "data" / "raw"
ALLOWED_HOSTS = {"lh3.googleusercontent.com"}
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
HEADERS = {
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/maps/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
}


def is_allowed_source(raw: str) -> bool:
    try:
        url = urlparse(raw)
        return url.scheme == "https" and url.hostname in ALLOWED_HOSTS
    except ValueError:
        return False


def candidate_urls(payload: dict) -> list[str]:
    values = [
        payload.get("coverUrl"),
        *(payload.get("galleryUrls") or []),
        *(payload.get("photoUrls") or []),
    ]
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def local_cover_url(shop_id: str) -> str:
    return f"/images/shops/{shop_id}.webp"


def load_overview_candidates(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT overview_metadata FROM places WHERE overview_metadata IS NOT NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        connection.close()

    candidates = {}
    for (raw,) in rows:
        try:
            metadata = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        shop_id = metadata.get("shop_id")
        if shop_id is None:
            continue
        urls = [
            metadata.get("overview_cover_url"),
            *(metadata.get("overview_photo_urls") or []),
        ]
        candidates[str(shop_id)] = list(
            dict.fromkeys(url for url in urls if isinstance(url, str) and url)
        )
    return candidates


def load_overview_places(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT COALESCE(NULLIF(resolved_url, ''), original_url), overview_metadata FROM places "
            "WHERE overview_metadata IS NOT NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        connection.close()

    places = {}
    for original_url, raw in rows:
        try:
            shop_id = json.loads(raw).get("shop_id")
        except (TypeError, json.JSONDecodeError):
            continue
        if shop_id is not None and original_url:
            places[str(shop_id)] = original_url
    return places


def load_place_id_urls(raw_dir: Path) -> dict[str, str]:
    places = {}
    for path in sorted(raw_dir.glob("places_extracted_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        shops = payload.get("shops", []) if isinstance(payload, dict) else payload
        for shop in shops or []:
            shop_id = shop.get("shop_id")
            place_id = shop.get("place_id")
            if shop_id is not None and place_id:
                places[str(shop_id)] = (
                    f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                )
    return places


def materialize_from_driver(
    driver,
    shop_id: str,
    candidates: list[str],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> str | None:
    script = """
        const [url, done] = arguments;
        const image = new Image();
        let settled = false;
        const finish = (value) => {
          if (settled) return;
          settled = true;
          done(value);
        };
        image.onload = () => {
          image.style.position = 'fixed';
          image.style.left = '0';
          image.style.top = '0';
          image.style.zIndex = '2147483647';
          image.style.width = `${image.naturalWidth}px`;
          image.style.height = `${image.naturalHeight}px`;
          document.body.appendChild(image);
          finish(image);
        };
        image.onerror = () => finish(null);
        image.src = url;
        setTimeout(() => finish(null), 8000);
    """
    for url in candidates:
        if not is_allowed_source(url):
            continue
        element = driver.execute_async_script(script, url)
        if element is None:
            continue
        try:
            screenshot = element.screenshot_as_png
            with Image.open(BytesIO(screenshot)) as image:
                if image.width < 280 or image.height < 180:
                    continue
            save_webp(screenshot, output_dir / f"{shop_id}.webp")
        except (OSError, ValueError, Image.UnidentifiedImageError):
            continue
        finally:
            driver.execute_script("arguments[0].remove()", element)
        return local_cover_url(shop_id)
    return None


def update_manifest_cover(path: Path, shop_id: str, local_url: str) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    shop = manifest.get("shops", {}).get(str(shop_id))
    if shop is None:
        return
    shop["coverUrl"] = local_url
    write_manifest(path, manifest)


def build_rescue_businesses(shops: dict, places: dict[str, str]) -> list[dict]:
    return [
        {"url": places[shop_id], "custom_params": {"shop_id": int(shop_id)}}
        for shop_id, payload in shops.items()
        if not str(payload.get("coverUrl") or "").startswith("/images/shops/")
        and shop_id in places
    ]


def save_webp(content: bytes, output: Path, max_width: int = 960) -> None:
    with Image.open(BytesIO(content)) as source:
        source.verify()
    with Image.open(BytesIO(content)) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("image dimensions exceed safety limit")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".webp.tmp")
        try:
            image.save(temporary, "WEBP", quality=80, method=6)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)


def download(url: str) -> bytes | None:
    if not is_allowed_source(url):
        return None
    try:
        with requests.get(
            url,
            headers=HEADERS,
            stream=True,
            timeout=(5, 15),
            allow_redirects=False,
        ) as response:
            content_type = response.headers.get("content-type", "").lower()
            content_length = int(response.headers.get("content-length") or 0)
            if response.status_code != 200 or not content_type.startswith("image/"):
                return None
            if content_length > MAX_DOWNLOAD_BYTES:
                return None
            chunks = []
            size = 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except (OSError, requests.RequestException, ValueError):
        return None


def materialize(shop_id: str, payload: dict, output_dir: Path) -> tuple[str, str | None, int]:
    output = output_dir / f"{shop_id}.webp"
    if payload.get("coverUrl") == local_cover_url(shop_id) and output.is_file():
        return shop_id, payload["coverUrl"], output.stat().st_size

    for url in candidate_urls(payload):
        content = download(url)
        if content is None:
            continue
        try:
            save_webp(content, output)
        except (OSError, ValueError, Image.UnidentifiedImageError):
            continue
        return shop_id, local_cover_url(shop_id), output.stat().st_size
    return shop_id, None, 0


def write_manifest(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="download assets and update manifest")
    parser.add_argument("--shop-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overview-db", type=Path, default=DEFAULT_OVERVIEW_DB)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--write-rescue-config", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    shops = manifest.get("shops", {})
    if args.write_rescue_config:
        places = load_overview_places(args.overview_db)
        places.update(load_place_id_urls(args.raw_dir))
        businesses = build_rescue_businesses(shops, places)
        if args.shop_id:
            requested = {int(shop_id) for shop_id in args.shop_id}
            businesses = [
                business
                for business in businesses
                if business["custom_params"]["shop_id"] in requested
            ]
        if args.limit is not None:
            businesses = businesses[: args.limit]
        config = {
            "db_path": str(args.overview_db),
            "headless": True,
            "overview_only": True,
            "materialize_overview_cover": True,
            "download_images": False,
            "use_mongodb": False,
            "backup_to_json": False,
            "log_level": "WARNING",
            "businesses": businesses,
        }
        args.write_rescue_config.parent.mkdir(parents=True, exist_ok=True)
        args.write_rescue_config.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"rescueBusinesses": len(businesses)}, ensure_ascii=False))
        return
    overview_candidates = load_overview_candidates(args.overview_db)
    selected = [(shop_id, shops[shop_id]) for shop_id in args.shop_id if shop_id in shops]
    if not selected:
        selected = list(shops.items())
    if args.limit is not None:
        selected = selected[: args.limit]
    selected = [
        (
            shop_id,
            {
                **payload,
                "galleryUrls": [
                    *overview_candidates.get(shop_id, []),
                    *(payload.get("galleryUrls") or []),
                ],
            },
        )
        for shop_id, payload in selected
    ]

    if not args.apply:
        print(json.dumps({"planned": len(selected), "output": str(args.output_dir)}, ensure_ascii=False))
        return

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(materialize, shop_id, payload, args.output_dir): shop_id
            for shop_id, payload in selected
        }
        for future in as_completed(futures):
            results.append(future.result())

    written = 0
    total_bytes = 0
    failed = []
    for shop_id, local_url, size in results:
        if local_url is None:
            failed.append(shop_id)
            continue
        shops[shop_id]["coverUrl"] = local_url
        written += 1
        total_bytes += size
    if written:
        write_manifest(args.manifest, manifest)

    print(
        json.dumps(
            {
                "selected": len(selected),
                "materialized": written,
                "failed": len(failed),
                "bytes": total_bytes,
                "failedShopIds": sorted(failed, key=int),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
