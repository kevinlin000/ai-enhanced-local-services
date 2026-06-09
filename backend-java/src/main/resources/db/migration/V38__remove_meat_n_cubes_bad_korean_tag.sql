-- Remove a misleading Korean tag found after the manual taxonomy audit.

START TRANSACTION;

DELETE FROM tb_shop_tag
WHERE tag_code = '韓式'
  AND shop_id IN (
    10175 -- 肉次方 燒肉放題 台北峨眉店
  );

COMMIT;
