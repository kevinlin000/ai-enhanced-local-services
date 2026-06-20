CREATE TABLE IF NOT EXISTS tb_merchant_notification_dispatch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id BIGINT NOT NULL,
    notification_type VARCHAR(60) NOT NULL,
    dispatch_source VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,
    reason VARCHAR(60) NULL,
    report_status VARCHAR(40) NULL,
    attention_count INT NOT NULL DEFAULT 0,
    pending_escalation_count INT NOT NULL DEFAULT 0,
    escalated_count INT NOT NULL DEFAULT 0,
    stuck_minutes INT NOT NULL DEFAULT 30,
    cooldown_minutes INT NOT NULL DEFAULT 120,
    line_user_id VARCHAR(100) NULL,
    headline VARCHAR(200) NULL,
    sent_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_merchant_notification_last_sent (
        shop_id,
        notification_type,
        status,
        sent_at
    ),
    INDEX idx_merchant_notification_created (
        shop_id,
        notification_type,
        created_at
    )
);
