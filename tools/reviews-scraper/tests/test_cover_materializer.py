from io import BytesIO
import json
import sqlite3

from PIL import Image

from modules.cover_materializer import (
    build_rescue_businesses,
    candidate_urls,
    high_resolution_url,
    is_allowed_source,
    load_overview_candidates,
    load_overview_places,
    load_place_id_urls,
    local_cover_url,
    local_gallery_urls,
    materialize_from_driver,
    materialize_gallery_from_driver,
    save_webp,
    update_manifest_cover,
    update_manifest_gallery,
)


def test_candidate_urls_preserve_order_and_remove_duplicates():
    payload = {
        "coverUrl": "https://lh3.googleusercontent.com/cover",
        "galleryUrls": [
            "https://lh3.googleusercontent.com/cover",
            "https://lh3.googleusercontent.com/gallery",
        ],
        "photoUrls": ["https://lh3.googleusercontent.com/photo"],
    }

    assert candidate_urls(payload) == [
        "https://lh3.googleusercontent.com/cover",
        "https://lh3.googleusercontent.com/gallery",
        "https://lh3.googleusercontent.com/photo",
    ]


def test_only_https_google_image_sources_are_allowed():
    assert is_allowed_source("https://lh3.googleusercontent.com/photo")
    assert not is_allowed_source("http://lh3.googleusercontent.com/photo")
    assert not is_allowed_source("https://lh3.googleusercontent.com.evil.example/photo")
    assert not is_allowed_source("http://127.0.0.1/photo")


def test_save_webp_bounds_dimensions(tmp_path):
    source = BytesIO()
    Image.new("RGB", (2_000, 1_000), "red").save(source, "JPEG")
    output = tmp_path / "cover.webp"

    save_webp(source.getvalue(), output, max_width=960)

    with Image.open(output) as image:
        assert image.format == "WEBP"
        assert image.size == (960, 480)


def test_local_cover_url_is_stable():
    assert local_cover_url("10123") == "/images/shops/10123.webp"


def test_google_photo_url_requests_original_quality():
    assert high_resolution_url(
        "https://lh3.googleusercontent.com/photo=w408-h272-k-no"
    ) == "https://lh3.googleusercontent.com/photo=w1200-h1200-no"
    assert high_resolution_url("https://example.com/photo=w408-h272-k-no") is None


def test_local_gallery_urls_are_stable():
    assert local_gallery_urls("10123") == [
        "/images/shops/10123.webp",
        "/images/shops/10123-2.webp",
        "/images/shops/10123-3.webp",
        "/images/shops/10123-4.webp",
        "/images/shops/10123-5.webp",
        "/images/shops/10123-6.webp",
    ]


def test_load_overview_candidates_indexes_urls_by_shop_id(tmp_path):
    database = tmp_path / "reviews.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE places (original_url TEXT, resolved_url TEXT, overview_metadata TEXT)"
    )
    connection.execute(
        "INSERT INTO places VALUES (?, ?, ?)",
        (
            "https://www.google.com/maps/search/old",
            "https://www.google.com/maps/place/resolved",
            json.dumps(
                {
                    "shop_id": 10123,
                    "overview_cover_url": "https://lh3.googleusercontent.com/cover",
                    "overview_photo_urls": ["https://lh3.googleusercontent.com/gallery"],
                }
            ),
        ),
    )
    connection.commit()
    connection.close()

    assert load_overview_candidates(database) == {
        "10123": [
            "https://lh3.googleusercontent.com/cover",
            "https://lh3.googleusercontent.com/gallery",
        ]
    }
    assert load_overview_places(database) == {
        "10123": "https://www.google.com/maps/place/resolved"
    }


def test_build_rescue_businesses_requires_six_local_photos():
    shops = {
        "10099": {
            "coverUrl": "/images/shops/10099.webp",
            "galleryUrls": ["https://lh3.googleusercontent.com/old"],
        },
        "10100": {
            "coverUrl": "/images/shops/10100.webp",
            "galleryUrls": local_gallery_urls("10100"),
        },
    }
    places = {"10099": "https://www.google.com/maps/place/?q=place_id:test"}

    assert build_rescue_businesses(shops, places) == [
        {
            "url": "https://www.google.com/maps/place/?q=place_id:test",
            "custom_params": {"shop_id": 10099},
        }
    ]


def test_load_place_id_urls_uses_extracted_shop_ids(tmp_path):
    (tmp_path / "places_extracted_1.json").write_text(
        json.dumps(
            {
                "shops": [
                    {
                        "shop_id": 10123,
                        "place_id": "ChIJ-test",
                        "display_name": "Test Shop",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_place_id_urls(tmp_path) == {
        "10123": "https://www.google.com/maps/place/?q=place_id:ChIJ-test"
    }


def test_materialize_from_driver_captures_matching_loaded_image(tmp_path):
    screenshot = BytesIO()
    Image.new("RGB", (1200, 900), "blue").save(screenshot, "PNG")

    class Element:
        screenshot_as_png = screenshot.getvalue()

    class Driver:
        def execute_async_script(self, _script, _url):
            return Element()

        def execute_script(self, _script, _element):
            return None

    local_url = materialize_from_driver(
        Driver(),
        "10123",
        ["https://lh3.googleusercontent.com/photo=w400"],
        tmp_path,
    )

    assert local_url == "/images/shops/10123.webp"
    assert (tmp_path / "10123.webp").is_file()


def test_materialize_gallery_from_driver_saves_six_clear_photos(tmp_path):
    screenshots = []
    for color in ["blue", "blue", "red", "green", "yellow", "purple", "orange"]:
        screenshot = BytesIO()
        Image.new("RGB", (1200, 900), color).save(screenshot, "PNG")
        screenshots.append(screenshot.getvalue())
    requested = []

    class Element:
        def __init__(self, screenshot_as_png):
            self.screenshot_as_png = screenshot_as_png

    class Driver:
        def execute_async_script(self, _script, url):
            requested.append(url)
            index = int(url.split("photo-", 1)[1].split("=", 1)[0])
            return Element(screenshots[index])

        def execute_script(self, _script, _element):
            return None

    urls = materialize_gallery_from_driver(
        Driver(),
        "10123",
        [f"https://lh3.googleusercontent.com/photo-{index}=w408-h272-k-no" for index in range(7)],
        tmp_path,
    )

    assert urls == local_gallery_urls("10123")
    assert all("=w1200-h1200-no" in url for url in requested)
    assert len(requested) == 7
    assert all((tmp_path / f"10123{'-' + str(index) if index > 1 else ''}.webp").is_file() for index in range(1, 7))


def test_update_manifest_cover_only_changes_requested_shop(tmp_path):
    manifest = tmp_path / "shop-media.json"
    manifest.write_text(
        json.dumps({"shops": {"10123": {"coverUrl": "remote"}, "10124": {"coverUrl": "keep"}}}),
        encoding="utf-8",
    )

    update_manifest_cover(manifest, "10123", "/images/shops/10123.webp")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["shops"]["10123"]["coverUrl"] == "/images/shops/10123.webp"
    assert payload["shops"]["10124"]["coverUrl"] == "keep"


def test_update_manifest_gallery_replaces_remote_urls(tmp_path):
    manifest = tmp_path / "shop-media.json"
    manifest.write_text(
        json.dumps({"shops": {"10123": {"coverUrl": "remote", "galleryUrls": ["remote"]}}}),
        encoding="utf-8",
    )
    urls = local_gallery_urls("10123")

    update_manifest_gallery(manifest, "10123", urls)

    shop = json.loads(manifest.read_text(encoding="utf-8"))["shops"]["10123"]
    assert shop["coverUrl"] == urls[0]
    assert shop["galleryUrls"] == urls
    assert shop["photoUrls"] == urls
