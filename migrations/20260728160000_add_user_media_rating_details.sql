CREATE TABLE user_media_rating_details (
    user_id       INTEGER NOT NULL,
    media_id      INTEGER NOT NULL,
    criterion     TEXT NOT NULL CHECK (criterion IN (
                      'acting', 'story', 'visuals', 'sound', 'overall',
                      'animation', 'characters'
                  )),
    score         INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, media_id, criterion),
    FOREIGN KEY (user_id, media_id)
        REFERENCES user_media (user_id, media_id) ON DELETE CASCADE
);
