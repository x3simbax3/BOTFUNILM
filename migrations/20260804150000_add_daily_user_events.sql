CREATE TABLE `bot_user_daily_events` (
  `user_id` integer NOT NULL,
  `event_date` text NOT NULL,
  `event_type` text NOT NULL,
  `event_count` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`user_id`, `event_date`, `event_type`),
  CHECK (`event_count` > 0)
);

CREATE INDEX `ix_bot_user_daily_events_metric`
  ON `bot_user_daily_events` (`event_type`, `event_date`, `user_id`);

INSERT OR IGNORE INTO `bot_user_daily_events` (
  `user_id`, `event_date`, `event_type`, `event_count`
)
SELECT `user_id`, date(`last_activity_at`), 'active', 1
FROM `bot_users`
WHERE `last_activity_at` != '';
