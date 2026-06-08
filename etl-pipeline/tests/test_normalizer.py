from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.normalizer import extract_district_from_address


def test_extract_district_prefers_formatted_address_over_crawler_target():
    assert (
        extract_district_from_address("114台灣臺北市內湖區寶湖里民權東路六段125之1號", "南港")
        == "內湖"
    )


def test_extract_district_handles_taipei_address_with_wrong_target():
    assert (
        extract_district_from_address("110台灣臺北市信義區永吉里松山路11號CITYLINK松山壹號店1F", "南港")
        == "信義"
    )


def test_extract_district_handles_simplified_area_suffix():
    assert (
        extract_district_from_address("104台北市中山区集英里抚顺街11號1樓", "大同")
        == "中山"
    )
    assert extract_district_from_address("110台北市信义区松山路11號", "南港") == "信義"
    assert extract_district_from_address("114台北市内湖区民權東路六段", "南港") == "內湖"
    assert extract_district_from_address("108台北市万华区漢中街", "中正") == "萬華"


def test_extract_district_falls_back_when_address_missing():
    assert extract_district_from_address(None, "南港") == "南港"
