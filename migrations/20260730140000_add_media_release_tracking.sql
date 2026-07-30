ALTER TABLE `media` ADD COLUMN `is_released` integer NOT NULL DEFAULT 1
  CHECK (`is_released` IN (0, 1));

UPDATE `media`
SET `is_released` = 0
WHERE (`content_format` = 'full_length' AND `release_date` > date('now'))
   OR (`content_format` = 'series' AND `first_air_date` > date('now'));

UPDATE `user_media`
SET `status` = 'planned'
WHERE `status` = 'completed'
  AND `media_id` IN (SELECT `id` FROM `media` WHERE `is_released` = 0);

CREATE INDEX `ix_media_unreleased_due`
  ON `media` (`is_released`, `tmdb_release_checked_at`, `id`);

CREATE TABLE `user_media_release_notifications` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `user_id` integer NOT NULL,
  `media_id` integer NOT NULL,
  `detected_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `sent_at` text NULL,
  CONSTRAINT `user_media_release_notifications_user_media`
    FOREIGN KEY (`user_id`, `media_id`)
    REFERENCES `user_media` (`user_id`, `media_id`) ON DELETE CASCADE
);

CREATE UNIQUE INDEX `user_media_release_notifications_user_id_media_id`
  ON `user_media_release_notifications` (`user_id`, `media_id`);

CREATE INDEX `ix_user_media_release_notifications_pending`
  ON `user_media_release_notifications` (`sent_at`, `user_id`, `id`);
