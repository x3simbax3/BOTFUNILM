CREATE TABLE `bot_features` (
  `feature` text NOT NULL PRIMARY KEY,
  `enabled` integer NOT NULL DEFAULT 1 CHECK (`enabled` IN (0, 1)),
  `updated_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `updated_by` integer NULL,
  CHECK (`feature` IN ('media_refresh', 'notifications', 'news'))
);

INSERT INTO `bot_features` (`feature`) VALUES
  ('media_refresh'),
  ('notifications'),
  ('news');
