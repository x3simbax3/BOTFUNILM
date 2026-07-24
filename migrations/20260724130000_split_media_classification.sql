-- atlas:txmode none

PRAGMA foreign_keys = OFF;

CREATE TABLE `media_new` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `tmdb_id` integer NULL,
  `content_format` text NOT NULL,
  `content_type` text NOT NULL,
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
  CHECK (content_format IN ('full_length', 'series')),
  CHECK (content_type IN ('movie', 'anime', 'cartoon')),
  CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
  CHECK (number_of_seasons IS NULL OR number_of_seasons >= 0),
  CHECK (number_of_episodes IS NULL OR number_of_episodes >= 0)
);

INSERT INTO `media_new` (
  `id`, `tmdb_id`, `content_format`, `content_type`, `title`,
  `original_title`, `description`, `poster_path`, `rating`, `release_date`,
  `first_air_date`, `number_of_seasons`, `number_of_episodes`, `status`,
  `last_updated`
)
SELECT
  `id`,
  `tmdb_id`,
  CASE `media_type`
    WHEN 'movie' THEN 'full_length'
    ELSE 'series'
  END,
  CASE `media_type`
    WHEN 'anime' THEN 'anime'
    ELSE 'movie'
  END,
  `title`,
  `original_title`,
  `description`,
  `poster_path`,
  `rating`,
  `release_date`,
  `first_air_date`,
  `number_of_seasons`,
  `number_of_episodes`,
  `status`,
  `last_updated`
FROM `media`;

DROP TABLE `media`;
ALTER TABLE `media_new` RENAME TO `media`;

CREATE UNIQUE INDEX `media_tmdb_id_content_format_content_type`
  ON `media` (`tmdb_id`, `content_format`, `content_type`);
CREATE INDEX `ix_media_status` ON `media` (`status`);

PRAGMA foreign_keys = ON;
