CREATE TABLE `news_articles` (
  `uuid` text NOT NULL PRIMARY KEY,
  `title` text NOT NULL,
  `description` text NOT NULL,
  `url` text NOT NULL,
  `image_url` text NOT NULL,
  `source` text NOT NULL,
  `published_at` text NOT NULL,
  `status` text NOT NULL DEFAULT 'candidate',
  `rejection_reason` text,
  `discovered_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  `selected_at` text,
  `sent_at` text,
  CONSTRAINT `news_articles_status_check`
    CHECK (`status` IN ('candidate', 'selected', 'sent', 'rejected'))
);

CREATE INDEX `ix_news_articles_selection`
  ON `news_articles` (`status`, `published_at` DESC);

CREATE UNIQUE INDEX `news_articles_url`
  ON `news_articles` (`url`);

CREATE TABLE `news_article_deliveries` (
  `article_uuid` text NOT NULL,
  `user_id` integer NOT NULL,
  `status` text NOT NULL,
  `delivered_at` text NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  PRIMARY KEY (`article_uuid`, `user_id`),
  CONSTRAINT `news_article_deliveries_article`
    FOREIGN KEY (`article_uuid`) REFERENCES `news_articles` (`uuid`)
    ON DELETE CASCADE,
  CONSTRAINT `news_article_deliveries_status_check`
    CHECK (`status` IN ('sent', 'deactivated'))
);
