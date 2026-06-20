ALTER TABLE tb_booking_deposit_adjustment
    ADD COLUMN refund_escalated_at DATETIME NULL AFTER settlement_recorded_by_user_id,
    ADD COLUMN refund_escalation_note VARCHAR(500) NULL AFTER refund_escalated_at,
    ADD COLUMN refund_escalated_by_user_id BIGINT NULL AFTER refund_escalation_note,
    ADD INDEX idx_deposit_adjustment_refund_escalation (
        shop_id,
        adjustment_type,
        settlement_status,
        refund_escalated_at
    );
