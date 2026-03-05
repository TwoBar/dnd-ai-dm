-- ============================================================
-- FORMULA SYSTEM MIGRATION
-- Migrates database schema for dynamic formula system
-- ============================================================

-- ============================================================
-- PART 1: REFERENCE.DB (Universal Formulas)
-- ============================================================

-- Create formulas table
CREATE TABLE IF NOT EXISTS formulas (
  formula_name TEXT PRIMARY KEY,
  base_formula TEXT NOT NULL,
  description TEXT,
  return_type TEXT DEFAULT 'int',
  source TEXT DEFAULT 'predefined',
  rule_reference TEXT,
  discovered_at TIMESTAMP,
  usage_count INTEGER DEFAULT 0,
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create formula aliases table
CREATE TABLE IF NOT EXISTS formula_aliases (
  alias TEXT PRIMARY KEY,
  formula_name TEXT NOT NULL,
  FOREIGN KEY (formula_name) REFERENCES formulas(formula_name)
);

-- Seed 11 base formulas
INSERT OR REPLACE INTO formulas (formula_name, base_formula, description, source) VALUES
  ('ability_modifier', 'floor((ability_score - 10) / 2)', 'Ability modifier', 'predefined'),
  ('proficiency_bonus', 'floor((level - 1) / 4) + 2', 'Proficiency bonus', 'predefined'),
  ('spell_save_dc', '8 + proficiency_bonus + spellcasting_ability_mod', 'Spell save DC', 'predefined'),
  ('spell_attack_bonus', 'proficiency_bonus + spellcasting_ability_mod', 'Spell attack bonus', 'predefined'),
  ('weapon_attack_roll', '1d20 + ability_mod + (proficient * proficiency_bonus)', 'Weapon attack roll', 'predefined'),
  ('weapon_damage', 'weapon_dice + ability_mod', 'Weapon damage', 'predefined'),
  ('initiative', '1d20 + dex_mod', 'Initiative', 'predefined'),
  ('ability_check', '1d20 + ability_mod + (proficient * proficiency_bonus)', 'Ability check', 'predefined'),
  ('saving_throw', '1d20 + ability_mod + (proficient * proficiency_bonus)', 'Saving throw', 'predefined'),
  ('passive_check', '10 + ability_mod + (proficient * proficiency_bonus)', 'Passive check', 'predefined'),
  ('armor_class', 'base_ac + dex_mod + shield_bonus', 'Armor class', 'predefined');

-- Seed formula aliases for natural language lookup
INSERT OR REPLACE INTO formula_aliases (alias, formula_name) VALUES
  ('save dc', 'spell_save_dc'),
  ('spell dc', 'spell_save_dc'),
  ('to hit', 'weapon_attack_roll'),
  ('attack roll', 'weapon_attack_roll'),
  ('armor class', 'armor_class'),
  ('armor', 'armor_class'),
  ('ac', 'armor_class'),
  ('initiative roll', 'initiative');
