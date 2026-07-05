"""查詢意圖解析與檢索排序層（自 main.py 機械搬出，行為不變）。

純函式：查詢條件抽取（分類/捷運/行政區/意圖）、候選過濾與各式 sort key。
IO（Qdrant/Gemini/Java 補查）留在 main.py。
"""
from __future__ import annotations

import json
import re
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo

from app.taxonomy import CATEGORY_BY_TYPE_ID as _tax_map

def taipei_today() -> date_cls:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


TYPE_ID_TO_CATEGORY: dict[int, str] = {
    tid: cat["slug"] for tid, cat in _tax_map.items()
}


INTENT_HINTS = {
    "約會": {"約會", "浪漫", "紀念日", "慶生"},
    "商務": {"商務", "請客", "正式", "聚會", "談生意", "談公事", "客戶"},
    "聚餐": {"聚餐", "朋友", "多人", "聚會"},
    "一人": {"一人", "一個人", "自己吃", "獨食", "單人"},
    "親子": {"親子", "小孩", "家庭"},
    "寵物友善": {"寵物", "毛孩"},
    "辣": {"吃辣", "麻辣", "嗜辣", "香辣", "辣的", "想吃辣"},
}


CATEGORY_HINTS = {
    "hotpot": {"火鍋", "鍋物", "麻辣鍋", "涮涮鍋", "shabu"},
    "yakiniku": {"燒肉", "烤肉", "yakiniku"},
    "izakaya": {"居酒屋", "串燒", "宵夜", "下酒", "下酒菜", "酒場", "酒吧", "精釀", "啤酒", "暢飲"},
    "japanese": {"日式", "日式料理", "日料", "日本料理", "壽司", "拉麵", "懷石"},
    "omakase": {"無菜單", "omakase"},
    "american": {"美式", "漢堡", "早午餐", "brunch", "牛排", "排餐", "steak"},
    "euro": {"義式", "法式", "義法", "歐陸", "義大利麵", "pasta", "pizza", "披薩"},
    "chinese": {"中菜", "中式", "台菜", "熱炒", "烤鴨", "港式", "粵菜", "川菜", "滬菜", "港點", "小籠包", "湯包", "上海湯包", "牛肉麵", "鵝肉"},
    "korean": {"韓式", "韓國料理", "豆腐鍋"},
    "international": {"異國料理", "印度料理", "泰式", "泰國菜", "越南料理", "中東料理", "墨西哥料理"},
    "vegetarian": {"素食", "蔬食", "全素", "蛋奶素", "vegan", "vegetarian"},
    # 注意：資料裡沒有 fine-dining slug；「高級/高檔/精緻」是奢華意圖（LUXURY_HINTS→wants_luxury）
    # 不是分類，「鐵板燒」實際掛在 euro/japanese 下。硬映射成分類會讓嚴格過濾全滅。
    "fine-dining": {"fine dining"},
    "cafe": {"咖啡", "咖啡廳", "下午茶", "甜點"},
}


CATEGORY_FALLBACK_KEYWORDS = {
    "hotpot": {"火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "涮涮屋", "涮涮鍋", "壽喜燒", "羊肉爐", "湯頭", "鴛鴦鍋", "鍋底"},
    "yakiniku": {"燒肉", "烤肉", "牛舌", "和牛燒肉"},
    "izakaya": {"居酒屋", "串燒", "烤串", "酒場", "酒吧", "精釀", "啤酒", "暢飲", "下酒菜"},
    "japanese": {"日式", "日式料理", "日料", "日本料理", "和食", "壽司", "生魚片", "拉麵", "天婦羅", "鰻魚飯"},
    "omakase": {"無菜單", "板前", "omakase"},
    "american": {"美式", "漢堡", "早午餐", "brunch", "牛排", "肋眼", "菲力", "排餐", "班尼迪克蛋"},
    "euro": {"義大利麵", "燉飯", "牛小排燉飯", "法式", "歐陸", "pasta", "pizza", "披薩"},
    "chinese": {"台菜", "熱炒", "烤鴨", "粵菜", "川菜", "滬菜", "港點", "中菜", "小籠包", "湯包", "上海湯包", "牛肉麵", "鵝肉"},
    "korean": {"韓式", "豆腐鍋", "炸雞", "石鍋拌飯"},
    "international": {"異國料理", "印度", "泰式", "泰國", "越南", "中東", "以色列", "墨西哥", "清真", "halal", "hummus"},
    "vegetarian": {"素食", "蔬食", "全素", "蛋奶素", "vegan", "vegetarian"},
    "fine-dining": {"fine dining", "高級餐廳", "高檔餐廳", "套餐", "品酒", "鐵板燒"},
    "cafe": {"咖啡", "拿鐵", "手沖", "甜點", "下午茶", "蛋糕"},
}


CATEGORY_CONFLICT_KEYWORDS = {
    "chinese": {
        "韓式",
        "韓國",
        "韓廚",
        "韓式烤肉",
        "韓式料理",
        "韓式豬腳",
        "韓義",
        "泡菜鍋",
        "石鍋拌飯",
        "部隊鍋",
        "義式",
        "義大利麵",
        "pasta",
        "pizza",
        "披薩",
        "日式",
        "日本料理",
        "壽司",
        "拉麵",
        "居酒屋",
        "串燒",
        "泰式",
        "泰國",
        "印度",
        "清真",
        "halal",
        "越南",
        "中東",
        "墨西哥",
        "美式",
        "漢堡",
        "brunch",
        "早午餐",
        "火鍋",
        "鍋物",
        "燒肉",
        "烤肉",
    },
    "korean": {
        "台菜",
        "臺菜",
        "中式",
        "中菜",
        "川菜",
        "粵菜",
        "港點",
        "義式",
        "義大利麵",
        "pasta",
        "日式",
        "日本料理",
        "壽司",
        "拉麵",
    },
    "japanese": {
        "台菜",
        "臺菜",
        "中式",
        "中菜",
        "韓式",
        "韓國",
        "韓廚",
        "義式",
        "義大利麵",
        "pasta",
    },
    "hotpot": {
        "韓式烤肉",
        "韓式燒肉",
        "日式燒肉",
        "和牛燒肉",
        "義大利麵",
        "pasta",
        "pizza",
        "早午餐",
        "brunch",
        "拉麵",
    },
    "yakiniku": {
        "台菜",
        "臺菜",
        "義大利麵",
        "pasta",
        "pizza",
        "火鍋",
        "鍋物",
        "拉麵",
        "咖啡",
        "甜點",
    },
}


CATEGORY_ALIASES = {
    "brunch": "american",
    "steakhouse": "american",
    "european": "euro",
    "cafe-premium": "cafe",
}


SUPPORTED_CATEGORY_SLUGS = set(CATEGORY_FALLBACK_KEYWORDS)


BURGER_QUERY_HINTS = {"漢堡", "burger", "burgers", "美式漢堡"}


BURGER_TEXT_HINTS = {"漢堡", "burger", "手拍牛肉", "美式漢堡"}


BURGER_BLOCK_HINTS = {"早餐", "早午餐", "brunch", "豆漿", "飯糰", "蛋餅", "燒餅", "軟食力"}


TAIWANESE_CUISINE_QUERY_HINTS = {
    "台菜",
    "臺菜",
    "台式料理",
    "臺式料理",
    "台灣料理",
    "臺灣料理",
    "台灣菜",
    "臺灣菜",
}


TAIWANESE_CUISINE_STRONG_HINTS = {
    "台菜",
    "臺菜",
    "台式",
    "臺式",
    "台灣料理",
    "臺灣料理",
    "台灣菜",
    "臺灣菜",
    "辦桌",
    "合菜",
    "古早味",
    "家常菜",
    "熱炒",
    "客家",
    "鵝肉",
    "三杯",
    "欣葉",
    "雞家莊",
    "阿城鵝肉",
}


TAIWANESE_CUISINE_BLOCK_HINTS = {
    "餐酒館",
    "bistro",
    "酒吧",
    "bar",
    "小酒館",
    "wine",
    "調酒",
    "精釀",
    "啤酒",
    "居酒屋",
    "酒場",
    "韓式",
    "韓國",
    "韓廚",
    "韓義",
    "泡菜鍋",
    "石鍋拌飯",
    "部隊鍋",
    "義式",
    "義大利麵",
    "pasta",
    "pizza",
    "披薩",
    "日式",
    "日本料理",
    "壽司",
    "拉麵",
    "泰式",
    "泰國",
    "印度",
    "清真",
    "halal",
    "越南",
    "中東",
    "墨西哥",
    "美式",
    "漢堡",
    "brunch",
    "早午餐",
    "火鍋",
    "鍋物",
    "燒肉",
    "烤肉",
}


BUSINESS_DINING_HINTS = {"商務", "請客", "正式", "包廂", "宴席", "聚餐", "老字號", "高級", "精緻"}


CONTEXT_INTENT_RULES = {
    "quiet_chat": {
        "query": {"聊天", "安靜", "久坐", "好聊", "慢慢聊"},
        "strong": {"安靜", "聊天", "舒適", "寬敞", "桌距", "久坐", "包廂", "自在", "放鬆"},
        "weak": {"約會", "精緻", "家庭", "親子"},
        "block": {
            "吵",
            "喧囂",
            "熱鬧",
            "桌距偏近",
            "桌距相對緊鄰",
            "緊鄰",
            "緊湊",
            "尖峰",
            "時間限制",
            "100分鐘",
            "油煙",
            "排隊",
            "熱炒",
            "燒肉",
            "烤網",
            "居酒屋",
            "串燒",
            "小酌",
            "微醺",
            "酒吧",
            "餐酒館",
        },
    },
    "business": {
        "query": {"商務", "請客", "宴客", "正式"},
        "strong": {"商務", "請客", "正式", "包廂", "宴席", "老字號", "高級", "精緻", "合菜"},
        "weak": {"安靜", "舒適", "桌距", "聚餐"},
        "block": {"酒吧", "餐酒館", "小酌", "吵", "喧囂", "油煙", "自助"},
    },
    "date": {
        "query": {"約會", "浪漫", "紀念日"},
        "strong": {"約會", "浪漫", "氣氛", "精緻", "安靜", "舒適"},
        "weak": {"甜點", "景觀", "調酒"},
        "block": {"吵", "喧囂", "油煙", "桌距偏近", "熱炒"},
    },
    "family": {
        "query": {"家庭", "親子", "小孩", "長輩"},
        "strong": {"家庭", "親子", "長輩", "寬敞", "安靜", "包廂", "舒適"},
        "weak": {"聚餐", "合菜"},
        "block": {"酒吧", "餐酒館", "吵", "喧囂", "排隊", "油煙"},
    },
}


CLOSED_SHOP_HINTS = {"暫停營業", "停業", "歇業", "永久停業", "設備整修", "結束營業"}


SPECIFIC_CUISINE_RULES = {
    "korean": {
        "query": {"韓式", "韓國料理", "韓國菜", "韓式料理", "韓式烤肉"},
        "strong": {
            "韓式",
            "韓國",
            "韓廚",
            "韓式烤肉",
            "韓國烤肉",
            "韓式燒肉",
            "泡菜鍋",
            "豆腐鍋",
            "部隊鍋",
            "豬肉湯飯",
            "韓式豬腳",
            "bornga",
            "홍대",
            "감자탕",
            "돼지국밥",
            "韓大佬",
            "弘大",
            "新村",
            "東大門",
        },
        "summary": {"韓式料理", "韓國料理", "韓式烤肉", "韓國烤肉", "韓式燒肉", "道地韓食", "韓式氛圍"},
        "block": {"日式燒肉", "yakiniku", "和牛燒肉", "居酒屋"},
    },
    "thai": {
        "query": {"泰式", "泰國料理", "泰國菜", "泰式料理"},
        "strong": {
            "泰式",
            "泰國",
            "thai",
            "莎瓦迪卡",
            "非常泰",
            "泰市場",
            "泰滾",
            "rolling thai",
            "pikul",
            "月亮蝦餅",
            "打拋",
            "冬蔭",
            "綠咖哩",
        },
        "summary": {"泰式料理", "泰國料理", "泰式火鍋", "泰國夜市", "南洋泰式"},
        "block": set(),
    },
    "indian": {
        "query": {"印度", "印度料理", "印度菜", "清真印度"},
        "strong": {
            "印度",
            "indian",
            "halal",
            "清真",
            "naan",
            "masala",
            "tandoori",
            "咖哩餃",
            "馬友友",
            "亞瑟蘭",
            "asrah",
            "三個傻瓜",
        },
        "summary": {"印度料理", "印度主廚", "印度廚房", "印度蔬食", "道地印度", "主打印度"},
        "block": {"日式咖哩", "日式", "雲の咖哩", "詹咖李", "moni咖哩"},
    },
}


def _canonical_category_slug(slug: str | None) -> str:
    normalized = str(slug or "").strip().lower()
    return CATEGORY_ALIASES.get(normalized, normalized)


STATION_HINTS = {
    "中山國小站": {"中山國小", "中山國小站"},
    "中山站": {"中山", "中山站"},
    "雙連站": {"雙連", "雙連站"},
    "行天宮站": {"行天宮", "行天宮站"},
    "市政府站": {"市政府", "市政府站"},
    "信義安和站": {"信義安和", "信義安和站", "大安站"},
    "象山站": {"象山", "象山站"},
    "芝山站": {"芝山", "芝山站"},
}


DISTRICT_HINTS = {
    "中山": {"中山區", "中山"},
    "信義": {"信義區", "信義"},
    "大安": {"大安區", "大安"},
    "松山": {"松山區", "松山"},
    "中正": {"中正區", "中正"},
    "士林": {"士林區", "士林"},
    "內湖": {"內湖區", "內湖"},
    "南港": {"南港區", "南港"},
    "文山": {"文山區", "文山", "木柵", "景美", "萬芳"},
    "大同": {"大同區", "大同"},
    "萬華": {"萬華區", "萬華", "西門"},
    "北投": {"北投區", "北投", "天母"},
}


STATION_NEIGHBORHOODS = {
    "中山國小": {"中山國小": 1.0, "行天宮": 0.55, "雙連": 0.45, "中山": 0.35},
    "中山": {"中山": 1.0, "雙連": 0.75, "中山國小": 0.45},
    "雙連": {"雙連": 1.0, "中山": 0.75, "中山國小": 0.45},
    "市政府": {"市政府": 1.0, "信義安和": 0.55, "象山": 0.45},
    "信義安和": {"信義安和": 1.0, "市政府": 0.55, "象山": 0.35},
    "行天宮": {"行天宮": 1.0, "中山國小": 0.45, "雙連": 0.3},
    "象山": {"象山": 1.0, "市政府": 0.45, "信義安和": 0.35},
    "芝山": {"芝山": 1.0, "士林": 0.6, "明德": 0.55, "劍潭": 0.35},
}


LUXURY_HINTS = {"高級", "精緻", "約會大餐", "請客", "慶生", "高檔", "高價"}


HOTPOT_STRONG_HINTS = {"火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "涮涮鍋", "涮涮屋", "壽喜燒", "羊肉爐", "鴛鴦鍋"}


HOTPOT_BLOCK_HINTS = {"拉麵", "鐵板燒", "韓式烤肉", "燒肉", "串燒"}


def _resolve_taipei_district(address: str | None, fallback: str | None = None) -> str:
    text = str(address or "")
    for district in DISTRICT_HINTS:
        simplified_name = (
            district
            .replace("萬", "万")
            .replace("華", "华")
            .replace("義", "义")
            .replace("內", "内")
        )
        if (
            f"{district}區" in text
            or f"{district}区" in text
            or f"{simplified_name}区" in text
        ):
            return district
    return str(fallback or "").strip()


def _parse_json_list(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                return [str(item) for item in loaded if item]
        except Exception:
            return [raw]
    return []


def _payload_text(payload: dict) -> str:
    district = _resolve_taipei_district(payload.get("address"), payload.get("district"))
    parts: list[str] = [
        payload.get("name", ""),
        district,
        payload.get("mrt_station", ""),
        payload.get("address", ""),
        payload.get("category", ""),
        payload.get("ai_summary", ""),
        payload.get("booking_difficulty", ""),
        payload.get("price_per_person", ""),
    ]
    parts.extend(_parse_json_list(payload.get("signature_dishes")))
    parts.extend(_parse_json_list(payload.get("atmosphere_tags")))
    return " ".join(str(part) for part in parts if part).lower()


def _extract_query_constraints(query: str) -> dict:
    query_lower = query.lower()
    stations = []
    for canonical, keywords in STATION_HINTS.items():
        matched_station = False
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if not keyword_lower.endswith("站") and f"{keyword_lower}區" in query_lower:
                continue
            if keyword_lower in query_lower:
                matched_station = True
                break
        if matched_station:
            station = canonical.replace("站", "")
            if station not in stations:
                stations.append(station)
    # Longer station names should dominate shorter substring matches.
    # Example: "中山國小" must not also become the broader "中山" station.
    for station in list(stations):
        if any(station != other and station in other for other in stations):
            stations.remove(station)

    districts = []
    for canonical, keywords in DISTRICT_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            districts.append(canonical)

    categories = []
    for category, keywords in CATEGORY_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            canonical_category = _canonical_category_slug(category)
            if canonical_category not in categories:
                categories.append(canonical_category)

    wants_hot_seat = any(
        keyword in query_lower
        for keyword in ("hot seat", "flash deal", "熱座", "搶位", "限量", "秒殺", "限時餐券", "餐券", "優惠券", "折扣券")
    )
    wants_nearby = any(keyword in query_lower for keyword in ("附近", "nearby"))
    wants_luxury = any(keyword in query_lower for keyword in LUXURY_HINTS)
    wants_burger = any(keyword in query_lower for keyword in BURGER_QUERY_HINTS)
    wants_steak = any(keyword in query_lower for keyword in ("牛排", "排餐", "steak", "肋眼", "菲力"))
    wants_taiwanese_cuisine = any(keyword.lower() in query_lower for keyword in TAIWANESE_CUISINE_QUERY_HINTS)
    specific_cuisines = [
        cuisine
        for cuisine, rule in SPECIFIC_CUISINE_RULES.items()
        if any(keyword.lower() in query_lower for keyword in rule["query"])
    ]

    has_primary_food_category = any(category != "fine-dining" for category in categories)
    if wants_luxury and has_primary_food_category:
        categories = [category for category in categories if category != "fine-dining"]
    elif wants_luxury and not categories:
        categories.append("fine-dining")

    return {
        "stations": stations,
        "districts": districts,
        "categories": categories,
        "wants_hot_seat": wants_hot_seat,
        "wants_nearby": wants_nearby,
        "wants_luxury": wants_luxury,
        "wants_burger": wants_burger,
        "wants_steak": wants_steak,
        "wants_taiwanese_cuisine": wants_taiwanese_cuisine,
        "specific_cuisines": specific_cuisines,
    }


def _restaurant_clarification_gaps(query: str) -> list[str]:
    normalized = str(query or "").strip()
    constraints = _extract_query_constraints(normalized)
    gaps: list[str] = []
    has_location = bool(constraints["districts"] or constraints["stations"])
    has_explicit_location_text = bool(re.search(r"(台北|新北|[^\s，,。；;]{1,8}(區|站|路|街|商圈|夜市|百貨))", normalized))
    has_category = bool(
        constraints["categories"]
        or constraints.get("wants_burger")
        or constraints.get("specific_cuisines")
    )
    has_people = bool(re.search(r"[一二三四五六七八九十\d]+\s*(個)?人", normalized))
    has_datetime = bool(re.search(r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|早午餐|下午|[0-2]?\d[:：點時])", normalized))
    has_specific_context = bool(re.search(r"(聊天|約會|請客|慶生|商務|安靜|家庭|長輩|包廂)", normalized))
    if constraints.get("wants_nearby") and not (has_location or has_explicit_location_text):
        gaps.append("位置或捷運站")
    elif not has_location and not has_explicit_location_text and not has_category:
        gaps.append("地點或捷運站")
    if not has_category and not has_specific_context:
        gaps.append("料理類型或氣氛")
    if ("聚餐" in normalized or "多人" in normalized) and not has_people:
        gaps.append("人數")
    if not has_datetime and has_people and not has_category:
        gaps.append("日期或時段")
    deduped: list[str] = []
    for gap in gaps:
        if gap not in deduped:
            deduped.append(gap)
    return deduped[:3]


def _strip_specific_shop_keyword(text: str) -> str:
    raw = str(text or "").strip()
    intent_match = re.search(
        r"(?:我要訂|我想訂|想訂|幫我訂|我要|我想要|選|改成|換成)([^，,。.!！?？\n]{2,32})",
        raw,
    )
    normalized = (intent_match.group(1) if intent_match else raw).strip("，,。.!！?？")
    normalized = re.sub(
        r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|下午|早午餐|"
        r"(下|這|本)?(週|星期|禮拜)[一二三四五六日天]?)",
        "",
        normalized,
    )
    normalized = re.sub(r"20\d{2}\s*[年/\-.]\s*(1[0-2]|0?[1-9])\s*[月/\-.]\s*(3[01]|[12]\d|0?[1-9])\s*日?", "", normalized)
    normalized = re.sub(r"(1[0-2]|0?[1-9])\s*月\s*(3[01]|[12]\d|0?[1-9])\s*日?", "", normalized)
    normalized = re.sub(r"[0-2]?\d[:：點時](半|[0-5]?\d分?)?", "", normalized)
    normalized = re.sub(r"\s+[一二兩三四五六七八九十\d]{1,3}\s*人", "", normalized)
    normalized = re.sub(r"\d{1,3}\s*人", "", normalized)
    normalized = re.sub(r"^[一二兩三四五六七八九十]{1,3}\s*人", "", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    for phrase in (
        "幫我訂",
        "預約",
        "幫我找",
        "幫我",
        "那我要",
        "那我想要",
        "我要訂",
        "我想訂",
        "想訂",
        "我要",
        "我想要",
        "請幫我",
        "推薦",
        "想吃",
        "想找",
        "找",
        "可以嗎",
        "好了",
        "的",
        "餐廳",
    ):
        normalized = normalized.replace(phrase, "")
    return normalized.strip("，,。.!！?？")


def _specific_shop_keyword(text: str) -> str:
    keyword = _strip_specific_shop_keyword(text)
    if len(keyword) < 2 or len(keyword) > 18:
        return ""
    if re.fullmatch(r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|下午|早午餐|[0-2]?\d[:：點時]?)", keyword):
        return ""
    constraints = _extract_query_constraints(keyword)
    if constraints["categories"] or constraints.get("wants_burger") or constraints.get("specific_cuisines"):
        return ""
    if keyword in {"推薦", "找", "餐廳", "聚餐", "吃飯", "用餐", "聊天", "約會", "請客", "附近", "圖卡", "卡片"}:
        return ""
    if any(phrase in keyword for phrase in ("聚餐", "聊天", "約會", "請客", "附近", "好吃", "安靜", "商務")):
        return ""
    if any(keyword in values or keyword == district for district, values in DISTRICT_HINTS.items()):
        return ""
    station_values = {station.replace("站", "") for station in STATION_HINTS} | {
        value.replace("站", "") for values in STATION_HINTS.values() for value in values
    }
    if keyword in station_values:
        return ""
    return keyword


def _booking_shop_keyword(text: str) -> str:
    keyword = _strip_specific_shop_keyword(text)
    if len(keyword) < 2 or len(keyword) > 32:
        return ""
    if re.fullmatch(r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|下午|早午餐|[0-2]?\d[:：點時]?)", keyword):
        return ""
    if keyword in {"推薦", "找", "餐廳", "聚餐", "吃飯", "用餐", "聊天", "約會", "請客", "附近", "圖卡", "卡片"}:
        return ""
    if any(keyword in values or keyword == district for district, values in DISTRICT_HINTS.items()):
        return ""
    station_values = {station.replace("站", "") for station in STATION_HINTS} | {
        value.replace("站", "") for values in STATION_HINTS.values() for value in values
    }
    if keyword in station_values:
        return ""
    constraints = _extract_query_constraints(keyword)
    if (
        constraints["categories"]
        or constraints.get("wants_burger")
        or constraints.get("specific_cuisines")
    ) and len(keyword) <= 5:
        return ""
    return keyword


def _normalized_name(value: str) -> str:
    return re.sub(r"[\s｜|\-－_（）()·・.,，。!！?？]+", "", str(value or "").lower())


def _recommended_shop_name_score(query: str, shop: dict) -> int:
    normalized_query = _normalized_name(query)
    raw_name = str(shop.get("name") or "")
    normalized_name = _normalized_name(raw_name)
    if not normalized_query or not normalized_name:
        return 0
    if normalized_name in normalized_query:
        return 1000 + len(normalized_name)
    if normalized_query in normalized_name and len(normalized_query) >= 3:
        return 800 + len(normalized_query)

    parts = [
        _normalized_name(part)
        for part in re.split(r"[\s｜|\-－_（）()·・/／]+", raw_name)
        if _normalized_name(part)
    ]
    generic_parts = {"台北", "臺北", "信義", "中山", "大安", "松山", "中正", "大同", "萬華", "文山", "店", "分店"}
    matched = [
        part
        for part in parts
        if len(part) >= 3 and part not in generic_parts and part in normalized_query
    ]
    if not matched:
        return 0
    if not any(len(part) >= 4 for part in matched):
        return 0
    return sum(len(part) for part in matched)


def _is_restaurant_clarification_response(turn: dict) -> bool:
    if turn.get("role") != "model":
        return False
    if turn.get("clarification_query"):
        return True
    content = str(turn.get("content") or "")
    return any(
        marker in content
        for marker in (
            "收斂方向",
            "我才能把候選收斂",
            "直接回一句就好",
            "我就能開始精準篩選",
        )
    )


def _authoritative_category_slug(payload: dict) -> str:
    explicit_slug = _canonical_category_slug(payload.get("category_slug"))
    if explicit_slug:
        return explicit_slug

    category = str(payload.get("category") or "").lower()
    if "火鍋" in category:
        return "hotpot"
    if "燒肉" in category:
        return "yakiniku"
    if "居酒屋" in category:
        return "izakaya"
    if "日式料理" in category:
        return "japanese"
    if "無菜單" in category:
        return "omakase"
    if "牛排" in category:
        return "american"
    if "義法" in category:
        return "euro"
    if "中式" in category:
        return "chinese"
    if "韓式" in category:
        return "korean"
    if "素食" in category or "蔬食" in category:
        return "vegetarian"
    if "brunch" in category or "美式" in category:
        return "american"
    if "高級" in category:
        return "fine-dining"
    if "咖啡" in category:
        return "cafe"
    return ""


def _category_slug_from_payload(payload: dict) -> str:
    authoritative_slug = _authoritative_category_slug(payload)
    if authoritative_slug:
        return authoritative_slug

    text = _payload_text(payload)
    if any(keyword.lower() in text for keyword in {"鐵板燒", "fine dining", "高級餐廳", "高檔餐廳"}):
        return "fine-dining"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["hotpot"]):
        return "hotpot"
    if any(keyword.lower() in text for keyword in {"拉麵", "壽司", "生魚片", "鰻魚飯", "天婦羅"}):
        return "japanese"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["yakiniku"]):
        return "yakiniku"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["izakaya"]):
        return "izakaya"
    return ""


def _semantic_category_slug(payload: dict) -> str:
    authoritative_slug = _authoritative_category_slug(payload)
    if authoritative_slug:
        return authoritative_slug

    text = _payload_text(payload)
    if any(keyword.lower() in text for keyword in {"鐵板燒", "fine dining", "高級餐廳", "高檔餐廳"}):
        return "fine-dining"
    if _has_hotpot_semantics(payload):
        return "hotpot"
    if any(keyword.lower() in text for keyword in {"拉麵", "壽司", "生魚片", "鰻魚飯", "天婦羅"}):
        return "japanese"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["yakiniku"]):
        return "yakiniku"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["izakaya"]):
        return "izakaya"
    return _category_slug_from_payload(payload)


def _station_proximity_score(constraints: dict, payload: dict) -> float:
    mrt_station = str(payload.get("mrt_station") or "")
    if not constraints["stations"]:
        return 0.0

    score = 0.0
    text = _payload_text(payload)
    for target in constraints["stations"]:
        if target and (target in mrt_station or target.lower() in text):
            score = max(score, 1.0)
        score = max(score, STATION_NEIGHBORHOODS.get(target, {}).get(mrt_station, 0.0))
    return score


def _normalize_district_name(value: str | None) -> str:
    return str(value or "").strip().lower().removesuffix("區")


def _district_matches(constraints: dict, payload: dict) -> bool:
    district = _normalize_district_name(_resolve_taipei_district(payload.get("address"), payload.get("district")))
    return bool(district) and any(
        _normalize_district_name(target) == district
        for target in constraints["districts"]
    )


def _has_hotpot_semantics(payload: dict) -> bool:
    text = _payload_text(payload)
    has_strong_hint = any(keyword.lower() in text for keyword in HOTPOT_STRONG_HINTS)
    has_block_hint = any(keyword.lower() in text for keyword in HOTPOT_BLOCK_HINTS)
    if has_strong_hint:
        return True
    if has_block_hint:
        return False
    return any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["hotpot"])


def _is_burger_hit(payload: dict) -> bool:
    name = str(payload.get("name") or "").lower()
    if any(keyword.lower() in name for keyword in BURGER_BLOCK_HINTS):
        return False
    return any(keyword.lower() in name for keyword in BURGER_TEXT_HINTS)


def _taiwanese_identity_text(payload: dict) -> str:
    parts = [
        payload.get("name", ""),
        payload.get("category", ""),
        payload.get("ai_summary", ""),
    ]
    parts.extend(_parse_json_list(payload.get("atmosphere_tags")))
    return " ".join(str(part) for part in parts if part).lower()


def _is_taiwanese_cuisine_mismatch(payload: dict) -> bool:
    text = _taiwanese_identity_text(payload)
    return any(keyword.lower() in text for keyword in TAIWANESE_CUISINE_BLOCK_HINTS)


def _has_taiwanese_cuisine_semantics(payload: dict) -> bool:
    text = _payload_text(payload)
    return any(keyword.lower() in text for keyword in TAIWANESE_CUISINE_STRONG_HINTS)


def _has_explicit_category_conflict(payload: dict, requested_category: str) -> bool:
    text = _payload_text(payload)
    return any(
        keyword.lower() in text
        for keyword in CATEGORY_CONFLICT_KEYWORDS.get(requested_category, set())
    )


def _matches_requested_category(payload: dict, constraints: dict) -> bool:
    categories = constraints.get("categories", [])
    if not categories:
        return True

    text = _payload_text(payload)
    for requested in categories:
        requested = _canonical_category_slug(requested)
        if _has_explicit_category_conflict(payload, requested):
            continue

        if _authoritative_category_slug(payload) == requested:
            return True

        # 「自助餐」是用餐形式不是菜系：和食吃到飽同時屬於 buffet 與 japanese，
        # 只要文本有明確菜系關鍵詞就允許跨分類匹配。
        if _authoritative_category_slug(payload) == "buffet" and any(
            keyword.lower() in text
            for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())
        ):
            return True

        # Specific cuisines such as Thai/Indian can be represented under the
        # broader international category while still carrying clear cuisine text.
        if any(
            _matches_specific_cuisine(payload, cuisine)
            for cuisine in constraints.get("specific_cuisines", [])
        ):
            return True

        if not _authoritative_category_slug(payload):
            if _semantic_category_slug(payload) == requested:
                return True
            if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())):
                return True

    return False


def _normalized_rating(value) -> float:
    try:
        rating = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if rating > 5:
        rating = rating / 10
    return rating


def _is_inactive_search_hit(payload: dict) -> bool:
    is_active = payload.get("is_active")
    if isinstance(is_active, bool):
        return not is_active
    if str(is_active).strip().lower() in {"false", "0", "inactive", "disabled"}:
        return True

    text = " ".join(
        str(part)
        for part in (
            payload.get("name", ""),
            payload.get("ai_summary", ""),
            payload.get("booking_difficulty", ""),
        )
        if part
    )
    return any(keyword in text for keyword in CLOSED_SHOP_HINTS)


def _matches_specific_cuisine(payload: dict, cuisine: str) -> bool:
    rule = SPECIFIC_CUISINE_RULES.get(cuisine)
    if not rule:
        return False
    if _authoritative_category_slug(payload) == cuisine:
        return True
    primary_text = " ".join(
        str(part)
        for part in (
            payload.get("name", ""),
            payload.get("category", ""),
        )
        if part
    ).lower()
    summary_text = str(payload.get("ai_summary") or "").lower()
    if any(keyword.lower() in primary_text for keyword in rule["strong"]):
        return True
    return any(keyword.lower() in summary_text for keyword in rule.get("summary", set()))


def _is_specific_cuisine_mismatch(payload: dict, cuisine: str) -> bool:
    rule = SPECIFIC_CUISINE_RULES.get(cuisine)
    if not rule:
        return False
    if _matches_specific_cuisine(payload, cuisine):
        return False
    text = _payload_text(payload)
    return any(keyword.lower() in text for keyword in rule["block"])


def _specific_cuisine_sort_key(cuisine: str, hit: dict) -> tuple[int, int, int, int, float, float]:
    avg_price = int(hit.get("avg_price") or 0)
    return (
        1 if _matches_specific_cuisine(hit, cuisine) else 0,
        0 if _is_specific_cuisine_mismatch(hit, cuisine) else 1,
        1 if _semantic_category_slug(hit) in {cuisine, "international", "vegetarian", "yakiniku"} else 0,
        float(hit.get("rerank_score") or hit.get("score") or 0.0),
        avg_price,
        _normalized_rating(hit.get("rating")),
    )


def _taiwanese_cuisine_sort_key(constraints: dict, hit: dict) -> tuple[int, int, int, int, int, int, float, float]:
    tags = set(hit.get("atmosphere_tags") or [])
    text = _payload_text(hit)
    avg_price = int(hit.get("avg_price") or 0)
    rating = _normalized_rating(hit.get("rating"))
    return (
        1 if _has_taiwanese_cuisine_semantics(hit) else 0,
        0 if _is_taiwanese_cuisine_mismatch(hit) else 1,
        1 if any(keyword.lower() in text for keyword in BUSINESS_DINING_HINTS) else 0,
        1 if ({"商務", "聚餐"} & tags) else 0,
        1 if avg_price >= 800 else 0,
        1 if _semantic_category_slug(hit) == "chinese" else 0,
        float(hit.get("rerank_score") or hit.get("score") or 0.0),
        rating,
    )


def _burger_sort_key(constraints: dict, hit: dict) -> tuple[int, float, int, int, float]:
    return (
        1 if _district_matches(constraints, hit) else 0,
        _station_proximity_score(constraints, hit),
        1 if _semantic_category_slug(hit) == "american" else 0,
        int(hit.get("avg_price") or 0),
        float(hit.get("rerank_score") or hit.get("score") or 0.0),
    )


def _query_requests_steak(query: str) -> bool:
    return any(token in str(query or "").lower() for token in ("牛排", "排餐", "steak", "肋眼", "菲力"))


def _steak_match_score(hit: dict) -> int:
    text = _payload_text(hit)
    name = str(hit.get("name") or "").lower()
    dishes = " ".join(_parse_json_list(hit.get("signature_dishes"))).lower()
    score = 0
    if any(token in name for token in ("牛排", "steak", "排餐")):
        score += 4
    if any(token in dishes for token in ("牛排", "steak", "肋眼", "菲力", "牛小排", "肋排", "熟成牛")):
        score += 3
    if any(token in text for token in ("牛排", "steak", "肋眼", "菲力", "牛小排", "肋排", "排餐")):
        score += 2
    if any(token in name for token in ("漢堡", "burger", "早午餐", "brunch")):
        score -= 2
    return score


def _has_steak_semantics(hit: dict) -> bool:
    return _steak_match_score(hit) >= 3


def _steak_sort_key(constraints: dict, hit: dict) -> tuple[int, int, int, int, float, int, float]:
    tags = set(_parse_json_list(hit.get("atmosphere_tags")))
    return (
        1 if _district_matches(constraints, hit) else 0,
        _steak_match_score(hit),
        1 if "約會" in tags else 0,
        int(hit.get("avg_price") or 0),
        _normalized_rating(hit.get("rating")),
        int(hit.get("comments") or 0),
        float(hit.get("rerank_score") or hit.get("score") or 0.0),
    )


def _prioritize_steak_hits(query: str, constraints: dict, hits: list[dict]) -> list[dict]:
    if not _query_requests_steak(query):
        return hits
    steak_hits = [hit for hit in hits if _has_steak_semantics(hit)]
    if not steak_hits:
        return hits
    other_hits = [hit for hit in hits if hit not in steak_hits]
    steak_hits.sort(key=lambda hit: _steak_sort_key(constraints, hit), reverse=True)
    return steak_hits + other_hits


def _search_category_match(query: str, constraints: dict, hit: dict) -> bool:
    if _query_requests_steak(query) and _has_steak_semantics(hit):
        return True
    return _matches_requested_category(hit, constraints)


def _premium_hotpot_key(constraints: dict, hit: dict) -> tuple[int, int, int, int, int, float, int, int, float]:
    avg_price = hit.get("avg_price") or 0
    tags = set(hit.get("atmosphere_tags") or [])
    text = _payload_text(hit)
    station_score = _station_proximity_score(constraints, hit)
    district_match = 1 if _district_matches(constraints, hit) else 0
    has_premium_cues = 1 if any(
        keyword in text
        for keyword in (
            "和牛",
            "a5",
            "套餐",
            "無菜單",
            "松葉蟹",
            "龍蝦",
            "精緻",
            "頂級",
            "高品質",
            "涮涮屋",
            "杏仁豆腐",
            "海鮮套餐",
        )
    ) else 0
    premium_price = 1 if avg_price >= 1000 else 0
    mid_price = 1 if avg_price >= 800 else 0
    date_night = 1 if ({"約會", "商務"} & tags) else 0
    nearby_bucket = 0
    if constraints["wants_nearby"] or constraints["stations"]:
        if station_score >= 1.0:
            nearby_bucket = 3
        elif station_score >= 0.7:
            nearby_bucket = 2
        elif district_match:
            nearby_bucket = 1
    return (
        premium_price,
        has_premium_cues,
        nearby_bucket,
        district_match,
        1 if _semantic_category_slug(hit) == "hotpot" else 0,
        station_score,
        date_night or mid_price,
        1 if avg_price >= 800 else 0,
        hit["rerank_score"],
    )


def _metadata_bonus(query: str, payload: dict) -> float:
    query_lower = query.lower()
    constraints = _extract_query_constraints(query)
    bonus = 0.0
    district = _resolve_taipei_district(payload.get("address"), payload.get("district")).lower()
    mrt_station = str(payload.get("mrt_station") or "").lower()
    category = str(payload.get("category") or "").lower()
    category_slug = _semantic_category_slug(payload)
    booking_difficulty = str(payload.get("booking_difficulty") or "").lower()
    price_per_person = str(payload.get("price_per_person") or "").lower()
    avg_price = payload.get("avg_price") or 0
    tags = [tag.lower() for tag in _parse_json_list(payload.get("atmosphere_tags"))]
    dishes = [dish.lower() for dish in _parse_json_list(payload.get("signature_dishes"))]
    text = _payload_text(payload)
    fallback_keywords = CATEGORY_FALLBACK_KEYWORDS.get(category_slug, set())
    category_semantic_match = bool(
        category_slug in constraints["categories"]
        or any(keyword.lower() in text for keyword in fallback_keywords)
    )

    if district and district in query_lower:
        bonus += 0.18
    if mrt_station and mrt_station in query_lower:
        bonus += 0.18
    if category and category in query_lower:
        bonus += 0.14

    if constraints["districts"]:
        if _district_matches(constraints, payload):
            bonus += 0.42
        else:
            bonus -= 0.18

    if constraints["stations"]:
        best_station_score = _station_proximity_score(constraints, payload)

        if best_station_score >= 1.0:
            bonus += 0.5
        elif best_station_score >= 0.7:
            bonus += 0.28 * best_station_score
        elif best_station_score > 0:
            bonus += 0.12 * best_station_score
        elif constraints["wants_nearby"] and mrt_station:
            bonus -= 0.32
        elif constraints["wants_nearby"]:
            bonus -= 0.18

    if constraints["categories"]:
        if category_slug in constraints["categories"]:
            bonus += 0.5
        elif any(
            keyword.lower() in text
            for requested in constraints["categories"]
            for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())
        ):
            bonus += 0.2
        else:
            bonus -= 0.55

    if constraints.get("wants_taiwanese_cuisine"):
        if _has_taiwanese_cuisine_semantics(payload):
            bonus += 0.36
        if any(keyword.lower() in text for keyword in BUSINESS_DINING_HINTS):
            bonus += 0.18
        if _is_taiwanese_cuisine_mismatch(payload):
            bonus -= 0.75

    for cuisine in constraints.get("specific_cuisines", []):
        if _matches_specific_cuisine(payload, cuisine):
            bonus += 0.42
        elif _is_specific_cuisine_mismatch(payload, cuisine):
            bonus -= 0.65

    bonus += _context_intent_bonus(query, payload)

    for canonical, keywords in INTENT_HINTS.items():
        if any(keyword in query_lower for keyword in keywords):
            if canonical.lower() in tags or canonical.lower() in text:
                bonus += 0.18

    if any(keyword in query_lower for keyword in ("便宜", "平價", "cp值", "學生")):
        if avg_price and avg_price <= 300:
            bonus += 0.15
    if any(keyword in query_lower for keyword in LUXURY_HINTS):
        if avg_price and avg_price >= 800:
            bonus += 0.15
        if category_slug == "fine-dining":
            bonus += 0.18
        if "困難" in booking_difficulty or "提前" in booking_difficulty:
            bonus += 0.1
        if "約會" in tags or "商務" in tags:
            bonus += 0.12
        if avg_price and avg_price < 500:
            bonus -= 0.3
        elif avg_price and avg_price < 800:
            bonus -= 0.12
        elif not avg_price and "未提及" in price_per_person:
            bonus -= 0.08
    if any(keyword in query_lower for keyword in ("難訂", "熱門", "搶位")):
        if "困難" in booking_difficulty:
            bonus += 0.12
    if any(keyword in query_lower for keyword in ("套餐", "折扣", "優惠", "hot seat", "flash deal", "熱座", "搶位", "限時餐券", "餐券", "優惠券", "折扣券")):
        if payload.get("hot_seat_vouchers"):
            bonus += 0.35
        elif constraints["wants_hot_seat"]:
            bonus -= 0.25

    for dish in dishes[:5]:
        if dish and dish in query_lower:
            bonus += 0.12
    if price_per_person and any(token in query_lower for token in ("價位", "預算", "人均")):
        bonus += 0.08

    return bonus


def _context_intent_bonus(query: str, payload: dict) -> float:
    query_lower = str(query or "").lower()
    text = _payload_text(payload)
    tags = {tag.lower() for tag in _parse_json_list(payload.get("atmosphere_tags"))}
    bonus = 0.0
    for rule in CONTEXT_INTENT_RULES.values():
        if not any(token.lower() in query_lower for token in rule["query"]):
            continue
        strong = {token.lower() for token in rule["strong"]}
        weak = {token.lower() for token in rule["weak"]}
        block = {token.lower() for token in rule["block"]}
        strong_hits = sum(1 for token in strong if token in text or token in tags)
        weak_hits = sum(1 for token in weak if token in text or token in tags)
        block_hits = sum(1 for token in block if token in text or token in tags)
        if strong_hits:
            bonus += min(0.48, 0.22 + strong_hits * 0.1)
        if weak_hits:
            bonus += min(0.16, weak_hits * 0.06)
        if block_hits:
            bonus -= min(0.42, 0.18 + block_hits * 0.08)
    return bonus


def _fallback_keyword_score(query: str, payload: dict) -> float:
    query_lower = query.lower()
    text = _payload_text(payload)
    score = 0.0

    for category, keywords in CATEGORY_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if _semantic_category_slug(payload) == category:
                score += 0.35
            elif any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS.get(category, set())):
                score += 0.18

    for keywords in INTENT_HINTS.values():
        if any(keyword in query_lower for keyword in keywords):
            if any(keyword.lower() in text for keyword in keywords):
                score += 0.12

    for canonical, keywords in STATION_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if canonical.replace("站", "").lower() == str(payload.get("mrt_station") or "").lower():
                score += 0.35

    for canonical, keywords in DISTRICT_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if canonical.lower() == str(payload.get("district") or "").lower():
                score += 0.28

    if any(keyword in query_lower for keyword in ("hot seat", "flash deal", "熱座", "搶位", "限量", "秒殺", "限時餐券", "餐券", "優惠券", "折扣券")) and payload.get("hot_seat_vouchers"):
        score += 0.25

    return score


def _java_shop_to_search_hit(shop: dict, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    type_id = shop.get("typeId")
    payload = {
        "shop_id": shop.get("id"),
        "name": shop.get("name"),
        "district": _resolve_taipei_district(shop.get("address"), shop.get("district") or shop.get("area")),
        "address": shop.get("address"),
        "mrt_station": shop.get("mrtStation"),
        "score": 0.0,
        "rating": shop.get("score"),
        "comments": shop.get("comments"),
        "category": TYPE_ID_TO_CATEGORY.get(type_id),
        "category_slug": TYPE_ID_TO_CATEGORY.get(type_id),
        "type_id": type_id,
        "avg_price": shop.get("avgPrice"),
        "ai_summary": metadata.get("aiSummary"),
        "signature_dishes": _parse_json_list(metadata.get("signatureDishes")),
        "atmosphere_tags": _parse_json_list(metadata.get("atmosphereTags")),
        "booking_difficulty": metadata.get("bookingDifficulty"),
        "price_per_person": metadata.get("pricePerPerson"),
        "hot_seat_vouchers": [],
    }
    if not payload["category_slug"]:
        inferred = _category_slug_from_payload(payload)
        payload["category"] = inferred
        payload["category_slug"] = inferred
    return payload


def _private_ai_offer_is_off_peak_time(raw_time: str) -> bool:
    match = re.search(r"([01]?\d|2[0-3]):([0-5]\d)", raw_time or "")
    if not match:
        return False
    hour = int(match.group(1))
    minute = int(match.group(2))
    return (hour, minute) <= (17, 30)


TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_shops_by_mrt",
                "description": "查詢指定捷運站附近的店家。當使用者提到特定捷運站名（如「市政府」「中山國小」「中山」「信義安和」）時使用。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "station": {
                            "type": "STRING",
                            "description": "捷運站名，例如「市政府」「中山國小」「中山」",
                        },
                        "radius": {
                            "type": "INTEGER",
                            "description": "搜尋半徑（公尺），預設 500",
                        },
                    },
                    "required": ["station"],
                },
            },
            {
                "name": "semantic_shop_search",
                "description": "語意搜尋店家。當使用者描述抽象需求（如「想吃手搖飲」「適合約會」「有沒有限時餐券或秒殺優惠」），用此 tool。回應含 hot_seat_vouchers 欄位。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "create_hot_seat_order",
                "description": """為用戶搶限時餐券名額。當用戶明確說想搶餐券、想搶優惠、想下訂某個限時餐券時呼叫。
回應含 voucher_order_id。僅支援已啟動限時餐券的方案。
若用戶尚未指定 voucher_id，應先呼叫 semantic_shop_search 找店，再從回應的 hot_seat_vouchers 挑一個。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "voucher_id": {
                            "type": "INTEGER",
                            "description": "限時餐券方案 ID（從 search 結果 hot_seat_vouchers 取得，不要瞎猜）",
                        },
                    },
                    "required": ["voucher_id"],
                },
            },
            {
                "name": "create_booking",
                "description": """為用戶建立餐廳訂位。當用戶說「幫我訂位」「我要訂」「訂明天晚上」時呼叫。
回應含 bookingCode、needsDeposit、depositTotal。
若用戶沒指定日期預設明天；沒指定時間預設 19:00。
若尚未取得 shop_id，應先 semantic_shop_search 找到店家再呼叫本 tool。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "shop_id":    {"type": "INTEGER", "description": "店家 ID"},
                        "people":     {"type": "INTEGER", "description": "人數 1-12"},
                        "date":       {"type": "STRING",  "description": "日期 YYYY-MM-DD，預設明天"},
                        "time":       {"type": "STRING",  "description": "時間 HH:MM，預設 19:00"},
                        "table_type": {"type": "STRING",  "description": "normal/bar/private，預設 normal"},
                    },
                    "required": ["shop_id", "people"],
                },
            },
            {
                "name": "pay_booking_with_test_card",
                "description": """用 TapPay sandbox 測試卡為訂位支付訂金。
僅在使用者明確要求支付某個 bookingCode 時呼叫；不要在建立訂位後自動付款。
回應含 rec_trade_id（TapPay 交易編號）。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "booking_code": {
                            "type": "STRING",
                            "description": "create_booking 回應的 bookingCode",
                        },
                    },
                    "required": ["booking_code"],
                },
            },
            {
                "name": "update_booking",
                "description": """修改既有訂位的日期、時間、人數或座位類型。
僅在已知 bookingCode 且使用者明確要求改單時呼叫；不要用它建立新訂位。
若使用者只說「改 8 點，同樣 4 位」，沿用原訂位未提到的欄位。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "booking_code": {"type": "STRING", "description": "既有訂位編號"},
                        "people": {"type": "INTEGER", "description": "新訂位人數 1-12"},
                        "date": {"type": "STRING", "description": "新日期 YYYY-MM-DD"},
                        "time": {"type": "STRING", "description": "新時間 HH:MM"},
                        "table_type": {"type": "STRING", "description": "normal/bar/private"},
                    },
                    "required": ["booking_code"],
                },
            },
        ]
    }
]
