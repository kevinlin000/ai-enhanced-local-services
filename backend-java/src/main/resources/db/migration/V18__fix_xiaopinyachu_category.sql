-- V18 fix data error: 小品雅廚 (id=10124) was assigned type_id=2005 (素食) in V16 remap
-- root cause: V16 hand-coded WHEN 10124 THEN 2005 incorrectly (primary_type is chinese_restaurant)
-- correct category: 2008 中式料理
-- data-only migration, no DDL
-- rollback note: UPDATE tb_shop SET type_id=2005 WHERE id=10124;
-- idempotent: WHERE clause guards against re-run side effects

UPDATE tb_shop SET type_id = 2008 WHERE id = 10124 AND type_id = 2005;
