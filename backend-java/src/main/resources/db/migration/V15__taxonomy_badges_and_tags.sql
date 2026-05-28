-- Taxonomy axis split, phase 1:
-- - keep tb_shop.type_id as primary cuisine axis for now
-- - add badge/tag dictionaries and m2m relations
-- - do NOT repurpose tb_shop_type ids here yet
--   reason: current shop rows still point to old type_id meaning until backfill lands

CREATE TABLE `tb_badge_def` (
  `code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'badge code, human-readable stable key',
  `display_name` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'badge display name',
  `sort` int(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT 'display order',
  `is_active` tinyint(1) UNSIGNED NOT NULL DEFAULT 1 COMMENT '1=active,0=inactive',
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `update_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`code`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = 'badge dictionary' ROW_FORMAT = Compact;

CREATE TABLE `tb_tag_def` (
  `code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'tag code, human-readable stable key',
  `display_name` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'tag display name',
  `sort` int(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT 'display order',
  `is_active` tinyint(1) UNSIGNED NOT NULL DEFAULT 1 COMMENT '1=active,0=inactive',
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `update_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`code`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = 'tag dictionary' ROW_FORMAT = Compact;

CREATE TABLE `tb_shop_badge` (
  `shop_id` bigint(20) UNSIGNED NOT NULL COMMENT 'shop id',
  `badge_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'badge code',
  `source` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'assignment source: allowlist/auto/manual',
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  PRIMARY KEY (`shop_id`, `badge_code`) USING BTREE,
  INDEX `idx_shop_badge_badge_code`(`badge_code`, `shop_id`) USING BTREE,
  CONSTRAINT `fk_shop_badge_shop` FOREIGN KEY (`shop_id`) REFERENCES `tb_shop` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_shop_badge_badge_def` FOREIGN KEY (`badge_code`) REFERENCES `tb_badge_def` (`code`)
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = 'shop to badge relation' ROW_FORMAT = Compact;

CREATE TABLE `tb_shop_tag` (
  `shop_id` bigint(20) UNSIGNED NOT NULL COMMENT 'shop id',
  `tag_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'tag code',
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  PRIMARY KEY (`shop_id`, `tag_code`) USING BTREE,
  INDEX `idx_shop_tag_tag_code`(`tag_code`, `shop_id`) USING BTREE,
  CONSTRAINT `fk_shop_tag_shop` FOREIGN KEY (`shop_id`) REFERENCES `tb_shop` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_shop_tag_tag_def` FOREIGN KEY (`tag_code`) REFERENCES `tb_tag_def` (`code`)
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = 'shop to tag relation' ROW_FORMAT = Compact;

INSERT INTO `tb_badge_def` (`code`, `display_name`, `sort`, `is_active`) VALUES
  ('高級', '高級', 1, 1);

INSERT INTO `tb_tag_def` (`code`, `display_name`, `sort`, `is_active`) VALUES
  ('Brunch', 'Brunch', 1, 1),
  ('早午餐', '早午餐', 2, 1),
  ('牛排', '牛排', 3, 1),
  ('韓式', '韓式', 4, 1),
  ('法式', '法式', 5, 1),
  ('義式', '義式', 6, 1),
  ('餐酒館', '餐酒館', 7, 1),
  ('鐵板燒', '鐵板燒', 8, 1),
  ('吃到飽', '吃到飽', 9, 1),
  ('約會', '約會', 10, 1),
  ('商務', '商務', 11, 1),
  ('包廂', '包廂', 12, 1),
  ('景觀', '景觀', 13, 1),
  ('親子', '親子', 14, 1),
  ('免訂金', '免訂金', 15, 1),
  ('HotSeat', 'HotSeat', 16, 1);
