-- V24: attach bookings to a user so post-transaction management is possible.
-- Existing demo rows stay nullable; new LINE/demo bookings populate user_id.
ALTER TABLE tb_booking
    ADD COLUMN user_id BIGINT NULL COMMENT 'Owner user id for my-bookings and cancellation' AFTER id;

CREATE INDEX idx_booking_user_created ON tb_booking (user_id, created_at);
CREATE INDEX idx_booking_user_status ON tb_booking (user_id, status);
