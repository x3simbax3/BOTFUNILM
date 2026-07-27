ALTER TABLE `user_library_filters`
  ADD COLUMN `completed` integer NOT NULL DEFAULT 1
  CHECK (`completed` IN (0, 1));

ALTER TABLE `user_library_filters`
  ADD COLUMN `planned` integer NOT NULL DEFAULT 1
  CHECK (`planned` IN (0, 1));
