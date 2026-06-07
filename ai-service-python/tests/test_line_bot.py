import base64
import hashlib
import hmac

import pytest

from app.line_bot import build_line_flex_message, reply_messages, verify_line_signature


def test_verify_line_signature_accepts_valid_signature():
    body = b'{"events":[]}'
    secret = "test-secret"
    signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")

    assert verify_line_signature(body, signature, secret)


def test_verify_line_signature_rejects_invalid_signature():
    assert not verify_line_signature(b"{}", "bad-signature", "test-secret")


def test_build_line_flex_message_limits_to_three_cards():
    shops = [
        {
            "shop_id": index,
            "name": f"店家 {index}",
            "district": "中山",
            "mrt_station": "中山",
            "ai_summary": "適合聚餐。",
        }
        for index in range(1, 6)
    ]

    message = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=[4, 2, 1, 5],
        answer="為你整理 3 間店。",
        public_web_url="https://bytebites.example.com",
    )

    assert message["type"] == "_bundle"
    flex = message["messages"][1]
    assert flex["type"] == "flex"
    bubbles = flex["contents"]["contents"]
    assert len(bubbles) == 3
    assert bubbles[0]["body"]["contents"][1]["text"] == "店家 4"


def test_build_line_flex_message_ignores_markdown_table_reason():
    message = build_line_flex_message(
        shops=[
            {
                "shop_id": 10115,
                "name": "辛殿麻辣鍋｜信義店",
                "district": "信義",
                "ai_summary": "備援摘要。",
            }
        ],
        recommended_shop_ids=[10115],
        answer=(
            "| 店家 | 類型 | 推薦原因 |\n"
            "|:---|:---|:---|\n"
            "| 辛殿麻辣鍋｜信義店 | 吃到飽 | 高人氣麻辣鍋吃到飽，肉品與甜點評價極佳 |"
        ),
        public_web_url="https://bytebites.example.com",
    )

    reason = message["messages"][1]["contents"]["contents"][0]["body"]["contents"][6]["text"]
    assert reason == "備援摘要。"


def test_build_line_flex_message_reason_uses_features_not_booking_status():
    message = build_line_flex_message(
        shops=[
            {
                "shop_id": 10009,
                "name": "橘色涮涮屋 信義館",
                "district": "信義區",
                "avg_price": 1200,
                "booking_difficulty": "預約困難",
                "signature_dishes": ["頂級肉品", "海鮮套餐", "杏仁豆腐"],
                "atmosphere_tags": ["精緻", "商務"],
            }
        ],
        recommended_shop_ids=[10009],
        answer="",
        public_web_url="https://bytebites.example.com",
    )

    texts = [
        item["text"]
        for item in message["messages"][1]["contents"]["contents"][0]["body"]["contents"]
        if item.get("type") == "text"
    ]
    joined = " ".join(texts)
    assert "預約困難" not in joined
    assert "頂級肉品" in joined
    assert "海鮮套餐" in joined


def test_build_line_flex_message_versions_photo_url():
    message = build_line_flex_message(
        shops=[{"shop_id": 10115, "name": "辛殿麻辣鍋｜信義店"}],
        recommended_shop_ids=[10115],
        answer="",
        public_web_url="https://bytebites.example.com",
    )

    hero_url = message["messages"][1]["contents"]["contents"][0]["hero"]["url"]
    assert hero_url.startswith("https://bytebites.example.com/line/photo/10115?v=")


@pytest.mark.anyio
async def test_reply_messages_returns_preview_when_disabled():
    result = await reply_messages(
        reply_token="reply-token",
        messages=[{"type": "text", "text": "hello"}],
        channel_access_token="",
        enabled=False,
    )

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["messages_preview"][0]["text"] == "hello"
