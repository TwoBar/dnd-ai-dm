-- ============================================================
-- DYNAMIC FORMULA SYSTEM
-- Store D&D calculation formulas discovered via RAG
-- ============================================================

-- Formulas table: Stores executable calculation rules
CREATE TABLE IF NOT EXISTS formulas (
  formula_name TEXT PRIMARY KEY,     -- 'spell_save_dc', 'attack_bonus', 'carrying_capacity'
  formula TEXT NOT NULL,              -- '8 + proficiency_bonus + spellcasting_ability_mod'
  description TEXT,                   -- Human-readable explanation
  return_type TEXT DEFAULT 'int',    -- 'int', 'dice', 'bool'

  -- Metadata
  source TEXT DEFAULT 'rag',          -- 'rag', 'predefined', 'manual'
  rule_reference TEXT,                -- RAG search result that produced this formula
  confidence REAL DEFAULT 1.0,        -- Confidence in formula accuracy (0-1)
  usage_count INTEGER DEFAULT 0,      -- How many times used

  -- Validation
  requires_variables JSON,            -- ['proficiency_bonus', 'cha_mod']
  validated BOOLEAN DEFAULT 0,        -- Has been manually verified

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_formulas_source ON formulas(source);
CREATE INDEX IF NOT EXISTS idx_formulas_usage ON formulas(usage_count DESC);

-- Seed with core D&D 5e formulas
INSERT OR IGNORE INTO formulas (formula_name, formula, description, return_type, source, validated) VALUES
  ('ability_modifier', 'floor((ability_score - 10) / 2)', 'Calculate ability modifier from score', 'int', 'predefined', 1),
  ('proficiency_bonus', 'floor((level - 1) / 4) + 2', 'Proficiency bonus by level', 'int', 'predefined', 1),
  ('spell_save_dc', '8 + proficiency_bonus + spellcasting_ability_mod', 'Spell save DC', 'int', 'predefined', 1),
  ('spell_attack_bonus', 'proficiency_bonus + spellcasting_ability_mod', 'Spell attack bonus', 'int', 'predefined', 1),
  ('initiative', 'dex_mod', 'Initiative bonus', 'int', 'predefined', 1),
  ('passive_perception', '10 + wis_mod + (perception_proficient * proficiency_bonus) + (perception_expertise * proficiency_bonus)', 'Passive Perception', 'int', 'predefined', 1),
  ('ac_unarmored', '10 + dex_mod', 'AC when unarmored', 'int', 'predefined', 1),
  ('ac_unarmored_barbarian', '10 + dex_mod + con_mod', 'Barbarian unarmored AC', 'int', 'predefined', 1),
  ('ac_unarmored_monk', '10 + dex_mod + wis_mod', 'Monk unarmored AC', 'int', 'predefined', 1),
  ('carrying_capacity', 'str * 15', 'Carrying capacity in pounds', 'int', 'predefined', 1),
  ('melee_attack_bonus', 'proficiency_bonus + str_mod + magic_bonus', 'Melee weapon attack bonus', 'int', 'predefined', 1),
  ('ranged_attack_bonus', 'proficiency_bonus + dex_mod + magic_bonus', 'Ranged weapon attack bonus', 'int', 'predefined', 1),
  ('melee_damage', 'damage_die + str_mod + magic_bonus', 'Melee weapon damage', 'dice', 'predefined', 1),
  ('ranged_damage', 'damage_die + dex_mod + magic_bonus', 'Ranged weapon damage', 'dice', 'predefined', 1);
