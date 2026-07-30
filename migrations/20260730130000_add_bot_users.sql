CREATE TABLE `bot_users` (
  `user_id` integer NOT NULL PRIMARY KEY,
  `is_active` integer NOT NULL DEFAULT 1,
  `started_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `last_started_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  CHECK (`is_active` IN (0, 1))
);

CREATE INDEX `ix_bot_users_active`
  ON `bot_users` (`is_active`, `user_id`);

INSERT OR IGNORE INTO `bot_users` (`user_id`)
SELECT `user_id` FROM `user_media`
UNION
SELECT `user_id` FROM `user_library_filters` WHERE `user_id` IS NOT NULL;
