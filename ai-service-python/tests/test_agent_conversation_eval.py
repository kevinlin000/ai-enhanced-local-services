import json
from pathlib import Path

import pytest

import app.main as main


EXPECTED_CASE_IDS = {
    "web_vague_group_need_clarifies",
    "web_exact_recommended_shop_booking_draft",
    "web_booking_draft_edit_time",
    "web_booking_draft_switch_shop",
    "line_exact_recommended_shop_booking_draft",
    "line_booking_draft_edit_time",
    "line_negative_selection_more_results",
    "hard_constraint_business_taiwanese",
    "hard_constraint_korean_cuisine",
}


async def _collect_web_done(query: str, session_id: str) -> dict:
    events = [event async for event in main._run_agent_turn_stream(query, session_id)]
    assert events, "agent stream returned no events"
    assert events[-1]["type"] == "done"
    return events[-1]


def _line_text_event(text: str, user_id: str = "eval-line-user") -> dict:
    return {
        "type": "message",
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "text", "text": text},
    }


def test_conversation_quality_eval_manifest_is_complete():
    path = Path(__file__).resolve().parents[1] / "evals" / "conversation_quality_cases.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert {case["id"] for case in cases} == EXPECTED_CASE_IDS
    assert all(case.get("query") and case.get("quality_gate") for case in cases)


@pytest.mark.anyio
async def test_eval_web_vague_group_need_clarifies(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("vague restaurant need must clarify before model/search")

    monkeypatch.setattr(main, "generate", fail_generate)

    done = await _collect_web_done("推薦7人聚餐餐廳", "eval-web-vague-group")

    assert done["tools_used"] == []
    assert "7人我先記下" in done["answer"]
    assert "地點或捷運站" in done["answer"]
    assert "料理類型或氣氛" in done["answer"]


@pytest.mark.anyio
async def test_eval_web_exact_recommended_shop_booking_draft(monkeypatch):
    saved = {}

    async def fail_create_booking(**kwargs):
        raise AssertionError("booking draft eval must not create booking before confirmation")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "推薦信義區高級火鍋"},
            {
                "role": "model",
                "content": "我整理了三間。",
                "recommendation": {
                    "query": "推薦信義區高級火鍋",
                    "shops": [
                        {"shop_id": 10009, "name": "橘色涮涮屋 信義館", "district": "信義"},
                        {"shop_id": 10115, "name": "辛殿麻辣鍋｜信義店", "district": "信義"},
                        {"shop_id": 10221, "name": "築間幸福鍋物 台北南門店", "district": "中正"},
                    ],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))
    monkeypatch.setattr(main, "tool_create_booking", fail_create_booking)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should bypass model")))
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    done = await _collect_web_done(
        "我要訂位 辛殿麻辣鍋｜信義店 明天 2人 晚上19:00",
        "eval-web-exact-recommended-booking",
    )

    assert done["booking_draft"] == {
        "shop_id": 10115,
        "shop_name": "辛殿麻辣鍋｜信義店",
        "date": "2026-06-11",
        "time": "19:00",
        "people": 2,
    }
    assert done["transaction"] is None
    assert "請先回覆要訂哪一間" not in done["answer"]
    assert saved["history"][-1]["booking_draft"]["shop_id"] == 10115


@pytest.mark.anyio
async def test_eval_web_booking_draft_edits_time_and_switches_shop(monkeypatch):
    saved = {}
    history = [
        {"role": "user", "content": "中山區適合聚餐"},
        {
            "role": "model",
            "content": "我整理了三間。",
            "recommendation": {
                "query": "中山區適合聚餐",
                "shops": [
                    {"shop_id": 10101, "name": "藝奇"},
                    {"shop_id": 10102, "name": "太田日式燒肉"},
                    {"shop_id": 10103, "name": "七転八起"},
                ],
            },
        },
        {
            "role": "model",
            "content": "我幫你整理好訂位內容了。",
            "recommendation": {
                "query": "訂第二間",
                "shops": [{"shop_id": 10102, "name": "太田日式燒肉"}],
            },
            "booking_draft": {
                "shop_id": 10102,
                "shop_name": "太田日式燒肉",
                "date": "2026-06-19",
                "time": "19:00",
                "people": 4,
            },
        },
    ]

    async def fail_create_booking(**kwargs):
        raise AssertionError("draft edit eval must not create booking before confirmation")

    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: history)
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, new_history: saved.update({"history": new_history}))
    monkeypatch.setattr(main, "tool_create_booking", fail_create_booking)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should bypass model")))

    time_done = await _collect_web_done("改成 20:00", "eval-web-draft-edit-time")
    assert time_done["booking_draft"]["shop_id"] == 10102
    assert time_done["booking_draft"]["date"] == "2026-06-19"
    assert time_done["booking_draft"]["time"] == "20:00"
    assert time_done["booking_draft"]["people"] == 4

    switch_done = await _collect_web_done("換第三間，同樣時間人數", "eval-web-draft-switch-shop")
    assert switch_done["booking_draft"]["shop_id"] == 10103
    assert switch_done["booking_draft"]["shop_name"] == "七転八起"
    assert switch_done["booking_draft"]["date"] == "2026-06-19"
    assert switch_done["booking_draft"]["time"] == "19:00"
    assert switch_done["booking_draft"]["people"] == 4
    assert saved["history"][-1]["booking_draft"]["shop_id"] == 10103


@pytest.mark.anyio
async def test_eval_line_exact_recommended_shop_booking_draft(monkeypatch):
    saved_draft = {}

    async def fake_fetch_java_shop(shop_id: int):
        assert shop_id == 10115
        return {"id": shop_id, "name": "辛殿麻辣鍋｜信義店"}

    monkeypatch.setattr(main, "_load_line_booking_state", lambda user_id: {})
    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {
            "query": "信義區高級火鍋",
            "shown_shop_ids": [10009, 10115, 10221],
            "shown_shops": [
                {"shop_id": 10009, "name": "橘色涮涮屋 信義館"},
                {"shop_id": 10115, "name": "辛殿麻辣鍋｜信義店"},
                {"shop_id": 10221, "name": "築間幸福鍋物 台北南門店"},
            ],
        },
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main, "_save_line_booking_draft_state", lambda user_id, draft: saved_draft.update(draft))
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        _line_text_event("我要訂位 辛殿麻辣鍋｜信義店 明天 2人 晚上19:00")
    )

    assert saved_draft["shop_id"] == 10115
    assert saved_draft["date"] == "2026-06-11"
    assert saved_draft["time"] == "19:00"
    assert saved_draft["people"] == 2
    assert "辛殿麻辣鍋｜信義店" in messages[0]["text"]
    assert messages[1]["type"] == "flex"


@pytest.mark.anyio
async def test_eval_line_draft_update_and_negative_selection(monkeypatch):
    saved_draft = {}
    captured_search = {}

    async def fake_fetch_java_shop(shop_id: int):
        return {"id": shop_id, "name": "七転八起" if shop_id == 10103 else f"店家 {shop_id}"}

    async def fake_semantic_hits(query: str, top_k: int):
        captured_search["query"] = query
        return [
            {"shop_id": 10101, "name": "藝奇", "district": "中山", "ai_summary": "已推薦。"},
            {"shop_id": 10102, "name": "太田日式燒肉", "district": "中山", "ai_summary": "已推薦。"},
            {"shop_id": 10103, "name": "七転八起", "district": "中山", "ai_summary": "新候選。"},
        ]

    draft = {
        "shop_id": 10102,
        "shop_name": "太田日式燒肉",
        "date": "2026-06-19",
        "time": "19:00",
        "people": 4,
        "table_type": "normal",
    }
    state = {
        "query": "中山區適合聚餐",
        "shown_shop_ids": [10101, 10102, 10103],
        "shown_shops": [
            {"shop_id": 10101, "name": "藝奇"},
            {"shop_id": 10102, "name": "太田日式燒肉"},
            {"shop_id": 10103, "name": "七転八起"},
        ],
    }

    monkeypatch.setattr(main, "_load_line_booking_state", lambda user_id: {})
    monkeypatch.setattr(main, "_load_line_booking_draft_state", lambda user_id: draft)
    monkeypatch.setattr(main, "_load_line_recommendation_state", lambda user_id: state)
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_save_line_booking_draft_state", lambda user_id, updated: saved_draft.update(updated))
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    update_messages = await main._build_line_reply_messages(_line_text_event("改成 20:00"))
    assert saved_draft["time"] == "20:00"
    assert saved_draft["shop_id"] == 10102
    assert "20:00" in update_messages[0]["text"]

    saved_draft.clear()
    switch_messages = await main._build_line_reply_messages(_line_text_event("換第三間，同樣時間人數"))
    assert saved_draft["shop_id"] == 10103
    assert saved_draft["date"] == "2026-06-19"
    assert saved_draft["time"] == "19:00"
    assert saved_draft["people"] == 4
    assert "七転八起" in switch_messages[0]["text"]

    state["shown_shop_ids"] = [10101, 10102]
    state["shown_shops"] = [
        {"shop_id": 10101, "name": "藝奇"},
        {"shop_id": 10102, "name": "太田日式燒肉"},
    ]
    more_messages = await main._build_line_reply_messages(_line_text_event("不要第二間，換一家"))
    assert captured_search["query"] == "中山區適合聚餐"
    assert any(message.get("type") == "flex" for message in more_messages)
    assert saved_draft["shop_id"] == 10103


def test_eval_hard_constraints_for_business_taiwanese_and_korean():
    taiwanese_constraints = main._extract_query_constraints("適合商務請客的台菜")
    assert taiwanese_constraints["wants_taiwanese_cuisine"]

    business_taiwanese = {
        "shop_id": 10135,
        "name": "榮榮園",
        "category_slug": "chinese",
        "avg_price": 1500,
        "rating": 4.6,
        "ai_summary": "老字號台菜，適合商務宴客與多人合菜。",
        "signature_dishes": ["佛跳牆", "白斬雞"],
        "atmosphere_tags": ["商務", "聚餐"],
        "rerank_score": 0.2,
    }
    bistro = {
        "shop_id": 10901,
        "name": "紅皇后川酒・RED QUEEN BISTRO",
        "category_slug": "chinese",
        "avg_price": 1100,
        "rating": 4.5,
        "ai_summary": "中式餐酒館，主打調酒與小酌。",
        "signature_dishes": ["藤椒白肉"],
        "atmosphere_tags": ["餐酒館", "聚餐"],
        "rerank_score": 1.5,
    }
    korean_pasta = {
        "shop_id": 10902,
        "name": "金孫韓廚 義大利麵",
        "category_slug": "chinese",
        "avg_price": 480,
        "rating": 4.5,
        "ai_summary": "韓義混血料理，韓國辣醬義大利麵與海鮮煎餅。",
        "signature_dishes": ["韓國辣醬義大利麵", "海鮮煎餅"],
        "atmosphere_tags": ["聚餐"],
        "rerank_score": 2.0,
    }

    assert main._matches_requested_category(business_taiwanese, taiwanese_constraints)
    assert main._is_taiwanese_cuisine_mismatch(bistro)
    assert main._is_taiwanese_cuisine_mismatch(korean_pasta)
    assert main._taiwanese_cuisine_sort_key(taiwanese_constraints, business_taiwanese) > main._taiwanese_cuisine_sort_key(
        taiwanese_constraints,
        bistro,
    )

    korean_constraints = main._extract_query_constraints("韓式料理")
    assert korean_constraints["specific_cuisines"] == ["korean"]
    korean_bbq = {
        "name": "韓式烤肉研究所",
        "category_slug": "yakiniku",
        "ai_summary": "韓式烤肉、泡菜鍋與海鮮煎餅。",
        "signature_dishes": ["韓式烤肉", "泡菜鍋"],
        "atmosphere_tags": ["聚餐"],
    }
    japanese_yakiniku = {
        "name": "太田日式燒肉",
        "category_slug": "yakiniku",
        "ai_summary": "日式燒肉與牛舌。",
        "signature_dishes": ["牛舌", "和牛"],
        "atmosphere_tags": ["聚餐"],
    }
    assert main._matches_specific_cuisine(korean_bbq, "korean")
    assert not main._is_specific_cuisine_mismatch(korean_bbq, "korean")
    assert not main._matches_specific_cuisine(japanese_yakiniku, "korean")
    assert main._is_specific_cuisine_mismatch(japanese_yakiniku, "korean")
