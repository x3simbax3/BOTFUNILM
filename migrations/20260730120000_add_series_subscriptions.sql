ALTER TABLE `user_media` ADD COLUMN `is_tracking` integer NOT NULL DEFAULT 0
  CHECK (`is_tracking` IN (0, 1));

CREATE INDEX `ix_user_media_tracked_by_media`
  ON `user_media` (`media_id`, `user_id`) WHERE `is_tracking` = 1;

CREATE TABLE `series_notification_batches` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `user_id` integer NOT NULL,
  `created_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `sent_at` text NULL
);

CREATE INDEX `ix_series_notification_batches_pending`
  ON `series_notification_batches` (`sent_at`, `id`);

CREATE TABLE `user_series_notifications` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `user_id` integer NOT NULL,
  `media_id` integer NOT NULL,
  `previous_episode_count` integer NOT NULL,
  `current_episode_count` integer NOT NULL,
  `season_number` integer NULL,
  `episode_number` integer NULL,
  `detected_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `batch_id` integer NULL,
  CONSTRAINT `user_series_notifications_user_media`
    FOREIGN KEY (`user_id`, `media_id`)
    REFERENCES `user_media` (`user_id`, `media_id`) ON DELETE CASCADE,
  CONSTRAINT `user_series_notifications_batch`
    FOREIGN KEY (`batch_id`) REFERENCES `series_notification_batches` (`id`)
    ON DELETE CASCADE,
  CHECK (previous_episode_count >= 0),
  CHECK (current_episode_count > previous_episode_count),
  CHECK (season_number IS NULL OR season_number > 0),
  CHECK (episode_number IS NULL OR episode_number > 0)
);

CREATE UNIQUE INDEX
  `user_series_notifications_user_id_media_id_current_episode_count`
  ON `user_series_notifications`
  (`user_id`, `media_id`, `current_episode_count`);

CREATE INDEX `ix_user_series_notifications_unbatched`
  ON `user_series_notifications` (`batch_id`, `user_id`, `id`);

CREATE INDEX `ix_user_series_notifications_batch_page`
  ON `user_series_notifications` (`batch_id`, `id`);
