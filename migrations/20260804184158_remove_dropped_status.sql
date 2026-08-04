-- Disable the enforcement of foreign-keys constraints
PRAGMA foreign_keys = off;
-- Preserve previously dropped titles as paused library entries.
UPDATE `user_media` SET `status` = 'on_hold' WHERE `status` = 'dropped';
-- Create "new_user_media" table
CREATE TABLE `new_user_media` (
  `user_id` integer NOT NULL,
  `media_id` integer NOT NULL,
  `status` text NOT NULL,
  `user_rating` integer NULL,
  `episodes_watched` integer NULL,
  `last_watched_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `added_at` text NOT NULL DEFAULT '',
  `is_tracking` integer NOT NULL DEFAULT 0,
  `badge` text NULL,
  PRIMARY KEY (`user_id`, `media_id`),
  CONSTRAINT `0` FOREIGN KEY (`media_id`) REFERENCES `media` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CHECK (`is_tracking` IN (0, 1)),
  CHECK (status IN ('planned', 'watching', 'completed', 'on_hold')),
  CHECK (user_rating IS NULL OR user_rating BETWEEN 1 AND 10),
  CHECK (episodes_watched IS NULL OR episodes_watched >= 0)
);
-- Copy rows from old table "user_media" to new temporary table "new_user_media"
INSERT INTO `new_user_media` (`user_id`, `media_id`, `status`, `user_rating`, `episodes_watched`, `last_watched_at`, `added_at`, `is_tracking`, `badge`) SELECT `user_id`, `media_id`, `status`, `user_rating`, `episodes_watched`, `last_watched_at`, `added_at`, `is_tracking`, `badge` FROM `user_media`;
-- Drop "user_media" table after copying rows
DROP TABLE `user_media`;
-- Rename temporary table "new_user_media" to "user_media"
ALTER TABLE `new_user_media` RENAME TO `user_media`;
-- Create index "ix_user_media_media_id" to table: "user_media"
CREATE INDEX `ix_user_media_media_id` ON `user_media` (`media_id`);
-- Create index "ix_user_media_tracked_by_media" to table: "user_media"
CREATE INDEX `ix_user_media_tracked_by_media` ON `user_media` (`media_id`, `user_id`) WHERE `is_tracking` = 1;
-- Recreate triggers attached to the replaced table.
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

CREATE TRIGGER `update_media_library_users_count_after_insert`
AFTER INSERT ON `user_media`
BEGIN
  UPDATE `media`
  SET `library_users_count` = (
    SELECT COUNT(*) FROM `user_media` WHERE `media_id` = NEW.`media_id`
  )
  WHERE `id` = NEW.`media_id`;
END;

CREATE TRIGGER `update_media_library_users_count_after_delete`
AFTER DELETE ON `user_media`
BEGIN
  UPDATE `media`
  SET `library_users_count` = (
    SELECT COUNT(*) FROM `user_media` WHERE `media_id` = OLD.`media_id`
  )
  WHERE `id` = OLD.`media_id`;
END;

CREATE TRIGGER `update_media_library_users_count_after_media_change`
AFTER UPDATE OF `media_id` ON `user_media`
WHEN OLD.`media_id` <> NEW.`media_id`
BEGIN
  UPDATE `media`
  SET `library_users_count` = (
    SELECT COUNT(*) FROM `user_media` WHERE `media_id` = OLD.`media_id`
  )
  WHERE `id` = OLD.`media_id`;

  UPDATE `media`
  SET `library_users_count` = (
    SELECT COUNT(*) FROM `user_media` WHERE `media_id` = NEW.`media_id`
  )
  WHERE `id` = NEW.`media_id`;
END;
-- Create "new_user_library_filters" table
CREATE TABLE `new_user_library_filters` (
  `user_id` integer NULL,
  `full_length` integer NOT NULL DEFAULT 1,
  `series` integer NOT NULL DEFAULT 1,
  `movie` integer NOT NULL DEFAULT 1,
  `anime` integer NOT NULL DEFAULT 1,
  `cartoon` integer NOT NULL DEFAULT 1,
  `completed` integer NOT NULL DEFAULT 1,
  `planned` integer NOT NULL DEFAULT 1,
  `unfinished` integer NOT NULL DEFAULT 1,
  `ongoing` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`user_id`),
  CHECK (`completed` IN (0, 1)),
  CHECK (`planned` IN (0, 1)),
  CHECK (`unfinished` IN (0, 1)),
  CHECK (`ongoing` IN (0, 1)),
  CHECK (full_length IN (0, 1)),
  CHECK (series IN (0, 1)),
  CHECK (movie IN (0, 1)),
  CHECK (anime IN (0, 1)),
  CHECK (cartoon IN (0, 1))
);
-- Copy rows from old table "user_library_filters" to new temporary table "new_user_library_filters"
INSERT INTO `new_user_library_filters` (`user_id`, `full_length`, `series`, `movie`, `anime`, `cartoon`, `completed`, `planned`, `unfinished`, `ongoing`) SELECT `user_id`, `full_length`, `series`, `movie`, `anime`, `cartoon`, `completed`, `planned`, `unfinished`, `ongoing` FROM `user_library_filters`;
-- Drop "user_library_filters" table after copying rows
DROP TABLE `user_library_filters`;
-- Rename temporary table "new_user_library_filters" to "user_library_filters"
ALTER TABLE `new_user_library_filters` RENAME TO `user_library_filters`;
-- Enable back the enforcement of foreign-keys constraints
PRAGMA foreign_keys = on;
