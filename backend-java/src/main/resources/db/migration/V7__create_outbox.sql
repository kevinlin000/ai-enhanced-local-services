CREATE TABLE outbox_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL COMMENT 'e.g. ORDER, REVIEW',
    aggregate_id BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL COMMENT 'e.g. order.created',
    payload JSON NOT NULL,
    routing_key VARCHAR(100) NOT NULL,
    exchange VARCHAR(100) NOT NULL,
    status TINYINT NOT NULL DEFAULT 0 COMMENT '0=pending, 1=sent, 2=failed',
    retry_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME NULL,
    INDEX idx_status_created (status, created_at)
) COMMENT='outbox pattern for reliable message publishing';
