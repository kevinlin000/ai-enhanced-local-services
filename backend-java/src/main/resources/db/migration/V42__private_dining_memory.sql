CREATE TABLE IF NOT EXISTS tb_dining_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    booking_code VARCHAR(50) NOT NULL,
    shop_id BIGINT UNSIGNED NOT NULL,
    rating TINYINT NOT NULL,
    tags_json TEXT NOT NULL,
    note VARCHAR(500),
    do_not_recommend BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR(32) NOT NULL DEFAULT 'BOOKING_FEEDBACK',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_dining_memory_user_booking (user_id, booking_code),
    INDEX idx_dining_memory_user_updated (user_id, updated_at),
    INDEX idx_dining_memory_user_shop (user_id, shop_id),
    CONSTRAINT fk_dining_memory_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Private user dining feedback and preference memory';
