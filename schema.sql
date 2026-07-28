CREATE TABLE media (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id             INTEGER,
    content_format      TEXT NOT NULL
                        CHECK (content_format IN ('full_length', 'series')),
    content_type        TEXT NOT NULL
                        CHECK (content_type IN ('movie', 'anime', 'cartoon')),
    title               TEXT NOT NULL,
    original_title      TEXT,
    description         TEXT,
    poster_path         TEXT,
    rating              REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
    release_date        TEXT,
    first_air_date      TEXT,
    number_of_seasons   INTEGER
                        CHECK (number_of_seasons IS NULL OR number_of_seasons >= 0),
    number_of_episodes  INTEGER
                        CHECK (number_of_episodes IS NULL OR number_of_episodes >= 0),
    library_users_count INTEGER NOT NULL DEFAULT 0
                        CHECK (library_users_count >= 0),
    tmdb_status         TEXT,
    tmdb_in_production  INTEGER CHECK (
                            tmdb_in_production IS NULL
                            OR tmdb_in_production IN (0, 1)
                        ),
    next_episode_air_date TEXT,
    next_episode_season_number INTEGER CHECK (
                            next_episode_season_number IS NULL
                            OR next_episode_season_number > 0
                        ),
    next_episode_number INTEGER CHECK (
                            next_episode_number IS NULL
                            OR next_episode_number > 0
                        ),
    tmdb_release_checked_at TEXT,
    status              TEXT,
    last_updated        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tmdb_id, content_format, content_type)
);

CREATE INDEX ix_media_status ON media (status);

CREATE TABLE user_media (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    status              TEXT NOT NULL
                        CHECK (status IN (
                            'planned', 'watching', 'completed', 'on_hold', 'dropped'
                        )),
    user_rating         INTEGER
                        CHECK (user_rating IS NULL OR user_rating BETWEEN 1 AND 10),
    episodes_watched    INTEGER
                        CHECK (episodes_watched IS NULL OR episodes_watched >= 0),
    last_watched_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_at            TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, media_id),
    FOREIGN KEY (media_id) REFERENCES media (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_media_media_id ON user_media (media_id);

-- Library count triggers are installed by
-- migrations/20260728120000_add_media_library_users_count.sql. Atlas Community
-- cannot currently represent SQLite triggers in a declarative schema.

CREATE TABLE user_season_progress (
    user_id             INTEGER NOT NULL,
    media_id            INTEGER NOT NULL,
    season_number       INTEGER NOT NULL
                        CHECK (season_number >= 0),
    episodes_watched    INTEGER NOT NULL
                        CHECK (episodes_watched >= 0),
    last_watched_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, media_id, season_number),
    FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id) ON DELETE CASCADE
);

CREATE INDEX ix_user_season_progress_media_id
    ON user_season_progress (media_id);

-- Series progress triggers are installed by
-- migrations/20260725130000_validate_series_progress.sql. Atlas Community
-- cannot currently represent SQLite triggers in a declarative schema.

CREATE TABLE user_library_filters (
    user_id             INTEGER,
    full_length         INTEGER NOT NULL DEFAULT 1 CHECK (full_length IN (0, 1)),
    series              INTEGER NOT NULL DEFAULT 1 CHECK (series IN (0, 1)),
    movie               INTEGER NOT NULL DEFAULT 1 CHECK (movie IN (0, 1)),
    anime               INTEGER NOT NULL DEFAULT 1 CHECK (anime IN (0, 1)),
    cartoon             INTEGER NOT NULL DEFAULT 1 CHECK (cartoon IN (0, 1)),
    completed           INTEGER NOT NULL DEFAULT 1 CHECK (completed IN (0, 1)),
    planned             INTEGER NOT NULL DEFAULT 1 CHECK (planned IN (0, 1)),
    PRIMARY KEY (user_id)
);
