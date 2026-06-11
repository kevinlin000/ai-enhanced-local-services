import json

import pytest

import app.main as main

from app.main import _line_should_force_recommendation_cards


def test_line_force_recommendation_cards_for_clear_restaurant_query():
    assert _line_should_force_recommendation_cards("推薦信義區高級火鍋")
    assert _line_should_force_recommendation_cards("信義區高級火鍋")
    assert not _line_should_force_recommendation_cards("附近高級火鍋")
    assert _line_should_force_recommendation_cards("韓式料理")


def test_line_force_recommendation_cards_skips_booking_and_payment_queries():
    assert not _line_should_force_recommendation_cards("我要訂信義區火鍋")
    assert not _line_should_force_recommendation_cards("我要付款訂金")


def test_agent_response_contract_orders_shops_and_builds_comparison_rows():
    payload = main._agent_response_contract(
        {
            "agent_decision": {
                "recommended_shop_ids": [3, 1],
                "narrative": "推薦 B 與 A。",
                "rejected_shop_ids": [2],
                "rejection_summary": None,
            },
            "scope_note": "附近符合條件較少，已擴大搜尋。",
            "transaction": {
                "kind": "booking",
                "success": True,
                "status": "PENDING_PAYMENT",
                "booking_code": "BK-CONTRACT-001",
            },
            "shops": [
                {
                    "shop_id": 1,
                    "name": "候選 A",
                    "district": "中山",
                    "avg_price": 500,
                    "ai_summary": "適合聊天的餐廳。",
                },
                {
                    "shop_id": 2,
                    "name": "候選 C",
                    "district": "信義",
                    "category": "美式料理",
                    "ai_summary": "資料較少。",
                },
                {
                    "shop_id": 3,
                    "name": "候選 B",
                    "district": "大安",
                    "mrt_station": "忠孝復興",
                    "price_per_person": "NT$ 450-650",
                    "signature_dishes": ["厚切牛肉堡", "奶昔"],
                    "atmosphere_tags": ["約會", "餐酒館"],
                    "booking_difficulty": "可線上訂位，建議提前",
                },
            ],
        }
    )

    assert payload["recommended_shop_ids"] == [3, 1]
    assert [shop["shop_id"] for shop in payload["shops"]] == [3, 1, 2]
    assert payload["scope_note"] == "附近符合條件較少，已擴大搜尋。"
    assert payload["transaction"]["booking_code"] == "BK-CONTRACT-001"
    assert payload["comparison_rows"][0] == {
        "shop_id": 3,
        "name": "候選 B",
        "feature_highlight": "招牌：厚切牛肉堡、奶昔",
        "best_for": "約會、餐酒館",
        "booking_status": "可線上訂位，建議提前",
        "meta": "NT$ 450-650 · 大安 · 捷運忠孝復興",
    }


def test_agent_concierge_narrative_uses_stable_decision_format():
    narrative = main._agent_concierge_narrative(
        "推薦大安區美式漢堡",
        {
            "shops": [
                {
                    "shop_id": 10549,
                    "name": "Fa Burger",
                    "district": "大安",
                    "category": "美式料理",
                    "category_slug": "american",
                    "signature_dishes": ["巧巴達粉嫩牛"],
                    "atmosphere_tags": ["聚餐"],
                    "booking_difficulty": "預約困難",
                },
                {
                    "shop_id": 10755,
                    "name": "樂漢堡美式餐廳 台北大安店",
                    "district": "大安",
                    "category": "美式料理",
                    "category_slug": "american",
                    "signature_dishes": ["風味起司漢堡"],
                    "atmosphere_tags": ["親子"],
                },
                {
                    "shop_id": 10638,
                    "name": "Takeout Burger&Cafe 延吉店 （最後點餐21：30）/美式漢堡/寵物友善/大安區美食",
                    "district": "大安",
                    "category": "美式料理",
                    "category_slug": "american",
                    "signature_dishes": ["蒜味乳酪漢堡", "塔塔醬炸魚堡", "松露漢堡"],
                    "atmosphere_tags": ["聚餐", "寵物友善"],
                },
            ]
        },
        main.AgentRecommendationDecision(
            recommended_shop_ids=[10549, 10755, 10638],
            narrative="模型原始長文不應直接控制最終格式。",
            rejected_shop_ids=[],
        ),
    )

    assert narrative.startswith("我先用「大安區 / 漢堡店」幫你篩，優先看這 3 家。")
    assert "1. Fa Burger：招牌 巧巴達粉嫩牛；適合 聚餐；訂位：預約困難。" in narrative
    assert "2. 樂漢堡美式餐廳 台北大安店：招牌 風味起司漢堡；適合 親子；訂位：可線上訂位，建議確認。" in narrative
    assert "3. Takeout Burger&Cafe 延吉店：招牌 蒜味乳酪漢堡、塔塔醬炸魚堡；適合 聚餐、寵物友善；訂位：可線上訂位，建議確認。" in narrative
    assert "最後點餐" not in narrative
    assert "大安區美食" not in narrative
    assert "下一步：告訴我日期、時間與人數" in narrative


def test_session_history_compacts_recommendation_context():
    compacted = main.session_store.compact_history(
        [
            {
                "role": "model",
                "content": "推薦青田七六。",
                "recommendation": {
                    "query": "青田七六",
                    "shops": [
                        {"shop_id": 10222, "name": "青田七六", "large": "ignored"},
                        {
                            "shop_id": 10223,
                            "name": "備選",
                            "district": "大安",
                            "category": "中式料理",
                            "ai_summary": "適合聊天。",
                            "signature_dishes": ["三杯雞"],
                            "atmosphere_tags": ["聊天"],
                            "booking_difficulty": "可線上訂位",
                        },
                    ],
                },
            }
        ]
    )

    assert compacted == [
        {
            "role": "model",
            "content": "推薦青田七六。",
            "recommendation": {
                "query": "青田七六",
                "shops": [
                    {"shop_id": 10222, "name": "青田七六"},
                        {
                            "shop_id": 10223,
                            "name": "備選",
                            "district": "大安",
                            "category": "中式料理",
                            "ai_summary": "適合聊天。",
                            "signature_dishes": ["三杯雞"],
                            "atmosphere_tags": ["聊天"],
                        "booking_difficulty": "可線上訂位",
                    },
                ],
            },
        }
    ]


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
    assert main._line_more_recommendation_intent("不要第二間")
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


def test_taiwanese_cuisine_query_rejects_bistro_fillers():
    constraints = main._extract_query_constraints("適合商務請客的台菜")
    assert constraints["categories"] == ["chinese"]
    assert constraints["wants_taiwanese_cuisine"]

    taicai = {
        "name": "欣葉台菜創始店",
        "category_slug": "chinese",
        "avg_price": 1200,
        "rating": 4.5,
        "ai_summary": "老字號台菜與合菜餐廳，適合商務請客與家庭聚餐。",
        "signature_dishes": ["煎豬肝", "三杯雞"],
        "atmosphere_tags": ["商務", "聚餐"],
        "rerank_score": 0.1,
    }
    bistro = {
        "name": "紅皇后川酒・RED QUEEN BISTRO",
        "category_slug": "chinese",
        "avg_price": 1100,
        "rating": 4.5,
        "ai_summary": "中式餐酒館，主打調酒、小酌與聚會氣氛。",
        "signature_dishes": ["藤椒浪花白肉"],
        "atmosphere_tags": ["餐酒館", "聚餐"],
        "rerank_score": 0.9,
    }
    korean_pasta = {
        "name": "金孫韓廚 義大利麵 (中山店)",
        "category_slug": "chinese",
        "avg_price": 480,
        "rating": 4.5,
        "ai_summary": "韓義混血料理，韓國辣醬魷魚義大利麵與海鮮煎餅是熱門選擇。",
        "signature_dishes": ["韓國辣醬魷魚義大利麵", "海鮮煎餅"],
        "atmosphere_tags": ["聚餐"],
        "rerank_score": 1.1,
    }

    assert main._has_taiwanese_cuisine_semantics(taicai)
    assert not main._is_taiwanese_cuisine_mismatch(taicai)
    assert main._is_taiwanese_cuisine_mismatch(bistro)
    assert main._is_taiwanese_cuisine_mismatch(korean_pasta)
    assert main._matches_requested_category(taicai, constraints)
    assert not main._matches_requested_category(korean_pasta, constraints)
    assert (
        main._taiwanese_cuisine_sort_key(constraints, taicai)
        > main._taiwanese_cuisine_sort_key(constraints, bistro)
    )
    assert main._metadata_bonus("適合商務請客的台菜", taicai) > main._metadata_bonus(
        "適合商務請客的台菜",
        bistro,
    )

    business_taicai = {
        "name": "新東南海鮮餐廳 松山店",
        "category_slug": "chinese",
        "avg_price": 1500,
        "rating": 44,
        "ai_summary": "海鮮台菜，適合商務宴客與多人合菜。",
        "signature_dishes": ["龍蝦三明治"],
        "atmosphere_tags": ["商務", "聚餐"],
        "rerank_score": 2.7,
    }
    popular_taicai = {
        "name": "享鴨 烤鴨與中華料理 台北忠孝東店",
        "category_slug": "chinese",
        "avg_price": 885,
        "rating": 48,
        "ai_summary": "烤鴨與熱炒，適合朋友家庭聚餐。",
        "signature_dishes": ["烤鴨"],
        "atmosphere_tags": ["聚餐"],
        "rerank_score": 2.4,
    }

    assert main._normalized_rating(48) == 4.8
    assert (
        main._taiwanese_cuisine_sort_key(constraints, business_taicai)
        > main._taiwanese_cuisine_sort_key(constraints, popular_taicai)
    )


def test_context_intent_bonus_prefers_quiet_chat_fit():
    quiet_shop = {
        "name": "大安舒適小館",
        "district": "大安",
        "category_slug": "euro",
        "ai_summary": "空間舒適，桌距寬敞，適合久坐聊天與放鬆聚餐。",
        "atmosphere_tags": ["安靜", "聊天"],
    }
    noisy_shop = {
        "name": "大安熱炒酒場",
        "district": "大安",
        "category_slug": "chinese",
        "ai_summary": "下班時段喧囂熱鬧，桌距偏近，適合小酌，油煙感明顯。",
        "atmosphere_tags": ["聚餐"],
    }

    query = "大安區適合聊天聚餐"

    assert main._context_intent_bonus(query, quiet_shop) > 0
    assert main._context_intent_bonus(query, noisy_shop) < 0
    assert main._metadata_bonus(query, quiet_shop) > main._metadata_bonus(query, noisy_shop)
    assert "適合 安靜聊天、聚餐" in main._agent_shop_line(quiet_shop, 1, query)


def test_explicit_chinese_query_rejects_conflicting_cuisine_identity():
    constraints = main._extract_query_constraints("中山區中式料理")
    assert constraints["categories"] == ["chinese"]
    assert constraints["districts"] == ["中山"]

    chinese = {
        "name": "雞家莊本店",
        "district": "中山",
        "category_slug": "chinese",
        "ai_summary": "老字號台菜餐廳，招牌三味雞與家庭聚餐合菜。",
    }
    stale_korean = {
        "name": "金孫韓廚 義大利麵 (中山店)",
        "district": "中山",
        "category_slug": "chinese",
        "ai_summary": "韓義混血料理，韓國辣醬魷魚義大利麵與海鮮煎餅是熱門選擇。",
    }
    euro_bistro = {
        "name": "WOWFFIZI cafe&Bistro 烏菲茲餐酒館",
        "district": "中山",
        "category_slug": "chinese",
        "ai_summary": "餐酒館，主打義大利麵、燉飯與紅白酒。",
    }

    assert main._matches_requested_category(chinese, constraints)
    assert not main._matches_requested_category(stale_korean, constraints)
    assert not main._matches_requested_category(euro_bistro, constraints)


def test_inactive_search_hit_detects_closed_restaurants():
    assert main._is_inactive_search_hit({"name": "【設備整修暫停營業】心潮飯店"})
    assert main._is_inactive_search_hit({"name": "測試餐廳", "is_active": False})
    assert not main._is_inactive_search_hit({"name": "欣葉台菜創始店", "is_active": True})


def test_specific_cuisine_constraints_keep_misclassified_real_matches():
    korean_constraints = main._extract_query_constraints("韓式料理")
    assert korean_constraints["categories"] == ["korean"]
    assert korean_constraints["specific_cuisines"] == ["korean"]

    korean_bbq = {
        "name": "本家BORNGA韓式燒肉 敦南店",
        "category_slug": "yakiniku",
        "category": "日式燒肉",
        "ai_summary": "韓國烤肉與韓式小菜。",
        "rerank_score": 0.2,
    }
    japanese_yakiniku = {
        "name": "發肉燒肉餐酒忠孝二店",
        "category_slug": "yakiniku",
        "category": "日式燒肉",
        "ai_summary": "日式和牛燒肉，附韓式泡菜小菜。",
        "rerank_score": 0.9,
    }

    assert main._matches_specific_cuisine(korean_bbq, "korean")
    assert not main._is_specific_cuisine_mismatch(korean_bbq, "korean")
    assert not main._matches_specific_cuisine(japanese_yakiniku, "korean")
    assert main._is_specific_cuisine_mismatch(japanese_yakiniku, "korean")
    assert (
        main._specific_cuisine_sort_key("korean", korean_bbq)
        > main._specific_cuisine_sort_key("korean", japanese_yakiniku)
    )


def test_specific_cuisine_constraints_for_thai_and_indian_queries():
    thai_constraints = main._extract_query_constraints("泰式料理")
    indian_constraints = main._extract_query_constraints("印度料理")
    assert thai_constraints["categories"] == ["international"]
    assert thai_constraints["specific_cuisines"] == ["thai"]
    assert indian_constraints["categories"] == ["international"]
    assert indian_constraints["specific_cuisines"] == ["indian"]

    thai = {
        "name": "非常泰 - 南港中信店",
        "category_slug": "chinese",
        "ai_summary": "泰式料理，招牌月亮蝦餅與打拋豬。",
        "rerank_score": 0.1,
    }
    unrelated_international = {
        "name": "BaganHood 蔬食餐酒館",
        "category_slug": "vegetarian",
        "ai_summary": "異國蔬食餐酒館，提供泰式茶飲。",
        "rerank_score": 0.9,
    }
    indian = {
        "name": "亞瑟蘭印度餐廳(士林店)Asrah Indian Cuisines 清真認證Halal",
        "category_slug": "chinese",
        "ai_summary": "印度料理與清真餐點。",
        "rerank_score": 0.1,
    }
    japanese_curry = {
        "name": "Moni咖哩",
        "category_slug": "japanese",
        "ai_summary": "日式咖哩飯，帶有印度風味香料。",
        "rerank_score": 0.9,
    }

    assert main._matches_specific_cuisine(thai, "thai")
    assert not main._matches_specific_cuisine(unrelated_international, "thai")
    assert main._matches_specific_cuisine(indian, "indian")
    assert main._is_specific_cuisine_mismatch(japanese_curry, "indian")


def test_prefer_rich_hits_filters_legacy_seed_when_possible():
    hits = [
        {"shop_id": 10009, "name": "橘色涮涮屋 信義館", "ai_summary": "高級火鍋。"},
        {"shop_id": 10014, "name": "劉山東小牛肉麵 中山店"},
        {"shop_id": 10123, "name": "海霸王 中山店", "ai_summary": "中式聚餐。"},
        {"shop_id": 10124, "name": "小品雅廚", "signature_dishes": ["家常菜"]},
        {"shop_id": 10126, "name": "阿城鵝肉 吉林二店", "atmosphere_tags": ["聚餐"]},
    ]

    filtered = main._prefer_rich_hits(hits, top_k=3)

    assert [hit["shop_id"] for hit in filtered] == [10123, 10124, 10126]


def test_prefer_rich_hits_returns_empty_when_only_legacy_seed_matches():
    hits = [
        {"shop_id": 10009, "name": "橘色涮涮屋 信義館", "ai_summary": "高級火鍋。"},
        {"shop_id": 10014, "name": "劉山東小牛肉麵 中山店"},
    ]

    assert main._prefer_rich_hits(hits, top_k=3) == []


def test_specific_shop_keyword_ignores_vague_or_time_only_followups():
    assert main._specific_shop_keyword("那我要青田七六好了") == "青田七六"
    assert main._specific_shop_keyword("？你怎麼推薦這個？我要青田七六") == "青田七六"
    assert main._specific_shop_keyword("我要訂青田七六明天晚上19點 4人") == "青田七六"
    assert main._specific_shop_keyword("我要訂青田七六下週五晚上7點 4人") == "青田七六"
    assert main._specific_shop_keyword("預約青田七六 4人") == "青田七六"
    assert main._specific_shop_keyword("明天 晚上") == ""
    assert main._specific_shop_keyword("推薦7人聚餐餐廳") == ""
    assert main._specific_shop_keyword("大安區，適合聊天") == ""
    assert main._restaurant_need_clarification("推薦7人聚餐餐廳")
    assert not main._restaurant_need_clarification("推薦7人聚餐餐廳，大安區，適合聊天")
    assert main._selection_index_from_text("第一間") == 0
    assert main._selection_index_from_text("訂第二家明天晚上") == 1
    assert main._selection_index_from_text("第3個 4人") == 2


def test_booking_prefill_parses_weekday_dates(monkeypatch):
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    assert main._line_booking_prefill_from_text("下週五晚上7點 4人") == {
        "date": "2026-06-19",
        "time": "19:00",
        "people": 4,
    }
    assert main._line_booking_prefill_from_text("週五晚上7點半 4人") == {
        "date": "2026-06-12",
        "time": "19:30",
        "people": 4,
    }
    assert main._line_booking_prefill_from_text("星期六中午 兩人") == {
        "date": "2026-06-13",
        "time": "12:00",
        "people": 2,
    }


def test_restaurant_clarification_text_targets_missing_fields():
    group_text = main._restaurant_clarification_text("推薦7人聚餐餐廳")
    assert "7人我先記下" in group_text
    assert "地點或捷運站" in group_text
    assert "料理類型或氣氛" in group_text
    assert "日期或時段" in group_text

    district_text = main._restaurant_clarification_text("大安區餐廳")
    assert "地點或捷運站" not in district_text
    assert "料理類型或氣氛" in district_text

    nearby_text = main._restaurant_clarification_text("附近高級火鍋")
    assert "位置或捷運站" in nearby_text


@pytest.mark.anyio
async def test_web_agent_stream_clarifies_vague_group_need(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("vague restaurant needs should be clarified before model search")

    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "推薦7人聚餐餐廳",
            "test-vague-web",
        )
    ]

    done = events[-1]
    assert done["tools_used"] == []
    assert "7人我先記下" in done["answer"]
    assert "直接回一句就好" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_merges_clarification_followup(monkeypatch):
    captured = {}

    class EmptyResponse:
        text = "我先整理。"

        class Candidate:
            class Content:
                parts = []

            content = Content()

        candidates = [Candidate()]

    async def fake_tool_semantic_search(query: str):
        captured["query"] = query
        return {
            "shops": [
                {
                    "shop_id": 10101,
                    "name": "大安聊天餐館",
                    "district": "大安",
                    "ai_summary": "座位寬敞，適合多人聊天。",
                }
            ]
        }

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "推薦7人聚餐餐廳"},
            {"role": "model", "content": main._restaurant_clarification_text()},
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: EmptyResponse())
    monkeypatch.setattr(main, "tool_semantic_search", fake_tool_semantic_search)
    monkeypatch.setattr(
        main,
        "_build_agent_recommendation_decision",
        lambda query, tool_result: main.AgentRecommendationDecision(
            recommended_shop_ids=[10101],
            narrative="我會優先看大安聊天餐館。",
            rejected_shop_ids=[],
        ),
    )

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "大安區，適合聊天",
            "test-clarify-followup",
        )
    ]

    done = events[-1]
    assert captured["query"] == "推薦7人聚餐餐廳，補充條件：大安區，適合聊天"
    assert done["recommended_shop_ids"] == [10101]


@pytest.mark.anyio
async def test_web_agent_stream_forces_clear_recommendation_search_before_model(monkeypatch):
    captured = {}

    def fail_generate(*args, **kwargs):
        raise AssertionError("clear recommendation queries should search before model tool-calling")

    async def fake_tool_semantic_search(query: str):
        captured["query"] = query
        return {
            "shops": [
                {
                    "shop_id": 10549,
                    "name": "Fa Burger",
                    "district": "大安",
                    "category": "美式料理",
                    "category_slug": "american",
                    "ai_summary": "職人麵包與現烤牛肉漢堡。",
                    "signature_dishes": ["巧巴達粉嫩牛"],
                    "atmosphere_tags": ["聚餐"],
                }
            ]
        }

    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", fail_generate)
    monkeypatch.setattr(main, "tool_semantic_search", fake_tool_semantic_search)
    monkeypatch.setattr(
        main,
        "_build_agent_recommendation_decision",
        lambda query, tool_result: main.AgentRecommendationDecision(
            recommended_shop_ids=[10549],
            narrative="我先用大安區與美式漢堡幫你篩選。我會優先看 Fa Burger：職人麵包與現烤牛肉漢堡；若要訂位，請補日期、人數與時間。",
            rejected_shop_ids=[],
        ),
    )

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "推薦大安區美式漢堡",
            "test-clear-recommendation",
        )
    ]

    done = events[-1]
    assert captured["query"] == "推薦大安區美式漢堡"
    assert done["tools_used"] == ["semantic_shop_search"]
    assert done["recommended_shop_ids"] == [10549]
    assert "Fa Burger" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_keeps_partial_clarification_draft(monkeypatch):
    saved = {}

    def fail_generate(*args, **kwargs):
        raise AssertionError("partial clarification followup should bypass model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "推薦7人聚餐餐廳"},
            {
                "role": "model",
                "content": main._restaurant_clarification_text("推薦7人聚餐餐廳"),
                "clarification_query": "推薦7人聚餐餐廳",
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "明天晚上",
            "test-web-partial-clarification",
        )
    ]

    done = events[-1]
    assert done["tools_used"] == []
    assert "地點或捷運站" in done["answer"]
    assert "料理類型或氣氛" in done["answer"]
    assert saved["history"][-1]["clarification_query"] == "推薦7人聚餐餐廳，補充條件：明天晚上"


@pytest.mark.anyio
async def test_web_agent_stream_books_from_single_recommendation_followup(monkeypatch):
    captured = {}
    saved = {}

    async def fake_create_booking(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "shopId": kwargs["shop_id"],
            "shopName": "青田七六",
            "bookingCode": "BK-WEB-FOLLOWUP",
            "people": kwargs["people"],
            "date": kwargs["date"],
            "time": kwargs["time"],
            "tableType": kwargs["table_type"],
            "needsDeposit": False,
        }

    def fail_generate(*args, **kwargs):
        raise AssertionError("single-shop booking followup should not ask the model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "青田七六"},
            {
                "role": "model",
                "content": "我已整理青田七六。",
                "recommendation": {"query": "青田七六", "shops": [{"shop_id": 10222, "name": "青田七六"}]},
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))
    monkeypatch.setattr(main, "tool_create_booking", fake_create_booking)
    monkeypatch.setattr(main, "generate", fail_generate)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "明天晚上19點 4人",
            "test-web-booking-followup",
        )
    ]

    done = events[-1]
    assert captured == {}
    assert done["booking_draft"]["shop_id"] == 10222
    assert done["booking_draft"]["people"] == 4
    assert done["booking_draft"]["date"] == "2026-06-11"
    assert done["booking_draft"]["time"] == "19:00"
    assert done["transaction"] is None
    assert "確認訂位" in done["answer"]
    assert saved["history"][-1]["booking_draft"]["shop_id"] == 10222


@pytest.mark.anyio
async def test_web_agent_stream_books_exact_shop_without_history(monkeypatch):
    captured_search = {}
    captured_booking = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured_search["query"] = query
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "category": "台菜",
                "ai_summary": "老屋空間，適合聊天聚餐。",
            },
            {
                "shop_id": 10223,
                "name": "青靜綠",
                "district": "文山",
                "category": "素食",
            },
        ]

    async def fake_create_booking(**kwargs):
        captured_booking.update(kwargs)
        return {
            "success": True,
            "shopId": kwargs["shop_id"],
            "shopName": "青田七六",
            "bookingCode": "BK-WEB-EXACT",
            "people": kwargs["people"],
            "date": kwargs["date"],
            "time": kwargs["time"],
            "tableType": kwargs["table_type"],
            "needsDeposit": False,
        }

    def fail_generate(*args, **kwargs):
        raise AssertionError("exact shop booking should bypass model")

    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "tool_create_booking", fake_create_booking)
    monkeypatch.setattr(main, "generate", fail_generate)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "我要訂青田七六下週五晚上7點 4人",
            "test-web-exact-booking",
        )
    ]

    done = events[-1]
    assert captured_search["query"] == "青田七六"
    assert captured_booking == {}
    assert done["booking_draft"]["shop_id"] == 10222
    assert done["booking_draft"]["people"] == 4
    assert done["booking_draft"]["date"] == "2026-06-19"
    assert done["booking_draft"]["time"] == "19:00"
    assert done["tools_used"] == ["semantic_shop_search"]
    assert done["transaction"] is None
    assert "確認訂位" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_exact_shop_booking_asks_missing_fields(monkeypatch):
    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "category": "台菜",
                "ai_summary": "老屋空間，適合聊天聚餐。",
            }
        ]

    def fail_generate(*args, **kwargs):
        raise AssertionError("missing exact booking fields should bypass model")

    async def fail_create_booking(**kwargs):
        raise AssertionError("missing exact booking fields should not create booking")

    monkeypatch.setattr(main.session_store, "load_history", lambda session_id: [])
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "tool_create_booking", fail_create_booking)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "我要訂青田七六",
            "test-web-exact-booking-missing",
        )
    ]

    done = events[-1]
    assert "青田七六" in done["answer"]
    assert "還缺日期、時間、人數" in done["answer"]
    assert done["tools_used"] == ["semantic_shop_search"]
    assert [shop["shop_id"] for shop in done["shops"]] == [10222]


@pytest.mark.anyio
async def test_web_agent_stream_rejects_same_day_booking_followup(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("same-day booking followup should bypass model")

    async def fail_create_booking(**kwargs):
        raise AssertionError("same-day booking followup should not create booking")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "青田七六"},
            {
                "role": "model",
                "content": "我已整理青田七六。",
                "recommendation": {"query": "青田七六", "shops": [{"shop_id": 10222, "name": "青田七六"}]},
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_create_booking", fail_create_booking)
    monkeypatch.setattr(main, "generate", fail_generate)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "今晚 4人",
            "test-web-same-day-followup",
        )
    ]

    done = events[-1]
    assert "今天" in done["answer"]
    assert "最早可預訂明天" in done["answer"]
    assert done["tools_used"] == []
    assert "transaction" not in done or done["transaction"] is None


@pytest.mark.anyio
async def test_web_agent_stream_locks_ordinal_booking_and_asks_missing_fields(monkeypatch):
    saved = {}

    def fail_generate(*args, **kwargs):
        raise AssertionError("ordinal booking selection should bypass model")

    async def fail_create_booking(**kwargs):
        raise AssertionError("missing booking fields should not create booking")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
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
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))
    monkeypatch.setattr(main, "tool_create_booking", fail_create_booking)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "訂第二間",
            "test-web-ordinal-booking-missing",
        )
    ]

    done = events[-1]
    assert "太田日式燒肉" in done["answer"]
    assert "還缺日期、時間、人數" in done["answer"]
    assert done["tools_used"] == []
    locked_shop = saved["history"][-1]["recommendation"]["shops"][0]
    assert locked_shop["shop_id"] == 10102
    assert locked_shop["name"] == "太田日式燒肉"
    assert saved["history"][-1]["booking_draft"]["shop_id"] == 10102


@pytest.mark.anyio
async def test_web_agent_stream_merges_booking_draft_after_locked_selection(monkeypatch):
    captured = {}

    async def fake_create_booking(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "shopId": kwargs["shop_id"],
            "shopName": "太田日式燒肉",
            "bookingCode": "BK-WEB-DRAFT",
            "people": kwargs["people"],
            "date": kwargs["date"],
            "time": kwargs["time"],
            "tableType": kwargs["table_type"],
            "needsDeposit": False,
        }

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "訂第二間"},
            {
                "role": "model",
                "content": "我已鎖定太田日式燒肉，還缺人數。",
                "recommendation": {
                    "query": "訂第二間",
                    "shops": [{"shop_id": 10102, "name": "太田日式燒肉"}],
                },
                "booking_draft": {
                    "shop_id": 10102,
                    "shop_name": "太田日式燒肉",
                    "date": "2026-06-19",
                    "time": "19:00",
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_create_booking", fake_create_booking)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("booking draft should bypass model")))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "4人",
            "test-web-booking-draft",
        )
    ]

    done = events[-1]
    assert captured == {}
    assert done["booking_draft"]["shop_id"] == 10102
    assert done["booking_draft"]["people"] == 4
    assert done["booking_draft"]["date"] == "2026-06-19"
    assert done["booking_draft"]["time"] == "19:00"
    assert done["transaction"] is None
    assert "確認訂位" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_confirms_booking_draft_after_explicit_confirmation(monkeypatch):
    captured = {}

    async def fake_create_booking(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "shopId": kwargs["shop_id"],
            "shopName": "太田日式燒肉",
            "bookingCode": "BK-WEB-DRAFT",
            "people": kwargs["people"],
            "date": kwargs["date"],
            "time": kwargs["time"],
            "tableType": kwargs["table_type"],
            "needsDeposit": False,
        }

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "我幫你整理好訂位內容了。",
                "booking_draft": {
                    "shop_id": 10102,
                    "shop_name": "太田日式燒肉",
                    "date": "2026-06-19",
                    "time": "19:00",
                    "people": 4,
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_create_booking", fake_create_booking)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("booking confirmation should bypass model")))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "沒問題",
            "test-web-booking-confirm",
        )
    ]

    done = events[-1]
    assert captured["shop_id"] == 10102
    assert captured["people"] == 4
    assert captured["date"] == "2026-06-19"
    assert captured["time"] == "19:00"
    assert captured["table_type"] == "normal"
    assert done["transaction"]["booking_code"] == "BK-WEB-DRAFT"


@pytest.mark.anyio
async def test_web_agent_stream_answers_latest_booking_status(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("booking status followup should bypass model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "訂位已保留。",
                "transaction": {
                    "kind": "booking",
                    "success": False,
                    "status": "PENDING_PAYMENT",
                    "shop_id": 10222,
                    "shop_name": "青田七六",
                    "booking_code": "BK-STATUS",
                    "people": 4,
                    "date": "2026-06-11",
                    "time": "19:00",
                    "needs_deposit": True,
                    "deposit_total": 400,
                },
            }
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "查看狀態",
            "test-web-booking-status",
        )
    ]

    done = events[-1]
    assert "BK-STATUS" in done["answer"]
    assert "待付訂金" in done["answer"]
    assert done["transaction"]["booking_code"] == "BK-STATUS"
    assert done["tools_used"] == []


@pytest.mark.anyio
async def test_web_agent_stream_pays_latest_pending_booking(monkeypatch):
    captured = {}

    async def fake_pay_booking_with_test_card(booking_code: str):
        captured["booking_code"] = booking_code
        return {
            "success": True,
            "rec_trade_id": "TAPPAY-DEMO-1",
            "amount": 400,
            "note": "信用卡 demo 付款完成",
        }

    def fail_generate(*args, **kwargs):
        raise AssertionError("payment followup should bypass model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "訂位已保留。",
                "transaction": {
                    "kind": "booking",
                    "success": False,
                    "status": "PENDING_PAYMENT",
                    "shop_id": 10222,
                    "shop_name": "青田七六",
                    "booking_code": "BK-PAY",
                    "people": 4,
                    "date": "2026-06-11",
                    "time": "19:00",
                    "needs_deposit": True,
                    "deposit_total": 400,
                },
            }
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_pay_booking_with_test_card", fake_pay_booking_with_test_card)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "我要付款",
            "test-web-booking-pay",
        )
    ]

    done = events[-1]
    assert captured["booking_code"] == "BK-PAY"
    assert done["tools_used"] == ["pay_booking_with_test_card"]
    assert done["transaction"]["status"] == "PAID"
    assert done["transaction"]["rec_trade_id"] == "TAPPAY-DEMO-1"


@pytest.mark.anyio
async def test_web_agent_stream_cancel_requires_confirmation(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("cancel prompt should bypass model")

    async def fail_cancel_booking(**kwargs):
        raise AssertionError("plain cancel should not execute destructive action")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "訂位已完成。",
                "transaction": {
                    "kind": "booking",
                    "success": True,
                    "status": "CONFIRMED",
                    "shop_id": 10222,
                    "shop_name": "青田七六",
                    "booking_code": "BK-CANCEL",
                    "people": 4,
                    "date": "2026-06-11",
                    "time": "19:00",
                },
            }
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_cancel_booking", fail_cancel_booking)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "取消訂位",
            "test-web-cancel-prompt",
        )
    ]

    done = events[-1]
    assert "確認取消" in done["answer"]
    assert "BK-CANCEL" in done["answer"]
    assert done["tools_used"] == []


@pytest.mark.anyio
async def test_web_agent_stream_confirm_cancel_latest_booking(monkeypatch):
    captured = {}

    async def fake_cancel_booking(booking_code: str):
        captured["booking_code"] = booking_code
        return {
            "success": True,
            "bookingCode": booking_code,
            "shopId": 10222,
            "shopName": "青田七六",
            "people": 4,
            "date": "2026-06-11",
            "time": "19:00",
            "tableType": "normal",
            "status": "CANCELED",
        }

    def fail_generate(*args, **kwargs):
        raise AssertionError("confirm cancel should bypass model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {
                "role": "model",
                "content": "訂位已完成。",
                "transaction": {
                    "kind": "booking",
                    "success": True,
                    "status": "CONFIRMED",
                    "shop_id": 10222,
                    "shop_name": "青田七六",
                    "booking_code": "BK-CANCEL",
                    "people": 4,
                    "date": "2026-06-11",
                    "time": "19:00",
                },
            }
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_cancel_booking", fake_cancel_booking)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "確認取消 BK-CANCEL",
            "test-web-confirm-cancel",
        )
    ]

    done = events[-1]
    assert captured["booking_code"] == "BK-CANCEL"
    assert done["tools_used"] == ["cancel_booking"]
    assert done["transaction"]["status"] == "CANCELED"
    assert "訂位已取消" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_books_ordinal_recommendation_followup(monkeypatch):
    captured = {}

    async def fake_create_booking(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "shopId": kwargs["shop_id"],
            "shopName": "太田日式燒肉",
            "bookingCode": "BK-WEB-SECOND",
            "people": kwargs["people"],
            "date": kwargs["date"],
            "time": kwargs["time"],
            "tableType": kwargs["table_type"],
            "needsDeposit": False,
        }

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
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
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "tool_create_booking", fake_create_booking)
    monkeypatch.setattr(main, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ordinal booking should bypass model")))
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "訂第二間明天晚上 4人",
            "test-web-booking-second",
        )
    ]

    done = events[-1]
    assert captured == {}
    assert done["booking_draft"]["shop_id"] == 10102
    assert done["booking_draft"]["people"] == 4
    assert done["booking_draft"]["date"] == "2026-06-11"
    assert done["booking_draft"]["time"] == "19:00"
    assert done["transaction"] is None
    assert "確認訂位" in done["answer"]


@pytest.mark.anyio
async def test_web_agent_stream_asks_missing_booking_people(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("missing booking fields should be handled before model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "青田七六"},
            {
                "role": "model",
                "content": "我已整理青田七六。",
                "recommendation": {"query": "青田七六", "shops": [{"shop_id": 10222, "name": "青田七六"}]},
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", fail_generate)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "明天晚上",
            "test-web-booking-missing-people",
        )
    ]

    done = events[-1]
    assert "還缺人數" in done["answer"]
    assert done["tools_used"] == []


@pytest.mark.anyio
async def test_web_agent_stream_more_recommendations_excludes_seen(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {"shop_id": 10009, "name": "橘色涮涮屋 信義館", "district": "信義", "ai_summary": "已推薦。"},
            {"shop_id": 10115, "name": "辛殿麻辣鍋 信義店", "district": "信義", "ai_summary": "已推薦。"},
            {"shop_id": 10220, "name": "麻凡麻辣火鍋", "district": "中山", "ai_summary": "新候選。"},
            {"shop_id": 10221, "name": "山上走走鍋物", "district": "中正", "ai_summary": "新候選。"},
        ]

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "信義區高級火鍋"},
            {
                "role": "model",
                "content": "我整理了兩間。",
                "recommendation": {
                    "query": "信義區高級火鍋",
                    "shops": [
                        {"shop_id": 10009, "name": "橘色涮涮屋 信義館"},
                        {"shop_id": 10115, "name": "辛殿麻辣鍋 信義店"},
                    ],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(
        main,
        "_build_agent_recommendation_decision",
        lambda query, tool_result: main.AgentRecommendationDecision(
            recommended_shop_ids=[10220, 10221],
            narrative="我避開剛剛兩間，改推麻凡與山上走走。",
            rejected_shop_ids=[],
        ),
    )

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "還有嗎",
            "test-web-more",
        )
    ]

    done = events[-1]
    assert captured["query"] == "信義區高級火鍋"
    assert "semantic_shop_search" in done["tools_used"]
    assert [shop["shop_id"] for shop in done["shops"]] == [10220, 10221]


@pytest.mark.anyio
async def test_web_agent_stream_answers_recommendation_advice(monkeypatch):
    def fail_generate(*args, **kwargs):
        raise AssertionError("recommendation advice should use saved context")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "大安區適合聊天"},
            {
                "role": "model",
                "content": "我整理了兩間。",
                "recommendation": {
                    "query": "大安區適合聊天",
                    "shops": [
                        {
                            "shop_id": 10101,
                            "name": "大安聊天餐館",
                            "district": "大安",
                            "ai_summary": "座位寬敞，適合慢慢聊天。",
                            "atmosphere_tags": ["聊天", "安靜"],
                            "signature_dishes": ["三杯雞"],
                        },
                        {
                            "shop_id": 10102,
                            "name": "熱鬧燒肉",
                            "district": "大安",
                            "ai_summary": "氣氛熱鬧，適合聚餐。",
                            "atmosphere_tags": ["聚餐"],
                        },
                    ],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "哪間最適合聊天？",
            "test-web-advice",
        )
    ]

    done = events[-1]
    assert "大安聊天餐館" in done["answer"]
    assert "聊天" in done["answer"]
    assert done["tools_used"] == []


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
                {
                    "shop_id": 10022,
                    "name": "青花驕 中山北店",
                    "district": "中山區",
                    "ai_summary": "中山聚餐。",
                    "signature_dishes": ["麻辣鍋", "牛肉"],
                    "atmosphere_tags": ["多人聚餐"],
                    "booking_difficulty": "可線上訂位，建議提前",
                },
                {
                    "shop_id": 10123,
                    "name": "海霸王 中山店",
                    "district": "中山",
                    "ai_summary": "中式聚餐。",
                    "signature_dishes": ["海鮮"],
                    "atmosphere_tags": ["家庭聚餐"],
                },
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
    assert [shop["shop_id"] for shop in done["shops"]] == [10022, 10123]
    assert done["comparison_rows"][0] == {
        "shop_id": 10022,
        "name": "青花驕 中山北店",
        "feature_highlight": "招牌：麻辣鍋、牛肉",
        "best_for": "多人聚餐",
        "booking_status": "可線上訂位，建議提前",
        "meta": "中山區",
    }
    assert [shop["shop_id"] for shop in done["tool_result"]["shops"]] == [10022, 10123]


@pytest.mark.anyio
async def test_web_agent_stream_exact_shop_correction_bypasses_model(monkeypatch):
    captured = {}
    saved = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "mrt_station": "東門",
                "category": "台菜",
                "ai_summary": "老屋空間，適合聊天與聚餐。",
                "atmosphere_tags": ["聊天", "聚餐"],
            },
            {
                "shop_id": 10223,
                "name": "青靜綠",
                "district": "文山",
                "category": "素食",
                "ai_summary": "山區蔬食餐廳。",
            },
        ]

    def fail_generate(*args, **kwargs):
        raise AssertionError("exact shop correction should bypass model")

    monkeypatch.setattr(
        main.session_store,
        "load_history",
        lambda session_id: [
            {"role": "user", "content": "大安區適合聊天"},
            {
                "role": "model",
                "content": "我整理了幾間。",
                "recommendation": {
                    "query": "大安區適合聊天",
                    "shops": [{"shop_id": 10101, "name": "大安聊天餐館"}],
                },
            },
        ],
    )
    monkeypatch.setattr(main.session_store, "save_history", lambda session_id, history: saved.update({"history": history}))
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "generate", fail_generate)

    events = [
        event
        async for event in main._run_agent_turn_stream(
            "不是這個，我要青田七六",
            "test-web-exact-correction",
        )
    ]

    done = events[-1]
    assert captured["query"] == "青田七六"
    assert done["tools_used"] == ["semantic_shop_search"]
    assert done["recommended_shop_ids"] == [10222]
    assert [shop["shop_id"] for shop in done["shops"]] == [10222]
    assert "青田七六" in done["answer"]
    assert saved["history"][-1]["recommendation"]["shops"][0]["shop_id"] == 10222


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
async def test_line_cards_use_shared_agent_search_result(monkeypatch):
    captured = {}

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
            },
            {
                "shop_id": 10746,
                "name": "Lin’s Burger 台北信義店",
                "district": "信義",
                "category": "美式料理",
            },
        ]

    async def fake_build_agent_search_result(query: str, shops: list[dict], recommended_shop_ids=None):
        captured["query"] = query
        captured["shop_ids"] = [shop["shop_id"] for shop in shops]
        captured["recommended_shop_ids"] = recommended_shop_ids
        enriched = [dict(shop) for shop in shops]
        enriched[0]["ai_summary"] = "共用 search builder 補上的漢堡亮點。"
        enriched[0]["signature_dishes"] = ["牛肉漢堡", "薯條"]
        return {
            "shops": enriched,
            "scope_note": "中山區符合條件較少，我先擴大到台北漢堡店，整理 3 間符合需求的餐廳。",
        }

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_build_agent_search_result", fake_build_agent_search_result)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_cards_for_query("推薦中山區高級漢堡店", "test-user")
    payload = json.dumps(messages, ensure_ascii=False)

    assert captured == {
        "query": "推薦中山區高級漢堡店",
        "shop_ids": [10680, 10201, 10746],
        "recommended_shop_ids": [10680, 10201, 10746],
    }
    assert messages[0]["text"].startswith("中山區符合條件較少，我先擴大到台北漢堡店")
    assert "共用 search builder 補上的漢堡亮點" in payload


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
async def test_line_vague_need_clarifies_and_saves_context(monkeypatch):
    saved = {}

    async def fail_run_agent_turn(query: str, session_id: str):
        raise AssertionError("vague line requests should not wait for model output")

    monkeypatch.setattr(main, "_load_line_recommendation_state", lambda user_id: {})
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda user_id, query, shown_shop_ids: saved.update({"user_id": user_id, "query": query, "shown": shown_shop_ids}))
    monkeypatch.setattr(main, "_run_agent_turn", fail_run_agent_turn)

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "推薦7人聚餐餐廳"},
        }
    )

    assert "7人我先記下" in messages[0]["text"]
    assert "直接回一句就好" in messages[0]["text"]
    assert saved == {"user_id": "test-user", "query": "推薦7人聚餐餐廳", "shown": []}


@pytest.mark.anyio
async def test_line_nearby_without_location_clarifies(monkeypatch):
    saved = {}

    async def fail_semantic_hits(query: str, top_k: int):
        raise AssertionError("nearby without location should not search")

    monkeypatch.setattr(main, "_load_line_recommendation_state", lambda user_id: {})
    monkeypatch.setattr(main, "_load_line_location_state", lambda user_id: {})
    monkeypatch.setattr(
        main,
        "_save_line_recommendation_state",
        lambda user_id, query, shown_shop_ids: saved.update({"user_id": user_id, "query": query, "shown": shown_shop_ids}),
    )
    monkeypatch.setattr(main, "_semantic_hits", fail_semantic_hits)

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "附近高級火鍋"},
        }
    )

    assert "位置或捷運站" in messages[0]["text"]
    assert saved == {"user_id": "test-user", "query": "附近高級火鍋", "shown": []}


@pytest.mark.anyio
async def test_line_nearby_with_saved_location_recommends_cards(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10115,
                "name": "辛殿麻辣鍋｜信義店",
                "district": "信義區",
                "category": "火鍋",
                "ai_summary": "適合聚餐的麻辣鍋。",
            }
        ]

    monkeypatch.setattr(main, "_load_line_recommendation_state", lambda user_id: {})
    monkeypatch.setattr(
        main,
        "_load_line_location_state",
        lambda user_id: {"title": "台北 101", "address": "台北市信義區信義路五段7號"},
    )
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "附近高級火鍋"},
        }
    )

    assert captured["query"] == "台北市信義區信義路五段7號附近，附近高級火鍋"
    assert messages[1]["type"] == "flex"


@pytest.mark.anyio
async def test_line_partial_clarification_followup_updates_context(monkeypatch):
    saved = {}

    async def fail_semantic_hits(query: str, top_k: int):
        raise AssertionError("partial clarification should not search yet")

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "推薦7人聚餐餐廳", "shown_shop_ids": []},
    )
    monkeypatch.setattr(
        main,
        "_save_line_recommendation_state",
        lambda user_id, query, shown_shop_ids: saved.update({"user_id": user_id, "query": query, "shown": shown_shop_ids}),
    )
    monkeypatch.setattr(main, "_semantic_hits", fail_semantic_hits)

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "明天晚上"},
        }
    )

    assert "地點或捷運站" in messages[0]["text"]
    assert "料理類型或氣氛" in messages[0]["text"]
    assert saved == {
        "user_id": "test-user",
        "query": "推薦7人聚餐餐廳，補充條件：明天晚上",
        "shown": [],
    }


@pytest.mark.anyio
async def test_line_completed_clarification_followup_searches(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10101,
                "name": "大安聊天餐館",
                "district": "大安",
                "category": "中式料理",
                "ai_summary": "座位寬敞，適合多人聊天。",
            }
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "推薦7人聚餐餐廳，補充條件：明天晚上", "shown_shop_ids": []},
    )
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "大安區，適合聊天"},
        }
    )

    assert captured["query"] == "推薦7人聚餐餐廳，補充條件：明天晚上，補充條件：大安區，適合聊天"
    assert messages[1]["type"] == "flex"


@pytest.mark.anyio
async def test_line_followup_after_clarification_merges_previous_need(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10101,
                "name": "大安聊天餐館",
                "district": "大安",
                "category": "中式料理",
                "ai_summary": "座位寬敞，適合多人聊天。",
            }
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "推薦7人聚餐餐廳", "shown_shop_ids": []},
    )
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "大安區，適合聊天"},
        }
    )

    assert captured["query"] == "推薦7人聚餐餐廳，補充條件：大安區，適合聊天"
    assert messages[1]["type"] == "flex"


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
async def test_line_ordinal_selects_previous_recommendation(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "ai_summary": "精緻涮涮屋路線。",
            },
            {
                "shop_id": 10115,
                "name": "辛殿麻辣鍋｜信義店",
                "district": "信義區",
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
            "message": {"type": "text", "text": "第二間"},
        }
    )

    assert captured["query"] == "信義區高級火鍋"
    bubbles = messages[1]["contents"]["contents"]
    assert len(bubbles) == 1
    assert bubbles[0]["body"]["contents"][1]["text"] == "辛殿麻辣鍋｜信義店"


@pytest.mark.anyio
async def test_line_negative_ordinal_gets_more_recommendations(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {"shop_id": 10009, "name": "橘色涮涮屋 信義館", "district": "信義", "ai_summary": "已推薦。"},
            {"shop_id": 10115, "name": "辛殿麻辣鍋｜信義店", "district": "信義", "ai_summary": "已推薦。"},
            {"shop_id": 10220, "name": "麻凡麻辣火鍋", "district": "中山", "ai_summary": "新候選。"},
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
            "message": {"type": "text", "text": "不要第二間，換一家"},
        }
    )

    assert captured["query"] == "信義區高級火鍋"
    payload = json.dumps(messages, ensure_ascii=False)
    assert "麻凡麻辣火鍋" in payload
    assert "辛殿麻辣鍋" not in payload


@pytest.mark.anyio
async def test_line_recommendation_advice_uses_previous_cards(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義",
                "ai_summary": "精緻火鍋，適合正式請客。",
                "atmosphere_tags": ["商務", "約會"],
                "signature_dishes": ["海鮮套餐"],
            },
            {
                "shop_id": 10115,
                "name": "辛殿麻辣鍋｜信義店",
                "district": "信義",
                "ai_summary": "麻辣鍋吃到飽，氣氛熱鬧。",
                "atmosphere_tags": ["聚餐"],
                "signature_dishes": ["麻辣鍋"],
            },
        ]

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10009, 10115]},
    )
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "為什麼推薦第二間？"},
        }
    )

    assert captured["query"] == "信義區高級火鍋"
    assert "辛殿麻辣鍋" in messages[0]["text"]
    assert "麻辣鍋吃到飽" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_specific_shop_name_returns_only_that_shop(monkeypatch):
    captured = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured["query"] = query
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "mrt_station": "東門",
                "category": "中式料理",
                "ai_summary": "老屋餐廳，適合聊天聚餐。",
            },
            {
                "shop_id": 10223,
                "name": "青靜綠",
                "district": "文山",
                "category": "素食",
                "ai_summary": "蔬食餐廳。",
            },
        ]

    monkeypatch.setattr(main, "_load_line_recommendation_state", lambda user_id: {})
    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "那我要青田七六好了"},
        }
    )

    assert captured["query"] == "青田七六"
    bubbles = messages[1]["contents"]["contents"]
    assert len(bubbles) == 1
    assert bubbles[0]["body"]["contents"][1]["text"] == "青田七六"


@pytest.mark.anyio
async def test_line_booking_followup_uses_selected_single_shop(monkeypatch):
    async def fake_fetch_java_shop(shop_id: int):
        return {"id": shop_id, "name": "青田七六"}

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "青田七六", "shown_shop_ids": [10222]},
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "明天晚上19點 4人"},
        }
    )

    assert "青田七六" in messages[0]["text"]
    assert "2026-06-11 19:00、4 人" in messages[0]["text"]
    assert "/line/book/10222?" in messages[0]["text"]
    assert "people=4" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_exact_shop_booking_without_history(monkeypatch):
    captured_search = {}
    saved_state = {}

    async def fake_semantic_hits(query: str, top_k: int):
        captured_search["query"] = query
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "category": "台菜",
                "ai_summary": "老屋空間，適合聊天聚餐。",
            },
            {
                "shop_id": 10223,
                "name": "青靜綠",
                "district": "文山",
                "category": "素食",
            },
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(
        main,
        "_save_line_recommendation_state",
        lambda *args, **kwargs: saved_state.update({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "我要訂青田七六下週五晚上7點 4人"},
        }
    )

    assert captured_search["query"] == "青田七六"
    assert "青田七六" in messages[0]["text"]
    assert "2026-06-19 19:00、4 人" in messages[0]["text"]
    assert "/line/book/10222?" in messages[0]["text"]
    assert "people=4" in messages[0]["text"]
    assert saved_state["kwargs"]["shown_shop_ids"] == [10222]


@pytest.mark.anyio
async def test_line_exact_shop_booking_asks_missing_fields(monkeypatch):
    async def fake_semantic_hits(query: str, top_k: int):
        return [
            {
                "shop_id": 10222,
                "name": "青田七六",
                "district": "大安",
                "category": "台菜",
                "ai_summary": "老屋空間，適合聊天聚餐。",
            }
        ]

    monkeypatch.setattr(main, "_semantic_hits", fake_semantic_hits)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main, "_save_line_recommendation_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "我要訂青田七六"},
        }
    )

    assert "青田七六" in messages[0]["text"]
    assert "還缺日期、時間、人數" in messages[0]["text"]
    assert "/line/book/10222?" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_exact_shop_booking_rejects_same_day(monkeypatch):
    async def fail_semantic_hits(query: str, top_k: int):
        raise AssertionError("same-day booking should be rejected before search")

    monkeypatch.setattr(main, "_semantic_hits", fail_semantic_hits)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "我要訂青田七六今天晚上7點 4人"},
        }
    )

    assert "今天" in messages[0]["text"]
    assert "最早可預訂明天" in messages[0]["text"]
    assert "/line/book/" not in messages[0]["text"]


@pytest.mark.anyio
async def test_line_booking_action_uses_latest_booking_state(monkeypatch):
    monkeypatch.setattr(
        main,
        "_load_line_booking_state",
        lambda user_id: {
            "phase": "created",
            "booking": {
                "bookingCode": "BK-LINE-PAY",
                "shopId": 10222,
                "shopName": "青田七六",
                "date": "2026-06-11",
                "time": "19:00",
                "people": 4,
                "status": "PENDING_PAYMENT",
                "needsDeposit": True,
                "depositTotal": 400,
            },
        },
    )
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "我要付款"},
        }
    )

    assert messages[0]["type"] == "flex"
    assert messages[0]["altText"] == "訂位保留成功，待付訂金"
    payload = json.dumps(messages[0], ensure_ascii=False)
    assert "BK-LINE-PAY" in payload
    assert "立即繳訂金" in payload
    assert "/line/book/10222/pay?" in payload


@pytest.mark.anyio
async def test_line_booking_action_without_state_links_my_bookings(monkeypatch):
    monkeypatch.setattr(main, "_load_line_booking_state", lambda user_id: {})
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "查看狀態"},
        }
    )

    assert messages[0]["type"] == "text"
    assert "/line/my-bookings?" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_confirm_cancel_uses_latest_booking_state(monkeypatch):
    captured = {}
    saved = {}

    async def fake_cancel_line_booking(booking_code: str, line_user_id: str, line_token: str):
        captured.update({"booking_code": booking_code, "line_user_id": line_user_id, "line_token": line_token})
        return {
            "success": True,
            "data": {
                "bookingCode": booking_code,
                "shopId": 10222,
                "shopName": "青田七六",
                "date": "2026-06-11",
                "time": "19:00",
                "people": 4,
                "status": "CANCELED",
            },
        }

    monkeypatch.setattr(
        main,
        "_load_line_booking_state",
        lambda user_id: {
            "phase": "created",
            "booking": {
                "bookingCode": "BK-LINE-CANCEL",
                "shopId": 10222,
                "shopName": "青田七六",
                "date": "2026-06-11",
                "time": "19:00",
                "people": 4,
                "status": "CONFIRMED",
            },
        },
    )
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main, "_cancel_line_booking", fake_cancel_line_booking)
    monkeypatch.setattr(main, "_save_line_booking_state", lambda *args, **kwargs: saved.update({"args": args}))
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "確認取消 BK-LINE-CANCEL"},
        }
    )

    assert captured == {
        "booking_code": "BK-LINE-CANCEL",
        "line_user_id": "test-user",
        "line_token": "line-token",
    }
    assert saved["args"][2] == "canceled"
    assert messages[0]["type"] == "flex"
    assert messages[0]["altText"] == "訂位已取消"


@pytest.mark.anyio
async def test_line_booking_followup_uses_ordinal_shop(monkeypatch):
    async def fake_fetch_java_shop(shop_id: int):
        return {"id": shop_id, "name": "辛殿麻辣鍋｜信義店"}

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10009, 10115]},
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "訂第二間明天晚上 4人"},
        }
    )

    assert "辛殿麻辣鍋｜信義店" in messages[0]["text"]
    assert "2026-06-11 19:00、4 人" in messages[0]["text"]
    assert "/line/book/10115?" in messages[0]["text"]
    assert "people=4" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_booking_followup_locks_ordinal_and_asks_missing_fields(monkeypatch):
    saved = {}

    async def fake_fetch_java_shop(shop_id: int):
        assert shop_id == 10115
        return {"id": shop_id, "name": "辛殿麻辣鍋｜信義店"}

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "信義區高級火鍋", "shown_shop_ids": [10009, 10115]},
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(
        main,
        "_save_line_recommendation_state",
        lambda *args, **kwargs: saved.update({"args": args, "kwargs": kwargs}),
    )

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "訂第二間"},
        }
    )

    assert "辛殿麻辣鍋｜信義店" in messages[0]["text"]
    assert "還缺日期、時間、人數" in messages[0]["text"]
    assert "/line/book/" not in messages[0]["text"]
    assert saved["kwargs"]["shown_shop_ids"] == [10115]
    assert saved["kwargs"]["booking_prefill"] == {"date": "", "time": "", "people": None}


@pytest.mark.anyio
async def test_line_booking_followup_merges_saved_prefill(monkeypatch):
    async def fake_fetch_java_shop(shop_id: int):
        return {"id": shop_id, "name": "辛殿麻辣鍋｜信義店"}

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {
            "query": "信義區高級火鍋",
            "shown_shop_ids": [10115],
            "booking_prefill": {"date": "2026-06-19", "time": "19:00"},
        },
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "4人"},
        }
    )

    assert "辛殿麻辣鍋｜信義店" in messages[0]["text"]
    assert "2026-06-19 19:00、4 人" in messages[0]["text"]
    assert "/line/book/10115?" in messages[0]["text"]
    assert "date=2026-06-19" in messages[0]["text"]
    assert "time=19%3A00" in messages[0]["text"]
    assert "people=4" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_booking_followup_asks_people_when_missing(monkeypatch):
    async def fake_fetch_java_shop(shop_id: int):
        return {"id": shop_id, "name": "青田七六"}

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "青田七六", "shown_shop_ids": [10222]},
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_java_shop)
    monkeypatch.setattr(main, "_line_token_for_user", lambda user_id: "line-token")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "明天晚上"},
        }
    )

    assert "還缺人數" in messages[0]["text"]
    assert "2026-06-11 19:00" in messages[0]["text"]


@pytest.mark.anyio
async def test_line_booking_followup_rejects_same_day_short_reply(monkeypatch):
    async def fail_fetch_java_shop(shop_id: int):
        raise AssertionError("same-day booking followup should stop before fetching shop")

    monkeypatch.setattr(
        main,
        "_load_line_recommendation_state",
        lambda user_id: {"query": "青田七六", "shown_shop_ids": [10222]},
    )
    monkeypatch.setattr(main, "_fetch_java_shop", fail_fetch_java_shop)
    monkeypatch.setattr(main, "taipei_today", lambda: main.date_cls(2026, 6, 10))

    messages = await main._build_line_reply_messages(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "message": {"type": "text", "text": "今晚 4人"},
        }
    )

    assert "今天" in messages[0]["text"]
    assert "最早可預訂明天" in messages[0]["text"]
    assert "/line/book/" not in messages[0]["text"]


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
    labels = [button["action"]["label"] for button in footer]
    assert "我會開車" in labels
    parking_uri = next(button["action"]["uri"] for button in footer if button["action"]["label"] == "我會開車")
    assert "/line/book/10009/parking?" in parking_uri
    assert "driving=true" in parking_uri


def test_line_booking_payment_page_has_selectable_methods(monkeypatch):
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")
    html = main._line_booking_payment_page(
        10009,
        "橘色涮涮屋 信義館",
        {
            "bookingCode": "BK-ABC",
            "people": 2,
            "date": "2026-06-08",
            "time": "19:00",
            "depositTotal": 600,
        },
        "line-token",
    )

    assert 'role="radiogroup"' in html
    assert 'name="paymentMethod" value="credit_card" checked' in html
    assert 'name="paymentMethod" value="line_pay"' in html
    assert 'name="paymentMethod" value="apple_pay"' in html
    assert 'name="paymentMethod" value="jkos_pay"' in html
    assert "LINE Pay" in html


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


def test_internal_line_secret_fails_closed_when_missing(monkeypatch):
    monkeypatch.setattr(main.settings, "line_internal_webhook_secret", "")
    monkeypatch.setattr(main.settings, "line_internal_webhook_require_secret", True)

    with pytest.raises(main.HTTPException) as exc:
        main._verify_internal_line_secret({"secret": "anything"})

    assert exc.value.status_code == 503


def test_internal_line_secret_rejects_invalid_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "line_internal_webhook_secret", "expected-secret")
    monkeypatch.setattr(main.settings, "line_internal_webhook_require_secret", True)

    with pytest.raises(main.HTTPException) as exc:
        main._verify_internal_line_secret({"secret": "wrong-secret"})

    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_internal_booking_updated_pushes_cancel_card(monkeypatch):
    pushed = {}
    saved = {}

    async def fake_push_messages(user_id, messages, channel_access_token, enabled):
        pushed["user_id"] = user_id
        pushed["messages"] = messages
        return {"ok": True}

    monkeypatch.setattr(main, "push_messages", fake_push_messages)
    monkeypatch.setattr(main, "_save_line_booking_state", lambda *args, **kwargs: saved.update({"args": args}))
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
    assert saved["args"][0] == "Uabc123"
    assert saved["args"][1]["bookingCode"] == "BK-CANCEL"
    assert saved["args"][2] == "canceled"


@pytest.mark.anyio
async def test_internal_parking_reminder_pushes_line_card(monkeypatch):
    pushed = {}

    async def fake_push_messages(user_id, messages, channel_access_token, enabled):
        pushed["user_id"] = user_id
        pushed["messages"] = messages
        return {"ok": True}

    monkeypatch.setattr(main, "push_messages", fake_push_messages)
    monkeypatch.setattr(main.settings, "line_internal_webhook_secret", "secret")
    monkeypatch.setattr(main.settings, "line_public_web_url", "https://bytebites.example.com")

    class FakeRequest:
        async def json(self):
            return {
                "secret": "secret",
                "lineUserId": "Uabc123",
                "bookingCode": "BK-PARK",
                "shopId": 10009,
                "shopName": "橘色涮涮屋 信義館",
                "date": "2026-06-10",
                "time": "19:00",
                "parkingLots": [
                    {
                        "name": "市府轉運站停車場",
                        "distanceMeters": 180,
                        "availableCar": 18,
                        "totalCar": 120,
                        "updatedAt": "2026-06-10 17:00:00",
                        "navigationUrl": "https://www.google.com/maps/dir/?api=1&destination=25.033,121.565&travelmode=driving",
                    }
                ],
            }

    response = await main.internal_line_parking_reminder(FakeRequest())

    assert response["ok"] is True
    assert pushed["user_id"] == "Uabc123"
    message = pushed["messages"][0]
    assert message["altText"] == "橘色涮涮屋 信義館 附近停車提醒"
    assert message["contents"]["footer"]["contents"][0]["action"]["label"] == "保留最近車位"
    assert "/line/book/10009/parking-reserve?" in message["contents"]["footer"]["contents"][0]["action"]["uri"]
    assert message["contents"]["footer"]["contents"][1]["action"]["label"] == "導航到最近停車場"


def test_mock_parking_reservation_reduces_displayed_spaces():
    main._PARKING_RESERVATIONS.clear()
    booking = {
        "bookingCode": "BK-PARK",
        "date": "2026-06-10",
        "time": "19:00",
        "shopName": "橘色涮涮屋 信義館",
    }
    shop = {"id": 10009, "name": "橘色涮涮屋 信義館"}
    lot = {
        "id": "lot-1",
        "name": "市府轉運站停車場",
        "area": "信義",
        "distanceMeters": 180,
        "availableCar": 18,
        "totalCar": 120,
    }

    reservation = main._mock_parking_reservation(booking, shop, lot)
    html = main._line_parking_html([lot], booking_code="BK-PARK")

    assert reservation["lotName"] == "市府轉運站停車場"
    assert reservation["floor"].startswith("B")
    assert "區" in reservation["zone"]
    assert "-" in reservation["stall"]
    assert "剩 17 / 120 格" in html
    assert "保留車格" in html


@pytest.mark.anyio
async def test_line_parking_reserve_success_pushes_confirmation(monkeypatch):
    main._PARKING_RESERVATIONS.clear()
    pushed = {}

    async def fake_push_messages(user_id, messages, channel_access_token, enabled):
        pushed["user_id"] = user_id
        pushed["messages"] = messages
        return {"ok": True}

    async def fake_fetch_shop(shop_id: int):
        return {
            "id": shop_id,
            "name": "橘色涮涮屋 信義館",
            "x": 121.565,
            "y": 25.033,
        }

    async def fake_fetch_booking(booking_code: str, line_user_id: str, line_token: str):
        return {
            "bookingCode": booking_code,
            "shopName": "橘色涮涮屋 信義館",
            "date": "2026-06-10",
            "time": "19:00",
        }

    async def fake_fetch_parking(lng, lat, limit=3):
        return [
            {
                "id": "lot-1",
                "name": "市府轉運站停車場",
                "area": "信義",
                "address": "台北市信義區忠孝東路五段",
                "distanceMeters": 180,
                "availableCar": 18,
                "totalCar": 120,
                "navigationUrl": "https://www.google.com/maps/dir/?api=1&destination=25.033,121.565&travelmode=driving",
            }
        ]

    monkeypatch.setattr(main, "_line_context", lambda lt="", line_user_id="": ("Uabc123", "token"))
    monkeypatch.setattr(main, "_fetch_java_shop", fake_fetch_shop)
    monkeypatch.setattr(main, "_fetch_line_booking", fake_fetch_booking)
    monkeypatch.setattr(main, "_fetch_java_nearby_parking", fake_fetch_parking)
    monkeypatch.setattr(main, "push_messages", fake_push_messages)

    response = await main.line_booking_parking_reserve(
        10009,
        "BK-PARK",
        lot=0,
        confirm=True,
        lt="token",
    )
    html = response.body.decode("utf-8")

    assert "已保留車位" in html
    assert "市府轉運站停車場" in html
    assert "剩 17 / 120 格" in html
    assert pushed["user_id"] == "Uabc123"
    message = pushed["messages"][0]
    assert message["altText"].startswith("市府轉運站停車場 已保留車位")
    assert "已保留車位" in message["contents"]["body"]["contents"][1]["text"]


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
