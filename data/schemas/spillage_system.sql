-- ============================================================
-- SPILLAGE SYSTEM
-- Movement-based spillage for non-secure containers
-- ============================================================

-- Add spillage fields to container_types
ALTER TABLE container_types ADD COLUMN security_level INTEGER DEFAULT 3;
  -- 0: Open (bowl, plate) - Spills easily
  -- 1: Semi-open (cup, mug) - Spills when moving
  -- 2: Closeable (bottle with cork) - Low spillage when closed
  -- 3: Sealed (waterskin, flask) - Minimal spillage
  -- 4: Watertight (metal flask, magic) - No spillage

ALTER TABLE container_types ADD COLUMN can_be_closed BOOLEAN DEFAULT 1;
ALTER TABLE container_types ADD COLUMN spillage_rate_multiplier REAL DEFAULT 1.0;
  -- Base spillage rate (percentage per hour at walking speed)

-- Add closure state to inventory
ALTER TABLE creature_inventory ADD COLUMN is_closed BOOLEAN DEFAULT 1;
  -- Whether lid/cork is currently on


-- ============================================================
-- MOVEMENT INTENSITIES
-- Defines spillage multipliers for different movement types
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_intensities (
  movement_type TEXT PRIMARY KEY,
  intensity INTEGER NOT NULL,     -- 0-5 scale
  spillage_multiplier REAL NOT NULL,
  description TEXT
);

INSERT INTO movement_intensities (movement_type, intensity, spillage_multiplier, description) VALUES
  ('idle', 0, 0.0, 'Standing still, resting - no spillage'),
  ('walking', 1, 1.0, 'Normal travel pace'),
  ('running', 2, 3.0, 'Quick movement, dashing'),
  ('combat', 3, 5.0, 'Fighting, dodging, intense action'),
  ('climbing', 4, 8.0, 'Climbing, swimming, acrobatics'),
  ('falling', 5, 100.0, 'Falling, tumbling - everything spills instantly!');


-- ============================================================
-- MOVEMENT LOG (Optional - for tracking)
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
  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  FOREIGN KEY (movement_type) REFERENCES movement_intensities(movement_type)
);

CREATE INDEX IF NOT EXISTS idx_movement_log_creature ON movement_log(creature_id);
CREATE INDEX IF NOT EXISTS idx_movement_log_session ON movement_log(session_id);


-- ============================================================
-- Update container_types to allow powders in liquid containers
-- ============================================================

-- Note: Already handled in material_properties.compatible_containers JSON
-- Just ensure container_types properly set can_hold_powder for liquid containers
