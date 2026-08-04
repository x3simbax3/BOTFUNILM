CREATE TABLE `notification_delivery_runs` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `notification_type` text NOT NULL,
  `selected` integer NOT NULL,
  `sent` integer NOT NULL,
  `failed` integer NOT NULL,
  `deactivated` integer NOT NULL DEFAULT 0,
  `created_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  CHECK (`notification_type` IN ('news', 'release')),
  CHECK (`selected` >= 0),
  CHECK (`sent` >= 0),
  CHECK (`failed` >= 0),
  CHECK (`deactivated` >= 0)
);

CREATE INDEX `ix_notification_delivery_runs_created`
  ON `notification_delivery_runs` (`created_at`, `notification_type`);
