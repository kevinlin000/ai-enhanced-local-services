import pytest

import app.main as main

from app.main import _line_should_force_recommendation_cards


def test_line_force_recommendation_cards_for_clear_restaurant_query():
    assert _line_should_force_recommendation_cards("推薦信義區高級火鍋")
    assert _line_should_force_recommendation_cards("信義區高級火鍋")
    assert _line_should_force_recommendation_cards("附近高級火鍋")


def test_line_force_recommendation_cards_skips_booking_and_payment_queries():
    assert not _line_should_force_recommendation_cards("我要訂信義區火鍋")
    assert not _line_should_force_recommendation_cards("我要付款訂金")


def test_line_location_context_merges_into_nearby_text():
    state = {"title": "台北101", "address": "台北市信義區市府路45號"}

    assert (
        main._line_effective_text_with_location("附近高級火鍋", state)
        == "台北市信義區市府路45號附近，附近高級火鍋"
    )
    assert main._line_effective_text_with_location("中山站附近火鍋", state) == "中山站附近火鍋"


def test_line_followup_adjustment_merge_rules():
    assert main._line_adjustment_intent("不要吃到飽")
    assert main._line_adjustment_intent("改成大安區")
    assert not main._line_adjustment_intent("還有嗎")
    assert main._line_merge_followup_query("信義區高級火鍋", "不要吃到飽") == "信義區高級火鍋，排除條件：不要吃到飽"
    assert main._line_merge_followup_query("信義區高級火鍋", "改成大安區") == "信義區高級火鍋，調整需求：改成大安區"


def test_premium_hotpot_key_prefers_luxury_cues_over_plain_hotpot():
    constraints = main._extract_query_constraints("信義區高級火鍋")
    orange = {
        "shop_id": 10009,
        "name": "橘色涮涮屋 信義館",
        "district": "信義區",
        "mrt_station": "市政府",
        "category_slug": "hotpot",
        "avg_price": 1200,
        "signature_dishes": ["海鮮套餐", "杏仁豆腐"],
        "atmosphere_tags": ["精緻", "商務"],
        "rerank_score": 0.1,
    }
    plain = {
        "shop_id": 10199,
        "name": "平價火鍋 信義店",
        "district": "信義區",
        "mrt_station": "市政府",
        "category_slug": "hotpot",
        "avg_price": 450,
        "signature_dishes": ["火鍋"],
        "atmosphere_tags": ["聚餐"],
        "rerank_score": 0.9,
    }

    assert main._premium_hotpot_key(constraints, orange) > main._premium_hotpot_key(constraints, plain)


@pytest.mark.anyio
async def test_line_reply_falls_back_to_flex_when_agent_skips_search(monkeypatch):
    async def fake_run_agent_turn(query: str, session_id: str):
        return "我推薦橘色涮涮屋。", [], {}

    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線，主打高品質食材與細緻服務。",
            }
        ]

    monkeypatch.setattr(main, "_run_agent_turn", fake_run_agent_turn)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "group", "groupId": "test-group"},
            "message": {"type": "text", "text": "推薦信義區高級火鍋"},
        }
    )

    assert len(messages) == 2
    assert messages[1]["type"] == "flex"
    bubble = messages[1]["contents"]["contents"][0]
    assert bubble["body"]["contents"][1]["text"] == "橘色涮涮屋 信義館"


@pytest.mark.anyio
async def test_line_user_recommendation_returns_cards_without_agent(monkeypatch):
    async def fail_run_agent_turn(query: str, session_id: str):
        raise AssertionError("clear line recommendation should not wait for agent text")

    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線。",
            }
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_run_agent_turn", fail_run_agent_turn)
    monkeypatch.setattr(main, "_start_line_background_recommendation", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_background_push_enabled", True)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "推薦信義區高級火鍋"},
        }
    )

    assert len(messages) == 2
    assert messages[1]["type"] == "flex"
    assert messages[1]["contents"]["contents"][0]["body"]["contents"][1]["text"] == "橘色涮涮屋 信義館"


def test_line_background_push_is_opt_in(monkeypatch):
    monkeypatch.setattr(main.settings, "line_background_push_enabled", False)

    assert not main._line_should_start_background_recommendation(
        {"type": "user"},
        "推薦信義區高級火鍋",
    )


@pytest.mark.anyio
async def test_line_text_uses_saved_location_context(monkeypatch):
    captured = {}

    async def fake_run_agent_turn(query: str, session_id: str):
        captured["query"] = query
        return "我推薦橘色涮涮屋。", [], {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["fallback_query"] = query
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線。",
            }
        ]

    monkeypatch.setattr(main, "_load_line_location_state", lambda user_id: {"address": "台北市信義區市府路45號"})
    monkeypatch.setattr(main, "_run_agent_turn", fake_run_agent_turn)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "附近高級火鍋"},
        }
    )

    assert captured["fallback_query"] == "台北市信義區市府路45號附近，附近高級火鍋"
    assert messages[1]["type"] == "flex"


@pytest.mark.anyio
async def test_line_card_request_replays_previous_cards(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線。",
            }
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10009]},
    )
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "給我圖卡啊"},
        }
    )

    assert captured["query"] == "信義區高級火鍋"
    assert messages[1]["type"] == "flex"
    assert messages[1]["contents"]["contents"][0]["body"]["contents"][1]["text"] == "橘色涮涮屋 信義館"


@pytest.mark.anyio
async def test_line_short_name_selects_previous_recommendation(monkeypatch):
    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線。",
            },
            {
                "shop_id": 10115,
                "name": "辛殿麻辣鍋｜信義店",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 900,
                "ai_summary": "麻辣鍋吃到飽。",
            },
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10009, 10115]},
    )
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "橘色"},
        }
    )

    bubbles = messages[1]["contents"]["contents"]
    assert len(bubbles) == 1
    assert bubbles[0]["body"]["contents"][1]["text"] == "橘色涮涮屋 信義館"


@pytest.mark.anyio
async def test_line_followup_adjustment_reuses_previous_query(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "mrt_station": "市政府",
                "avg_price": 1200,
                "ai_summary": "精緻涮涮屋路線。",
            }
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10115]},
    )
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "不要吃到飽"},
        }
    )

    assert captured["query"] == "信義區高級火鍋，排除條件：不要吃到飽"
    assert messages[1]["type"] == "flex"


@pytest.mark.anyio
async def test_line_followup_cancel_clears_previous_query(monkeypatch):
    cleared = {}
    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10115]},
    )
    monkeypatch.setattr(main, "_clear_line_recommendation_state", lambda user_id: cleared.setdefault("user_id", user_id))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "取消"},
        }
    )

    assert cleared["user_id"] == "test-user"
    assert "清掉剛剛的推薦條件" in messages[0]["text"]


def test_line_detail_helpers_use_manifest_reviews_and_photo_fallbacks(monkeypatch):
    monkeypatch.setattr(
        main,
        "_LINE_MEDIA_CACHE",
        {
            "shops": {
                "123": {
                    "galleryUrls": ["https://img.example/a.jpg", "https://img.example/b.jpg"],
                    "photoUrls": ["https://img.example/b.jpg", "https://img.example/c.jpg"],
                    "reviews": [
                        {"author": "A", "rating": 5, "text": "湯頭細緻，肉品和海鮮都有水準。"},
                        {"author": "B", "rating": 3, "text": "尖峰時段上菜稍慢，建議避開熱門時間。"},
                    ],
                }
            }
        },
    )
    monkeypatch.setattr(main, "best_shop_photo_url", lambda shop_id: "https://img.example/cover.jpg")

    candidates = main._line_photo_candidates(123)
    assert candidates == [
        "https://img.example/cover.jpg",
        "https://img.example/a.jpg",
        "https://img.example/b.jpg",
        "https://img.example/c.jpg",
    ]

    html = main._line_review_html(main._line_review_groups(123))
    assert "精選正負評" in html
    assert "正面摘要" in html
    assert "需要留意" in html
    assert "湯頭細緻" in html

    map_url = main._line_google_maps_uri("辛殿麻辣鍋", "台北市信義區")
    assert map_url.startswith("https://www.google.com/maps/search/")
    assert "query=" in map_url


def test_line_detail_helpers_use_orange_media_alias(monkeypatch):
    monkeypatch.setattr(
        main,
        "_LINE_MEDIA_CACHE",
        {
            "shops": {
                "10550": {
                    "galleryUrls": ["https://img.example/orange.jpg"],
                    "reviews": [
                        {"author": "A", "rating": 5, "text": "肉品、海鮮與服務都很細緻。"},
                        {"author": "B", "rating": 3, "text": "熱門時段建議先訂位。"},
                    ],
                }
            }
        },
    )
    monkeypatch.setattr(main, "best_shop_photo_url", lambda shop_id: None)

    assert main._line_photo_candidates(10009) == ["https://img.example/orange.jpg"]
    review_html = main._line_review_html(main._line_review_groups(10009))
    assert "肉品、海鮮與服務" in review_html
    assert "熱門時段建議先訂位" in review_html


def test_line_detail_helpers_normalize_rating_and_hours():
    assert main._line_display_rating(47) == "4.7"
    assert main._line_display_rating(4.0) == "4"
    assert main._line_business_hours(
        {"businessHours": '{"mon":"11:30-23:00","tue":"11:30-23:00"}'},
        {},
    ) == ["週一 11:30-23:00", "週二 11:30-23:00"]
    assert main._line_business_hours({"openHours": "11:30-23:00"}, {}) == ["每日 11:30-23:00"]


def test_line_booking_flex_pending_payment_has_pay_action(monkeypatch):
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    message = main._line_booking_flex_message(
        {
            "bookingCode": "BK-ABC",
            "shopId": 10009,
            "shopName": "橘色涮涮屋 信義館",
            "people": 2,
            "date": "2026-06-08",
            "time": "19:00",
            "status": "PENDING_PAYMENT",
            "needsDeposit": True,
            "depositTotal": 600,
        },
        "reserved",
        line_user_id="Uabc123",
    )

    footer = message["contents"]["footer"]["contents"]
    assert message["altText"] == "訂位保留成功，待付訂金"
    assert footer[0]["action"]["label"] == "立即繳訂金"
    assert "bookingCode=BK-ABC" in footer[0]["action"]["uri"]
    assert "lineUserId=Uabc123" in footer[0]["action"]["uri"]


def test_line_booking_result_page_shows_paid_completion(monkeypatch):
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    html = main._line_booking_result_page(
        10009,
        "橘色涮涮屋 信義館",
        {
            "bookingCode": "BK-ABC",
            "shopId": 10009,
            "shopName": "橘色涮涮屋 信義館",
            "people": 2,
            "date": "2026-06-08",
            "time": "19:00",
            "status": "PAID",
            "needsDeposit": True,
            "depositTotal": 600,
            "paymentTransId": "DEMO-123",
        },
    )

    assert "訂位完成" in html
    assert "已付款，訂位完成" in html
    assert "DEMO-123" in html


@pytest.mark.anyio
async def test_line_shop_detail_renders_concierge_sections(monkeypatch):
    async def fake_fetch_shop(shop_id: int):
        return {
            "id": shop_id,
            "name": "辛殿麻辣鍋｜信義店",
            "district": "信義區",
            "mrtStation": "市政府",
            "address": "台北市信義區松壽路",
            "avgPrice": 900,
            "score": 4.2,
            "comments": 5500,
            "businessHours": "週一至週日 11:30-22:00",
        }

    async def fake_fetch_metadata(shop_id: int):
        return {
            "aiSummary": "麻辣鍋吃到飽，肉品、海鮮與甜點選擇完整。",
            "signatureDishes": '["麻辣鍋", "海鮮拼盤"]',
            "atmosphereTags": '["聚餐", "信義商圈"]',
            "openingHours": '["週一至週日 11:30-22:00"]',
            "pricePerPerson": "NT$ 900",
            "bookingDifficulty": "建議提前訂位",
            "phone": "02-1234-5678",
        }

    async def fake_fetch_policy(shop_id: int):
        return {"needsDeposit": True, "depositPerPerson": 300, "reason": "熱門時段保留座位"}

    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_shop)
    monkeypatch.setattr(main, "_fetch_java_ai_metadata", fake_fetch_metadata)
    monkeypatch.setattr(main, "_fetch_java_booking_policy", fake_fetch_policy)
    monkeypatch.setattr(main, "_line_photo_candidates", lambda shop_id: ["https://img.example/cover.jpg"])
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(
        main,
        "_LINE_MEDIA_CACHE",
        {
            "shops": {
                "10115": {
                    "reviews": [
                        {"author": "A", "rating": 5, "text": "湯頭與肉品表現穩定。"},
                        {"author": "B", "rating": 3, "text": "尖峰時段要注意等候。"},
                    ]
                }
            }
        },
    )

    response = await main.line_shop_detail(10115)
    html = response.body.decode("utf-8")

    assert "https://img.example/cover.jpg" in html
    assert "/line/photo/10115" not in html
    assert "推薦依據" in html
    assert "精選正負評" in html
    assert "訂金與訂位規則" in html
    assert "Google 地圖開啟" in html
    assert "填日期人數" in html
