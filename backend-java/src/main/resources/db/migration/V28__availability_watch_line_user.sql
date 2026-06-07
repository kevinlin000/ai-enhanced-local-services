ALTER TABLE tb_availability_watch
    ADD COLUMN line_user_id VARCHAR(128) NULL COMMENT 'LINE Messaging API user id for push notification' AFTER user_id;

CREATE INDEX idx_availability_watch_line_user ON tb_availability_watch (line_user_id);
