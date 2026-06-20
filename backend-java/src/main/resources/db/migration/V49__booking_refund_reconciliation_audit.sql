CREATE TABLE IF NOT EXISTS tb_booking_refund_reconciliation_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_key VARCHAR(120) NULL,
    adjustment_id BIGINT NOT NULL,
    booking_code VARCHAR(50) NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    result_status VARCHAR(30) NOT NULL,
    amount INT NOT NULL,
    settlement_trans_id VARCHAR(100) NULL,
    message VARCHAR(500) NULL,
    recorded_by_user_id BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_refund_reconciliation_event_key (event_key),
    INDEX idx_refund_reconciliation_adjustment (adjustment_id, created_at),
    INDEX idx_refund_reconciliation_booking (booking_code, created_at)
);
