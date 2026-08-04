ALTER TABLE `bot_users`
  ADD COLUMN `last_activity_at` text NOT NULL DEFAULT '';

UPDATE `bot_users`
SET `last_activity_at` = `last_started_at`
WHERE `last_activity_at` = '';

CREATE INDEX `ix_bot_users_last_activity`
  ON `bot_users` (`last_activity_at`);
