CREATE TABLE IF NOT EXISTS tb_availability_watch (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    shop_id BIGINT UNSIGNED NOT NULL,
    booking_date DATE NOT NULL,
    booking_time VARCHAR(5) NOT NULL,
    table_type VARCHAR(20) NOT NULL DEFAULT 'normal',
    people INT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    triggered_at DATETIME NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_availability_watch_slot (user_id, shop_id, booking_date, booking_time, table_type, people, status),
    INDEX idx_availability_watch_trigger (status, shop_id, booking_date, booking_time, table_type, people),
    CONSTRAINT fk_availability_watch_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User watch requests for sold-out booking slots';

CREATE TABLE IF NOT EXISTS tb_user_notification (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type VARCHAR(40) NOT NULL,
    title VARCHAR(160) NOT NULL,
    body VARCHAR(500) NOT NULL,
    shop_id BIGINT UNSIGNED NULL,
    watch_id BIGINT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'UNREAD',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME NULL,
    UNIQUE KEY uk_notification_watch (watch_id),
    INDEX idx_user_notification_user_status (user_id, status, created_at),
    CONSTRAINT fk_user_notification_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE SET NULL,
    CONSTRAINT fk_user_notification_watch FOREIGN KEY (watch_id) REFERENCES tb_availability_watch(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='In-app user notifications';
