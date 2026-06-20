ALTER TABLE tb_booking_deposit_adjustment
    ADD COLUMN settlement_status VARCHAR(30) NOT NULL DEFAULT 'PENDING' AFTER applied_booking_update,
    ADD COLUMN settlement_provider VARCHAR(30) NULL AFTER settlement_status,
    ADD COLUMN settlement_trans_id VARCHAR(100) NULL AFTER settlement_provider,
    ADD COLUMN settlement_amount INT NOT NULL DEFAULT 0 AFTER settlement_trans_id,
    ADD COLUMN settlement_requested_at DATETIME NULL AFTER settlement_amount,
    ADD COLUMN settlement_completed_at DATETIME NULL AFTER settlement_requested_at,
    ADD COLUMN settlement_note VARCHAR(500) NULL AFTER settlement_completed_at,
    ADD COLUMN settlement_recorded_by_user_id BIGINT NULL AFTER settlement_note,
    ADD INDEX idx_deposit_adjustment_settlement (shop_id, settlement_status, created_at);
