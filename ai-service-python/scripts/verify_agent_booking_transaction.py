"""Smoke-test the Agent booking transaction loop end-to-end.

Checks:
- Agent SSE emits semantic search -> create_booking -> pay-test.
- done.transaction is structured and paid.
- The booking row exists in MySQL with the same payment transaction id.
- pay-test retry is idempotent.
- Backend rejects past-date reservations.
- Ambiguous multi-branch brand bookings ask for branch selection before booking.
- Repeating the same booking request in one Agent session reuses the existing booking.
- Backend reserve idempotency key handles duplicate/racing requests.

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
                select booking_code, shop_id, people, booking_date, booking_time,
                       status, needs_deposit, deposit_total, payment_trans_id,
                       idempotency_key
                from tb_booking
                where booking_code = %s
                """,
                (booking_code,),
            )
            return cur.fetchone()


def delete_booking(booking_code: str) -> None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from tb_booking where booking_code = %s", (booking_code,))


def delete_booking_by_idempotency_key(idempotency_key: str) -> None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from tb_booking where idempotency_key = %s", (idempotency_key,))


def assert_agent_transaction(events: list[dict[str, Any]]) -> dict[str, Any]:
    tools = [event["name"] for event in events if event.get("type") == "tool"]
    expected_tools = ["semantic_shop_search", "create_booking", "pay_booking_with_test_card"]
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
    if txn.get("status") != "PAID" or not txn.get("success"):
        fail(f"transaction not paid/successful: {txn}")
    if not txn.get("booking_code") or not txn.get("rec_trade_id"):
        fail(f"transaction missing booking_code or rec_trade_id: {txn}")
    if date.fromisoformat(txn["date"]) < date.today():
        fail(f"transaction date is in the past: {txn['date']}")
    ok(
        "done.transaction paid "
        f"booking={txn['booking_code']} trade={txn['rec_trade_id']} date={txn['date']}"
    )
    return txn


def assert_db_row(txn: dict[str, Any]) -> None:
    row = fetch_booking(txn["booking_code"])
    if not row:
        fail(f"booking row missing: {txn['booking_code']}")
    if row["status"] != 2:
        fail(f"booking row not paid: {row}")
    if row["payment_trans_id"] != txn["rec_trade_id"]:
        fail(f"payment trans mismatch: db={row['payment_trans_id']} txn={txn['rec_trade_id']}")
    if str(row["booking_date"]) != txn["date"]:
        fail(f"booking date mismatch: db={row['booking_date']} txn={txn['date']}")
    if not row.get("idempotency_key"):
        fail(f"booking row missing idempotency_key: {row}")
    ok("MySQL row matches paid transaction")


def assert_pay_retry_idempotent(txn: dict[str, Any]) -> None:
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/pay-test",
        json={"bookingCode": txn["booking_code"]},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        fail(f"pay-test retry failed: {payload}")
    data = payload.get("data") or {}
    if data.get("rec_trade_id") != txn["rec_trade_id"]:
        fail(f"pay-test retry returned different trade id: {data}")
    ok("pay-test retry is idempotent")


def assert_agent_duplicate_booking_reuses_transaction(session_id: str, txn: dict[str, Any]) -> None:
    events = stream_agent(
        "幫我訂辛殿麻辣鍋明天晚上7點2人",
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
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
        json={
            "shopId": 10115,
            "people": 2,
            "date": tomorrow,
            "time": "18:30",
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


def assert_backend_rejects_past_date() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    response = httpx.post(
        f"{JAVA_BACKEND_URL}/api/booking/reserve",
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
            "幫我訂辛殿麻辣鍋明天晚上7點2人",
            session_id,
        )
        txn = assert_agent_transaction(events)
        assert_db_row(txn)
        assert_pay_retry_idempotent(txn)
        assert_agent_duplicate_booking_reuses_transaction(session_id, txn)
        assert_backend_reserve_idempotency(run_id)
        assert_backend_rejects_past_date()
        assert_ambiguous_branch_requires_clarification(run_id)
    finally:
        if txn and not args.keep_booking:
            delete_booking(txn["booking_code"])
            ok(f"cleaned generated booking {txn['booking_code']}")


if __name__ == "__main__":
    main()
