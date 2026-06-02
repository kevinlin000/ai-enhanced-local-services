-- V25: pending-payment reservations are temporary holds, not permanent capacity locks.
ALTER TABLE tb_booking
    ADD COLUMN hold_expires_at DATETIME NULL COMMENT 'Payment hold expiry for pending-deposit bookings' AFTER payment_trans_id;

CREATE INDEX idx_booking_hold_expiry ON tb_booking (status, hold_expires_at);
