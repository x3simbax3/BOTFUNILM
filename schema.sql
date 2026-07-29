CREATE TABLE user_media (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    status              TEXT NOT NULL,
    user_rating         INTEGER,
    episodes_watched    INTEGER,
    last_watched_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    added_at            TEXT NOT NULL DEFAULT '',
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
    available_episode_count INTEGER,
    CHECK (`library_users_count` >= 0),
    CHECK (`tmdb_in_production` IS NULL OR `tmdb_in_production` IN (0, 1)),
    CHECK (`next_episode_season_number` IS NULL OR `next_episode_season_number` > 0),
    CHECK (`next_episode_number` IS NULL OR `next_episode_number` > 0),
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
    PRIMARY KEY (user_id),
    CHECK (`completed` IN (0, 1)),
    CHECK (`planned` IN (0, 1)),
    CHECK (`unfinished` IN (0, 1)),
    CHECK (`ongoing` IN (0, 1)),
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

-- Library-count and series-progress triggers are installed by migrations.
-- Atlas Community cannot represent SQLite triggers in a declarative schema.
