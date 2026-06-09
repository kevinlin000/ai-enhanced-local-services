-- Remove the first 25 demo restaurants from active product surfaces.
-- Keep booking history intact by soft-deleting the shops instead of removing rows.

DELETE FROM tb_shop_badge WHERE shop_id BETWEEN 10001 AND 10025;
DELETE FROM tb_shop_tag WHERE shop_id BETWEEN 10001 AND 10025;
DELETE FROM tb_shop_ai_metadata WHERE shop_id BETWEEN 10001 AND 10025;
DELETE FROM tb_shop_absa WHERE shop_id BETWEEN 10001 AND 10025;
DELETE FROM tb_shop_favorite WHERE shop_id BETWEEN 10001 AND 10025;

UPDATE tb_availability_watch
SET status = 'CANCELED',
    updated_at = NOW()
WHERE shop_id BETWEEN 10001 AND 10025
  AND status IN ('ACTIVE', 'TRIGGERED');

UPDATE tb_shop
SET is_active = 0,
    source = 'legacy_seed_removed',
    update_time = NOW()
WHERE id BETWEEN 10001 AND 10025;
