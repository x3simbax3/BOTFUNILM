-- Create "media" table
CREATE TABLE `media` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `tmdb_id` integer NULL,
  `media_type` text NOT NULL,
  `title` text NOT NULL,
  `original_title` text NULL,
  `description` text NULL,
  `poster_path` text NULL,
  `rating` real NULL,
  `release_date` text NULL,
  `first_air_date` text NULL,
  `number_of_seasons` integer NULL,
  `number_of_episodes` integer NULL,
  `status` text NULL,
  `last_updated` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  CHECK (media_type IN ('movie', 'tv', 'anime')),
  CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
  CHECK (number_of_seasons IS NULL OR number_of_seasons >= 0),
  CHECK (number_of_episodes IS NULL OR number_of_episodes >= 0)
);
-- Create index "media_tmdb_id_media_type" to table: "media"
CREATE UNIQUE INDEX `media_tmdb_id_media_type` ON `media` (`tmdb_id`, `media_type`);
-- Create index "ix_media_status" to table: "media"
CREATE INDEX `ix_media_status` ON `media` (`status`);
-- Create "user_media" table
CREATE TABLE `user_media` (
  `user_id` integer NOT NULL,
  `media_id` integer NOT NULL,
  `status` text NOT NULL,
  `user_rating` integer NULL,
  `episodes_watched` integer NULL,
  `last_watched_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  PRIMARY KEY (`user_id`, `media_id`),
  CONSTRAINT `0` FOREIGN KEY (`media_id`) REFERENCES `media` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CHECK (status IN (
                            'planned', 'watching', 'completed', 'on_hold', 'dropped'
                        )),
  CHECK (user_rating IS NULL OR user_rating BETWEEN 1 AND 10),
  CHECK (episodes_watched IS NULL OR episodes_watched >= 0)
);
-- Create index "ix_user_media_media_id" to table: "user_media"
CREATE INDEX `ix_user_media_media_id` ON `user_media` (`media_id`);
