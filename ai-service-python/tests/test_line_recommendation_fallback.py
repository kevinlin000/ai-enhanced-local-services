import json

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


def test_zhishan_station_nearby_constraints_and_expansion_intro():
    constraints = main._extract_query_constraints("我想吃芝山站附近的火鍋")
    assert constraints["stations"] == ["芝山"]
    assert constraints["categories"] == ["hotpot"]

    selected = [
        {"name": "錢都日式涮涮鍋 士林芝山店", "district": "士林", "category_slug": "hotpot"},
        {"name": "山上走走 日式鍋物台北華山店", "district": "中正", "category_slug": "hotpot"},
        {"name": "麻凡麻辣火鍋", "district": "中山", "category_slug": "hotpot"},
    ]

    assert main._station_proximity_score(constraints, selected[0]) == 1.0
    intro = main._line_scope_expansion_intro("我想吃芝山站附近的火鍋", selected)
    assert intro
    assert "芝山站附近符合條件較少" in intro
    assert "擴大到台北火鍋" in intro


def test_resolve_taipei_district_accepts_simplified_area_suffix():
    assert main._resolve_taipei_district("104台北市中山区集英里抚顺街11號1樓", "大同") == "中山"
    assert main._resolve_taipei_district("110台北市信义区松山路11號", "南港") == "信義"
    assert main._resolve_taipei_district("114台北市内湖区民權東路六段", "南港") == "內湖"
    assert main._resolve_taipei_district("108台北市万华区漢中街", "中正") == "萬華"


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


def test_burger_hit_rejects_brunch_fillers():
    assert main._is_burger_hit({"name": "Bounce Back 美式漢堡"})
    assert main._is_burger_hit({"name": "TakeOut Burger&Cafe 忠孝新生店"})
    assert not main._is_burger_hit(
        {
            "name": (
                "鹿境早午餐 Arrival Brunch & Cafe - 早午餐推薦 ｜ 餐廳 ｜"
                "小巨蛋早午餐 ｜ 漢堡"
            )
        }
    )
    assert not main._is_burger_hit({"name": "軟食力 行天宮店"})


def test_prefer_rich_hits_filters_low_detail_seed_when_possible():
    hits = [
        {"shop_id": 10014, "name": "劉山東小牛肉麵 中山店"},
        {"shop_id": 10123, "name": "海霸王 中山店", "ai_summary": "中式聚餐。"},
        {"shop_id": 10124, "name": "小品雅廚", "signature_dishes": ["家常菜"]},
        {"shop_id": 10126, "name": "阿城鵝肉 吉林二店", "atmosphere_tags": ["聚餐"]},
    ]

    filtered = main._prefer_rich_hits(hits, top_k=3)

    assert [hit["shop_id"] for hit in filtered] == [10123, 10124, 10126]


@pytest.mark.anyio
async def test_web_agent_stream_forces_cards_when_model_skips_search(monkeypatch):
    class EmptyResponse:
        text = "我先用文字推薦青花驕。"

        class Candidate:
            class Content:
                parts = []

            content = Content()

        candidates = [Candidate()]

    async def fake_tool_semantic_search(query: str):
        return {
            "shops": [
                {"shop_id": 10022, "name": "青花驕 中山北店", "district": "中山區", "ai_summary": "中山聚餐。"},
                {"shop_id": 10123, "name": "海霸王 中山店", "district": "中山", "ai_summary": "中式聚餐。"},
            ]
        }

    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: EmptyResponse())
    monkeypatch.setattr(main, "tool_semantic_search", fake_tool_semantic_search)
    monkeypatch.setattr(
        main,
        "_build_agent_recommendation_decision",
        lambda query, tool_result: main.AgentRecommendationDecision(
            recommended_shop_ids=[10022, 10123],
            narrative="我推薦青花驕與海霸王。",
            rejected_shop_ids=[],
        ),
    )

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "推薦中山區的中式餐廳",
            "test-web-stream",
        )
    ]

    done = events[-1]
    assert "semantic_shop_search" in done["tools_used"]
    assert done["recommended_shop_ids"] == [10022, 10123]
    assert [shop["shop_id"] for shop in done["tool_result"]["shops"]] == [10022, 10123]


@pytest.mark.anyio
async def test_tool_semantic_search_returns_hydrated_shops_and_scope_note(monkeypatch):
    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10680,
                "name": "TakeOut Burger&Cafe 民權店",
                "district": "中山",
                "category": "美式料理",
            },
            {
                "shop_id": 10201,
                "name": "Juicy Bun Burger 政大店",
                "district": "文山",
                "category": "美式料理",
                "ai_summary": "政大附近美式漢堡。",
            },
            {
                "shop_id": 10746,
                "name": "Lin’s Burger 台北信義店",
                "district": "信義",
                "category": "美式料理",
                "ai_summary": "信義區美式餐廳。",
            },
        ]

    async def fake_fetch_metadata(shop_id: int):
        return {
            "aiSummary": "主打厚實漢堡與美式餐點。",
            "signatureDishes": '["牛肉漢堡", "薯條"]',
            "atmosphereTags": '["朋友聚餐"]',
            "pricePerPerson": "NT$ 300-600",
        }

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_fetch_java_ai_metadata", fake_fetch_metadata)

    result = await main.tool_semantic_search("推薦中山區高級漢堡店")

    assert result["scope_note"].startswith("中山區符合條件較少，我先擴大到台北漢堡店")
    assert result["shops"][0]["ai_summary"] == "主打厚實漢堡與美式餐點。"
    assert result["shops"][0]["signature_dishes"] == ["牛肉漢堡", "薯條"]


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


@pytest.mark.anyio
async def test_line_cards_hydrate_selected_shop_metadata(monkeypatch):
    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10680,
                "name": "TakeOut Burger&Cafe 民權店",
                "district": "中山",
                "category": "american",
                "avg_price": 450,
            }
        ]

    async def fake_fetch_metadata(shop_id: int):
        return {
            "aiSummary": "主打厚實漢堡與美式餐點，適合想吃肉感漢堡的聚餐。",
            "signatureDishes": '["牛肉漢堡", "薯條"]',
            "atmosphereTags": '["朋友聚餐", "快速用餐"]',
            "pricePerPerson": "NT$ 300-600",
        }

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_fetch_java_ai_metadata", fake_fetch_metadata)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_cards_for_query("推薦中山區高級漢堡店", "test-user")
    payload = json.dumps(messages, ensure_ascii=False)

    assert "主打厚實漢堡" in payload
    assert "招牌重點：牛肉漢堡、薯條" in payload
    assert "用餐情境：朋友聚餐、快速用餐" in payload


@pytest.mark.anyio
async def test_line_burger_reply_explains_expanded_scope(monkeypatch):
    async def fail_run_agent_turn(query: str, session_id: str):
        raise AssertionError("clear line recommendation should not wait for agent text")

    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10201,
                "name": "Juicy Bun Burger 就是棒 美式餐廳 政大店",
                "district": "文山",
                "category": "美式料理",
            },
            {
                "shop_id": 10746,
                "name": "林斯漢堡美式餐廳Lin’s Burger 台北信義店",
                "district": "信義",
                "category": "美式料理",
            },
            {
                "shop_id": 10618,
                "name": "TakeOut Burger&Cafe 忠孝新生店",
                "district": "中正",
                "category": "美式料理",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_run_agent_turn", fail_run_agent_turn)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "推薦中山區高級漢堡店"},
        }
    )

    assert messages[0]["text"].startswith("中山區符合條件較少，我先擴大到台北漢堡店")
    assert len(messages[1]["contents"]["contents"]) == 3


@pytest.mark.anyio
async def test_line_agent_cards_explain_station_scope_expansion(monkeypatch):
    async def fake_run_agent_turn(query: str, session_id: str):
        return (
            "我先幫你整理 3 間符合需求的餐廳。",
            ["semantic_shop_search"],
            {
                "shops": [
                    {
                        "shop_id": 10344,
                        "name": "錢都日式涮涮鍋 士林芝山店",
                        "district": "士林",
                        "category_slug": "hotpot",
                    },
                    {
                        "shop_id": 10687,
                        "name": "山上走走 日式鍋物台北華山店",
                        "district": "中正",
                        "category_slug": "hotpot",
                    },
                    {
                        "shop_id": 10481,
                        "name": "麻凡麻辣火鍋",
                        "district": "中山",
                        "category_slug": "hotpot",
                    },
                ],
                "agent_decision": {"recommended_shop_ids": [10344, 10687, 10481]},
            },
        )

    monkeypatch.setattr(main, "_run_agent_turn", fake_run_agent_turn)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_agent_recommendation_messages("我想吃芝山站附近的火鍋", "test-user")

    assert messages[0]["text"].startswith("芝山站附近符合條件較少")
    assert "擴大到台北火鍋" in messages[0]["text"]
    assert messages[1]["type"] == "flex"


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
    assert "lineUserId=" not in footer[0]["action"]["uri"]
    assert "lt=v1." in footer[0]["action"]["uri"]


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


def test_line_availability_flex_prefills_booking_link(monkeypatch):
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    message = main._line_availability_flex_message(
        {
            "lineUserId": "Uabc123",
            "shopId": 10009,
            "shopName": "橘色涮涮屋 信義館",
            "date": "2026-06-08",
            "time": "19:00",
            "tableType": "normal",
            "people": 2,
        }
    )

    assert message["altText"] == "橘色涮涮屋 信義館 有空位了"
    booking_uri = message["contents"]["footer"]["contents"][0]["action"]["uri"]
    assert booking_uri.startswith("https://bytebites.example.com/line/book/10009?")
    assert "lineUserId=" not in booking_uri
    assert "lt=v1." in booking_uri
    assert "date=2026-06-08" in booking_uri
    assert "time=19%3A00" in booking_uri


@pytest.mark.anyio
async def test_internal_availability_released_pushes_line_card(monkeypatch):
    pushed = {}

    async def fake_push_messages(user_id, messages, channel_access_token, enabled):
        pushed["user_id"] = user_id
        pushed["messages"] = messages
        return {"ok": True}

    monkeypatch.setattr(main, "push_messages", fake_push_messages)
    monkeypatch.setattr(main.settings, "line_internal_webhook_secret", "secret")

    class FakeRequest:
        async def json(self):
            return {
                "secret": "secret",
                "lineUserId": "Uabc123",
                "shopId": 10009,
                "shopName": "橘色涮涮屋 信義館",
                "date": "2026-06-08",
                "time": "19:00",
                "tableType": "normal",
                "people": 2,
            }

    response = await main.internal_line_availability_released(FakeRequest())

    assert response["ok"] is True
    assert pushed["user_id"] == "Uabc123"
    assert pushed["messages"][0]["type"] == "flex"


@pytest.mark.anyio
async def test_internal_booking_updated_pushes_cancel_card(monkeypatch):
    pushed = {}

    async def fake_push_messages(user_id, messages, channel_access_token, enabled):
        pushed["user_id"] = user_id
        pushed["messages"] = messages
        return {"ok": True}

    monkeypatch.setattr(main, "push_messages", fake_push_messages)
    monkeypatch.setattr(main.settings, "line_internal_webhook_secret", "secret")

    class FakeRequest:
        async def json(self):
            return {
                "secret": "secret",
                "lineUserId": "Uabc123",
                "phase": "canceled",
                "booking": {
                    "bookingCode": "BK-CANCEL",
                    "shopId": 10009,
                    "shopName": "橘色涮涮屋 信義館",
                    "date": "2026-06-08",
                    "time": "19:00",
                    "people": 2,
                    "status": "CANCELED",
                    "needsDeposit": True,
                    "depositTotal": 600,
                },
            }

    response = await main.internal_line_booking_updated(FakeRequest())

    assert response["ok"] is True
    assert pushed["user_id"] == "Uabc123"
    assert pushed["messages"][0]["altText"] == "訂位已取消"


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
