import json
import os

from google import genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

EXTRACT_PROMPT = """你是餐廳資料分析師。根據以下 Google 評論、抽取結構化資訊。

餐廳：{name}
類型：{primary_type}
價位等級：{price_level}

評論（{review_count} 則）：
{reviews_text}

請輸出 JSON、格式如下：
{{
  "ai_summary": "50-80 字餐廳介紹、客觀描述特色與氛圍",
  "highlight_review": "從評論中挑 1 句最代表性的、30 字內",
  "signature_dishes": ["招牌菜1", "招牌菜2"],
  "atmosphere_tags": ["從以下選: 約會, 聚餐, 商務, 一人, 親子, 寵物友善"],
  "booking_difficulty": "預約困難 / 現場可入 / 未提及",
  "price_per_person": "具體價位區間如 $600-1000、或填「未提及」"
}}

重要規則：
1. 評論沒提到的欄位填「未提及」、絕不編造
2. signature_dishes 至少 1 個、至多 5 個、必須在評論中出現
3. atmosphere_tags 只能從給定清單選、不可自創
4. 輸出純 JSON、不要 markdown code block
"""


class Extractor:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def extract(self, shop: dict) -> dict:
        reviews_text = "\n\n".join(
            f"[{i + 1}] {review['text']}"
            for i, review in enumerate(shop.get("reviews", []))
            if review.get("text")
        )
        prompt = EXTRACT_PROMPT.format(
            name=shop["display_name"],
            primary_type=shop.get("primary_type", "未知"),
            price_level=shop.get("price_level", "未知"),
            review_count=len(shop.get("reviews", [])),
            reviews_text=reviews_text,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) > 1:
                text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
