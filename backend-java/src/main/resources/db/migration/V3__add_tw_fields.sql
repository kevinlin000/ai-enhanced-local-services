-- V3: add taiwan-specific columns to existing tables
-- design principle:
--   - all new columns are nullable, won't break existing rows
--   - mrt_station (台北捷運站) used for spatial demo + UX
--   - line_user_id prepared for LINE Login integration (B2)

-- ============================================================
-- tb_user: add LINE Login fields (will be populated in B2)
-- ============================================================
ALTER TABLE tb_user
    ADD COLUMN line_user_id VARCHAR(64) NULL COMMENT 'line user id (sub from id_token)',
    ADD COLUMN line_display_name VARCHAR(100) NULL COMMENT 'line display name',
    ADD COLUMN line_picture_url VARCHAR(500) NULL COMMENT 'line avatar url',
    ADD UNIQUE INDEX uk_line_user_id (line_user_id);

-- ============================================================
-- tb_shop: add taiwan-specific fields
-- ============================================================
ALTER TABLE tb_shop
    ADD COLUMN mrt_station VARCHAR(50) NULL COMMENT '最近捷運站 (e.g. 信義安和)',
    ADD COLUMN mrt_distance_meters INT NULL COMMENT '距離捷運站公尺數',
    ADD COLUMN district VARCHAR(20) NULL COMMENT '行政區 (e.g. 信義區)',
    ADD COLUMN price_range TINYINT NULL COMMENT '價位等級 1-4 (對應 $/$$/$$$/$$$$)',
    ADD COLUMN business_hours JSON NULL COMMENT '營業時間 (json schema TBD)',
    ADD INDEX idx_mrt_station (mrt_station),
    ADD INDEX idx_district (district);

-- ============================================================
-- tb_shop_type: redesign categories for taiwan food scene
-- (we will not alter rows here, just prepare; V4 will insert tw categories)
-- ============================================================
ALTER TABLE tb_shop_type
    ADD COLUMN slug VARCHAR(50) NULL COMMENT 'url-friendly identifier (e.g. beef-noodle)',
    ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'soft delete flag',
    ADD INDEX idx_slug (slug);

-- ============================================================
-- tb_review: track sentiment for AI integration (Stage 3+)
-- ============================================================
ALTER TABLE tb_review
    ADD COLUMN ai_summary TEXT NULL COMMENT 'ai-generated review summary (filled by python ai service)',
    ADD COLUMN ai_sentiment TINYINT NULL COMMENT 'ai sentiment score 1-5 (filled by python ai service)',
    ADD COLUMN ai_processed_at DATETIME NULL COMMENT 'when ai service last processed this review';
