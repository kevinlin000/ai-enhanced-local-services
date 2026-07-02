from __future__ import annotations

import json
import re
from urllib.parse import quote_plus


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def line_public_uri(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def line_booking_path(
    shop_id: int,
    line_token: str = "",
    name: str = "",
    district: str = "",
    mrt: str = "",
    avg_price: str = "",
) -> str:
    params = {
        "lt": line_token,
        "name": name,
        "district": district,
        "mrt": mrt,
        "avgPrice": avg_price,
    }
    query = "&".join(
        f"{key}={quote_plus(str(value))}"
        for key, value in params.items()
        if str(value or "").strip()
    )
    return f"/line/book/{shop_id}?{query}" if query else f"/line/book/{shop_id}"


def line_google_maps_uri(name: str, address: str) -> str:
    query = " ".join(part for part in [name.strip(), address.strip()] if part)
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query or name or address or '台北餐廳')}"


def dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def truncate_words(text: str, max_length: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def line_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-store">
  <meta http-equiv="Pragma" content="no-cache">
  <title>{html_escape(title)}</title>
  <style>
    body {{ margin:0; background:#f7f3ec; color:#171512; font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif; }}
    .hero {{ position:relative; width:100%; aspect-ratio:16/10; overflow:hidden; background:#e8e1d5; }}
    .hero img {{ width:100%; height:100%; object-fit:cover; display:block; }}
    .hero span {{ display:none; }}
    .hero-fallback {{ display:flex; align-items:center; justify-content:center; color:#16833a; font-size:18px; font-weight:900; letter-spacing:0; }}
    .hero-fallback span {{ display:block; }}
    main {{ padding:24px 20px 36px; }}
    .eyebrow {{ margin:0 0 8px; color:#16833a; font-size:12px; font-weight:800; letter-spacing:0; }}
    h1 {{ margin:0; font-size:30px; line-height:1.18; letter-spacing:0; }}
    h2 {{ margin:0 0 8px; font-size:16px; }}
    .meta {{ margin-top:10px; color:#6f6a62; font-weight:700; }}
    section {{ margin-top:22px; padding:16px; border:1px solid rgba(0,0,0,.08); border-radius:8px; background:rgba(255,255,255,.72); }}
    p {{ line-height:1.7; }}
    a {{ color:#16833a; font-weight:800; text-decoration:none; }}
    .pills {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .pills span {{ border-radius:999px; background:#eaf4ec; color:#16833a; font-size:12px; font-weight:900; padding:6px 10px; }}
    .bullets {{ margin:10px 0 0; padding-left:18px; line-height:1.65; }}
    .bullets li + li {{ margin-top:6px; }}
    .review {{ margin-top:12px; padding-left:12px; border-left:3px solid #f1c45c; }}
    .review p {{ margin:6px 0 0; color:#514d47; }}
    .parking-list {{ display:grid; gap:10px; margin-top:12px; }}
    .parking-card {{ padding:12px; border:1px solid rgba(0,0,0,.08); border-radius:8px; background:#fff; }}
    .parking-card p {{ margin:6px 0 0; color:#514d47; font-size:14px; }}
    .parking-card a {{ display:inline-flex; margin-top:10px; margin-right:10px; }}
    .parking-card .parking-reserve {{ align-items:center; justify-content:center; min-height:36px; border-radius:8px; background:#16833a; color:#fff; padding:0 12px; }}
    .hours p {{ margin:4px 0; }}
    .status-list p {{ margin:6px 0; }}
    .booking-form {{ display:grid; gap:14px; margin-top:12px; }}
    .payment-options {{ display:grid; gap:10px; margin-top:12px; }}
    .payment-option {{ display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:12px; padding:12px 14px; border:1px solid rgba(0,0,0,.12); border-radius:8px; background:#fff; cursor:pointer; }}
    .payment-option input {{ width:18px; height:18px; min-height:18px; margin:0; padding:0; accent-color:#16833a; }}
    .payment-option span {{ color:#6f6a62; font-size:13px; font-weight:700; text-align:right; }}
    .payment-option:has(input:checked) {{ border-color:#16833a; background:#eef8f1; }}
    label {{ display:grid; gap:6px; color:#514d47; font-size:13px; font-weight:800; }}
    input, select {{ min-height:48px; border:1px solid rgba(0,0,0,.14); border-radius:8px; background:#fff; color:#171512; font:inherit; font-size:16px; padding:0 12px; }}
    button {{ border:0; font:inherit; cursor:pointer; }}
    .actions {{ display:grid; gap:10px; margin-top:22px; }}
    .primary, .secondary {{ display:flex; align-items:center; justify-content:center; min-height:52px; border-radius:8px; font-weight:900; text-decoration:none; width:100%; box-sizing:border-box; }}
    main > .primary, main > .secondary {{ margin-top:22px; }}
    .primary {{ background:#16833a; color:#fff; }}
    .secondary {{ background:#e3e5e9; color:#171512; }}
    strong {{ font-weight:900; }}
  </style>
</head>
<body>{body}</body>
</html>"""


def line_html_page(title: str, message: str, links: list[tuple[str, str]]) -> str:
    link_html = "".join(f'<a class="primary" href="{html_escape(href)}">{html_escape(label)}</a>' for label, href in links)
    return line_shell(title, f"<main><h1>{html_escape(title)}</h1><p>{html_escape(message)}</p>{link_html}</main>")


def line_display_rating(raw) -> str:
    try:
        rating = float(raw)
    except (TypeError, ValueError):
        return ""
    if rating <= 0:
        return ""
    if 5 < rating <= 50:
        rating = rating / 10
    return f"{rating:.1f}".rstrip("0").rstrip(".")


def line_parse_hours(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        labels = {
            "mon": "週一",
            "tue": "週二",
            "wed": "週三",
            "thu": "週四",
            "fri": "週五",
            "sat": "週六",
            "sun": "週日",
        }
        hours = []
        for key in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            value = str(raw.get(key) or "").strip()
            if value:
                hours.append(f"{labels[key]} {value}")
        return hours
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None:
        return line_parse_hours(parsed)
    return [f"每日 {text}"] if re.fullmatch(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", text) else [text]


def line_review_rating(review: dict) -> float:
    try:
        return float(review.get("rating") or 0)
    except (TypeError, ValueError):
        return 0.0


def line_review_card_html(label: str, review: dict) -> str:
    rating = int(line_review_rating(review))
    text = html_escape(truncate_words(str(review.get("text") or ""), 90))
    author = html_escape(str(review.get("author") or "Google 評論"))
    return f'<div class="review"><div><strong>{label}</strong> · {author} · {"★" * rating}</div><p>{text}</p></div>'


def line_bullet_html(items: list[str]) -> str:
    clean = [html_escape(str(item)) for item in items if str(item).strip()]
    if not clean:
        return "<p>目前資料不足，建議先查看評論與店家資訊。</p>"
    return '<ul class="bullets">' + "".join(f"<li>{item}</li>" for item in clean[:5]) + "</ul>"


def line_pills_html(items: list[str]) -> str:
    clean = [html_escape(str(item)) for item in items if str(item).strip()]
    if not clean:
        return ""
    return '<div class="pills">' + "".join(f"<span>{item}</span>" for item in clean[:6]) + "</div>"


def line_hours_html(hours: list[str]) -> str:
    clean = [html_escape(str(item)) for item in hours if str(item).strip()]
    if not clean:
        return '<div class="hours"><p>營業時間資料未標示</p></div>'
    return '<div class="hours">' + "".join(f"<p>{item}</p>" for item in clean[:7]) + "</div>"


def line_parking_distance(value: object) -> str:
    try:
        meters = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{max(1, meters)} m"


def line_parking_spaces(lot: dict) -> str:
    available = lot.get("availableCar")
    total = lot.get("totalCar")
    if isinstance(available, int) and isinstance(total, int):
        return f"剩 {available} / {total} 格"
    if isinstance(available, int):
        return f"剩 {available} 格"
    if isinstance(total, int):
        return f"共 {total} 格"
    return "車位資料更新中"
