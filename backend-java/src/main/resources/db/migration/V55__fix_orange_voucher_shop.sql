-- Voucher 30103 was renamed for 橘色涮涮屋 in V53 but retained 榮榮園's shop ID.
UPDATE tb_voucher
SET shop_id = 10550
WHERE id = 30103;
