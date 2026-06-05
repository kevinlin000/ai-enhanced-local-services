from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from google_maps_query import build_query_text, clean_name


def test_clean_name_strips_seo_tail_after_hyphen_and_slash():
    name = (
        "花嶼輕食館Flower Island Brunch-台北士林站輕食早午餐/"
        "下午茶/咖啡廳 異國料理/義大利麵/燉飯 親子/寵物友善 "
        "2026熱門訂位評價推薦 PTT Dcard threads"
    )

    assert clean_name(name) == "花嶼輕食館Flower Island Brunch"


def test_query_uses_full_address_for_generic_shop_name():
    query = build_query_text("大安米粉湯", "106台灣臺北市大安區龍淵里復興南路二段316號")

    assert query == "大安米粉湯 臺北市大安區龍淵里復興南路二段316號"


def test_clean_name_keeps_real_brand_with_punctuation():
    assert clean_name("12:59早午餐Brunch.Pasta.Coffee.Dessert") == (
        "12:59早午餐Brunch.Pasta.Coffee.Dessert"
    )
