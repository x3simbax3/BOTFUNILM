CREATE TABLE media_search_terms (
    media_id integer NOT NULL,
    term text NOT NULL,
    PRIMARY KEY (media_id, term),
    CONSTRAINT media_search_terms_media
        FOREIGN KEY (media_id) REFERENCES media (id) ON DELETE CASCADE
);

CREATE INDEX ix_media_search_terms_term
    ON media_search_terms(term, media_id);
