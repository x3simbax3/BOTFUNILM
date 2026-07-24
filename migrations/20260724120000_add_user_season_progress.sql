-- Create "user_season_progress" table
CREATE TABLE `user_season_progress` (
  `user_id` integer NOT NULL,
  `media_id` integer NOT NULL,
  `season_number` integer NOT NULL,
  `episodes_watched` integer NOT NULL,
  `last_watched_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  PRIMARY KEY (`user_id`, `media_id`, `season_number`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`, `media_id`) REFERENCES `user_media` (`user_id`, `media_id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CHECK (season_number >= 0),
  CHECK (episodes_watched >= 0)
);
-- Create index "ix_user_season_progress_media_id" to table: "user_season_progress"
CREATE INDEX `ix_user_season_progress_media_id` ON `user_season_progress` (`media_id`);
