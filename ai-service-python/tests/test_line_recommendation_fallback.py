import pytest

import app.main as main

from app.main import _line_should_force_recommendation_cards


def test_line_force_recommendation_cards_for_clear_restaurant_query():
    assert _line_should_force_recommendation_cards("推薦信義區高級火鍋")


def test_line_force_recommendation_cards_skips_booking_and_payment_queries():
    assert not _line_should_force_recommendation_cards("我要訂信義區火鍋")
    assert not _line_should_force_recommendation_cards("我要付款訂金")


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
