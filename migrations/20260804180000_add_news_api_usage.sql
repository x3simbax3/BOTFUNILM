ALTER TABLE `user_library_filters`
  ADD COLUMN `dropped` integer NOT NULL DEFAULT 1
  CHECK (`dropped` IN (0, 1));

CREATE TABLE `news_api_daily_usage` (
  `usage_date` text NOT NULL PRIMARY KEY,
  `requests` integer NOT NULL DEFAULT 0,
  `api_limit` integer NULL,
  `api_remaining` integer NULL,
  `updated_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  CHECK (`requests` >= 0),
  CHECK (`api_limit` IS NULL OR `api_limit` >= 0),
  CHECK (`api_remaining` IS NULL OR `api_remaining` >= 0)
);

CREATE TABLE `new_notification_delivery_runs` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `notification_type` text NOT NULL,
  `selected` integer NOT NULL,
  `sent` integer NOT NULL,
  `failed` integer NOT NULL,
  `deactivated` integer NOT NULL DEFAULT 0,
  `created_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  CHECK (`notification_type` IN ('news', 'release', 'broadcast')),
  CHECK (`selected` >= 0),
  CHECK (`sent` >= 0),
  CHECK (`failed` >= 0),
  CHECK (`deactivated` >= 0)
);

INSERT INTO `new_notification_delivery_runs`
SELECT * FROM `notification_delivery_runs`;

DROP TABLE `notification_delivery_runs`;

ALTER TABLE `new_notification_delivery_runs`
RENAME TO `notification_delivery_runs`;

CREATE INDEX `ix_notification_delivery_runs_created`
  ON `notification_delivery_runs` (`created_at`, `notification_type`);
