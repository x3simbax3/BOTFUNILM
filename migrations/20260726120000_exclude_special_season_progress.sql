-- Keep legacy season 0 rows readable so the application can ignore and replace
-- them, but reject new progress for TMDB specials at the database boundary.
CREATE TRIGGER `reject_special_season_progress_insert`
BEFORE INSERT ON `user_season_progress`
WHEN NEW.`season_number` = 0
BEGIN
  SELECT RAISE(ABORT, 'season 0 specials are excluded from progress');
END;

CREATE TRIGGER `reject_special_season_progress_update`
BEFORE UPDATE ON `user_season_progress`
WHEN NEW.`season_number` = 0
BEGIN
  SELECT RAISE(ABORT, 'season 0 specials are excluded from progress');
END;
