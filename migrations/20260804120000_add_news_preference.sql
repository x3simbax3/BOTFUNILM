ALTER TABLE `bot_users`
  ADD COLUMN `news_enabled` integer NOT NULL DEFAULT 1
  CHECK (`news_enabled` IN (0, 1));

DROP INDEX `ix_bot_users_active`;

CREATE INDEX `ix_bot_users_news_recipients`
  ON `bot_users` (`is_active`, `news_enabled`, `user_id`);
