ALTER TABLE tb_voucher_order
MODIFY COLUMN pay_type tinyint unsigned NOT NULL DEFAULT 1
COMMENT '支付方式 1:信用卡 2:LinePay 3:ApplePay 4:街口';

ALTER TABLE tb_voucher_order
ADD COLUMN payment_provider varchar(20) DEFAULT 'tappay' COMMENT '金流商' AFTER pay_type,
ADD COLUMN payment_trans_id varchar(64) DEFAULT NULL COMMENT 'TapPay rec_trade_id' AFTER payment_provider;

UPDATE tb_voucher_order SET payment_provider = 'tappay' WHERE payment_provider IS NULL;
