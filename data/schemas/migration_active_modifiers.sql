-- ============================================================
-- ACTIVE MODIFIERS MIGRATION
-- Recreates active_modifiers table with correct schema
-- ============================================================

-- Drop existing table (data loss acceptable per user)
DROP TABLE IF EXISTS active_modifiers;

-- Create new active_modifiers table with correct schema
CREATE TABLE active_modifiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,

  -- What formula does this modify?
  applies_to TEXT NOT NULL,          -- 'spell_save_dc', 'melee_attack_bonus', 'all_saving_throws'

  -- Modifier details
  modifier_type TEXT NOT NULL,       -- 'flat', 'dice', 'advantage', 'disadvantage', 'multiplier'
  modifier_value TEXT NOT NULL,      -- '2', '1d4', 'true', '2.0'

  -- Source tracking
  source_name TEXT,                  -- 'Robe of the Archmagi', 'Bless', 'Poisoned'
  source_id TEXT,                    -- 'item:robe-id', 'spell:bless-id', 'condition:poisoned'

  -- Duration management
  duration_type TEXT DEFAULT 'permanent',  -- 'permanent', 'temporary', 'concentration', 'rounds'
  expires_at TIMESTAMP,
  duration_rounds INTEGER,
  rounds_remaining INTEGER,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_active_modifiers_creature ON active_modifiers(creature_id);
CREATE INDEX idx_active_modifiers_applies ON active_modifiers(applies_to);
CREATE INDEX idx_active_modifiers_source ON active_modifiers(source_id);
