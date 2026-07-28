ALTER TABLE `user_library_filters`
  ADD COLUMN `unfinished` integer NOT NULL DEFAULT 1
  CHECK (`unfinished` IN (0, 1));

ALTER TABLE `user_library_filters`
  ADD COLUMN `ongoing` integer NOT NULL DEFAULT 1
  CHECK (`ongoing` IN (0, 1));
