-- V23: Merchant console ownership mapping.
-- One ByteBites merchant account can manage one or more shops; all merchant APIs
-- must authorize by this mapping before reading or mutating shop inventory.
CREATE TABLE IF NOT EXISTS tb_merchant_shop (
    user_id    BIGINT       NOT NULL,
    shop_id    BIGINT UNSIGNED NOT NULL,
    role       VARCHAR(20)  NOT NULL DEFAULT 'owner',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, shop_id),
    INDEX idx_merchant_shop_shop (shop_id),
    CONSTRAINT fk_merchant_shop_shop FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Merchant user to manageable shop mapping';

-- Demo merchant account. This is portfolio/demo seed data, not real merchant onboarding.
INSERT IGNORE INTO tb_merchant_shop (user_id, shop_id, role)
SELECT 1001, id, 'owner'
FROM tb_shop
WHERE id IN (10115, 10102)
   OR name LIKE '刁民%';
