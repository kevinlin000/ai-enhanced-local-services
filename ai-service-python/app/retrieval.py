"""檢索層：Qdrant 語意搜尋、Java 補查、候選集組裝（自 main.py 機械搬出，行為不變）。"""
from __future__ import annotations

import httpx
from google.genai import types

from app.config import _agent_auth_token, get_gemini, get_qdrant, logger, settings
from app.ranking import (
    HOTPOT_BLOCK_HINTS,
    LUXURY_HINTS,
    TYPE_ID_TO_CATEGORY,
    _burger_sort_key,
    _category_slug_from_payload,
    _district_matches,
    _extract_query_constraints,
    _fallback_keyword_score,
    _has_explicit_category_conflict,
    _has_hotpot_semantics,
    _has_steak_semantics,
    _has_taiwanese_cuisine_semantics,
    _is_burger_hit,
    _is_inactive_search_hit,
    _is_taiwanese_cuisine_mismatch,
    _java_shop_to_search_hit,
    _matches_specific_cuisine,
    _metadata_bonus,
    _normalized_name,
    _parse_json_list,
    _payload_text,
    _premium_hotpot_key,
    _prioritize_steak_hits,
    _private_ai_offer_is_off_peak_time,
    _query_requests_steak,
    _resolve_taipei_district,
    _search_category_match,
    _semantic_category_slug,
    _specific_cuisine_sort_key,
    _specific_shop_keyword,
    _station_proximity_score,
    _steak_match_score,
    _steak_sort_key,
    _taiwanese_cuisine_sort_key,
    taipei_today,
)

_LINE_SHOP_NAME_FALLBACKS: dict[int, str] = {
    10009: "橘色涮涮屋 信義館",
}


PREMIUM_HOTPOT_SUPPLEMENT_IDS: tuple[int, ...] = ()


LEGACY_SEED_SHOP_IDS = {
    10001, 10002, 10003, 10004, 10005,
    10006, 10007, 10008, 10009, 10010,
    10011, 10012, 10013, 10014, 10015,
    10016, 10017, 10018, 10019, 10020,
    10021, 10022, 10023, 10024, 10025,
}


def _dedupe_search_hits(hits: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    positions: dict[int, int] = {}

    def quality(hit: dict) -> tuple[int, int, float, int]:
        return (
            _steak_match_score(hit),
            1 if _shop_has_rich_context(hit) else 0,
            float(hit.get("rerank_score") or hit.get("score") or 0.0),
            int(hit.get("comments") or 0),
        )

    for hit in hits:
        try:
            shop_id = int(hit.get("shop_id") or 0)
        except (TypeError, ValueError):
            shop_id = 0
        if not shop_id:
            deduped.append(hit)
            continue
        if shop_id not in positions:
            positions[shop_id] = len(deduped)
            deduped.append(hit)
            continue
        index = positions[shop_id]
        if quality(hit) > quality(deduped[index]):
            deduped[index] = hit
    return deduped


async def _fetch_all_shops_fallback() -> list[dict]:
    shops = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        category_resp = await client.get(f"{settings.java_backend_url}/api/category/list")
        categories = category_resp.json().get("data", []) if category_resp.status_code == 200 else []

        for category in categories:
            slug = category.get("slug")
            if not slug:
                continue
            resp = await client.get(
                f"{settings.java_backend_url}/api/category/{slug}/shops",
                params={"page": 1, "size": 50},
            )
            if resp.status_code == 200:
                shops.extend(resp.json().get("data", []))

        deduped: dict[int, dict] = {}
        for shop in shops:
            deduped[shop["id"]] = shop

        enriched = []
        for shop in deduped.values():
            try:
                meta_resp = await client.get(f"{settings.java_backend_url}/api/shop/{shop['id']}/ai-metadata")
                metadata = meta_resp.json().get("data") if meta_resp.status_code == 200 else None
            except Exception:
                metadata = None

            enriched.append(
                {
                    "shop_id": shop["id"],
                    "name": shop.get("name"),
                    "district": _resolve_taipei_district(shop.get("address"), shop.get("district")),
                    "address": shop.get("address"),
                    "mrt_station": shop.get("mrtStation"),
                    "score": 0.0,
                    "rating": shop.get("score"),
                    "comments": shop.get("comments"),
                    "category": TYPE_ID_TO_CATEGORY.get(shop.get("typeId")),
                    "category_slug": TYPE_ID_TO_CATEGORY.get(shop.get("typeId")),
                    "avg_price": shop.get("avgPrice"),
                    "ai_summary": metadata.get("aiSummary") if metadata else None,
                    "signature_dishes": _parse_json_list(metadata.get("signatureDishes")) if metadata else [],
                    "atmosphere_tags": _parse_json_list(metadata.get("atmosphereTags")) if metadata else [],
                    "booking_difficulty": metadata.get("bookingDifficulty") if metadata else None,
                    "price_per_person": metadata.get("pricePerPerson") if metadata else None,
                }
            )
    return enriched


def _is_legacy_seed_hit(hit: dict) -> bool:
    try:
        shop_id = int(hit.get("shop_id") or 0)
    except (TypeError, ValueError):
        return False
    return shop_id in LEGACY_SEED_SHOP_IDS


def _prefer_rich_hits(hits: list[dict], top_k: int) -> list[dict]:
    if not hits:
        return hits
    rich_hits = [hit for hit in hits if not _is_legacy_seed_hit(hit)]
    skipped = [hit.get("name") for hit in hits if _is_legacy_seed_hit(hit)]
    if skipped:
        logger.warning("search_legacy_seed_filtered skipped=%s", skipped[:8])
        return rich_hits[:top_k]
    if rich_hits:
        return rich_hits[:top_k]
    return hits


async def _premium_hotpot_supplements(constraints: dict, existing_ids: set[int]) -> list[dict]:
    if "hotpot" not in constraints["categories"] or not constraints.get("wants_luxury"):
        return []

    supplements: list[dict] = []
    for shop_id in PREMIUM_HOTPOT_SUPPLEMENT_IDS:
        if shop_id in existing_ids:
            continue
        shop = await _fetch_java_shop(shop_id)
        if not shop:
            continue
        hit = _java_shop_to_search_hit(shop, await _fetch_java_ai_metadata(shop_id))
        if not _has_hotpot_semantics(hit):
            continue
        if constraints["districts"] and not _district_matches(constraints, hit):
            continue
        hit["ai_summary"] = hit.get("ai_summary") or "精緻涮涮屋路線，主打高品質食材、細緻服務與較正式的聚餐氛圍。"
        hit["signature_dishes"] = hit.get("signature_dishes") or ["頂級肉品", "海鮮套餐", "杏仁豆腐"]
        hit["atmosphere_tags"] = hit.get("atmosphere_tags") or ["精緻", "商務", "約會"]
        hit["price_per_person"] = hit.get("price_per_person") or f"NT$ {hit.get('avg_price')}"
        supplements.append(hit)
    return supplements


async def _burger_supplements(constraints: dict, existing_ids: set[int], limit: int = 12) -> list[dict]:
    if not constraints.get("wants_burger"):
        return []

    supplements: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": "burger", "page": 1, "size": max(limit, 12)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("burger_supplement_failed")
        return []

    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id or shop_id in existing_ids:
            continue
        hit = _java_shop_to_search_hit(shop)
        hit["rerank_score"] = float(hit.get("score") or 0.0) + _metadata_bonus("漢堡 美式餐廳", hit)
        if not _is_burger_hit(hit):
            continue
        supplements.append(hit)

    supplements.sort(key=lambda hit: _burger_sort_key(constraints, hit), reverse=True)
    return supplements[:limit]


async def _steak_supplements(query: str, constraints: dict, _existing_ids: set[int], limit: int = 8) -> list[dict]:
    if not _query_requests_steak(query):
        return []

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": "牛排", "page": 1, "size": max(limit, 12)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("steak_supplement_failed")
        return []

    supplements: list[dict] = []
    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id:
            continue
        metadata = await _fetch_java_ai_metadata(shop_id)
        hit = _java_shop_to_search_hit(shop, metadata)
        if constraints["districts"] and not _district_matches(constraints, hit):
            continue
        if not _has_steak_semantics(hit):
            continue
        hit["score"] = max(float(hit.get("score") or 0.0), 2.5)
        hit["rerank_score"] = float(hit.get("score") or 0.0) + _metadata_bonus(query, hit)
        supplements.append(hit)

    supplements.sort(key=lambda hit: _steak_sort_key(constraints, hit), reverse=True)
    return supplements[:limit]


async def _java_shop_name_supplements(query: str, existing_ids: set[int], limit: int = 5) -> list[dict]:
    keyword = _specific_shop_keyword(query)
    if not keyword:
        return []

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": keyword, "page": 1, "size": max(limit, 8)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("shop_name_supplement_failed query=%s keyword=%s", query, keyword)
        return []

    normalized_keyword = _normalized_name(keyword)
    supplements: list[dict] = []
    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id or shop_id in existing_ids:
            continue
        name = str(shop.get("name") or "")
        normalized_name = _normalized_name(name)
        if not normalized_keyword or (
            normalized_keyword not in normalized_name and normalized_name not in normalized_keyword
        ):
            continue
        metadata = await _fetch_java_ai_metadata(shop_id)
        hit = _java_shop_to_search_hit(shop, metadata)
        hit["score"] = 2.0
        hit["rerank_score"] = 2.0 + _metadata_bonus(keyword, hit)
        supplements.append(hit)

    supplements.sort(
        key=lambda hit: (
            1 if _normalized_name(keyword) == _normalized_name(str(hit.get("name") or "")) else 0,
            hit.get("rating") or 0,
            hit.get("comments") or 0,
        ),
        reverse=True,
    )
    return supplements[:limit]


_QUERY_EMBEDDING_CACHE: dict[str, list[float]] = {}


_QUERY_EMBEDDING_CACHE_MAX = 512


def _query_embedding(query: str) -> list[float]:
    """查詢向量快取：同 query 重問省一次 Gemini embedding 往返（~0.5-1s）。"""
    cached = _QUERY_EMBEDDING_CACHE.get(query)
    if cached is not None:
        return cached
    emb_resp = get_gemini().models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    vector = list(emb_resp.embeddings[0].values)
    if len(_QUERY_EMBEDDING_CACHE) >= _QUERY_EMBEDDING_CACHE_MAX:
        _QUERY_EMBEDDING_CACHE.pop(next(iter(_QUERY_EMBEDDING_CACHE)))
    _QUERY_EMBEDDING_CACHE[query] = vector
    return vector


async def _semantic_hits(query: str, top_k: int) -> list[dict]:
    query_vector = _query_embedding(query)
    raw_hits = []
    try:
        qdrant = get_qdrant()
        results = qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=max(top_k * 12, 60),
        ).points

        for result in results:
            payload = result.payload
            raw_hits.append(
                {
                    "shop_id": payload.get("shop_id"),
                    "name": payload.get("name"),
                    "district": _resolve_taipei_district(payload.get("address"), payload.get("district")),
                    "address": payload.get("address"),
                    "mrt_station": payload.get("mrt_station"),
                    "score": float(result.score),
                    "rating": payload.get("rating") or payload.get("google_score"),
                    "comments": payload.get("comments") or payload.get("review_count"),
                    "category": payload.get("category"),
                    "category_slug": payload.get("category_slug"),
                    "type_id": payload.get("type_id"),
                    "avg_price": payload.get("avg_price"),
                    "ai_summary": payload.get("ai_summary"),
                    "signature_dishes": _parse_json_list(payload.get("signature_dishes")),
                    "atmosphere_tags": _parse_json_list(payload.get("atmosphere_tags")),
                    "booking_difficulty": payload.get("booking_difficulty"),
                    "price_per_person": payload.get("price_per_person"),
                    "is_active": payload.get("is_active"),
                }
            )
    except Exception as exc:
        logger.warning("qdrant_unavailable_fallback query=%r error=%s", query, exc)
        raw_hits = await _fetch_all_shops_fallback()

    constraints = _extract_query_constraints(query)
    supplement_hits = await _premium_hotpot_supplements(
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if supplement_hits:
        raw_hits.extend(supplement_hits)
    burger_hits = await _burger_supplements(
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if burger_hits:
        raw_hits.extend(burger_hits)
    steak_hits = await _steak_supplements(
        query,
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if steak_hits:
        raw_hits.extend(steak_hits)
    exact_name_hits = await _java_shop_name_supplements(
        query,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
        limit=max(3, top_k),
    )
    if exact_name_hits:
        raw_hits = exact_name_hits + raw_hits
        logger.warning(
            "search_exact_name_supplement query=%r exact=%s",
            query,
            [hit.get("name") for hit in exact_name_hits[:8]],
        )

    raw_hits = _dedupe_search_hits(raw_hits)
    before_active_filter = len(raw_hits)
    raw_hits = [hit for hit in raw_hits if not _is_inactive_search_hit(hit)]
    if len(raw_hits) != before_active_filter:
        logger.warning("search_inactive_filtered count=%s", before_active_filter - len(raw_hits))

    shop_ids = [hit["shop_id"] for hit in raw_hits if hit["shop_id"]]
    voucher_map = await _fetch_hot_seat_vouchers(shop_ids)
    for hit in raw_hits:
        hit["hot_seat_vouchers"] = voucher_map.get(hit["shop_id"], [])
        hit["rerank_score"] = hit["score"] + _metadata_bonus(query, hit) + _fallback_keyword_score(query, hit)

    if constraints["categories"] or constraints["stations"] or constraints["districts"] or constraints["wants_hot_seat"]:
        logger.warning(
            "search_constraints query=%r constraints=%s",
            query,
            constraints,
        )
        for hit in raw_hits[:8]:
            logger.warning(
                "search_candidate_pre_sort name=%r category=%r mrt=%r district=%r base=%.4f rerank=%.4f hot_seat=%s",
                hit.get("name"),
                _category_slug_from_payload(hit),
                hit.get("mrt_station"),
                hit.get("district"),
                hit.get("score"),
                hit.get("rerank_score"),
                bool(hit.get("hot_seat_vouchers")),
            )
    raw_hits.sort(key=lambda hit: hit["rerank_score"], reverse=True)

    if constraints.get("wants_burger"):
        burger_only = [hit for hit in raw_hits if _is_burger_hit(hit)]
        burger_other = [hit for hit in raw_hits if not _is_burger_hit(hit)]
        burger_only.sort(key=lambda hit: _burger_sort_key(constraints, hit), reverse=True)
        raw_hits = burger_only + burger_other
        logger.warning(
            "search_burger_partition query=%r burger=%s others=%s",
            query,
            [hit.get("name") for hit in burger_only[:8]],
            [hit.get("name") for hit in burger_other[:8]],
        )

    if _query_requests_steak(query):
        raw_hits = _prioritize_steak_hits(query, constraints, raw_hits)
        logger.warning(
            "search_steak_partition query=%r steak=%s",
            query,
            [hit.get("name") for hit in raw_hits[:8] if _has_steak_semantics(hit)],
        )

    if constraints["categories"]:
        def category_match(hit: dict) -> bool:
            return _search_category_match(query, constraints, hit)

        matching = [
            hit for hit in raw_hits
            if category_match(hit)
        ]
        non_matching = [
            hit for hit in raw_hits
            if not category_match(hit)
        ]
        if matching:
            raw_hits = matching + non_matching
            logger.warning(
                "search_category_partition query=%r matching=%s",
                query,
                [hit.get("name") for hit in matching[:8]],
            )

    # Explicit business rule:
    # For queries like "高級火鍋", "火鍋" is the primary constraint.
    # Only compare luxury signals after the candidate is already a hotpot-like shop.
    requested_hotpot = "hotpot" in constraints["categories"]
    requested_luxury = constraints.get("wants_luxury", False)
    if requested_hotpot and requested_luxury:
        def is_hotpot_candidate(hit: dict) -> bool:
            category_slug = _semantic_category_slug(hit)
            text = _payload_text(hit)
            if category_slug == "hotpot" and not any(keyword.lower() in text for keyword in HOTPOT_BLOCK_HINTS):
                return True
            return _has_hotpot_semantics(hit)

        hotpot_hits = [hit for hit in raw_hits if is_hotpot_candidate(hit)]
        other_hits = [hit for hit in raw_hits if not is_hotpot_candidate(hit)]
        if hotpot_hits:
            hotpot_hits.sort(key=lambda hit: _premium_hotpot_key(constraints, hit), reverse=True)
            other_hits.sort(key=lambda hit: hit["rerank_score"], reverse=True)
            raw_hits = hotpot_hits + other_hits
            logger.warning(
                "search_hotpot_partition query=%r hotpot=%s others=%s",
                query,
                [hit.get("name") for hit in hotpot_hits[:8]],
                [hit.get("name") for hit in other_hits[:8]],
            )

    if any(keyword in query.lower() for keyword in LUXURY_HINTS) and not constraints.get("wants_burger"):
        def luxury_score(hit: dict) -> tuple:
            if requested_hotpot:
                return _premium_hotpot_key(constraints, hit)

            avg_price = hit.get("avg_price") or 0
            tags = set(hit.get("atmosphere_tags") or [])
            station_score = _station_proximity_score(constraints, hit)
            district_match = 1 if _district_matches(constraints, hit) else 0
            return (
                0,
                1 if avg_price >= 1000 else 0,
                0,
                station_score,
                district_match,
                1 if ({"約會", "商務"} & tags) else 0,
                1 if avg_price >= 800 else 0,
                hit["rerank_score"],
            )

        raw_hits.sort(
            key=lambda hit: (luxury_score(hit), hit["rerank_score"]),
            reverse=True,
        )
        logger.warning(
            "search_luxury_sorted query=%r ranked=%s",
            query,
            [
                {
                    "name": hit.get("name"),
                    "category": _semantic_category_slug(hit),
                    "luxury": luxury_score(hit),
                    "rerank": round(hit.get("rerank_score", 0.0), 4),
                }
                for hit in raw_hits[:8]
            ],
        )

    if requested_hotpot and constraints["wants_nearby"]:
        def is_hotpot_like(hit: dict) -> bool:
            return _semantic_category_slug(hit) == "hotpot" or _has_hotpot_semantics(hit)

        def is_nearby_hit(hit: dict) -> bool:
            return _station_proximity_score(constraints, hit) > 0 or _district_matches(constraints, hit)

        near_hotpot_hits = [hit for hit in raw_hits if is_hotpot_like(hit) and is_nearby_hit(hit)]
        far_hotpot_hits = [hit for hit in raw_hits if is_hotpot_like(hit) and not is_nearby_hit(hit)]
        other_hits = [hit for hit in raw_hits if not is_hotpot_like(hit)]
        if near_hotpot_hits:
            raw_hits = near_hotpot_hits + far_hotpot_hits + other_hits
            logger.warning(
                "search_nearby_partition query=%r near_hotpot=%s far_hotpot=%s others=%s",
                query,
                [hit.get("name") for hit in near_hotpot_hits[:8]],
                [hit.get("name") for hit in far_hotpot_hits[:8]],
                [hit.get("name") for hit in other_hits[:8]],
            )

    if constraints["wants_hot_seat"]:
        hot_hits = [hit for hit in raw_hits if hit.get("hot_seat_vouchers")]
        cold_hits = [hit for hit in raw_hits if not hit.get("hot_seat_vouchers")]
        raw_hits = hot_hits + cold_hits
        logger.warning(
            "search_hot_seat_sorted query=%r hot=%s cold=%s",
            query,
            [hit.get("name") for hit in hot_hits[:8]],
            [hit.get("name") for hit in cold_hits[:8]],
        )

    if constraints["categories"] or constraints["stations"] or constraints["districts"] or constraints["wants_hot_seat"]:
        logger.warning(
            "search_final_rank query=%r ranked=%s",
            query,
            [
                {
                    "name": hit.get("name"),
                    "category": _semantic_category_slug(hit),
                    "mrt": hit.get("mrt_station"),
                    "rerank": round(hit.get("rerank_score", 0.0), 4),
                }
                for hit in raw_hits[:8]
            ],
        )

    # Hard nearby filter: when query has "附近/nearby" + explicit station or district,
    # force candidates from that area into top slots.  Only fill from outside the area
    # if strict matches are fewer than 5.
    if constraints["wants_nearby"] and (constraints["stations"] or constraints["districts"]):
        def _is_strict_nearby(hit: dict) -> bool:
            mrt = str(hit.get("mrt_station") or "").lower()
            station_match = _station_proximity_score(constraints, hit) > 0 or any(
                s.lower() in mrt for s in constraints["stations"]
            )
            district_match = _district_matches(constraints, hit)
            return station_match or district_match

        strict_nearby = [h for h in raw_hits if _is_strict_nearby(h)]
        loose_nearby  = [h for h in raw_hits if not _is_strict_nearby(h)]

        MIN_STRICT = 5
        if len(strict_nearby) >= MIN_STRICT:
            raw_hits = strict_nearby
        else:
            raw_hits = strict_nearby + loose_nearby[: max(0, MIN_STRICT + 3 - len(strict_nearby))]

        logger.warning(
            "search_strict_nearby_filter query=%r strict=%s loose_added=%s",
            query,
            [h.get("name") for h in strict_nearby[:8]],
            [h.get("name") for h in loose_nearby[: max(0, MIN_STRICT + 3 - len(strict_nearby))]],
        )

    if constraints["categories"]:
        if constraints.get("wants_burger"):
            raw_hits = [hit for hit in raw_hits if _is_burger_hit(hit)]
            raw_hits = _prefer_rich_hits(raw_hits, top_k)
            logger.warning(
                "search_strict_burger_filter query=%r strict=%s",
                query,
                [hit.get("name") for hit in raw_hits[:8]],
            )
            return raw_hits[:top_k]
        specific_cuisine_hits = []
        for cuisine in constraints.get("specific_cuisines", []):
            specific_cuisine_hits.extend(
                hit for hit in raw_hits
                if _matches_specific_cuisine(hit, cuisine)
            )
        if specific_cuisine_hits:
            seen_specific_ids = set()
            unique_specific_hits = []
            for hit in specific_cuisine_hits:
                shop_id = hit.get("shop_id")
                if shop_id in seen_specific_ids:
                    continue
                seen_specific_ids.add(shop_id)
                unique_specific_hits.append(hit)
            raw_hits = unique_specific_hits
            for cuisine in constraints.get("specific_cuisines", []):
                raw_hits.sort(key=lambda hit: _specific_cuisine_sort_key(cuisine, hit), reverse=True)
            logger.warning(
                "search_specific_cuisine_filter query=%r cuisines=%s strict=%s",
                query,
                constraints.get("specific_cuisines", []),
                [hit.get("name") for hit in raw_hits[:8]],
            )
        else:
            strict_category = [
                hit for hit in raw_hits
                if _search_category_match(query, constraints, hit)
            ]
            rejected_conflicts = [
                hit for hit in raw_hits
                if any(_has_explicit_category_conflict(hit, category) for category in constraints["categories"])
            ]
            if strict_category:
                raw_hits = strict_category
            else:
                # 分類無人符合時不可清空結果（district/station 過濾都有保底，這裡曾缺）；
                # 退回語意排序、僅剔除明確衝突的店。
                raw_hits = [hit for hit in raw_hits if hit not in rejected_conflicts]
            logger.warning(
                "search_strict_category_filter query=%r categories=%s rejected_conflicts=%s strict=%s",
                query,
                constraints["categories"],
                [hit.get("name") for hit in rejected_conflicts[:8]],
                [hit.get("name") for hit in strict_category[:8]],
            )

    if constraints.get("wants_taiwanese_cuisine"):
        clean_taiwanese_pool = [
            hit for hit in raw_hits
            if not _is_taiwanese_cuisine_mismatch(hit)
        ]
        strong_taiwanese = [
            hit for hit in clean_taiwanese_pool
            if _has_taiwanese_cuisine_semantics(hit)
        ]
        generic_chinese = [
            hit for hit in clean_taiwanese_pool
            if hit not in strong_taiwanese
            and _semantic_category_slug(hit) == "chinese"
        ]
        rejected_mismatch = [
            hit for hit in raw_hits
            if _is_taiwanese_cuisine_mismatch(hit)
        ]
        if strong_taiwanese or generic_chinese:
            strong_taiwanese.sort(key=lambda hit: _taiwanese_cuisine_sort_key(constraints, hit), reverse=True)
            generic_chinese.sort(key=lambda hit: _taiwanese_cuisine_sort_key(constraints, hit), reverse=True)
            raw_hits = strong_taiwanese + generic_chinese
        logger.warning(
            "search_taiwanese_cuisine_filter query=%r strong=%s generic=%s rejected=%s",
            query,
            [hit.get("name") for hit in strong_taiwanese[:8]],
            [hit.get("name") for hit in generic_chinese[:8]],
            [hit.get("name") for hit in rejected_mismatch[:8]],
        )

    if constraints["districts"]:
        strict_district = [
            hit for hit in raw_hits
            if _district_matches(constraints, hit)
        ]
        if strict_district:
            loose_district = [hit for hit in raw_hits if hit not in strict_district]
            min_results = min(top_k, 3)
            raw_hits = strict_district if len(strict_district) >= min_results else strict_district + loose_district
        logger.warning(
            "search_strict_district_filter query=%r districts=%s strict=%s",
            query,
            constraints["districts"],
            [hit.get("name") for hit in strict_district[:8]],
        )

    if constraints["stations"]:
        strict_station = [
            hit for hit in raw_hits
            if _station_proximity_score(constraints, hit) > 0
            or any(target.lower() in str(hit.get("mrt_station") or "").lower() for target in constraints["stations"])
        ]
        if strict_station:
            loose_station = [hit for hit in raw_hits if hit not in strict_station]
            min_results = min(top_k, 3)
            raw_hits = strict_station if len(strict_station) >= min_results else strict_station + loose_station
        logger.warning(
            "search_strict_station_filter query=%r stations=%s strict=%s",
            query,
            constraints["stations"],
            [hit.get("name") for hit in strict_station[:8]],
        )

    raw_hits = _prioritize_steak_hits(query, constraints, raw_hits)
    raw_hits = _prefer_rich_hits(raw_hits, top_k)
    return raw_hits[:top_k]


async def _fetch_hot_seat_vouchers(shop_ids: list[int]) -> dict[int, list]:
    """Return {shop_id: [{id, title, pay_value, actual_value, stock}]}. N+1 ok for demo."""
    out: dict[int, list] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sid in shop_ids:
            try:
                r = await client.get(f"{settings.java_backend_url}/api/shop/{sid}/flash-deals")
                if r.status_code == 404:
                    r = await client.get(f"{settings.java_backend_url}/api/shop/{sid}/hot-seat-vouchers")
                out[sid] = r.json().get("data", []) if r.status_code == 200 else []
            except Exception:
                out[sid] = []
    return out








def _agent_java_auth_headers() -> dict[str, str] | None:
    token = _agent_auth_token.get("").strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _shop_has_rich_context(shop: dict) -> bool:
    return bool(
        str(shop.get("ai_summary") or "").strip()
        or _parse_json_list(shop.get("signature_dishes"))
        or _parse_json_list(shop.get("atmosphere_tags"))
    )




async def _fetch_java_shop(shop_id: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.java_backend_url}/api/shop/{shop_id}")
        if response.status_code != 200:
            return None
        payload = response.json()
        data = payload.get("data")
        if isinstance(data, dict) and data:
            return data
        return await _fetch_java_shop_by_fallback_name(shop_id)
    except Exception:
        logger.exception("line_shop_fetch_failed shop_id=%s", shop_id)
        return None


async def _fetch_java_shop_by_fallback_name(shop_id: int) -> dict | None:
    fallback_name = _LINE_SHOP_NAME_FALLBACKS.get(shop_id)
    if not fallback_name:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/of/name",
                params={"name": fallback_name},
            )
        if response.status_code != 200:
            return None
        payload = response.json()
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and int(item.get("id") or 0) == shop_id:
                    return item
            return data[0] if data and isinstance(data[0], dict) else None
        return data if isinstance(data, dict) and data else None
    except Exception:
        logger.exception("line_shop_fallback_fetch_failed shop_id=%s", shop_id)
        return None


async def _fetch_java_ai_metadata(shop_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.java_backend_url}/api/shop/{shop_id}/ai-metadata")
        if response.status_code != 200:
            return {}
        payload = response.json()
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("line_shop_metadata_fetch_failed shop_id=%s", shop_id)
        return {}
