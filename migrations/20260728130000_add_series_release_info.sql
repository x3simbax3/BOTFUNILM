-- Cache current TMDB release information for series cards.
ALTER TABLE `media` ADD COLUMN `tmdb_status` text NULL;
ALTER TABLE `media` ADD COLUMN `tmdb_in_production` integer NULL
  CHECK (`tmdb_in_production` IS NULL OR `tmdb_in_production` IN (0, 1));
ALTER TABLE `media` ADD COLUMN `next_episode_air_date` text NULL;
ALTER TABLE `media` ADD COLUMN `next_episode_season_number` integer NULL
  CHECK (`next_episode_season_number` IS NULL OR `next_episode_season_number` > 0);
ALTER TABLE `media` ADD COLUMN `next_episode_number` integer NULL
  CHECK (`next_episode_number` IS NULL OR `next_episode_number` > 0);
ALTER TABLE `media` ADD COLUMN `tmdb_release_checked_at` text NULL;
