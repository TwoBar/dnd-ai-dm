-- ============================================================
-- DYNAMIC FORMULA SYSTEM V2
-- Base formulas + conditional modifiers
-- ============================================================

-- Base formulas table: Core calculations
CREATE TABLE IF NOT EXISTS formulas (
  formula_name TEXT PRIMARY KEY,     -- 'spell_save_dc', 'attack_bonus'
  base_formula TEXT NOT NULL,        -- '8 + proficiency_bonus + spellcasting_ability_mod'
  description TEXT,
  return_type TEXT DEFAULT 'int',    -- 'int', 'dice', 'bool'

  -- Discovery metadata
  source TEXT DEFAULT 'predefined',  -- 'predefined', 'rag_discovered'
  rule_reference TEXT,               -- RAG search that discovered this
  discovered_at TIMESTAMP,

  -- Usage tracking
  usage_count INTEGER DEFAULT 0,
  last_used_at TIMESTAMP,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Active modifiers table: Dynamic bonuses/penalties per entity
CREATE TABLE IF NOT EXISTS active_modifiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,         -- Which character/monster

  -- What formula does this modify?
  applies_to TEXT NOT NULL,          -- 'spell_save_dc', 'attack_bonus', 'ac'

  -- Modifier details
  modifier_value INTEGER NOT NULL,   -- +2, -1, etc.
  modifier_type TEXT NOT NULL,       -- 'item', 'condition', 'feature', 'spell'

  -- Source
  source_name TEXT,                  -- 'Robe of the Archmagi', 'Poisoned', 'Bardic Inspiration'
  source_id TEXT,                    -- Reference to item/spell/feature

  -- Duration
  duration_type TEXT DEFAULT 'permanent', -- 'permanent', 'temporary', 'concentration'
  expires_at TIMESTAMP,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_active_modifiers_creature ON active_modifiers(creature_id);
CREATE INDEX IF NOT EXISTS idx_active_modifiers_applies ON active_modifiers(applies_to);

-- Formula aliases: Map natural language to formula names
CREATE TABLE IF NOT EXISTS formula_aliases (
  alias TEXT PRIMARY KEY,            -- 'save dc', 'to hit bonus', 'damage roll'
  formula_name TEXT NOT NULL,        -- 'spell_save_dc', 'attack_bonus', 'weapon_damage'

  FOREIGN KEY (formula_name) REFERENCES formulas(formula_name)
);

-- Seed base formulas
INSERT OR IGNORE INTO formulas (formula_name, base_formula, description, source) VALUES
  ('spell_save_dc', '8 + proficiency_bonus + spellcasting_ability_mod + spell_save_dc_bonus', 'Spell save DC', 'predefined'),
  ('spell_attack_bonus', 'proficiency_bonus + spellcasting_ability_mod + spell_attack_bonus', 'Spell attack bonus', 'predefined'),
  ('melee_attack_bonus', 'proficiency_bonus + str_mod + attack_bonus', 'Melee attack bonus', 'predefined'),
  ('ranged_attack_bonus', 'proficiency_bonus + dex_mod + attack_bonus', 'Ranged attack bonus', 'predefined'),
  ('ac', 'base_ac + dex_mod + shield_bonus + ac_bonus', 'Armor class', 'predefined'),
  ('initiative', 'dex_mod + initiative_bonus', 'Initiative', 'predefined'),
  ('passive_perception', '10 + wis_mod + (perception_proficient * proficiency_bonus) + (perception_expertise * proficiency_bonus) + passive_perception_bonus', 'Passive Perception', 'predefined');

-- Seed aliases for natural language lookup
INSERT OR IGNORE INTO formula_aliases (alias, formula_name) VALUES
  ('save dc', 'spell_save_dc'),
  ('spell dc', 'spell_save_dc'),
  ('to hit', 'melee_attack_bonus'),
  ('attack roll', 'melee_attack_bonus'),
  ('armor class', 'ac'),
  ('armor', 'ac');

-- Example: Bard with Robe of the Archmagi (+2 spell save DC)
-- INSERT INTO active_modifiers (creature_id, applies_to, modifier_value, modifier_type, source_name)
-- VALUES ('creature:lyra-id', 'spell_save_dc', 2, 'item', 'Robe of the Archmagi');

-- Example: Character poisoned (-2 to attack rolls)
-- INSERT INTO active_modifiers (creature_id, applies_to, modifier_value, modifier_type, source_name, duration_type, expires_at)
-- VALUES ('creature:lyra-id', 'melee_attack_bonus', -2, 'condition', 'Poisoned', 'temporary', datetime('now', '+1 hour'));
