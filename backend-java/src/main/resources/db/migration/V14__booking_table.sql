-- V14: tb_booking 訂位記錄表
CREATE TABLE IF NOT EXISTS tb_booking (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    booking_code       VARCHAR(50)  NOT NULL UNIQUE COMMENT 'BK-XXXXXXXXXXXX 唯一訂位編號',
    shop_id            BIGINT       NOT NULL COMMENT '店家 ID',
    people             INT          NOT NULL DEFAULT 1 COMMENT '訂位人數',
    booking_date       DATE         NOT NULL COMMENT '訂位日期',
    booking_time       VARCHAR(10)  NOT NULL COMMENT '時段，e.g. 18:30',
    table_type         VARCHAR(20)  NOT NULL DEFAULT 'normal' COMMENT 'normal / bar / private',
    status             TINYINT      NOT NULL DEFAULT 1 COMMENT '1=待付款 2=已付款 3=已確認(免訂金)',
    needs_deposit      TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否需訂金',
    deposit_per_person INT          NOT NULL DEFAULT 0 COMMENT '每人訂金（元）',
    deposit_total      INT          NOT NULL DEFAULT 0 COMMENT '訂金總額（元）',
    payment_trans_id   VARCHAR(100) DEFAULT NULL COMMENT 'TapPay rec_trade_id',
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_shop_id   (shop_id),
    INDEX idx_booking_code (booking_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='訂位記錄表';
