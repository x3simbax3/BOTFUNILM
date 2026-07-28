-- Track announced and already aired episodes separately for active series.
ALTER TABLE `media` ADD COLUMN `available_episode_count` integer NULL
  CHECK (`available_episode_count` IS NULL OR `available_episode_count` >= 0);

UPDATE `media`
SET `available_episode_count` = `number_of_episodes`
WHERE `content_format` = 'series' AND `number_of_episodes` IS NOT NULL;

CREATE TABLE `media_seasons` (
  `media_id` integer NOT NULL,
  `season_number` integer NOT NULL CHECK (`season_number` > 0),
  `name` text NOT NULL,
  `announced_episode_count` integer NOT NULL
    CHECK (`announced_episode_count` >= 0),
  `available_episode_count` integer NOT NULL
    CHECK (`available_episode_count` >= 0
           AND `available_episode_count` <= `announced_episode_count`),
  `last_updated` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  PRIMARY KEY (`media_id`, `season_number`),
  FOREIGN KEY (`media_id`) REFERENCES `media` (`id`) ON DELETE CASCADE
);

DROP TRIGGER `validate_user_season_progress_insert`;
DROP TRIGGER `validate_user_season_progress_update`;
DROP TRIGGER `validate_user_media_series_progress_insert`;
DROP TRIGGER `validate_user_media_series_progress_update`;

CREATE TRIGGER `validate_user_season_progress_insert`
BEFORE INSERT ON `user_season_progress`
BEGIN
  SELECT CASE
    WHEN NOT EXISTS (
      SELECT 1 FROM `media`
      WHERE `id` = NEW.`media_id` AND `content_format` = 'series'
    )
    THEN RAISE(ABORT, 'progress can only be saved for series')
  END;
  SELECT CASE
    WHEN (SELECT `number_of_seasons` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND NEW.`season_number` > (SELECT `number_of_seasons` FROM `media` WHERE `id` = NEW.`media_id`)
    THEN RAISE(ABORT, 'season number exceeds series season count')
  END;
  SELECT CASE
    WHEN EXISTS (
      SELECT 1 FROM `media_seasons`
      WHERE `media_id` = NEW.`media_id`
        AND `season_number` = NEW.`season_number`
        AND NEW.`episodes_watched` > `available_episode_count`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available season episodes')
  END;
  SELECT CASE
    WHEN COALESCE((
      SELECT SUM(`episodes_watched`) FROM `user_season_progress`
      WHERE `user_id` = NEW.`user_id` AND `media_id` = NEW.`media_id`
    ), 0) + NEW.`episodes_watched` > (
      SELECT `available_episode_count` FROM `media` WHERE `id` = NEW.`media_id`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available series episodes')
  END;
END;

CREATE TRIGGER `validate_user_season_progress_update`
BEFORE UPDATE ON `user_season_progress`
BEGIN
  SELECT CASE
    WHEN NOT EXISTS (
      SELECT 1 FROM `media`
      WHERE `id` = NEW.`media_id` AND `content_format` = 'series'
    )
    THEN RAISE(ABORT, 'progress can only be saved for series')
  END;
  SELECT CASE
    WHEN (SELECT `number_of_seasons` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND NEW.`season_number` > (SELECT `number_of_seasons` FROM `media` WHERE `id` = NEW.`media_id`)
    THEN RAISE(ABORT, 'season number exceeds series season count')
  END;
  SELECT CASE
    WHEN EXISTS (
      SELECT 1 FROM `media_seasons`
      WHERE `media_id` = NEW.`media_id`
        AND `season_number` = NEW.`season_number`
        AND NEW.`episodes_watched` > `available_episode_count`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available season episodes')
  END;
  SELECT CASE
    WHEN COALESCE((
      SELECT SUM(`episodes_watched`) FROM `user_season_progress`
      WHERE `user_id` = NEW.`user_id`
        AND `media_id` = NEW.`media_id`
        AND NOT (
          `user_id` = OLD.`user_id`
          AND `media_id` = OLD.`media_id`
          AND `season_number` = OLD.`season_number`
        )
    ), 0) + NEW.`episodes_watched` > (
      SELECT `available_episode_count` FROM `media` WHERE `id` = NEW.`media_id`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available series episodes')
  END;
END;

CREATE TRIGGER `validate_user_media_series_progress_insert`
BEFORE INSERT ON `user_media`
WHEN NEW.`episodes_watched` IS NOT NULL
BEGIN
  SELECT CASE
    WHEN NEW.`episodes_watched` > (
      SELECT `available_episode_count` FROM `media` WHERE `id` = NEW.`media_id`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available series episodes')
  END;
END;

CREATE TRIGGER `validate_user_media_series_progress_update`
BEFORE UPDATE OF `episodes_watched` ON `user_media`
WHEN NEW.`episodes_watched` IS NOT NULL
BEGIN
  SELECT CASE
    WHEN NEW.`episodes_watched` > (
      SELECT `available_episode_count` FROM `media` WHERE `id` = NEW.`media_id`
    )
    THEN RAISE(ABORT, 'watched episodes exceed available series episodes')
  END;
END;
