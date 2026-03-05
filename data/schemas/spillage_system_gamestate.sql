-- ============================================================
-- SPILLAGE SYSTEM (Game State DB portion)
-- Tracks actual spillage events and container closure state
-- ============================================================

-- Add closure state to inventory (Game State DB)
ALTER TABLE creature_inventory ADD COLUMN is_closed BOOLEAN DEFAULT 1;

-- ============================================================
-- MOVEMENT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  creature_id TEXT NOT NULL,

  -- Movement type
  movement_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,

  -- Duration
  started_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP,
  hours_duration REAL,

  -- Spillage results
  containers_affected INTEGER DEFAULT 0,
  total_volume_spilled_ml REAL DEFAULT 0,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id)
);

CREATE INDEX IF NOT EXISTS idx_movement_log_creature ON movement_log(creature_id);
CREATE INDEX IF NOT EXISTS idx_movement_log_session ON movement_log(session_id);
