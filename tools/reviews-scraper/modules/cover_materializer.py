"""Materialize six clear shop photos as bounded local WebP assets."""

from __future__ import annotations

import argparse
import hashlib
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
GALLERY_SIZE = 6
TARGET_IMAGE_SIZE = 1200
MIN_LONG_EDGE = 900
MIN_SHORT_EDGE = 600
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
    candidates = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not value or not is_allowed_source(value):
            continue
        key = value.split("=", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        candidates.append(value)
    return candidates


def high_resolution_url(raw: str) -> str | None:
    if not is_allowed_source(raw):
        return None
    return raw.split("=", 1)[0] + f"=w{TARGET_IMAGE_SIZE}-h{TARGET_IMAGE_SIZE}-no"


def local_cover_url(shop_id: str) -> str:
    return f"/images/shops/{shop_id}.webp"


def local_gallery_urls(shop_id: str, count: int = GALLERY_SIZE) -> list[str]:
    return [
        local_cover_url(shop_id)
        if index == 0
        else f"/images/shops/{shop_id}-{index + 1}.webp"
        for index in range(count)
    ]


def _output_path(output_dir: Path, shop_id: str, index: int) -> Path:
    suffix = "" if index == 0 else f"-{index + 1}"
    return output_dir / f"{shop_id}{suffix}.webp"


def _is_clear_image(content: bytes) -> bool:
    with Image.open(BytesIO(content)) as image:
        long_edge = max(image.size)
        short_edge = min(image.size)
    return long_edge >= MIN_LONG_EDGE and short_edge >= MIN_SHORT_EDGE


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
    urls = materialize_gallery_from_driver(
        driver,
        shop_id,
        candidates,
        output_dir,
        limit=1,
    )
    return urls[0] if urls else None


def materialize_gallery_from_driver(
    driver,
    shop_id: str,
    candidates: list[str],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int = GALLERY_SIZE,
) -> list[str]:
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
    local_urls = []
    seen = set()
    seen_content = set()
    for candidate in candidates:
        if len(local_urls) >= limit:
            break
        url = high_resolution_url(candidate)
        if not url:
            continue
        source_key = url.split("=", 1)[0]
        if source_key in seen:
            continue
        seen.add(source_key)
        try:
            element = driver.execute_async_script(script, url)
        except Exception:
            continue
        if element is None:
            continue
        try:
            screenshot = element.screenshot_as_png
            if not _is_clear_image(screenshot):
                continue
            content_hash = hashlib.sha256(screenshot).digest()
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            output = _output_path(output_dir, shop_id, len(local_urls))
            save_webp(screenshot, output)
            local_urls.append(local_gallery_urls(shop_id, limit)[len(local_urls)])
        except (OSError, ValueError, Image.UnidentifiedImageError):
            continue
        finally:
            try:
                driver.execute_script("arguments[0].remove()", element)
            except Exception:
                pass
    return local_urls


def update_manifest_cover(path: Path, shop_id: str, local_url: str) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    shop = manifest.get("shops", {}).get(str(shop_id))
    if shop is None:
        return
    shop["coverUrl"] = local_url
    write_manifest(path, manifest)


def update_manifest_gallery(path: Path, shop_id: str, local_urls: list[str]) -> None:
    if len(local_urls) != GALLERY_SIZE:
        raise ValueError(f"expected {GALLERY_SIZE} local photos")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    shop = manifest.get("shops", {}).get(str(shop_id))
    if shop is None:
        return
    shop["coverUrl"] = local_urls[0]
    shop["galleryUrls"] = local_urls
    shop["photoUrls"] = local_urls
    write_manifest(path, manifest)


def build_rescue_businesses(shops: dict, places: dict[str, str]) -> list[dict]:
    return [
        {"url": places[shop_id], "custom_params": {"shop_id": int(shop_id)}}
        for shop_id, payload in shops.items()
        if not _has_local_gallery(payload)
        and shop_id in places
    ]


def _has_local_gallery(payload: dict) -> bool:
    urls = payload.get("galleryUrls") or []
    return len(urls) >= GALLERY_SIZE and all(
        isinstance(url, str) and url.startswith("/images/shops/")
        for url in urls[:GALLERY_SIZE]
    )


def save_webp(content: bytes, output: Path, max_width: int = TARGET_IMAGE_SIZE) -> None:
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
            image.save(temporary, "WEBP", quality=82, method=6)
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


def materialize(shop_id: str, payload: dict, output_dir: Path) -> tuple[str, list[str], int]:
    expected_urls = local_gallery_urls(shop_id)
    expected_paths = [_output_path(output_dir, shop_id, index) for index in range(GALLERY_SIZE)]
    if _has_local_gallery(payload) and all(path.is_file() for path in expected_paths):
        return shop_id, expected_urls, sum(path.stat().st_size for path in expected_paths)

    written_paths = []
    seen_content = set()
    for candidate in candidate_urls(payload):
        url = high_resolution_url(candidate)
        if not url:
            continue
        content = download(url)
        if content is None:
            continue
        try:
            if not _is_clear_image(content):
                continue
            content_hash = hashlib.sha256(content).digest()
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            output = _output_path(output_dir, shop_id, len(written_paths))
            save_webp(content, output)
        except (OSError, ValueError, Image.UnidentifiedImageError):
            continue
        written_paths.append(output)
        if len(written_paths) == GALLERY_SIZE:
            return shop_id, expected_urls, sum(path.stat().st_size for path in written_paths)
    return shop_id, [], sum(path.stat().st_size for path in written_paths)


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
            "materialize_overview_gallery": True,
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
    for shop_id, local_urls, size in results:
        if len(local_urls) != GALLERY_SIZE:
            failed.append(shop_id)
            continue
        shops[shop_id]["coverUrl"] = local_urls[0]
        shops[shop_id]["galleryUrls"] = local_urls
        shops[shop_id]["photoUrls"] = local_urls
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
