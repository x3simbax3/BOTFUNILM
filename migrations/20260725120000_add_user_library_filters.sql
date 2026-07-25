-- Keep the original addition date separate from progress updates.
ALTER TABLE `user_media` ADD COLUMN `added_at` text NOT NULL DEFAULT '';
UPDATE `user_media` SET `added_at` = `last_watched_at` WHERE `added_at` = '';

-- Create "user_library_filters" table
CREATE TABLE `user_library_filters` (
  `user_id` integer NULL,
  `full_length` integer NOT NULL DEFAULT 1,
  `series` integer NOT NULL DEFAULT 1,
  `movie` integer NOT NULL DEFAULT 1,
  `anime` integer NOT NULL DEFAULT 1,
  `cartoon` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`user_id`),
  CHECK (full_length IN (0, 1)),
  CHECK (series IN (0, 1)),
  CHECK (movie IN (0, 1)),
  CHECK (anime IN (0, 1)),
  CHECK (cartoon IN (0, 1))
);
