-- ============================================================
-- SPILLAGE SYSTEM (Reference DB portion)
-- Movement intensities and base container security definitions
-- ============================================================

-- Add spillage fields to container_types (Reference DB)
ALTER TABLE container_types ADD COLUMN security_level INTEGER DEFAULT 3;
ALTER TABLE container_types ADD COLUMN can_be_closed BOOLEAN DEFAULT 1;
ALTER TABLE container_types ADD COLUMN spillage_rate_multiplier REAL DEFAULT 1.0;

-- ============================================================
-- MOVEMENT INTENSITIES
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_intensities (
  movement_type TEXT PRIMARY KEY,
  intensity INTEGER NOT NULL,
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
