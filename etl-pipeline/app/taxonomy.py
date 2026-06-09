from __future__ import annotations

import re

PRIMARY_TYPE_MAP = {
    "hot_pot_restaurant": 2001,
    "shabu_shabu_restaurant": 2001,
    "soup_restaurant": 2001,
    "sukiyaki_restaurant": 2001,
    "barbecue_restaurant": 2010,
    "korean_barbecue_restaurant": 2009,
    "korean_restaurant": 2009,
    "yakiniku_restaurant": 2002,
    "mongolian_barbecue_restaurant": 2001,
    "yakitori_restaurant": 2003,
    "japanese_pub": 2003,
    "izakaya": 2003,
    "japanese_izakaya_restaurant": 2003,
    "japanese_restaurant": 2004,
    "ramen_restaurant": 2004,
    "sushi_restaurant": 2004,
    "udon_noodle_restaurant": 2004,
    "vegetarian_restaurant": 2005,
    "vegan_restaurant": 2005,
    "italian_restaurant": 2007,
    "french_restaurant": 2007,
    "european_restaurant": 2007,
    "pizza_restaurant": 2007,
    "spanish_restaurant": 2007,
    "bistro": 2007,
    "gastropub": 2007,
    "mediterranean_restaurant": 2007,
    "middle_eastern_restaurant": 2013,
    "indian_restaurant": 2013,
    "thai_restaurant": 2013,
    "vietnamese_restaurant": 2013,
    "mexican_restaurant": 2013,
    "chinese_restaurant": 2008,
    "taiwanese_restaurant": 2008,
    "cantonese_restaurant": 2008,
    "dim_sum_restaurant": 2008,
    "dumpling_restaurant": 2008,
    "chinese_noodle_restaurant": 2008,
    "seafood_restaurant": 2008,
    "asian_restaurant": 2008,
    "cafeteria": 2011,
    "buffet_restaurant": 2011,
    "brunch_restaurant": 2010,
    "american_restaurant": 2010,
    "australian_restaurant": 2010,
    "mexican_restaurant": 2010,
    "hamburger_restaurant": 2010,
    "breakfast_restaurant": 2010,
    "hot_dog_restaurant": 2010,
    "bar_and_grill": 2010,
    "steak_house": 2010,
    "cafe": 2012,
    "coffee_shop": 2012,
    "dessert_shop": 2012,
    "pastry_shop": 2012,
    "tea_house": 2012,
    "food_court": 2008,
    "restaurant": 2008,
    "bar": 2003,
}

FALLBACK_PRIMARY_TYPE_VALUES = {"restaurant", "food_court", None, ""}
AMBIGUOUS_PRIMARY_TYPE_VALUES = FALLBACK_PRIMARY_TYPE_VALUES | {
    "asian_restaurant",
    "barbecue_restaurant",
    "middle_eastern_restaurant",
    "seafood_restaurant",
}

MANUAL_AUDIT_PRIMARY_OVERRIDES = (
    ("青青食尚花園會館", 2007),
    ("溫咖哩 Wen Curry", 2004),
    ("瀧厚炙燒熟成牛排 台北.北車店", 2010),
    ("沾美西餐廳", 2007),
    ("SALT&STONE", 2007),
    ("樂野食", 2007),
    ("北投文物館", 2004),
    ("秦味館", 2008),
    ("孫立人將軍官邸", 2008),
    ("大嗑西式餐館", 2007),
    ("莎諾西餐", 2007),
    ("士林放感情餐酒館", 2007),
    ("泰和樓", 2008),
    ("頁小館", 2007),
    ("築本屋公館店", 2004),
    ("泰市場", 2011),
    ("漢來上海湯包", 2008),
    ("Moni咖哩", 2004),
    ("KOBE SWEETS CAFE", 2012),
    ("蘭亭燒肉", 2002),
    ("茶茶王國", 2012),
    ("波 WAVE", 2007),
    ("夏綠沁私房義大利麵燉飯", 2007),
    ("東京廚房", 2004),
    ("詹咖李", 2004),
    ("Tierra Casa", 2007),
    ("TankQ", 2010),
    ("燒肉中山", 2002),
    ("樂軒松阪亭", 2002),
    ("大樹先生的家", 2007),
    ("發肉燒肉餐酒忠孝二店", 2002),
    ("大河牧場 漢堡排專売", 2004),
    ("大叔食事", 2004),
    ("ONE GOOD烤肉飯", 2004),
    ("小尚品精制鍋物", 2001),
    ("蘋果肉桂", 2012),
    ("小蔬同手作蔬食", 2005),
    ("和牛涮台北忠孝東店", 2001),
    ("狗一下居食酒堂-忠孝店", 2003),
    ("豐 FOOD", 2011),
    ("尬鍋", 2001),
    ("和牛涮 台北羅斯福店", 2001),
    ("金洹苑", 2002),
    ("林美如", 2008),
    ("山上走走 日式燒肉", 2002),
    ("西堤牛排台北羅斯福店", 2007),
    ("solo pasta", 2007),
    ("麵屋 千雲", 2004),
    ("大阪燒肉 燒魂", 2002),
    ("艾朋牛排餐酒館", 2007),
    ("老井極上燒肉", 2002),
    ("Meat Up", 2010),
    ("藝奇", 2004),
    ("新馬辣經典麻辣鍋", 2001),
    ("大村武串燒居酒屋", 2003),
    ("歐買尬日式海鮮串燒 市民一店", 2004),
    ("熊一頂級燒肉", 2002),
    ("夏慕尼", 2007),
    ("旭集", 2011),
    ("小倉庫食研所", 2010),
    ("GYUU NIKU", 2004),
    ("一蘭", 2004),
    ("饗食天堂", 2011),
    ("燒肉神保町", 2002),
    ("赤富士日式燒肉鍋物", 2002),
    ("TakeOut Burger&Cafe 忠孝新生店", 2010),
    ("老倉庫", 2010),
    ("錢都日式涮涮鍋 台北延平店", 2001),
    ("好食多涮涮鍋", 2001),
    ("辛殿麻辣鍋", 2001),
    ("陶板屋", 2004),
    ("HOOTERS", 2010),
    ("狗一下居食酒屋-西門店", 2003),
    ("WOW Bistro", 2007),
    ("下港吔羊肉", 2001),
    ("亞瑟蘭印度餐廳", 2013),
    ("亞瑟蘭印度料理", 2013),
    ("馬友友印度廚房", 2013),
    ("莎瓦迪卡海鮮.泰", 2013),
    ("初泰Pikul", 2013),
    ("塔吉摩洛哥料理", 2013),
    ("非常泰", 2013),
)

NAME_PRIMARY_OVERRIDES = MANUAL_AUDIT_PRIMARY_OVERRIDES + (
    ("鼎泰豐", 2008),
    ("一蘭", 2004),
    ("旭集", 2011),
    ("饗饗", 2011),
    ("INPARADISE", 2011),
    ("饗食天堂", 2011),
    ("島語", 2011),
    ("一千零一夜廚房", 2011),
    ("老井極上燒肉", 2002),
    ("肉執事", 2002),
    ("燒肉Smile", 2002),
    ("肉次方", 2002),
    ("弘大一號出口", 2009),
    ("梨谷韓式鐵板烤肉", 2009),
    ("一番地", 2001),
    ("竹村居酒屋", 2003),
    ("古記雞.私房菜.居酒屋", 2003),
    ("武侍酒", 2003),
    ("板前屋", 2003),
    ("呼嚕小酒館", 2007),
    ("The Public House", 2007),
    ("Woolloomooloo", 2007),
    ("夏慕尼", 2007),
    ("西堤", 2007),
    ("徙巷小餐酒", 2007),
    ("HOOTERS", 2010),
    ("Bogart's", 2010),
    ("Fa Burger", 2010),
    ("Takeout Burger", 2010),
    ("Takeout burger", 2010),
    ("Juicy Bun", 2010),
    ("樂子", 2010),
    ("M One Cafe", 2010),
    ("BRUN不然", 2010),
    ("Second Floor", 2010),
    ("貳樓", 2010),
    ("B&B STEAK", 2010),
    ("WilsonPark", 2010),
    ("品田牧場", 2010),
    ("TankQ", 2010),
    ("BT BURGER", 2010),
    ("BURGER OUT", 2010),
    ("莫克漢堡", 2010),
    ("大樹先生的家", 2010),
    ("小倉庫食研所", 2010),
    ("軟食力", 2010),
    ("Pastaio", 2007),
    ("Pastai", 2007),
    ("Pizzeria", 2007),
    ("Trattoria", 2007),
    ("gonnaEAT", 2007),
    ("AN58", 2007),
    ("Hanna Pasta", 2007),
    ("HANNA Pasta", 2007),
    ("A Beach", 2007),
    ("A-LI阿理義式廚房", 2007),
    ("布納咖啡館", 2012),
    ("2J CAFE", 2012),
    ("Uh huh cafe", 2012),
    ("嗯哼咖啡", 2012),
    ("正當冰", 2012),
    ("波赫士", 2012),
    ("貳號基地Cafe", 2012),
    ("疍宅", 2012),
    ("深夜裡的法國手工甜點", 2012),
    ("悠悠龍貓咖啡", 2012),
    ("小廢墟咖啡", 2012),
    ("初心菓寮", 2012),
    ("小小樹食", 2005),
    ("蔬食百匯", 2005),
    ("旭穗蔬食", 2005),
    ("VEGANala", 2005),
    ("原蔬生活", 2005),
    ("三個傻瓜印度蔬食", 2005),
    ("雞老闆", 2008),
    ("泰和樓", 2008),
    ("紅翻天", 2008),
    ("秦味館", 2008),
    ("漢來上海湯包", 2008),
    ("大河牧場", 2010),
    ("掌門精釀啤酒", 2003),
    ("來吧台北", 2003),
)

MANUAL_NO_KOREAN_TAG_OVERRIDES = (
    "TankQ",
    "燒肉中山",
    "樂軒松阪亭",
    "發肉燒肉餐酒忠孝二店",
    "大河牧場 漢堡排專売",
    "大叔食事",
    "ONE GOOD烤肉飯",
    "小尚品精制鍋物",
    "小蔬同手作蔬食",
    "和牛涮台北忠孝東店",
    "金洹苑",
)

BUFFET_KEYWORDS = {"自助餐", "buffet", "百匯", "cafeteria"}
HOTPOT_KEYWORDS = {
    "火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "酸菜白肉", "羊肉爐", "涮涮", "涮涮鍋",
    "涮涮屋", "壽喜燒", "鍋底", "鴛鴦鍋", "shabu", "石二鍋", "詹記",
}
YAKINIKU_KEYWORDS = {"燒肉", "烤肉", "和牛燒肉", "牛舌", "韓式烤肉"}
IZAKAYA_KEYWORDS = {"居酒屋", "串燒", "酒場", "炭烤鰻魚飯", "精釀", "啤酒", "酒吧", "暢飲", "下酒"}
VEGETARIAN_KEYWORDS = {"蔬食", "vegan", "vegetarian", "素食"}
CAFE_KEYWORDS = {"甜點", "蛋糕", "下午茶", "手工甜點", "咖啡", "coffee", "cafe", "手沖", "拿鐵"}
BRUNCH_KEYWORDS = {"早午餐", "brunch", "漢堡", "diner", "burger", "美式", "班尼迪克"}
EUROPEAN_KEYWORDS = {
    "義式", "義大利", "法式", "歐陸", "pasta", "燉飯", "pizza", "披薩",
    "pizzeria", "trattoria", "西班牙", "spanish", "義大利麵",
}
JAPANESE_KEYWORDS = {"壽司", "生魚片", "拉麵", "天婦羅", "懷石", "沾麵", "烏龍麵"}
KOREAN_PRIMARY_KEYWORDS = {
    "韓式", "韓國", "韓廚", "韓式烤肉", "韓式料理", "韓式豬腳", "泡菜鍋", "石鍋拌飯", "部隊鍋",
    "금하동", "친구", "弘大", "東大門", "新村", "bornga", "uncle-k",
}
INTERNATIONAL_KEYWORDS = {
    "印度料理", "indian", "asrah", "清真", "halal", "印度烤餅", "窯烤雞塊", "瑪莎拉",
    "泰式料理", "泰國菜", "thai", "打拋", "月亮蝦餅", "綠咖哩",
    "越南料理", "越南河粉", "vietnamese", "pho",
    "中東料理", "middle eastern", "以色列", "鷹嘴豆泥", "hummus", "摩洛哥", "moroccan",
    "墨西哥料理", "mexican",
}
CHINESE_KEYWORDS = {"台菜", "滬菜", "粵菜", "港點", "熱炒", "台式", "川菜", "客家", "小籠包", "麵食", "鵝肉"}
STEAK_TAG_KEYWORDS = {"牛排", "steak"}
KOREAN_TAG_KEYWORDS = {"韓式", "韓國", "泡菜", "弘大"}
INDIAN_TAG_KEYWORDS = {"印度", "indian", "asrah", "瑪莎拉", "清真", "halal"}
THAI_TAG_KEYWORDS = {"泰式", "泰國", "thai", "打拋", "月亮蝦餅", "綠咖哩"}
MIDDLE_EASTERN_TAG_KEYWORDS = {"中東", "以色列", "鷹嘴豆泥", "hummus", "摩洛哥", "moroccan"}
FRENCH_TAG_KEYWORDS = {"法式", "french"}
ITALIAN_TAG_KEYWORDS = {"義式", "義大利", "italian", "pasta"}
BISTRO_TAG_KEYWORDS = {"餐酒館", "bistro", "pub", "小酒館"}
TEPPANYAKI_TAG_KEYWORDS = {"鐵板燒", "teppanyaki"}
SCENIC_TAG_KEYWORDS = {"景觀", "高空", "天際線", "101大樓"}
FAMILY_TAG_KEYWORDS = {"親子", "家庭", "小孩", "兒童"}

PREMIUM_BADGE_ALLOWLIST = {
    10101, 10111, 10114, 10191, 10198,
    10103, 10104, 10107, 10125, 10149, 10176,
}


def extract_avg_price(price_str: str | None) -> int | None:
    if not price_str or price_str == "未提及":
        return None
    nums = re.findall(r"\d+", price_str.replace(",", ""))
    if not nums:
        return None
    values = [int(n) for n in nums]
    if len(values) >= 2:
        return (values[0] + values[1]) // 2
    return values[0]


def _build_text_blob(shop: dict) -> str:
    ai = shop.get("ai_extracted", {}) or {}
    parts = [
        shop.get("display_name", ""),
        shop.get("primary_type", ""),
        " ".join(shop.get("types", []) or []),
        ai.get("ai_summary", ""),
        " ".join(ai.get("signature_dishes", []) or []),
        " ".join(ai.get("atmosphere_tags", []) or []),
        ai.get("booking_difficulty", ""),
        ai.get("price_per_person", ""),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _base_primary_type_id(shop: dict) -> int:
    primary_type = shop.get("primary_type")
    if primary_type in PRIMARY_TYPE_MAP:
        return PRIMARY_TYPE_MAP[primary_type]
    return 2008


def _should_run_keyword_correction(shop: dict) -> bool:
    primary_type = shop.get("primary_type")
    return primary_type in AMBIGUOUS_PRIMARY_TYPE_VALUES


def _apply_name_override(text: str, current_type_id: int) -> tuple[int, bool]:
    for keyword, override_type_id in NAME_PRIMARY_OVERRIDES:
        if keyword.lower() in text:
            return override_type_id, True
    return current_type_id, False


def _apply_keyword_correction(text: str, current_type_id: int) -> int:
    if _contains_any(text, BUFFET_KEYWORDS):
        return 2011
    if _contains_any(text, HOTPOT_KEYWORDS):
        return 2001
    if _contains_any(text, VEGETARIAN_KEYWORDS):
        return 2005
    if _contains_any(text, KOREAN_PRIMARY_KEYWORDS):
        return 2009
    if _contains_any(text, INTERNATIONAL_KEYWORDS):
        return 2013
    if _contains_any(text, YAKINIKU_KEYWORDS):
        return 2002
    if _contains_any(text, IZAKAYA_KEYWORDS) and current_type_id not in {2007, 2010}:
        return 2003
    if _contains_any(text, EUROPEAN_KEYWORDS):
        return 2007
    if _contains_any(text, BRUNCH_KEYWORDS) and current_type_id not in {2007}:
        return 2010
    if _contains_any(text, CAFE_KEYWORDS):
        return 2012
    if _contains_any(text, JAPANESE_KEYWORDS) and current_type_id not in {2001, 2002, 2003}:
        return 2004
    if _contains_any(text, CHINESE_KEYWORDS):
        return 2008
    return current_type_id


def _append_tag(tags: list[str], tag: str) -> None:
    if tag not in tags:
        tags.append(tag)


def _extract_tags(shop: dict, text: str) -> list[str]:
    tags: list[str] = []
    primary_type = shop.get("primary_type") or ""
    ai = shop.get("ai_extracted", {}) or {}
    atmosphere_tags = [str(tag) for tag in (ai.get("atmosphere_tags") or [])]
    name = str(shop.get("display_name", ""))
    suppress_korean_tag = any(keyword.lower() in text for keyword in MANUAL_NO_KOREAN_TAG_OVERRIDES)

    if primary_type == "brunch_restaurant" or _contains_any(text, {"brunch"}):
        _append_tag(tags, "Brunch")
    if _contains_any(text, {"早午餐"}):
        _append_tag(tags, "早午餐")
    if _contains_any(text, STEAK_TAG_KEYWORDS):
        _append_tag(tags, "牛排")
    if not suppress_korean_tag and (
        primary_type in {"korean_restaurant", "korean_barbecue_restaurant"} or _contains_any(text, KOREAN_TAG_KEYWORDS)
    ):
        _append_tag(tags, "韓式")
    if primary_type == "indian_restaurant" or _contains_any(text, INDIAN_TAG_KEYWORDS):
        _append_tag(tags, "印度")
    if primary_type == "thai_restaurant" or _contains_any(text, THAI_TAG_KEYWORDS):
        _append_tag(tags, "泰式")
    if primary_type == "middle_eastern_restaurant" or _contains_any(text, MIDDLE_EASTERN_TAG_KEYWORDS):
        _append_tag(tags, "中東")
    if _contains_any(text, FRENCH_TAG_KEYWORDS):
        _append_tag(tags, "法式")
    if primary_type == "italian_restaurant" or _contains_any(text, ITALIAN_TAG_KEYWORDS):
        _append_tag(tags, "義式")
    if primary_type in {"bistro", "gastropub"} or _contains_any(text, BISTRO_TAG_KEYWORDS):
        _append_tag(tags, "餐酒館")
    if _contains_any(text, TEPPANYAKI_TAG_KEYWORDS):
        _append_tag(tags, "鐵板燒")
    if _contains_any(text, BUFFET_KEYWORDS) or "吃到飽" in text or "放題" in text:
        _append_tag(tags, "吃到飽")

    for tag in ("約會", "商務", "包廂", "景觀", "親子"):
        if tag in atmosphere_tags:
            _append_tag(tags, tag)
    if _contains_any(text, SCENIC_TAG_KEYWORDS) or "Woolloomooloo" in name:
        _append_tag(tags, "景觀")
    if _contains_any(text, FAMILY_TAG_KEYWORDS):
        _append_tag(tags, "親子")

    return tags


def _extract_badges(shop: dict) -> list[str]:
    shop_id = shop.get("shop_id")
    if shop_id in PREMIUM_BADGE_ALLOWLIST:
        return ["高級"]
    return []


def classify_shop(shop: dict) -> dict[str, int | list[str]]:
    text = _build_text_blob(shop)
    primary_type_id = _base_primary_type_id(shop)
    primary_type_id, override_matched = _apply_name_override(text, primary_type_id)
    if not override_matched and _should_run_keyword_correction(shop):
        primary_type_id = _apply_keyword_correction(text, primary_type_id)

    badges = _extract_badges(shop)
    tags = _extract_tags(shop, text)

    return {
        "primary_type_id": primary_type_id,
        "badges": badges,
        "tags": tags,
    }
