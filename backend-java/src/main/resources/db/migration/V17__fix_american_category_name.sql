-- V17 fix schema drift: align tb_shop_type name for id=2010 with taxonomy.json
-- data-only migration, no DDL
-- source of drift: V9 inserted '美式 / Brunch'; taxonomy.json defines '美式料理' (Brunch demoted to tag)
-- rollback note: UPDATE tb_shop_type SET name='美式 / Brunch' WHERE id=2010;
-- idempotent: UPDATE to fixed value, safe to re-run

UPDATE tb_shop_type SET name = '美式料理' WHERE id = 2010 AND name != '美式料理';
