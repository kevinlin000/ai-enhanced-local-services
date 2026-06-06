from __future__ import annotations

from app.main import (
    _authoritative_category_slug,
    _extract_query_constraints,
    _semantic_category_slug,
    _station_proximity_score,
)


def assert_contains(values: list[str], expected: str, label: str) -> None:
    if expected not in values:
        raise AssertionError(f"{label}: expected {expected!r}, got {values!r}")


def assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    constraints = _extract_query_constraints("中山國小附近吃中式料理")
    assert_contains(constraints["stations"], "中山國小", "中山國小 station extraction")
    assert_equal("中山" in constraints["stations"], False, "中山國小 should not broaden to 中山")
    assert_contains(constraints["categories"], "chinese", "中式 category extraction")

    constraints = _extract_query_constraints("信義安和附近火鍋")
    assert_contains(constraints["stations"], "信義安和", "信義安和 station extraction")
    assert_contains(constraints["categories"], "hotpot", "火鍋 category extraction")

    constraints = _extract_query_constraints("大安區美式漢堡")
    assert_contains(constraints["districts"], "大安", "大安 district extraction")
    assert_contains(constraints["categories"], "american", "美式 category extraction")

    assert_equal(
        _station_proximity_score({"stations": ["中山國小"]}, {"mrt_station": "中山國小"}),
        1.0,
        "exact station score",
    )
    assert_equal(
        _station_proximity_score({"stations": ["中山國小"]}, {"mrt_station": "象山"}),
        0.0,
        "unrelated station score",
    )

    assert_equal(
        _authoritative_category_slug({"category_slug": "hotpot", "name": "辛殿麻辣鍋"}),
        "hotpot",
        "authoritative hotpot slug",
    )
    assert_equal(
        _authoritative_category_slug({"category": "中式料理"}),
        "chinese",
        "authoritative Chinese label",
    )
    assert_equal(
        _semantic_category_slug({"category_slug": "hotpot", "name": "海底撈火鍋"}),
        "hotpot",
        "semantic hotpot slug",
    )

    print("PASS agent filter guards")


if __name__ == "__main__":
    main()
