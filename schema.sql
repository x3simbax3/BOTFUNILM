CREATE TABLE user_media (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    status              TEXT NOT NULL,
    user_rating         INTEGER,
    episodes_watched    INTEGER,
    last_watched_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    added_at            TEXT NOT NULL DEFAULT '',
    is_tracking         INTEGER NOT NULL DEFAULT 0
                        CHECK (`is_tracking` IN (0, 1)),
    badge               TEXT,
    PRIMARY KEY (user_id, media_id),
    CONSTRAINT `0` FOREIGN KEY (media_id) REFERENCES media (id)
        ON UPDATE NO ACTION ON DELETE CASCADE,
    CHECK (status IN (
                            'planned', 'watching', 'completed', 'on_hold', 'dropped'
                        )),
    CHECK (user_rating IS NULL OR user_rating BETWEEN 1 AND 10),
    CHECK (episodes_watched IS NULL OR episodes_watched >= 0)
);

CREATE INDEX ix_user_media_media_id ON user_media (media_id);
CREATE INDEX ix_user_media_tracked_by_media
    ON user_media (media_id, user_id) WHERE `is_tracking` = 1;

CREATE TABLE bot_users (
    user_id             INTEGER NOT NULL PRIMARY KEY,
    username            TEXT,
    display_name        TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1,
    news_enabled        INTEGER NOT NULL DEFAULT 1,
    started_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_started_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_activity_at    TEXT NOT NULL DEFAULT '',
    CHECK (`is_active` IN (0, 1)),
    CHECK (`news_enabled` IN (0, 1))
);

CREATE INDEX ix_bot_users_news_recipients
    ON bot_users (is_active, news_enabled, user_id);
CREATE INDEX ix_bot_users_last_activity
    ON bot_users (last_activity_at);

CREATE TABLE bot_user_daily_events (
    user_id             INTEGER NOT NULL,
    event_date          TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    event_count         INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, event_date, event_type),
    CHECK (`event_count` > 0)
);

CREATE INDEX ix_bot_user_daily_events_metric
    ON bot_user_daily_events (event_type, event_date, user_id);

CREATE TABLE user_season_progress (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    season_number       INTEGER NOT NULL,
    episodes_watched    INTEGER NOT NULL,
    last_watched_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    PRIMARY KEY (user_id, media_id, season_number),
    CONSTRAINT `0` FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id)
        ON UPDATE NO ACTION ON DELETE CASCADE,
    CHECK (season_number >= 0),
    CHECK (episodes_watched >= 0)
);

CREATE INDEX ix_user_season_progress_media_id
    ON user_season_progress (media_id);

CREATE TABLE media (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id             INTEGER,
    content_format      TEXT NOT NULL,
    content_type        TEXT NOT NULL,
    title               TEXT NOT NULL,
    original_title      TEXT,
    normalized_title    TEXT,
    normalized_original_title TEXT,
    description         TEXT,
    poster_path         TEXT,
    telegram_poster_file_id TEXT,
    rating              REAL,
    release_date        TEXT,
    first_air_date      TEXT,
    is_released         INTEGER NOT NULL DEFAULT 1,
    number_of_seasons   INTEGER,
    number_of_episodes  INTEGER,
    status              TEXT,
    last_updated        TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    library_users_count INTEGER NOT NULL DEFAULT 0,
    tmdb_status         TEXT,
    tmdb_in_production  INTEGER,
    next_episode_air_date TEXT,
    next_episode_season_number INTEGER,
    next_episode_number INTEGER,
    tmdb_release_checked_at TEXT,
    tmdb_metadata_checked_at TEXT,
    tmdb_refresh_error  TEXT,
    last_episode_air_date TEXT,
    last_episode_season_number INTEGER,
    last_episode_number INTEGER,
    available_episode_count INTEGER,
    CHECK (`library_users_count` >= 0),
    CHECK (`is_released` IN (0, 1)),
    CHECK (`tmdb_in_production` IS NULL OR `tmdb_in_production` IN (0, 1)),
    CHECK (`next_episode_season_number` IS NULL OR `next_episode_season_number` > 0),
    CHECK (`next_episode_number` IS NULL OR `next_episode_number` > 0),
    CHECK (`last_episode_season_number` IS NULL OR `last_episode_season_number` > 0),
    CHECK (`last_episode_number` IS NULL OR `last_episode_number` > 0),
    CHECK (`available_episode_count` IS NULL OR `available_episode_count` >= 0),
    CHECK (content_format IN ('full_length', 'series')),
    CHECK (content_type IN ('movie', 'anime', 'cartoon')),
    CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
    CHECK (number_of_seasons IS NULL OR number_of_seasons >= 0),
    CHECK (number_of_episodes IS NULL OR number_of_episodes >= 0)
);

CREATE UNIQUE INDEX media_tmdb_id_content_format_content_type
    ON media (tmdb_id, content_format, content_type);
CREATE INDEX ix_media_status ON media (status);
CREATE INDEX ix_media_normalized_title
    ON media (content_format, content_type, normalized_title, id);
CREATE INDEX ix_media_normalized_original_title
    ON media (content_format, content_type, normalized_original_title, id);
CREATE INDEX ix_media_daily_refresh_due
    ON media (content_format, tmdb_release_checked_at, id);
CREATE INDEX ix_media_weekly_refresh_due
    ON media (content_format, tmdb_metadata_checked_at, id);
CREATE INDEX ix_media_unreleased_due
    ON media (is_released, tmdb_release_checked_at, id);

CREATE TABLE media_search_terms (
    media_id            INTEGER NOT NULL,
    term                TEXT NOT NULL,
    PRIMARY KEY (media_id, term),
    CONSTRAINT media_search_terms_media
        FOREIGN KEY (media_id) REFERENCES media (id) ON DELETE CASCADE
);

CREATE INDEX ix_media_search_terms_term
    ON media_search_terms (term, media_id);

CREATE TABLE user_library_filters (
    user_id             INTEGER,
    full_length         INTEGER NOT NULL DEFAULT 1,
    series              INTEGER NOT NULL DEFAULT 1,
    movie               INTEGER NOT NULL DEFAULT 1,
    anime               INTEGER NOT NULL DEFAULT 1,
    cartoon             INTEGER NOT NULL DEFAULT 1,
    completed           INTEGER NOT NULL DEFAULT 1,
    planned             INTEGER NOT NULL DEFAULT 1,
    unfinished          INTEGER NOT NULL DEFAULT 1,
    ongoing             INTEGER NOT NULL DEFAULT 1,
    dropped             INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id),
    CHECK (`completed` IN (0, 1)),
    CHECK (`planned` IN (0, 1)),
    CHECK (`unfinished` IN (0, 1)),
    CHECK (`ongoing` IN (0, 1)),
    CHECK (`dropped` IN (0, 1)),
    CHECK (full_length IN (0, 1)),
    CHECK (series IN (0, 1)),
    CHECK (movie IN (0, 1)),
    CHECK (anime IN (0, 1)),
    CHECK (cartoon IN (0, 1))
);

CREATE TABLE media_seasons (
    media_id                  INTEGER NOT NULL,
    season_number             INTEGER NOT NULL,
    name                      TEXT NOT NULL,
    announced_episode_count   INTEGER NOT NULL,
    available_episode_count   INTEGER NOT NULL,
    last_updated              TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    PRIMARY KEY (media_id, season_number),
    CONSTRAINT `0` FOREIGN KEY (media_id) REFERENCES media (id)
        ON UPDATE NO ACTION ON DELETE CASCADE,
    CHECK (`season_number` > 0),
    CHECK (`announced_episode_count` >= 0),
    CHECK (`available_episode_count` >= 0
           AND `available_episode_count` <= `announced_episode_count`)
);

CREATE TABLE user_media_rating_details (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    criterion           TEXT NOT NULL,
    score               INTEGER NOT NULL,
    updated_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    PRIMARY KEY (user_id, media_id, criterion),
    CONSTRAINT `0` FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id)
        ON UPDATE NO ACTION ON DELETE CASCADE,
    CHECK (criterion IN (
                      'acting', 'story', 'visuals', 'sound', 'overall',
                      'animation', 'characters'
                  )),
    CHECK (score BETWEEN 1 AND 10)
);

CREATE TABLE series_notification_batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    sent_at             TEXT
);

CREATE INDEX ix_series_notification_batches_pending
    ON series_notification_batches (sent_at, id);

CREATE TABLE user_series_notifications (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL,
    media_id                 INTEGER NOT NULL,
    previous_episode_count   INTEGER NOT NULL,
    current_episode_count    INTEGER NOT NULL,
    season_number            INTEGER,
    episode_number           INTEGER,
    detected_at              TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    batch_id                 INTEGER,
    CONSTRAINT user_series_notifications_user_media
        FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id) ON DELETE CASCADE,
    CONSTRAINT user_series_notifications_batch
        FOREIGN KEY (batch_id) REFERENCES series_notification_batches (id)
        ON DELETE CASCADE,
    UNIQUE (user_id, media_id, current_episode_count),
    CHECK (previous_episode_count >= 0),
    CHECK (current_episode_count > previous_episode_count),
    CHECK (season_number IS NULL OR season_number > 0),
    CHECK (episode_number IS NULL OR episode_number > 0)
);

CREATE INDEX ix_user_series_notifications_unbatched
    ON user_series_notifications (batch_id, user_id, id);
CREATE INDEX ix_user_series_notifications_batch_page
    ON user_series_notifications (batch_id, id);

CREATE TABLE user_media_release_notifications (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL,
    media_id                 INTEGER NOT NULL,
    detected_at              TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    sent_at                  TEXT,
    CONSTRAINT user_media_release_notifications_user_media
        FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id) ON DELETE CASCADE,
    UNIQUE (user_id, media_id)
);

CREATE INDEX ix_user_media_release_notifications_pending
    ON user_media_release_notifications (sent_at, user_id, id);

CREATE TABLE notification_delivery_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type   TEXT NOT NULL,
    selected            INTEGER NOT NULL,
    sent                INTEGER NOT NULL,
    failed              INTEGER NOT NULL,
    deactivated         INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    CHECK (`notification_type` IN ('news', 'release', 'broadcast')),
    CHECK (`selected` >= 0),
    CHECK (`sent` >= 0),
    CHECK (`failed` >= 0),
    CHECK (`deactivated` >= 0)
);

CREATE INDEX ix_notification_delivery_runs_created
  ON notification_delivery_runs (created_at, notification_type);

CREATE TABLE news_api_daily_usage (
    usage_date          TEXT NOT NULL PRIMARY KEY,
    requests            INTEGER NOT NULL DEFAULT 0,
    api_limit           INTEGER,
    api_remaining       INTEGER,
    updated_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    CHECK (`requests` >= 0),
    CHECK (`api_limit` IS NULL OR `api_limit` >= 0),
    CHECK (`api_remaining` IS NULL OR `api_remaining` >= 0)
);

CREATE TABLE bot_features (
    feature      TEXT NOT NULL PRIMARY KEY,
    enabled      INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_by   INTEGER,
    CHECK (`feature` IN ('media_refresh', 'notifications', 'news')),
    CHECK (`enabled` IN (0, 1))
);

-- Library-count and series-progress triggers are installed by migrations.
-- Atlas Community cannot represent SQLite triggers in a declarative schema.
