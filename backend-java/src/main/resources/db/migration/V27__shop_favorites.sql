CREATE TABLE IF NOT EXISTS tb_shop_favorite (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    shop_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_shop_favorite_user_shop (user_id, shop_id),
    INDEX idx_shop_favorite_user_status (user_id, status, updated_at),
    INDEX idx_shop_favorite_shop_status (shop_id, status),
    CONSTRAINT fk_shop_favorite_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User saved restaurants';
