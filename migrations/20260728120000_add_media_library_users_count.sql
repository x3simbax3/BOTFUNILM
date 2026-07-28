-- Add a denormalized count of users who saved each title.
ALTER TABLE `media` ADD COLUMN `library_users_count` integer NOT NULL DEFAULT 0
  CHECK (`library_users_count` >= 0);

-- Backfill titles already present in user libraries.
UPDATE `media`
SET `library_users_count` = (
  SELECT COUNT(*)
  FROM `user_media`
  WHERE `user_media`.`media_id` = `media`.`id`
);

-- Keep the count correct for every writer, including future code paths.
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
