-- V41: Align demo merchant console with the presentation stories.
-- These are presentation/demo ownership rows so the merchant console can
-- adjust the same shops used by the Web and LINE demo flows.
INSERT IGNORE INTO tb_merchant_shop (user_id, shop_id, role)
SELECT 1001, id, 'owner'
FROM tb_shop
WHERE is_active = 1
  AND (
      id IN (
          10673, 10709, 10404, 10610, 10701,
          10113, 10108, 10598, 10225, 10111,
          10115, 10102, 10116
      )
      OR name LIKE '刁民%'
  );
