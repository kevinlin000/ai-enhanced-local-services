"""Smoke-test the Agent booking transaction loop end-to-end.

Checks:
- Agent SSE emits semantic search -> create_booking, without automatic payment.
- done.transaction is structured and pending payment when deposit is required.
- The booking row exists in MySQL as pending payment.
- Explicit pay-test completes payment and retry is idempotent.
- Backend rejects past-date reservations.
- Ambiguous multi-branch brand bookings ask for branch selection before booking.
- Repeating the same booking request in one Agent session reuses the existing booking.
- Backend reserve idempotency key handles duplicate/racing requests.
- Simulated slot inventory rejects over-capacity reservations.

Prereqs: Java backend, AI service, MySQL, Qdrant, and Gemini env are running.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import httpx
import pymysql


AI_STREAM_URL = os.getenv(
    "AI_AGENT_STREAM_URL",
    "http://127.0.0.1:8000/api/ai/agent/stream",
)
JAVA_BACKEND_URL = os.getenv("JAVA_BACKEND_URL", "http://127.0.0.1:8081")
DEMO_HEADERS = {"X-Demo-Mode": "true"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def stream_agent(query: str, session_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with httpx.stream(
        "POST",
        AI_STREAM_URL,
        json={"query": query, "session_id": session_id},
        timeout=60,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            events.append(event)
            if event.get("type") == "error":
                fail(f"agent error event: {event.get('message')}")
    return events


def mysql_conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def fetch_booking(booking_code: str) -> dict[str, Any] | None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select booking_code, shop_id, people, booking_date, booking_time, table_type,
                       status, needs_deposit, deposit_total, payment_trans_id,
                       idempotency_key
                from tb_booking
                where booking_code = %s
                """,
                (booking_code,),
            )
            return cur.fetchone()


def release_slot_for_booking(row: dict[str, Any]) -> None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update tb_booking_slot_inventory
                set booked_count = greatest(booked_count - %s, 0)
                where shop_id = %s
                  and booking_date = %s
                  and booking_time = %s
                  and table_type = %s
                """,
                (
                    row["people"],
                    row["shop_id"],
                    row["booking_date"],
                    row["booking_time"],
                    row["table_type"],
                ),
            )


def delete_idempotency_lock(idempotency_key: str | None) -> None:
    if not idempotency_key:
        return
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from tb_booking_idempotency_lock where idempotency_key = %s",
                (idempotency_key,),
            )


def delete_booking(booking_code: str) -> None:
    row = fetch_booking(booking_code)
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from tb_booking where booking_code = %s", (booking_code,))
    if row:
        release_slot_for_booking(row)
        delete_idempotency_lock(row.get("idempotency_key"))


def delete_booking_by_idempotency_key(idempotency_key: str) -> None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select booking_code, shop_id, people, booking_date, booking_time, table_type
                from tb_booking
                where idempotency_key = %s
                """,
                (idempotency_key,),
            )
            rows = cur.fetchall()
            cur.execute("delete from tb_booking where idempotency_key = %s", (idempotency_key,))
    for row in rows:
        release_slot_for_booking(row)
    delete_idempotency_lock(idempotency_key)


def assert_agent_transaction(events: list[dict[str, Any]]) -> dict[str, Any]:
    tools = [event["name"] for event in events if event.get("type") == "tool"]
    expected_tools = ["semantic_shop_search", "create_booking"]
    if tools != expected_tools:
        fail(f"tool sequence mismatch: expected={expected_tools} got={tools}")
    ok(f"tool sequence {tools}")

    done = next((event for event in events if event.get("type") == "done"), None)
    if not done:
        fail("missing done event")

    txn = done.get("transaction")
    if not isinstance(txn, dict):
        fail("done.transaction missing or not object")
    if txn.get("kind") != "booking":
        fail(f"unexpected transaction kind: {txn.get('kind')}")
    if txn.get("needs_deposit") and txn.get("status") != "PENDING_PAYMENT":
        fail(f"deposit booking should wait for explicit payment: {txn}")
    if txn.get("needs_deposit") and txn.get("success"):
        fail(f"pending-payment transaction should not be marked successful yet: {txn}")
    if not txn.get("booking_code"):
        fail(f"transaction missing booking_code: {txn}")
    if txn.get("rec_trade_id"):
        fail(f"Agent should not auto-pay or return rec_trade_id before explicit payment: {txn}")
    if date.fromisoformat(txn["date"]) < date.today():
        fail(f"transaction date is in the past: {txn['date']}")
    ok(
        "done.transaction pending explicit payment "
        f"booking={txn['booking_code']} date={txn['date']}"
    )
    return txn


def assert_db_row_pending_payment(txn: dict[str, Any]) -> None:
    row = fetch_booking(txn["booking_code"])
    if not row:
        fail(f"booking row missing: {txn['booking_code']}")
    if txn.get("needs_deposit") and row["status"] != 1:
        fail(f"deposit booking row should be pending payment: {row}")
    if row["payment_trans_id"]:
        fail(f"booking row should not have payment transaction before explicit pay: {row}")
    if str(row["booking_date"]) != txn["date"]:
        fail(f"booking date mismatch: db={row['booking_date']} txn={txn['date']}")
    if not row.get("idempotency_key"):
        fail(f"booking row missing idempotency_key: {row}")
    ok("MySQL row matches pending-payment transaction")


def assert_explicit_pay_test_completes_and_retries(txn: dict[str, Any]) -> None:
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/pay-test",
        headers=DEMO_HEADERS,
        json={"bookingCode": txn["booking_code"]},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        fail(f"explicit pay-test failed: {payload}")
    first = payload.get("data") or {}
    if first.get("status") != "PAID" or not first.get("rec_trade_id"):
        fail(f"explicit pay-test did not return paid transaction: {first}")

    retry = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/pay-test",
        headers=DEMO_HEADERS,
        json={"bookingCode": txn["booking_code"]},
        timeout=15,
    )
    retry.raise_for_status()
    retry_payload = retry.json()
    if not retry_payload.get("success"):
        fail(f"pay-test retry failed: {retry_payload}")
    second = retry_payload.get("data") or {}
    if second.get("rec_trade_id") != first.get("rec_trade_id"):
        fail(f"pay-test retry returned different trade id: first={first} second={second}")
    row = fetch_booking(txn["booking_code"])
    if not row or row["status"] != 2 or row["payment_trans_id"] != first.get("rec_trade_id"):
        fail(f"booking row was not paid after explicit pay-test: row={row} payment={first}")
    ok("explicit pay-test completes payment and retry is idempotent")


def assert_agent_duplicate_booking_reuses_transaction(session_id: str, txn: dict[str, Any]) -> None:
    events = stream_agent(
        "幫我訂辛殿麻辣鍋明天18:30 2人",
        session_id,
    )
    tools = [event["name"] for event in events if event.get("type") == "tool"]
    if "create_booking" in tools or "pay_booking_with_test_card" in tools:
        fail(f"duplicate booking request should not create/pay again: tools={tools}")
    done = next((event for event in events if event.get("type") == "done"), None)
    if not done:
        fail("duplicate booking request missing done event")
    duplicate_txn = done.get("transaction")
    if not isinstance(duplicate_txn, dict):
        fail(f"duplicate booking request missing transaction: {done}")
    if duplicate_txn.get("booking_code") != txn["booking_code"]:
        fail(
            "duplicate booking did not reuse original booking: "
            f"original={txn['booking_code']} duplicate={duplicate_txn.get('booking_code')}"
        )
    if not duplicate_txn.get("duplicate"):
        fail(f"duplicate booking transaction missing duplicate marker: {duplicate_txn}")
    ok("duplicate Agent booking request reuses existing transaction")


def reserve_with_idempotency_key(idempotency_key: str) -> dict[str, Any]:
    smoke_date = (date.today() + timedelta(days=10)).isoformat()
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
        headers=DEMO_HEADERS,
        json={
            "shopId": 10115,
            "people": 2,
            "date": smoke_date,
            "time": "20:30",
            "tableType": "normal",
            "idempotencyKey": idempotency_key,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        fail(f"idempotent reserve failed: {payload}")
    return payload["data"]


def assert_backend_reserve_idempotency(run_id: str) -> None:
    idempotency_key = f"smoke-idem-{run_id}"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(reserve_with_idempotency_key, [idempotency_key, idempotency_key]))
        if first["bookingCode"] != second["bookingCode"]:
            fail(f"idempotent reserve returned different booking codes: {first}, {second}")
        if not (first.get("idempotentReplay") or second.get("idempotentReplay")):
            fail(f"idempotent reserve did not mark either response as replay: {first}, {second}")
        ok("backend reserve idempotency key handles duplicate requests")
    finally:
        delete_booking_by_idempotency_key(idempotency_key)


def reserve_capacity_case(idempotency_key: str, booking_date: str) -> dict[str, Any]:
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
        headers=DEMO_HEADERS,
        json={
            "shopId": 10115,
            "people": 5,
            "date": booking_date,
            "time": "18:30",
            "tableType": "normal",
            "idempotencyKey": idempotency_key,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def assert_backend_slot_capacity(run_id: str) -> None:
    booking_date = (date.today() + timedelta(days=9)).isoformat()
    keys = [f"smoke-capacity-a-{run_id}", f"smoke-capacity-b-{run_id}"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda key: reserve_capacity_case(key, booking_date), keys))
        payloads = [first, second]
        successes = [payload for payload in payloads if payload.get("success")]
        failures = [payload for payload in payloads if payload.get("success") is False]
        if len(successes) != 1 or len(failures) != 1:
            fail(f"capacity test expected one success and one failure: {payloads}")
        if "額滿" not in str(failures[0].get("errorMsg") or ""):
            fail(f"capacity failure did not explain sold-out slot: {failures[0]}")
        ok("backend slot inventory rejects over-capacity reservations")
    finally:
        for key in keys:
            delete_booking_by_idempotency_key(key)


def assert_backend_rejects_past_date() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
        headers=DEMO_HEADERS,
        json={
            "shopId": 10115,
            "people": 2,
            "date": yesterday,
            "time": "19:00",
            "tableType": "normal",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("success") is not False:
        fail(f"past-date booking was not rejected: {payload}")
    if (payload.get("data") or {}).get("bookingCode"):
        fail(f"past-date rejection returned a booking code: {payload}")
    ok(f"backend rejects past-date reservation ({yesterday})")


def assert_backend_rejects_same_day() -> None:
    today = date.today().isoformat()
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
        headers=DEMO_HEADERS,
        json={
            "shopId": 10115,
            "people": 2,
            "date": today,
            "time": "19:00",
            "tableType": "normal",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("success") is not False:
        fail(f"same-day booking was not rejected: {payload}")
    if "明天" not in str(payload.get("errorMsg") or ""):
        fail(f"same-day rejection did not explain next-day policy: {payload}")
    if (payload.get("data") or {}).get("bookingCode"):
        fail(f"same-day rejection returned a booking code: {payload}")
    ok(f"backend rejects same-day reservation ({today})")


def assert_ambiguous_branch_requires_clarification(run_id: str) -> None:
    events = stream_agent(
        "幫我訂刁民明天晚上7點2人",
        f"agent-booking-branch-ambiguity-{run_id}",
    )
    tools = [event["name"] for event in events if event.get("type") == "tool"]
    if "create_booking" in tools or "pay_booking_with_test_card" in tools:
        fail(f"ambiguous branch query should not book or pay: tools={tools}")
    done = next((event for event in events if event.get("type") == "done"), None)
    if not done:
        fail("ambiguous branch query missing done event")
    answer = str(done.get("answer") or "")
    if "分店" not in answer or "請" not in answer:
        fail(f"ambiguous branch answer did not ask for branch selection: {answer}")
    if done.get("transaction"):
        fail(f"ambiguous branch query returned transaction: {done.get('transaction')}")
    ok("ambiguous multi-branch booking asks for branch selection")


def assert_agent_today_requires_reschedule(run_id: str) -> None:
    events = stream_agent(
        "幫我訂辛殿麻辣鍋今天晚上7點2人",
        f"agent-booking-today-reject-{run_id}",
    )
    tools = [event["name"] for event in events if event.get("type") == "tool"]
    if "create_booking" in tools or "pay_booking_with_test_card" in tools:
        fail(f"same-day query should not create or pay booking: tools={tools}")
    done = next((event for event in events if event.get("type") == "done"), None)
    if not done:
        fail("same-day query missing done event")
    answer = str(done.get("answer") or "")
    if "明天" not in answer or "今天" not in answer:
        fail(f"same-day query did not explain next-day policy: {answer}")
    if done.get("transaction"):
        fail(f"same-day query returned transaction: {done.get('transaction')}")
    ok("Agent asks to reschedule explicit same-day booking")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keep-booking",
        action="store_true",
        help="keep the generated booking row as manual proof",
    )
    args = parser.parse_args()

    txn: dict[str, Any] | None = None
    try:
        run_id = uuid.uuid4().hex[:10]
        session_id = f"agent-booking-smoke-{run_id}"
        events = stream_agent(
            "幫我訂辛殿麻辣鍋明天18:30 2人",
            session_id,
        )
        txn = assert_agent_transaction(events)
        assert_db_row_pending_payment(txn)
        assert_agent_duplicate_booking_reuses_transaction(session_id, txn)
        assert_explicit_pay_test_completes_and_retries(txn)
        assert_backend_reserve_idempotency(run_id)
        assert_backend_slot_capacity(run_id)
        assert_backend_rejects_past_date()
        assert_backend_rejects_same_day()
        assert_ambiguous_branch_requires_clarification(run_id)
        assert_agent_today_requires_reschedule(run_id)
    finally:
        if txn and not args.keep_booking:
            delete_booking(txn["booking_code"])
            ok(f"cleaned generated booking {txn['booking_code']}")


if __name__ == "__main__":
    main()
