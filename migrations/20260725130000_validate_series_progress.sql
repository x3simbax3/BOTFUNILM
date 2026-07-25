-- Reject invalid series progress even when writes bypass application services.
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
    WHEN (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND COALESCE((
        SELECT SUM(`episodes_watched`) FROM `user_season_progress`
        WHERE `user_id` = NEW.`user_id` AND `media_id` = NEW.`media_id`
      ), 0) + NEW.`episodes_watched` > (
        SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`
      )
    THEN RAISE(ABORT, 'watched episodes exceed series episode count')
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
    WHEN (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND COALESCE((
        SELECT SUM(`episodes_watched`) FROM `user_season_progress`
        WHERE `user_id` = NEW.`user_id`
          AND `media_id` = NEW.`media_id`
          AND NOT (
            `user_id` = OLD.`user_id`
            AND `media_id` = OLD.`media_id`
            AND `season_number` = OLD.`season_number`
          )
      ), 0) + NEW.`episodes_watched` > (
        SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`
      )
    THEN RAISE(ABORT, 'watched episodes exceed series episode count')
  END;
END;

CREATE TRIGGER `validate_user_media_series_progress_insert`
BEFORE INSERT ON `user_media`
WHEN NEW.`episodes_watched` IS NOT NULL
BEGIN
  SELECT CASE
    WHEN (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND NEW.`episodes_watched` > (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`)
    THEN RAISE(ABORT, 'watched episodes exceed series episode count')
  END;
END;

CREATE TRIGGER `validate_user_media_series_progress_update`
BEFORE UPDATE OF `episodes_watched` ON `user_media`
WHEN NEW.`episodes_watched` IS NOT NULL
BEGIN
  SELECT CASE
    WHEN (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`) IS NOT NULL
      AND NEW.`episodes_watched` > (SELECT `number_of_episodes` FROM `media` WHERE `id` = NEW.`media_id`)
    THEN RAISE(ABORT, 'watched episodes exceed series episode count')
  END;
END;
