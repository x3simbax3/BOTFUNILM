-- Track the independent daily release and weekly metadata refresh schedules.
-- SQLite CURRENT_TIMESTAMP is UTC, regardless of the worker's scheduling zone.
ALTER TABLE `media` ADD COLUMN `tmdb_metadata_checked_at` text NULL;
ALTER TABLE `media` ADD COLUMN `tmdb_refresh_error` text NULL;
ALTER TABLE `media` ADD COLUMN `last_episode_air_date` text NULL;
ALTER TABLE `media` ADD COLUMN `last_episode_season_number` integer NULL
  CHECK (`last_episode_season_number` IS NULL OR `last_episode_season_number` > 0);
ALTER TABLE `media` ADD COLUMN `last_episode_number` integer NULL
  CHECK (`last_episode_number` IS NULL OR `last_episode_number` > 0);

CREATE INDEX `ix_media_daily_refresh_due`
  ON `media` (`content_format`, `tmdb_release_checked_at`, `id`);
CREATE INDEX `ix_media_weekly_refresh_due`
  ON `media` (`content_format`, `tmdb_metadata_checked_at`, `id`);
