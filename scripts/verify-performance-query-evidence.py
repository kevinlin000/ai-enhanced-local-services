#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "performance-query-evidence.md"


def fail(message: str) -> None:
    print(f"PERFORMANCE QUERY EVIDENCE FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(path: Path, snippet: str, label: str) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing file for {label}: {path.relative_to(ROOT)}")
    if snippet not in text:
        fail(f"missing {label}: {path.relative_to(ROOT)} -> {snippet}")


def verify_doc() -> None:
    required = {
        "title": "ByteBites 效能與查詢證據",
        "scope": "目前最重要的 runtime surfaces",
        "query path map": "查詢路徑對照",
        "slot reservation": "座位保留",
        "refund operations": "Refund operations",
        "verifier command": "python3 scripts/verify-performance-query-evidence.py",
        "no throughput overclaim": "這份證據不證明 production-scale throughput。",
        "next performance work": "下一步效能工作",
    }
    for label, snippet in required.items():
        require(DOC, snippet, label)


def verify_indexes() -> None:
    index_snippets = {
        "booking code": ("backend-java/src/main/resources/db/migration/V14__booking_table.sql", "INDEX idx_booking_code (booking_code)"),
        "booking user created": ("backend-java/src/main/resources/db/migration/V24__booking_user_ownership.sql", "CREATE INDEX idx_booking_user_created ON tb_booking (user_id, created_at);"),
        "booking user status": ("backend-java/src/main/resources/db/migration/V24__booking_user_ownership.sql", "CREATE INDEX idx_booking_user_status ON tb_booking (user_id, status);"),
        "booking hold expiry": ("backend-java/src/main/resources/db/migration/V25__booking_hold_expiration.sql", "CREATE INDEX idx_booking_hold_expiry ON tb_booking (status, hold_expires_at);"),
        "parking reminder": ("backend-java/src/main/resources/db/migration/V39__booking_parking_reminders.sql", "CREATE INDEX idx_booking_parking_reminder"),
        "slot unique": ("backend-java/src/main/resources/db/migration/V21__booking_slot_inventory.sql", "UNIQUE KEY uk_booking_slot (shop_id, booking_date, booking_time, table_type)"),
        "slot lookup": ("backend-java/src/main/resources/db/migration/V21__booking_slot_inventory.sql", "INDEX idx_booking_slot_lookup (shop_id, booking_date, booking_time)"),
        "incident booking status": ("backend-java/src/main/resources/db/migration/V44__booking_incidents.sql", "INDEX idx_booking_incident_booking_status (booking_code, status, created_at)"),
        "incident user status": ("backend-java/src/main/resources/db/migration/V44__booking_incidents.sql", "INDEX idx_booking_incident_user_status (user_id, status, created_at)"),
        "incident shop status": ("backend-java/src/main/resources/db/migration/V44__booking_incidents.sql", "INDEX idx_booking_incident_shop_status (shop_id, status, created_at)"),
        "proposal status": ("backend-java/src/main/resources/db/migration/V45__booking_incident_proposals.sql", "ADD INDEX idx_booking_incident_proposal_status (proposal_status, proposed_at);"),
        "deposit adjustment state": ("backend-java/src/main/resources/db/migration/V47__booking_deposit_adjustments.sql", "UNIQUE KEY uk_booking_deposit_adjustment_state"),
        "deposit adjustment shop status": ("backend-java/src/main/resources/db/migration/V47__booking_deposit_adjustments.sql", "INDEX idx_deposit_adjustment_shop_status (shop_id, status, created_at)"),
        "deposit adjustment booking": ("backend-java/src/main/resources/db/migration/V47__booking_deposit_adjustments.sql", "INDEX idx_deposit_adjustment_booking (booking_code)"),
        "deposit settlement": ("backend-java/src/main/resources/db/migration/V48__booking_deposit_adjustment_settlement.sql", "ADD INDEX idx_deposit_adjustment_settlement (shop_id, settlement_status, created_at);"),
        "refund event key": ("backend-java/src/main/resources/db/migration/V49__booking_refund_reconciliation_audit.sql", "UNIQUE KEY uk_refund_reconciliation_event_key (event_key)"),
        "refund adjustment": ("backend-java/src/main/resources/db/migration/V49__booking_refund_reconciliation_audit.sql", "INDEX idx_refund_reconciliation_adjustment (adjustment_id, created_at)"),
        "refund booking": ("backend-java/src/main/resources/db/migration/V49__booking_refund_reconciliation_audit.sql", "INDEX idx_refund_reconciliation_booking (booking_code, created_at)"),
        "refund escalation": ("backend-java/src/main/resources/db/migration/V50__booking_refund_escalation.sql", "ADD INDEX idx_deposit_adjustment_refund_escalation"),
        "merchant notification last sent": ("backend-java/src/main/resources/db/migration/V51__merchant_notification_dispatch.sql", "INDEX idx_merchant_notification_last_sent"),
        "merchant notification created": ("backend-java/src/main/resources/db/migration/V51__merchant_notification_dispatch.sql", "INDEX idx_merchant_notification_created"),
        "deposit booking collation": ("backend-java/src/main/resources/db/migration/V52__align_deposit_adjustment_booking_code_collation.sql", "MODIFY booking_code VARCHAR(50)"),
    }
    for label, (relative_path, snippet) in index_snippets.items():
        require(ROOT / relative_path, snippet, label)


def verify_code_paths() -> None:
    code_snippets = {
        "conditional slot reserve": ("backend-java/src/main/java/com/bytebites/service/BookingSlotInventory.java", "AND booked_count + ? <= capacity"),
        "slot insert ignore": ("backend-java/src/main/java/com/bytebites/service/BookingSlotInventory.java", "INSERT IGNORE INTO tb_booking_slot_inventory"),
        "reserve before release": ("backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java", "bookingSlotInventory.reserve(booking.getShopId(), newDate, newTime, targetTableType, newPeople)"),
        "release old slot": ("backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java", "releaseOldSlot(booking.getShopId(), oldDate, oldTime, oldTableType, oldPeople);"),
        "my bookings query": ("backend-java/src/main/java/com/bytebites/repository/BookingJpaRepository.java", "findByUserIdInOrderByCreatedAtDesc"),
        "hold expiry query": ("backend-java/src/main/java/com/bytebites/repository/BookingJpaRepository.java", "findTop50ByStatusAndHoldExpiresAtBeforeOrderByHoldExpiresAtAsc"),
        "parking reminder query": ("backend-java/src/main/java/com/bytebites/repository/BookingJpaRepository.java", "findUpcomingParkingReminderCandidates"),
        "latest incident": ("backend-java/src/main/java/com/bytebites/service/BookingIncidentService.java", "latestIncidentForBookingCode"),
        "merchant incident sql": ("backend-java/src/main/java/com/bytebites/controller/MerchantController.java", "private String merchantIncidentSql"),
        "alternative slots": ("backend-java/src/main/java/com/bytebites/controller/MerchantController.java", "private List<Map<String, Object>> alternativeSlotsFor"),
        "deposit adjustment sql": ("backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java", "private String depositAdjustmentSql"),
        "refund sla summary": ("backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java", "refundSlaSummaryForMerchantShop"),
        "refund digest dispatch": ("backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java", "latestRefundOperationsDigestDispatch"),
    }
    for label, (relative_path, snippet) in code_snippets.items():
        require(ROOT / relative_path, snippet, label)


def main() -> None:
    verify_doc()
    verify_indexes()
    verify_code_paths()
    print("performance query evidence: hot paths, indexes, and code anchors passed")


if __name__ == "__main__":
    main()
