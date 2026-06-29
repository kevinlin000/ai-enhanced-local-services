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
    "demo_story_department_group_recommends_with_reasons",
    "demo_story_family_driving_recommends_with_parking",
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


def test_effective_agent_query_does_not_merge_complete_fresh_search():
    history = [
        {"role": "user", "content": "大安區人均200到400義式餐廳"},
        {
            "role": "model",
            "content": "還需要日期或時段。",
            "clarification_query": "大安區人均200到400義式餐廳",
        },
    ]
    query = "大安區想吃牛排，適合約會聊天，也想知道附近停車"

    assert main._complete_fresh_restaurant_query(query)
    assert main._effective_agent_query(query, history) == query


def test_validator_replaces_llm_choice_that_violates_steak_constraint():
    query = "大安區想吃牛排，適合約會聊天，也想知道附近停車"
    shops = [
        {
            "shop_id": 10673,
            "name": "光司DATE 義大利麵 大安店",
            "district": "大安",
            "category_slug": "euro",
            "avg_price": 300,
            "signature_dishes": ["煙燻培根白醬", "松露燉飯"],
            "atmosphere_tags": ["約會", "安靜聊天"],
        },
        {
            "shop_id": 10544,
            "name": "茱莉金牛排餐酒館",
            "district": "大安",
            "category_slug": "american",
            "avg_price": 1750,
            "signature_dishes": ["安格斯肋眼牛排", "酥烤法式半雞"],
            "atmosphere_tags": ["約會", "聚餐"],
        },
        {
            "shop_id": 10696,
            "name": "Agusto奧古斯托 牛排龍蝦餐酒館 大安店",
            "district": "大安",
            "category_slug": "euro",
            "avg_price": 1500,
            "signature_dishes": ["肋眼牛排", "龍蝦義大利麵"],
            "atmosphere_tags": ["約會", "聚餐"],
        },
    ]
    decision = main.AgentRecommendationDecision(
        recommended_shop_ids=[10673],
        rejected_shop_ids=[10544, 10696],
        narrative="推薦光司DATE。",
    )

    validated = main._validate_agent_decision(decision, {"shops": shops}, query)

    assert validated.recommended_shop_ids == [10544, 10696]
    assert 10673 in validated.rejected_shop_ids


def test_validator_drops_rejection_summary_that_mentions_recommended_shop():
    shops = [
        {"shop_id": 10544, "name": "茱莉金牛排餐酒館", "district": "大安", "signature_dishes": ["安格斯肋眼牛排"]},
        {"shop_id": 10159, "name": "西堤牛排台北羅斯福店", "district": "大安", "signature_dishes": ["鴨胸"]},
        {"shop_id": 10765, "name": "AW Cafe Wine Bistro", "district": "大安", "signature_dishes": ["牛排"]},
    ]
    decision = main.AgentRecommendationDecision(
        recommended_shop_ids=[10544, 10159],
        rejected_shop_ids=[10765],
        narrative="推薦茱莉金與西堤。",
        rejection_summary="西堤牛排定位較偏大眾化連鎖，AW Cafe Wine Bistro 則以輕食與餐酒為主。",
    )

    validated = main._validate_agent_decision(decision, {"shops": shops}, "大安區想吃牛排，適合約會聊天")

    assert validated.rejection_summary is None


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
    assert "沿用上一輪" in time_done["answer"]
    assert "即時檢查店家容量" in time_done["answer"]

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


@pytest.mark.anyio
async def test_eval_demo_story_department_group_recommendation(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [201, 202],
                "narrative": "我會優先看這兩家。",
                "rejected_shop_ids": [203],
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "部門聚餐" in query
        return [
            {
                "shop_id": 201,
                "name": "大安會館",
                "district": "大安",
                "mrt_station": "大安",
                "category_slug": "chinese",
                "avg_price": 900,
                "ai_summary": "桌距寬敞，適合多人合菜與聊天。",
                "signature_dishes": ["砂鍋雞湯", "合菜"],
                "atmosphere_tags": ["聚餐", "安靜", "包廂"],
                "booking_difficulty": "預約困難",
            },
            {
                "shop_id": 202,
                "name": "仁愛聚餐廳",
                "district": "大安",
                "mrt_station": "信義安和",
                "category_slug": "japanese",
                "avg_price": 1100,
                "ai_summary": "座位舒適，適合公司聚餐。",
                "signature_dishes": ["套餐", "烤物"],
                "atmosphere_tags": ["聚餐", "舒適"],
                "booking_difficulty": "建議提前預約",
            },
            {
                "shop_id": 203,
                "name": "深夜餐酒館",
                "district": "大安",
                "category_slug": "izakaya",
                "ai_summary": "小酌熱鬧，尖峰音量較高。",
                "signature_dishes": ["調酒"],
                "atmosphere_tags": ["餐酒館", "熱鬧"],
                "booking_difficulty": "未提及",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: None)

    query = "明天晚上 7 點，7 個人部門聚餐，想找大安區適合聊天、不會太吵的餐廳。"
    done = await _collect_web_done(query, "eval-demo-story-department")

    assert done["tools_used"] == ["semantic_shop_search"]
    assert "部門聚餐" in done["answer"]
    assert "聊天" in done["answer"]
    assert "候位" in done["answer"] or "空位通知" in done["answer"]
    assert done["recommended_shop_ids"] == [201, 202]
    assert done["comparison_rows"][0]["feature_highlight"] == "招牌：砂鍋雞湯、合菜"
    assert "部門聚餐" in done["comparison_rows"][0]["best_for"]
    assert "中式合菜" in done["comparison_rows"][0]["best_for"]
    assert "額滿可候位通知" in done["comparison_rows"][0]["booking_status"]


@pytest.mark.anyio
async def test_eval_demo_story_department_prefers_koji_for_chat(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [403, 401, 402],
                "narrative": "我會優先看這三家。",
                "rejected_shop_ids": [],
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "部門聚餐" in query
        return [
            {
                "shop_id": 401,
                "name": "光司DATE 義大利麵 大安店",
                "district": "大安",
                "category_slug": "euro",
                "avg_price": 520,
                "price_per_person": "未提及",
                "ai_summary": "二樓座位區採光良好，桌距充裕，氛圍溫馨自在，適合朋友聚餐慢慢聊天。",
                "signature_dishes": ["煙燻培根白醬", "松露燉飯", "粉紅醬雞肉麵"],
                "atmosphere_tags": ["約會", "聚餐", "一人"],
                "booking_difficulty": "未提及",
            },
            {
                "shop_id": 402,
                "name": "Lazy Pasta 慵懶義式廚房大安國館店",
                "district": "大安",
                "category_slug": "euro",
                "avg_price": None,
                "price_per_person": "未提及",
                "ai_summary": "明亮簡潔，適合聚餐，但離場時間與節奏掌控較明確。",
                "signature_dishes": ["北海道干貝鮮蝦啵啵麵", "奶油培根蛋黃麵"],
                "atmosphere_tags": ["聚餐", "親子"],
                "booking_difficulty": "現場可入",
            },
            {
                "shop_id": 403,
                "name": "知初植物系永續廚房",
                "district": "大安",
                "category_slug": "vegetarian",
                "avg_price": 400,
                "price_per_person": "$400以上",
                "ai_summary": "光線柔和且座位間距寬敞，強調無麩質與蔬食。",
                "signature_dishes": ["佛陀碗", "青檸檬塔"],
                "atmosphere_tags": ["聚餐"],
                "booking_difficulty": "預約困難",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: None)

    query = "明天晚上 7 點，7 個人部門聚餐，想找大安區適合聊天、不會太吵的餐廳。"
    done = await _collect_web_done(query, "eval-demo-story-koji-chat")

    assert done["recommended_shop_ids"][0] == 401
    assert done["shops"][0]["name"] == "光司DATE 義大利麵 大安店"
    assert done["shops"][0]["price_per_person"] == "NT$ 520"
    assert done["comparison_rows"][0]["meta"].startswith("NT$ 520")
    assert "部門聚餐" in done["comparison_rows"][0]["best_for"]
    assert "安靜聊天" in done["comparison_rows"][0]["best_for"]


@pytest.mark.anyio
async def test_eval_demo_story_complex_department_briefing(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [401, 403],
                "narrative": "我會優先看這兩家。",
                "rejected_shop_ids": [402],
                "rejection_summary": "Lazy Pasta 招牌含蝦蟹，先保留作備案比較。",
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "不能吃蝦蟹" in query
        return [
            {
                "shop_id": 401,
                "name": "光司DATE 義大利麵 大安店",
                "district": "大安",
                "category_slug": "euro",
                "avg_price": 520,
                "ai_summary": "二樓座位區採光良好，桌距充裕，適合朋友聚餐慢慢聊天。",
                "signature_dishes": ["煙燻培根白醬", "松露燉飯", "粉紅醬雞肉麵"],
                "atmosphere_tags": ["聚餐"],
                "booking_difficulty": "未提及",
            },
            {
                "shop_id": 402,
                "name": "Lazy Pasta 慵懶義式廚房大安國館店",
                "district": "大安",
                "category_slug": "euro",
                "ai_summary": "招牌含蝦蟹，尖峰時段偏熱鬧。",
                "signature_dishes": ["北海道干貝鮮蝦啵啵麵", "紅白醬雞肉菌菇寬麵", "奶油培根蛋黃麵"],
                "atmosphere_tags": ["熱鬧"],
                "booking_difficulty": "現場可入",
            },
            {
                "shop_id": 403,
                "name": "知初植物系永續廚房",
                "district": "大安",
                "category_slug": "vegetarian",
                "avg_price": 400,
                "ai_summary": "光線柔和且座位間距寬敞，強調無麩質與蔬食。",
                "signature_dishes": ["佛陀碗", "青檸檬塔"],
                "atmosphere_tags": ["聚餐"],
                "booking_difficulty": "預約困難",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: None)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 12))

    done = await _collect_web_done(
        "明天晚上七點，我們部門 7 個人要聚餐。想找大安區適合聊天、不用講話用吼的義式餐廳。有人不能吃蝦蟹，兩位無肉不歡，預算一人 500 到 700。",
        "eval-demo-story-complex-department",
    )

    assert "我先把條件拆開" in done["answer"]
    assert "甲殼類過敏先避開蝦蟹" in done["answer"]
    assert "預算抓 NT$ 500-700/人" in done["answer"]
    assert "安全點餐" in done["answer"]
    assert "北海道干貝鮮蝦啵啵麵" not in done["answer"]
    assert all("鮮蝦" not in row["feature_highlight"] for row in done["comparison_rows"])


def test_eval_initial_complex_recommendation_keeps_two_options():
    query = "明天晚上7點，部門7個人聚餐，想找大安區適合聊天、不會太吵的義式餐廳。有人不能吃蝦蟹，有兩位偏愛肉類，預算一人200到400，有什麼選擇？"
    shops = [
        {
            "shop_id": 401,
            "name": "光司DATE 義大利麵 大安店",
            "district": "大安",
            "category_slug": "euro",
            "price_per_person": "$200-400",
            "ai_summary": "桌距充裕，適合部門聚餐慢慢聊天。",
            "signature_dishes": ["煙燻培根白醬", "粉紅醬雞肉麵", "松露燉飯"],
            "atmosphere_tags": ["部門聚餐", "安靜聊天"],
        },
        {
            "shop_id": 402,
            "name": "Lazy Pasta 慵懶義式廚房大安國館店",
            "district": "大安",
            "category_slug": "euro",
            "price_per_person": "$200-400",
            "ai_summary": "多人分食方便，也有雞肉與培根類主餐。",
            "signature_dishes": ["北海道干貝鮮蝦啵啵麵", "紅白醬雞肉菌菇寬麵", "奶油培根蛋黃麵"],
            "atmosphere_tags": ["部門聚餐", "安靜聊天"],
        },
        {
            "shop_id": 403,
            "name": "不二煮藝",
            "district": "大安",
            "category_slug": "euro",
            "price_per_person": "$400-600",
            "ai_summary": "菜色偏正式，價格略高。",
            "signature_dishes": ["嫩煎豬腰內菲力", "香煎辣味骰子牛"],
            "atmosphere_tags": ["部門聚餐"],
        },
    ]

    decision = main._validate_agent_decision(
        main.AgentRecommendationDecision(
            recommended_shop_ids=[401],
            rejected_shop_ids=[402, 403],
            rejection_summary="Lazy Pasta 有蝦蟹招牌，先保留作備案比較。",
        ),
        {"shops": shops},
        query,
    )

    assert decision.recommended_shop_ids[:2] == [401, 402]
    assert 402 not in decision.rejected_shop_ids
    assert "Lazy Pasta" not in (decision.rejection_summary or "")


def test_eval_demo_story_meat_budget_rerank_avoids_premium_outlier():
    query = (
        "明天晚上七點，我們部門 7 個人要聚餐。想找大安區適合聊天、"
        "不用講話用吼的燒肉或肉類餐廳。有人不能吃蝦蟹，預算一人 700 到 1200。"
    )
    shops = [
        {
            "shop_id": 501,
            "name": "初樂燒肉",
            "district": "大安",
            "category_slug": "yakiniku",
            "price_per_person": "$700-1000",
            "ai_summary": "環境乾淨，適合朋友聚餐，出餐速度穩定。",
            "signature_dishes": ["牛五花套餐", "豬霜降套餐", "牛舌"],
            "atmosphere_tags": ["聚餐", "舒適"],
            "booking_difficulty": "可線上訂位",
        },
        {
            "shop_id": 502,
            "name": "樂軒和牛專門店",
            "district": "大安",
            "category_slug": "yakiniku",
            "price_per_person": "$3180-8800",
            "ai_summary": "高級和牛燒肉，適合請客。",
            "signature_dishes": ["和牛套餐", "牛舌"],
            "atmosphere_tags": ["聚餐", "舒適"],
            "booking_difficulty": "可線上訂位",
        },
        {
            "shop_id": 503,
            "name": "肉你好燒肉-延吉店",
            "district": "大安",
            "category_slug": "yakiniku",
            "price_per_person": "$800-1200",
            "ai_summary": "多人聚餐可共享肉盤，桌距舒適。",
            "signature_dishes": ["牛小排", "松阪豬", "雞腿肉"],
            "atmosphere_tags": ["聚餐", "舒適"],
            "booking_difficulty": "可線上訂位",
        },
    ]

    ordered = main._prioritize_contextual_recommended_ids(query, [501, 502, 503], shops)

    assert ordered[:2] == [503, 501]
    assert ordered[-1] == 502
    assert "燒肉" in main._agent_story_frame(query)
    assert "大安義式" not in main._agent_story_frame(query)


def test_eval_agent_price_label_extracts_review_price_range():
    shop = {
        "name": "光司DATE 義大利麵 大安店",
        "district": "大安",
        "ai_summary": "Google 平均每人 $200-400，份量充足，適合聚餐。",
        "price_per_person": "未提及",
    }

    assert main._agent_price_label(shop) == "$200-400"


def test_eval_agent_price_label_uses_media_manifest_price():
    shop = {
        "shop_id": 10673,
        "name": "光司DATE 義大利麵 大安店",
        "district": "大安",
        "price_per_person": "未提及",
    }

    assert main._agent_price_label(shop) == "$200-400"


@pytest.mark.anyio
async def test_eval_recommendation_advice_uses_previous_demo_context(monkeypatch):
    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "明天晚上 7 點，7 個人部門聚餐，想找大安區適合聊天、不會太吵的餐廳。"},
            {
                "role": "model",
                "content": "我整理了三間。",
                "recommendation": {
                    "query": "明天晚上 7 點，7 個人部門聚餐，想找大安區適合聊天、不會太吵的餐廳。",
                    "shops": [
                        {
                            "shop_id": 401,
                            "name": "光司DATE 義大利麵 大安店",
                            "district": "大安",
                            "avg_price": 520,
                            "price_per_person": "未提及",
                            "ai_summary": "二樓座位區採光良好，桌距充裕，氛圍溫馨自在，適合朋友聚餐慢慢聊天。",
                            "signature_dishes": ["煙燻培根白醬", "松露燉飯", "粉紅醬雞肉麵"],
                            "atmosphere_tags": ["約會", "聚餐", "一人"],
                            "booking_difficulty": "未提及",
                        },
                        {
                            "shop_id": 402,
                            "name": "Lazy Pasta 慵懶義式廚房大安國館店",
                            "district": "大安",
                            "price_per_person": "未提及",
                            "ai_summary": "明亮簡潔，適合聚餐，但離場時間與節奏掌控較明確。",
                            "signature_dishes": ["北海道干貝鮮蝦啵啵麵", "奶油培根蛋黃麵"],
                            "atmosphere_tags": ["聚餐", "親子"],
                            "booking_difficulty": "現場可入",
                        },
                        {
                            "shop_id": 403,
                            "name": "知初植物系永續廚房",
                            "district": "大安",
                            "price_per_person": "$400以上",
                            "ai_summary": "光線柔和且座位間距寬敞，強調無麩質與蔬食。",
                            "signature_dishes": ["佛陀碗", "青檸檬塔"],
                            "atmosphere_tags": ["聚餐"],
                            "booking_difficulty": "預約困難",
                        },
                    ],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("advice should bypass model")))

    done = await _collect_web_done("這三家你會怎麼幫我選？推薦什麼菜，有什麼要避雷？", "eval-demo-advice-koji")

    assert done["tools_used"] == []
    assert "優先選「光司DATE 義大利麵 大安店」" in done["answer"]
    assert "煙燻培根白醬" in done["answer"]
    assert "訂位備註可寫希望安排較不吵的位置" in done["answer"]
    assert "未提及" not in done["answer"]
    assert "符合大安區" not in done["answer"]
    assert "適合 部門聚餐" not in done["answer"]
    assert len(done["answer"]) < 620


@pytest.mark.anyio
async def test_eval_recommendation_advice_handles_allergy_meat_budget_and_executives(monkeypatch):
    complex_query = (
        "明天晚上七點，我們部門 7 個人要聚餐。想找大安區適合聊天、不用講話用吼的義式餐廳。"
        "有人不能吃蝦蟹，兩位無肉不歡，預算一人 500 到 700。"
    )
    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": complex_query},
            {
                "role": "model",
                "content": "我整理了三間。",
                "recommendation": {
                    "query": complex_query,
                    "shops": [
                        {
                            "shop_id": 401,
                            "name": "光司DATE 義大利麵 大安店",
                            "district": "大安",
                            "avg_price": 520,
                            "ai_summary": "二樓座位區採光良好，桌距充裕，氛圍溫馨自在，適合朋友聚餐慢慢聊天。",
                            "signature_dishes": ["煙燻培根白醬", "松露燉飯", "粉紅醬雞肉麵"],
                            "atmosphere_tags": ["聚餐"],
                            "booking_difficulty": "未提及",
                        },
                        {
                            "shop_id": 402,
                            "name": "Lazy Pasta 慵懶義式廚房大安國館店",
                            "district": "大安",
                            "ai_summary": "明亮簡潔，適合聚餐，但離場時間與節奏掌控較明確。",
                            "signature_dishes": ["北海道干貝鮮蝦啵啵麵", "紅白醬雞肉菌菇寬麵", "奶油培根蛋黃麵"],
                            "atmosphere_tags": ["聚餐"],
                            "booking_difficulty": "現場可入",
                        },
                        {
                            "shop_id": 403,
                            "name": "知初植物系永續廚房",
                            "district": "大安",
                            "avg_price": 400,
                            "ai_summary": "光線柔和且座位間距寬敞，強調無麩質與蔬食。",
                            "signature_dishes": ["佛陀碗", "青檸檬塔"],
                            "atmosphere_tags": ["聚餐"],
                            "booking_difficulty": "預約困難",
                        },
                    ],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("advice should bypass model")))

    done = await _collect_web_done(
        "主管也會去，幫我看服務節奏、適合聊天程度、推薦菜、避雷跟預算。",
        "eval-demo-advice-complex-koji",
    )

    assert "結論：我會選「光司DATE 義大利麵 大安店」" in done["answer"]
    assert "安全點餐：煙燻培根白醬、粉紅醬雞肉麵、松露燉飯" in done["answer"]
    assert "蝦、蟹、龍蝦類不要放進建議菜單" in done["answer"]
    assert "主管在場" in done["answer"]
    assert "預算抓 NT$ 500-700/人" in done["answer"]
    assert "北海道干貝鮮蝦啵啵麵" not in done["answer"]


@pytest.mark.anyio
async def test_eval_fresh_complex_request_ignores_previous_advice_context(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [501, 502],
                "narrative": "模型原文不應直接使用。",
                "rejected_shop_ids": [],
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "燒肉" in query
        return [
            {
                "shop_id": 501,
                "name": "初樂燒肉",
                "district": "大安",
                "category_slug": "yakiniku",
                "price_per_person": "$700-1000",
                "ai_summary": "日系裝潢搭配柔和燈光，適合朋友聚餐。",
                "signature_dishes": ["厚切牛舌", "松阪豬", "牛五花"],
                "atmosphere_tags": ["聚餐", "舒適"],
                "booking_difficulty": "可線上訂位",
            },
            {
                "shop_id": 502,
                "name": "肉你好燒肉-延吉店",
                "district": "大安",
                "category_slug": "yakiniku",
                "price_per_person": "$800-1200",
                "ai_summary": "多人聚餐可共享肉盤，桌距舒適。",
                "signature_dishes": ["牛小排", "松阪豬", "雞腿肉"],
                "atmosphere_tags": ["聚餐", "舒適"],
                "booking_difficulty": "可線上訂位",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "舊的一輪推薦",
                "recommendation": {
                    "query": "明天晚上 7 點，7 個人部門聚餐，想找大安區適合聊天的義式餐廳。",
                    "shops": [
                        {"shop_id": 401, "name": "光司DATE 義大利麵 大安店", "district": "大安"},
                    ],
                },
            }
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 12))

    done = await _collect_web_done(
        "明天晚上七點，我們部門 7 個人要聚餐。想找大安區適合聊天、不用講話用吼的燒肉或肉類餐廳。有一位同事對甲殼類過敏，不能吃蝦蟹，兩位無肉不歡，預算一人 700 到 1200。",
        "eval-fresh-complex-ignores-advice-history",
    )

    assert done["tools_used"] == ["semantic_shop_search"]
    assert done["answer"].startswith("**結論：我先用")
    assert "**精選推薦**" in done["answer"]
    assert "初樂燒肉" in done["answer"]
    assert "光司DATE" not in done["answer"]


@pytest.mark.anyio
async def test_eval_demo_story_family_driving_recommendation(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [301, 302],
                "narrative": "我會優先看這兩家。",
                "rejected_shop_ids": [],
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "方便開車" in query
        return [
            {
                "shop_id": 301,
                "name": "信義家庭小館",
                "district": "信義",
                "mrt_station": "市政府",
                "category_slug": "chinese",
                "avg_price": 700,
                "ai_summary": "空間舒適，適合家庭與長輩同行。",
                "signature_dishes": ["雞湯", "合菜"],
                "atmosphere_tags": ["家庭", "舒適", "聚餐"],
                "booking_difficulty": "可線上訂位",
            },
            {
                "shop_id": 302,
                "name": "松壽長輩聚餐",
                "district": "信義",
                "mrt_station": "象山",
                "category_slug": "japanese",
                "avg_price": 950,
                "ai_summary": "座位安靜，適合長輩聚餐。",
                "signature_dishes": ["定食", "鍋物"],
                "atmosphere_tags": ["長輩", "安靜"],
                "booking_difficulty": "建議提前預約",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: None)

    query = "週六晚上要帶爸媽吃飯，想找信義區附近適合家庭聚餐、方便開車的餐廳。"
    done = await _collect_web_done(query, "eval-demo-story-family-driving")

    assert done["tools_used"] == ["semantic_shop_search"]
    assert "家庭" in done["answer"]
    assert "停車提醒" in done["answer"]
    assert "車位保留展示" in done["answer"]
    assert done["recommended_shop_ids"] == [301, 302]
    assert "家庭聚餐" in done["comparison_rows"][0]["best_for"]
    assert "開車用餐" in done["comparison_rows"][0]["best_for"]
    assert "停車" in done["comparison_rows"][0]["booking_status"]


@pytest.mark.anyio
async def test_eval_fresh_recommendation_ignores_stale_booking_draft(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "recommended_shop_ids": [301, 302],
                "narrative": "我改以這次家庭聚餐與開車需求重新篩選。",
                "rejected_shop_ids": [],
            },
            ensure_ascii=False,
        )

    async def fake_semantic_hits(query: str, top_k: int):
        assert "信義" in query
        assert "方便開車" in query
        return [
            {
                "shop_id": 301,
                "name": "信義家庭小館",
                "district": "信義",
                "mrt_station": "市政府",
                "category_slug": "chinese",
                "avg_price": 700,
                "ai_summary": "空間舒適，適合家庭與長輩同行。",
                "signature_dishes": ["雞湯", "合菜"],
                "atmosphere_tags": ["家庭", "舒適", "聚餐"],
                "booking_difficulty": "可線上訂位",
            },
            {
                "shop_id": 302,
                "name": "松壽長輩聚餐",
                "district": "信義",
                "mrt_station": "象山",
                "category_slug": "japanese",
                "avg_price": 950,
                "ai_summary": "座位安靜，適合長輩聚餐。",
                "signature_dishes": ["定食", "鍋物"],
                "atmosphere_tags": ["長輩", "安靜"],
                "booking_difficulty": "建議提前預約",
            },
        ]

    saved = {}
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "我幫你整理好訂位內容了。",
                "booking_draft": {
                    "shop_id": 10673,
                    "shop_name": "光司DATE 義大利麵 大安店",
                    "date": "2026-06-13",
                    "time": "19:00",
                    "people": 7,
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))

    query = "週六晚上要帶爸媽吃飯，想找信義區附近適合家庭聚餐、方便開車的餐廳。"
    done = await _collect_web_done(query, "eval-stale-draft-new-family-search")

    assert done["tools_used"] == ["semantic_shop_search"]
    assert done["booking_draft"] is None
    assert done["recommended_shop_ids"] == [301, 302]
    assert "光司DATE" not in done["answer"]
    assert "家庭" in done["answer"]
    assert saved["history"][-1]["recommendation"]["shops"][0]["shop_id"] == 301
    assert "booking_draft" not in saved["history"][-1]


def test_eval_new_recommendation_context_expires_older_booking_draft():
    history = [
        {
            "role": "model",
            "content": "我幫你整理好訂位內容了。",
            "booking_draft": {
                "shop_id": 10673,
                "shop_name": "光司DATE 義大利麵 大安店",
                "date": "2026-06-13",
                "time": "19:00",
                "people": 7,
            },
        },
        {
            "role": "model",
            "content": "我重新整理信義區家庭聚餐餐廳。",
            "recommendation": {
                "query": "信義區家庭聚餐",
                "shops": [{"shop_id": 301, "name": "信義家庭小館"}],
            },
        },
    ]

    assert main._latest_booking_draft(history) == {}


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
