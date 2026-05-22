-- tb_shop 只加最小欄位
ALTER TABLE tb_shop
    ADD COLUMN place_id VARCHAR(255) NULL COMMENT 'Google Places ID',
    ADD COLUMN source VARCHAR(50) NULL DEFAULT 'manual' COMMENT 'google_places / seed / manual';

ALTER TABLE tb_shop
    ADD UNIQUE INDEX uk_place_id (place_id(191));

-- 既有 25 家標記 seed
UPDATE tb_shop SET source = 'seed' WHERE source IS NULL OR source = 'manual';

-- AI metadata 獨立表、1:1 關係
CREATE TABLE tb_shop_ai_metadata (
    shop_id BIGINT UNSIGNED NOT NULL PRIMARY KEY COMMENT 'tb_shop.id 1:1',
    ai_summary TEXT NULL COMMENT 'LLM 生成餐廳介紹 50-80 字',
    highlight_review VARCHAR(500) NULL COMMENT 'LLM 抽 1 句代表',
    signature_dishes JSON NULL COMMENT '招牌菜 array',
    atmosphere_tags JSON NULL COMMENT '用餐目的 array',
    booking_difficulty VARCHAR(50) NULL COMMENT '預約困難 / 現場可入 / 未提及',
    price_per_person VARCHAR(50) NULL COMMENT '具體價位區間',
    phone VARCHAR(50) NULL COMMENT '電話',
    opening_hours JSON NULL COMMENT '7 天營業時間 array',
    extracted_at TIMESTAMP NULL COMMENT 'LLM 抽取時間',
    model_version VARCHAR(50) NULL COMMENT '抽取用的 LLM 模型',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_shop_ai_metadata_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='餐廳 AI 抽取 metadata';
