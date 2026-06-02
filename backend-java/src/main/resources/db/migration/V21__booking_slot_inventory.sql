-- V21: Simulated booking slot inventory.
-- Availability source is owned by ByteBites for demo reliability; not scraped from Google/inline.
CREATE TABLE IF NOT EXISTS tb_booking_slot_inventory (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    shop_id        BIGINT      NOT NULL,
    booking_date   DATE        NOT NULL,
    booking_time   VARCHAR(10) NOT NULL,
    table_type     VARCHAR(20) NOT NULL DEFAULT 'normal',
    capacity       INT         NOT NULL DEFAULT 8 COMMENT 'Max people available in this slot',
    booked_count   INT         NOT NULL DEFAULT 0 COMMENT 'People already booked in this slot',
    created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_booking_slot (shop_id, booking_date, booking_time, table_type),
    INDEX idx_booking_slot_lookup (shop_id, booking_date, booking_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Simulated booking availability inventory';
