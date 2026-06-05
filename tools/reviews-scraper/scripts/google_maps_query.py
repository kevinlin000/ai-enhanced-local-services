#!/usr/bin/env python3
"""Build high-precision Google Maps search URLs for ByteBites shop scraping."""

from __future__ import annotations

import re
import sys
import urllib.parse


DISTRICT_OR_CATEGORY_RE = re.compile(
    r"(?:台北|臺北|士林|大安|信義|中山|內湖|南港|松山|北投|萬華|中正|文山|"
    r"餐廳|餐酒館|酒吧|咖啡|甜點|早午餐|下午茶|義大利麵|燉飯|異國料理|"
    r"親子|寵物|聚餐|慶生|約會|網美|推薦|熱門|訂位|評價|PTT|Dcard|threads)",
    re.IGNORECASE,
)

SEO_TAIL_RE = re.compile(
    r"(?:202\d\s*)?(?:熱門)?(?:訂位|評價|推薦|美食|餐廳|PTT|Dcard|threads).*$",
    re.IGNORECASE,
)


def _collapse_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """Remove SEO/category stuffing while preserving the actual brand name."""
    original = _collapse_space(value)
    text = original
    if not text:
        return text

    text = re.sub(r"[【\\[].*$", "", text).strip()

    # Slash-separated suffixes are usually category/marketing lists, not brand.
    if "/" in text or "／" in text:
        left, right = re.split(r"[／/]", text, maxsplit=1)
        if left.strip() and DISTRICT_OR_CATEGORY_RE.search(right):
            text = left.strip()

    # Pipe-separated suffixes are branch/category notes.
    text = re.split(r"[｜|]", text, maxsplit=1)[0].strip()

    # Parenthetical tails are often SEO/location hints in imported data.
    text = re.sub(r"[\(（][^\)）]*$", "", text).strip()

    # Strip SEO terms even when they are not separated by punctuation.
    text = SEO_TAIL_RE.sub("", text).strip()

    # Hyphen tails like "品牌-台北士林站輕食早午餐" hurt Maps resolution.
    hyphen_parts = re.split(r"\s*[-—－]\s*", text, maxsplit=1)
    if len(hyphen_parts) == 2 and hyphen_parts[0].strip():
        head, tail = hyphen_parts[0].strip(), hyphen_parts[1].strip()
        if len(head) >= 2 and DISTRICT_OR_CATEGORY_RE.search(tail):
            text = head

    # Space-separated marketing tails.
    text = re.split(
        r"\s+(?:台北|臺北|士林區|大安區|信義區|中山區|內湖區|南港區|松山區|"
        r"北投區|萬華區|中正區|文山區|石牌|天母|公館|萬隆|餐廳|餐酒館|酒吧|"
        r"活動|生日|企業|推薦|包場|美食|燒肉|火鍋|聚餐)",
        text,
        maxsplit=1,
    )[0].strip()

    text = text.strip(" -—－｜|／/")
    return text or original


def clean_address(value: str) -> str:
    """Keep enough address detail to avoid generic district/category pages."""
    text = _collapse_space(value)
    text = re.sub(r"^\d{3,6}\s*", "", text)
    text = text.replace("台灣", "").strip()
    text = re.sub(r"\s+", "", text)
    return text


def build_query_text(name: str, address: str) -> str:
    name_part = clean_name(name)
    address_part = clean_address(address)
    return " ".join(part for part in (name_part, address_part) if part).strip()


def build_search_url(name: str, address: str) -> str:
    query = urllib.parse.quote(build_query_text(name, address))
    return f"https://www.google.com/maps/search/{query}"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: google_maps_query.py NAME ADDRESS", file=sys.stderr)
        return 2
    print(build_search_url(argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
