-- V20: Idempotency key for booking reservation retries.
-- Nullable for existing/manual bookings; unique when provided by Agent/client.
ALTER TABLE tb_booking
    ADD COLUMN idempotency_key VARCHAR(120) NULL COMMENT 'Client/Agent supplied idempotency key';

CREATE UNIQUE INDEX uk_booking_idempotency_key ON tb_booking (idempotency_key);
