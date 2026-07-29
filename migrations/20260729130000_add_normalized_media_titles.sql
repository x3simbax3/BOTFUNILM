ALTER TABLE `media` ADD COLUMN `normalized_title` text NULL;
ALTER TABLE `media` ADD COLUMN `normalized_original_title` text NULL;

CREATE INDEX `ix_media_normalized_title`
  ON `media` (`content_format`, `content_type`, `normalized_title`, `id`);
CREATE INDEX `ix_media_normalized_original_title`
  ON `media` (
    `content_format`, `content_type`, `normalized_original_title`, `id`
  );
