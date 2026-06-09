-- V39: opt-in parking reminders for LINE/web bookings.
ALTER TABLE tb_booking
    ADD COLUMN driving_to_booking TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'User plans to drive to this booking' AFTER idempotency_key,
    ADD COLUMN parking_reminder_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Send pre-arrival parking availability reminder' AFTER driving_to_booking,
    ADD COLUMN parking_reminder_sent_at DATETIME NULL COMMENT 'When the parking reminder was sent' AFTER parking_reminder_enabled;

CREATE INDEX idx_booking_parking_reminder
    ON tb_booking (parking_reminder_enabled, parking_reminder_sent_at, booking_date, booking_time, status);
