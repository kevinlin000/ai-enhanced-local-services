-- V22: Serialize duplicate booking requests by idempotency key.
-- This prevents concurrent same-key requests from racing into the booking unique constraint.
CREATE TABLE IF NOT EXISTS tb_booking_idempotency_lock (
    idempotency_key VARCHAR(120) PRIMARY KEY,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Booking idempotency lock rows';
