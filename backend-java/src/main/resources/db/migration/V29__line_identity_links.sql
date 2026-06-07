CREATE TABLE IF NOT EXISTS tb_line_identity_link (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    line_user_id VARCHAR(128) NOT NULL,
    user_id BIGINT NOT NULL,
    display_name VARCHAR(255),
    source VARCHAR(32) NOT NULL DEFAULT 'line_bot',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_line_identity_link_user_id (line_user_id),
    KEY idx_line_identity_link_user (user_id)
);
