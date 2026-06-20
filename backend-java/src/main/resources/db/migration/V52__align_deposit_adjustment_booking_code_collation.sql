-- Keep booking adjustment joins stable on clean and upgraded MySQL schemas.
-- V47 created this column with the table default collation; older base tables can
-- use utf8mb4_0900_ai_ci, which makes booking_code joins fail at runtime.
ALTER TABLE tb_booking_deposit_adjustment
    MODIFY booking_code VARCHAR(50)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci
    NOT NULL;
