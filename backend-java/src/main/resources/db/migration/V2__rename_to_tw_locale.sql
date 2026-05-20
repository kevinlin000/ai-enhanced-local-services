-- V2: rename tables and columns to taiwan locale
-- design principle:
--   - chinese-locale naming (商戶/探店筆記) -> taiwan-locale english naming (shop/review)
--   - keep all PKs and indexes intact
--   - no destructive changes; new columns added in V3

-- ============================================================
-- table: tb_shop (no rename, already english)
-- only update comment to taiwan context
-- ============================================================
ALTER TABLE tb_shop COMMENT = 'shop / store entity (taiwan locale)';

-- ============================================================
-- table: tb_blog -> tb_review
-- "探店筆記" in original heima dianping is essentially user reviews;
-- renaming to match taiwan locale and inline-style review platforms
-- ============================================================
RENAME TABLE tb_blog TO tb_review;
ALTER TABLE tb_review COMMENT = 'user review for shops';

-- ============================================================
-- table: tb_blog_comments -> tb_review_comments
-- (note: this table was already removed from java code in dead-code cleanup,
--  but the DB table may still exist; rename for consistency)
-- ============================================================
-- skip if table doesn't exist
DROP TABLE IF EXISTS tb_blog_comments;
-- we removed the java code earlier, no need to keep this table at all

-- ============================================================
-- table: tb_voucher / tb_seckill_voucher / tb_voucher_order
-- keep as-is, "voucher" is already taiwan-friendly english naming
-- ============================================================
ALTER TABLE tb_voucher COMMENT = 'shop voucher / coupon';
ALTER TABLE tb_seckill_voucher COMMENT = 'seckill (flash sale) voucher';
ALTER TABLE tb_voucher_order COMMENT = 'voucher order';

-- ============================================================
-- table: tb_user
-- phone column will be updated in V3 (china format -> taiwan format)
-- only update comment here
-- ============================================================
ALTER TABLE tb_user COMMENT = 'user account (taiwan locale)';
