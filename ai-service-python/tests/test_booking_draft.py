from app.booking_draft import (
    booking_draft_confirmation_answer,
    booking_draft_missing,
    booking_draft_payload,
    compact_booking_prefill,
    merge_booking_prefill,
)


def test_booking_draft_payload_compacts_valid_prefill():
    draft = booking_draft_payload(
        10115,
        "辛殿麻辣鍋｜信義店",
        {"date": "2026-06-19", "time": "19:00", "people": "4", "ignored": "x"},
    )

    assert draft == {
        "shop_id": 10115,
        "shop_name": "辛殿麻辣鍋｜信義店",
        "date": "2026-06-19",
        "time": "19:00",
        "people": 4,
    }


def test_merge_booking_prefill_fills_missing_fields_without_overwriting():
    merged = merge_booking_prefill(
        {"time": "20:00", "people": None},
        {"date": "2026-06-19", "time": "19:00", "people": 4},
    )

    assert merged == {"time": "20:00", "people": 4, "date": "2026-06-19"}


def test_merge_booking_prefill_override_applies_current_edits_to_draft():
    merged = merge_booking_prefill(
        {"time": "20:00"},
        {"date": "2026-06-19", "time": "19:00", "people": 4},
        override=True,
    )

    assert merged == {"date": "2026-06-19", "time": "20:00", "people": 4}


def test_booking_draft_missing_and_confirmation_answer():
    draft = booking_draft_payload(10115, "辛殿麻辣鍋｜信義店", {"date": "2026-06-19"})

    assert booking_draft_missing(draft) == ["時間", "人數"]
    assert "還缺時間、人數" in booking_draft_confirmation_answer(draft)


def test_booking_draft_confirmation_answer_mentions_capacity_check_on_edits():
    draft = booking_draft_payload(
        10115,
        "辛殿麻辣鍋｜信義店",
        {"date": "2026-06-19", "time": "20:00", "people": 4},
    )

    answer = booking_draft_confirmation_answer(draft, "改成 20:00")

    assert "沿用上一輪" in answer
    assert "即時檢查店家容量" in answer


def test_compact_booking_prefill_ignores_invalid_people():
    assert compact_booking_prefill({"date": "2026-06-19", "people": "oops"}) == {
        "date": "2026-06-19"
    }
