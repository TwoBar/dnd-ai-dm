-- ============================================================
-- REFERENCE DATABASE SCHEMA
-- ============================================================
-- This database contains templates and definitions for D&D 5E entities.
-- It's shared across all game sessions and expandable via AI generation.
-- Think of it as the "Monster Manual + PHB + DMG" in database form.
--
-- Database: reference.db
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- CLASSES (Bard, Paladin, Fighter, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS classes (
  id TEXT PRIMARY KEY,              -- 'class:bard', 'class:paladin'
  name TEXT NOT NULL UNIQUE,

  -- Core Properties
  hit_die INTEGER NOT NULL,         -- 6, 8, 10, 12
  primary_ability TEXT,             -- 'str', 'dex', 'cha', etc.

  -- Saving Throw Proficiencies
  saving_throw_proficiencies JSON,  -- ["dex", "cha"]

  -- Proficiencies
  armor_proficiencies JSON,         -- ["light", "medium", "shields"]
  weapon_proficiencies JSON,        -- ["simple", "martial"]
  skill_proficiencies JSON,         -- {"choose": 2, "from": ["persuasion", "performance", ...]}
  tool_proficiencies JSON,          -- {"choose": 3, "from": ["any"]}

  -- Spellcasting
  is_spellcaster BOOLEAN DEFAULT 0,
  spellcasting_ability TEXT,        -- 'int', 'wis', 'cha'
  spell_slots_by_level JSON,        -- {"1": [0,2,3,3], "2": [0,0,2,3], ...} indexed by char level
  cantrips_known_by_level JSON,     -- {"1": 2, "4": 3, "10": 4}
  spells_known_by_level JSON,       -- {"1": 4, "2": 5, "3": 6} (for known casters)
  ritual_casting BOOLEAN DEFAULT 0,
  spellcasting_type TEXT,           -- 'known', 'prepared', 'none'

  -- Multiclass Spellcasting (for spell slot calculation)
  spellcasting_progression TEXT,    -- 'full', 'half', 'third', 'pact-magic', 'none'
  caster_level_multiplier REAL,     -- 1.0 (full), 0.5 (half), 0.33 (third), 0 (none/pact-magic)

  -- Starting Equipment
  starting_equipment JSON,          -- [{"choose": 1, "from": ["item:rapier", "item:longsword"]}, ...]
  starting_wealth_dice TEXT,        -- '5d4 x 10'

  -- Class Resource Template
  class_resource_template JSON,     -- {"bardic_inspiration": {"die_progression": {"1": "d6", "5": "d8"}}}

  -- Multiclassing
  multiclass_prerequisites JSON,    -- {"cha": 13}
  multiclass_proficiencies JSON,    -- {"armor": ["light"], "weapons": [...]}

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);

-- ============================================================
-- CLASS_PROGRESSION (Level-by-level progression for each class)
-- ============================================================
CREATE TABLE IF NOT EXISTS class_progression (
  id TEXT PRIMARY KEY,              -- 'progression:bard:1', 'progression:paladin:5'
  class_id TEXT NOT NULL,
  level INTEGER NOT NULL,           -- Class level (1-20)

  -- Hit Points
  hit_points_formula TEXT,          -- 'hit_die' (first level max) or 'hit_die + con_mod'

  -- Features Gained at This Level
  features_gained JSON,             -- [{"id": "feature:bardic-inspiration", "name": "Bardic Inspiration (d6)"}]

  -- Spell Progression (for spellcasters)
  cantrips_known INTEGER,
  spells_known INTEGER,             -- For known casters (Bard, Sorcerer, Ranger, Warlock)
  spell_slots JSON,                 -- {"1": 2, "2": 0} - slots at THIS class level (single-class)

  -- Class Resources at This Level
  class_resources JSON,             -- {"bardic_inspiration": {"die": "d6", "uses": "cha_mod"}}

  -- Character Advancement
  grants_asi BOOLEAN DEFAULT 0,     -- Does this level grant Ability Score Improvement?
  grants_subclass_choice BOOLEAN DEFAULT 0,  -- Does this level grant subclass selection?
  subclass_feature_id TEXT,         -- Feature ID from subclass (if applicable)

  -- Source
  source_book TEXT,
  page INTEGER,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(class_id, level),
  FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE INDEX IF NOT EXISTS idx_class_progression_class ON class_progression(class_id);
CREATE INDEX IF NOT EXISTS idx_class_progression_level ON class_progression(class_id, level);

-- ============================================================
-- SUBCLASSES (Oath of Devotion, College of Lore, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS subclasses (
  id TEXT PRIMARY KEY,              -- 'subclass:oath-of-devotion'
  class_id TEXT NOT NULL,
  name TEXT NOT NULL,

  -- When Available
  available_at_level INTEGER DEFAULT 3,

  -- Description
  description TEXT,

  -- Subclass Features (by level)
  features JSON,                    -- [{"level": 3, "feature_id": "feature:sacred-weapon"}, ...]

  -- Additional Spell Lists (for some subclasses)
  bonus_spells JSON,                -- {"3": ["spell:protection-from-evil"], "5": ["spell:aid"]}

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE INDEX IF NOT EXISTS idx_subclasses_class ON subclasses(class_id);
CREATE INDEX IF NOT EXISTS idx_subclasses_name ON subclasses(name);

-- ============================================================
-- RACES (Human, Elf, Tiefling, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS races (
  id TEXT PRIMARY KEY,              -- 'race:human', 'race:elf'
  name TEXT NOT NULL UNIQUE,

  -- Physical Properties
  size TEXT DEFAULT 'Medium',       -- Tiny, Small, Medium, Large
  base_speed INTEGER DEFAULT 30,

  -- Ability Score Increases
  ability_score_increases JSON,     -- {"cha": 2, "int": 1} or {"choose": 2, "from": ["str", "dex", ...]}

  -- Racial Traits
  traits JSON,                      -- [{"name": "Darkvision", "description": "..."}]

  -- Proficiencies
  skill_proficiencies JSON,
  weapon_proficiencies JSON,
  tool_proficiencies JSON,
  languages JSON,                   -- ["Common", "Infernal"] or {"choose": 1, "from": [...]}

  -- Subraces
  has_subraces BOOLEAN DEFAULT 0,

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_races_name ON races(name);

-- ============================================================
-- SUBRACES (High Elf, Mountain Dwarf, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS subraces (
  id TEXT PRIMARY KEY,              -- 'subrace:high-elf'
  race_id TEXT NOT NULL,
  name TEXT NOT NULL,

  -- Additional Ability Score Increases
  ability_score_increases JSON,

  -- Additional Traits
  traits JSON,

  -- Additional Proficiencies
  skill_proficiencies JSON,
  weapon_proficiencies JSON,
  tool_proficiencies JSON,
  languages JSON,

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (race_id) REFERENCES races(id)
);

CREATE INDEX IF NOT EXISTS idx_subraces_race ON subraces(race_id);

-- ============================================================
-- BACKGROUNDS (Charlatan, Soldier, Acolyte, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS backgrounds (
  id TEXT PRIMARY KEY,              -- 'background:charlatan'
  name TEXT NOT NULL UNIQUE,

  -- Proficiencies
  skill_proficiencies JSON,         -- ["deception", "sleight-of-hand"]
  tool_proficiencies JSON,
  languages JSON,                   -- {"choose": 2, "from": ["any"]}

  -- Equipment
  starting_equipment JSON,
  starting_wealth INTEGER,          -- In GP

  -- Feature
  feature_name TEXT,
  feature_description TEXT,

  -- Personality Options
  personality_traits JSON,          -- Array of trait options
  ideals JSON,
  bonds JSON,
  flaws JSON,

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backgrounds_name ON backgrounds(name);

-- ============================================================
-- SPELLS (Fireball, Healing Word, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS spells (
  id TEXT PRIMARY KEY,              -- 'spell:fireball'
  name TEXT NOT NULL UNIQUE,
  level INTEGER NOT NULL,           -- 0-9 (0 = cantrip)
  school TEXT NOT NULL,             -- Evocation, Abjuration, Conjuration, etc.

  -- Casting
  casting_time TEXT,                -- '1 action', '1 bonus action', '1 reaction'
  range_value INTEGER,              -- 60, 120, etc.
  range_type TEXT,                  -- 'self', 'touch', 'feet', 'sight', 'unlimited'
  components JSON,                  -- {"v": true, "s": true, "m": "a bit of fleece"}
  duration TEXT,                    -- 'Instantaneous', '1 minute', 'Concentration, up to 10 minutes'
  concentration BOOLEAN DEFAULT 0,
  ritual BOOLEAN DEFAULT 0,

  -- Description
  description TEXT,
  higher_levels TEXT,               -- Upcast scaling description

  -- Effects
  damage_dice TEXT,                 -- '8d6'
  damage_type TEXT,                 -- 'fire', 'cold', 'lightning', etc.
  healing_dice TEXT,                -- '1d8'
  save_type TEXT,                   -- 'dex', 'con', 'wis', etc.
  attack_type TEXT,                 -- 'melee', 'ranged', null

  -- Effect Formulas (text formulas to be parsed)
  damage_formula TEXT,              -- '8d6 + spellcasting_ability_mod'
  healing_formula TEXT,             -- '1d8 + spellcasting_ability_mod'
  save_dc_formula TEXT,             -- '8 + proficiency_bonus + spellcasting_ability_mod'
  attack_bonus_formula TEXT,        -- 'proficiency_bonus + spellcasting_ability_mod'

  -- Upcast Scaling
  upcast_scaling JSON,              -- {"damage_per_level": "1d6", "targets_per_level": 1}

  -- Availability
  available_to_classes JSON,        -- ["wizard", "sorcerer", "bard"]

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_spells_name ON spells(name);
CREATE INDEX IF NOT EXISTS idx_spells_level ON spells(level);
CREATE INDEX IF NOT EXISTS idx_spells_school ON spells(school);

-- ============================================================
-- ITEMS (Longsword, Leather Armor, Potion of Healing, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,              -- 'item:longsword', 'item:potion-of-healing'
  name TEXT NOT NULL,
  type TEXT NOT NULL,               -- 'weapon', 'armor', 'gear', 'magic-item', 'consumable'
  subtype TEXT,                     -- 'melee-weapon', 'light-armor', 'potion', etc.

  -- Physical Properties
  weight REAL,                      -- In pounds
  value INTEGER,                    -- In copper pieces (1 GP = 100 CP)
  rarity TEXT,                      -- 'common', 'uncommon', 'rare', 'very-rare', 'legendary', 'artifact'

  -- Description
  description TEXT,

  -- Magic Item Properties
  requires_attunement BOOLEAN DEFAULT 0,
  attunement_requirements TEXT,     -- 'by a spellcaster', 'by a bard'
  charges INTEGER,                  -- Max charges
  recharge_mechanism TEXT,          -- 'dawn', '1d6+4 at dawn'

  -- Weapon Properties
  weapon_properties JSON,           -- {"damage": "1d8", "damage_type": "slashing", "properties": ["versatile"], "versatile_damage": "1d10"}

  -- Armor Properties
  armor_properties JSON,            -- {"ac_base": 11, "ac_bonus": "dex", "max_dex": 2, "type": "light", "stealth_disadvantage": false}

  -- Magical Effects
  magical_effects JSON,             -- [{"type": "bonus", "applies_to": "ac", "value": 1}]

  -- Consumable Properties
  consumable_properties JSON,       -- {"healing": "2d4+2", "effects": [...]}

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
CREATE INDEX IF NOT EXISTS idx_items_rarity ON items(rarity);

-- ============================================================
-- MONSTER TEMPLATES (Goblin, Ancient Red Dragon, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS monster_templates (
  id TEXT PRIMARY KEY,              -- 'monster:goblin', 'monster:ancient-red-dragon'
  name TEXT NOT NULL,

  -- Classification
  size TEXT,                        -- Tiny, Small, Medium, Large, Huge, Gargantuan
  type TEXT,                        -- Beast, Humanoid, Dragon, Undead, Fiend, etc.
  subtype TEXT,                     -- Goblinoid, Shapechanger, etc.
  alignment TEXT,

  -- Defenses
  ac INTEGER,
  ac_formula TEXT,                  -- 'natural armor', '13 + dex_mod'
  hp_dice TEXT,                     -- '2d6+2'
  hp_average INTEGER,

  -- Movement
  speed JSON,                       -- {"walk": 30, "fly": 60, "swim": 30}

  -- Ability Scores
  str INTEGER,
  dex INTEGER,
  con INTEGER,
  int INTEGER,
  wis INTEGER,
  cha INTEGER,

  -- Combat Stats
  cr REAL,                          -- Challenge Rating
  proficiency_bonus INTEGER,
  xp INTEGER,

  -- Proficiencies
  saving_throws JSON,               -- {"dex": 4, "wis": 2}
  skills JSON,                      -- {"stealth": 6, "perception": 3}

  -- Resistances/Immunities
  damage_vulnerabilities JSON,      -- ["fire", "cold"]
  damage_resistances JSON,
  damage_immunities JSON,
  condition_immunities JSON,

  -- Senses
  senses JSON,                      -- {"darkvision": 60, "passive_perception": 13}
  languages JSON,                   -- ["Common", "Goblin"]

  -- Abilities
  traits JSON,                      -- [{"name": "Pack Tactics", "description": "..."}]
  actions JSON,                     -- [{"name": "Bite", "attack_bonus": 4, "damage": "1d6+2", "damage_type": "piercing"}]
  reactions JSON,
  legendary_actions JSON,
  legendary_actions_per_round INTEGER,
  lair_actions JSON,

  -- Spellcasting
  spellcasting JSON,                -- {"ability": "cha", "dc": 15, "bonus": 7, "spells": {...}}

  -- Loot
  loot_table JSON,                  -- {"coins": "3d6 GP", "items": ["item:shortsword"]}

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monster_templates_name ON monster_templates(name);
CREATE INDEX IF NOT EXISTS idx_monster_templates_cr ON monster_templates(cr);
CREATE INDEX IF NOT EXISTS idx_monster_templates_type ON monster_templates(type);

-- ============================================================
-- CLASS FEATURES (Bardic Inspiration, Lay on Hands, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS class_features (
  id TEXT PRIMARY KEY,              -- 'feature:bardic-inspiration'
  class_id TEXT NOT NULL,
  name TEXT NOT NULL,
  level_required INTEGER,

  -- Description
  description TEXT,

  -- Mechanics
  feature_type TEXT,                -- 'passive', 'active', 'resource'
  activation TEXT,                  -- 'action', 'bonus-action', 'reaction', 'free', 'passive'

  -- Resource Usage
  uses_per_rest TEXT,               -- 'short', 'long', 'none'
  uses_formula TEXT,                -- 'cha_mod', 'proficiency_bonus', '3', 'level'

  -- Effects
  effects JSON,                     -- [{"type": "bonus", "applies_to": "damage", "value": "1d6"}]

  -- Source
  source_book TEXT,
  page INTEGER,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE INDEX IF NOT EXISTS idx_class_features_class ON class_features(class_id);
CREATE INDEX IF NOT EXISTS idx_class_features_level ON class_features(level_required);

-- ============================================================
-- CONDITIONS (Poisoned, Frightened, Paralyzed, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS conditions (
  id TEXT PRIMARY KEY,              -- 'condition:poisoned'
  name TEXT NOT NULL UNIQUE,

  -- Description
  description TEXT,

  -- Mechanical Effects
  effects JSON,                     -- {"disadvantage": ["attack", "ability-check"], "speed": 0, "automatic_fail": ["str-save", "dex-save"]}

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conditions_name ON conditions(name);

-- ============================================================
-- DAMAGE TYPES
-- ============================================================
CREATE TABLE IF NOT EXISTS damage_types (
  id TEXT PRIMARY KEY,              -- 'damage:fire'
  name TEXT NOT NULL UNIQUE,        -- Fire, Cold, Lightning, etc.
  description TEXT,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- SKILLS
-- ============================================================
CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,              -- 'skill:persuasion'
  name TEXT NOT NULL UNIQUE,
  ability TEXT NOT NULL,            -- 'str', 'dex', 'cha', etc.
  description TEXT,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- FEATS (Optional rule - PHB p165)
-- ============================================================
CREATE TABLE IF NOT EXISTS feats (
  id TEXT PRIMARY KEY,              -- 'feat:lucky'
  name TEXT NOT NULL UNIQUE,

  -- Prerequisites
  prerequisites JSON,               -- {"min_ability_scores": {"str": 13}, "required_proficiencies": [...]}

  -- Description
  description TEXT,

  -- Benefits
  ability_score_increases JSON,    -- {"choose": 1, "from": ["str", "dex"], "amount": 1}
  granted_proficiencies JSON,
  effects JSON,

  -- Source
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feats_name ON feats(name);

-- ============================================================
-- FORMULA DEFINITIONS (For parsing text formulas)
-- ============================================================
-- This table helps the formula parser understand variables
CREATE TABLE IF NOT EXISTS formula_variables (
  variable_name TEXT PRIMARY KEY,  -- 'proficiency_bonus', 'cha_mod', 'level'
  description TEXT,
  variable_type TEXT,               -- 'ability_mod', 'stat', 'computed'
  source TEXT,                      -- Where this variable comes from

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Populate standard variables
INSERT OR IGNORE INTO formula_variables (variable_name, description, variable_type, source) VALUES
  ('str_mod', 'Strength modifier', 'ability_mod', 'creatures.str'),
  ('dex_mod', 'Dexterity modifier', 'ability_mod', 'creatures.dex'),
  ('con_mod', 'Constitution modifier', 'ability_mod', 'creatures.con'),
  ('int_mod', 'Intelligence modifier', 'ability_mod', 'creatures.int'),
  ('wis_mod', 'Wisdom modifier', 'ability_mod', 'creatures.wis'),
  ('cha_mod', 'Charisma modifier', 'ability_mod', 'creatures.cha'),
  ('proficiency_bonus', 'Proficiency bonus', 'computed', 'floor((level - 1) / 4) + 2'),
  ('level', 'Character level', 'stat', 'characters.level'),
  ('spellcasting_ability_mod', 'Spellcasting ability modifier', 'computed', 'Based on class'),
  ('spell_attack_bonus', 'Spell attack bonus', 'computed', 'proficiency_bonus + spellcasting_ability_mod'),
  ('spell_save_dc', 'Spell save DC', 'computed', '8 + proficiency_bonus + spellcasting_ability_mod');

-- ============================================================
-- METADATA
-- ============================================================
CREATE TABLE IF NOT EXISTS reference_metadata (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO reference_metadata (key, value) VALUES
  ('schema_version', '1.0.0'),
  ('created_at', datetime('now')),
  ('description', 'D&D 5E Reference Database - Templates and Definitions');
-- ============================================================
-- MATERIAL STATE SYSTEM
-- Handles physical states, container compatibility, and material properties
-- ============================================================

-- ============================================================
-- MATERIAL PROPERTIES (Physical states of contents)
-- ============================================================
CREATE TABLE IF NOT EXISTS material_properties (
  id TEXT PRIMARY KEY,              -- 'content:water', 'content:lava', 'content:ice'
  name TEXT NOT NULL,

  -- Physical State
  matter_state TEXT NOT NULL,       -- 'solid', 'liquid', 'gas', 'powder', 'plasma'

  -- Temperature (Celsius)
  base_temperature REAL,            -- Default temp (20°C for room temp water)
  min_stable_temp REAL,             -- Below this: state change (0°C water → ice)
  max_stable_temp REAL,             -- Above this: state change (100°C water → steam)
  state_change_to_cold TEXT,        -- Transform when too cold
  state_change_to_hot TEXT,         -- Transform when too hot

  -- Chemical Properties
  ph_level REAL DEFAULT 7.0,        -- 0-14 (7 = neutral, <7 acid, >7 base)
  salinity_ppm INTEGER DEFAULT 0,   -- Parts per million (ocean = 35000)

  -- Physical Properties
  flammable BOOLEAN DEFAULT 0,
  currently_burning BOOLEAN DEFAULT 0,
  toxic BOOLEAN DEFAULT 0,
  radioactive BOOLEAN DEFAULT 0,
  explosive BOOLEAN DEFAULT 0,

  -- Collection Requirements
  requires_container TEXT,          -- 'liquid', 'powder', 'gas', NULL (can hold with hands)
  compatible_containers JSON,       -- ["container_type:liquid", "container_type:watertight"]
  collection_tool TEXT,             -- 'tool:shovel', 'tool:tongs', NULL

  -- Content Properties (for liquids/powders)
  content_weight_per_ml REAL,       -- 0.001 kg/ml for water (1g/ml)
  serving_size_ml INTEGER,          -- 330ml per serving for MEDIUM creatures

  -- Time-Based Changes
  decays_over_time BOOLEAN DEFAULT 0,
  decay_rate_per_hour REAL,         -- Temperature change per hour (°C/hour)
  evaporation_rate_per_hour REAL,   -- Volume loss per hour (% per hour)
  decay_transforms_to TEXT,         -- What it becomes (ice → water, hot_water → water)

  -- Effects (links to effect_templates)
  effects JSON,                     -- [{"effect_id": "effect:restore_thirst", "multiplier": 1.0}]

  -- Source
  description TEXT,
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (state_change_to_cold) REFERENCES material_properties(id),
  FOREIGN KEY (state_change_to_hot) REFERENCES material_properties(id),
  FOREIGN KEY (decay_transforms_to) REFERENCES material_properties(id),
  FOREIGN KEY (collection_tool) REFERENCES tools(id)
);

CREATE INDEX IF NOT EXISTS idx_material_matter_state ON material_properties(matter_state);
CREATE INDEX IF NOT EXISTS idx_material_requires_container ON material_properties(requires_container);


-- ============================================================
-- CONTAINER TYPES (Capabilities of containers)
-- ============================================================
CREATE TABLE IF NOT EXISTS container_types (
  id TEXT PRIMARY KEY,              -- 'container_type:watertight', 'container_type:solid'
  name TEXT NOT NULL,

  -- What states of matter can it hold?
  can_hold_solid BOOLEAN DEFAULT 1,
  can_hold_liquid BOOLEAN DEFAULT 0,
  can_hold_gas BOOLEAN DEFAULT 0,
  can_hold_powder BOOLEAN DEFAULT 0,

  -- Physical constraints
  is_watertight BOOLEAN DEFAULT 0,
  is_airtight BOOLEAN DEFAULT 0,
  is_fireproof BOOLEAN DEFAULT 0,
  is_shatterproof BOOLEAN DEFAULT 0,

  -- Temperature limits
  max_temperature REAL,             -- 100°C for leather waterskin (will melt/burn)
  min_temperature REAL,             -- -20°C for glass bottle (will crack)

  -- Chemical resistance
  acid_resistant BOOLEAN DEFAULT 0,
  corrosive_resistant BOOLEAN DEFAULT 0,

  description TEXT,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- TOOLS (Required for collecting certain materials)
-- ============================================================
CREATE TABLE IF NOT EXISTS tools (
  id TEXT PRIMARY KEY,              -- 'tool:shovel', 'tool:tongs', 'tool:fireproof-bucket'
  name TEXT NOT NULL,
  tool_type TEXT,                   -- 'digging', 'grabbing', 'liquid_collection'

  -- What can this tool collect/handle?
  can_collect_solids BOOLEAN DEFAULT 0,
  can_collect_liquids BOOLEAN DEFAULT 0,
  can_collect_powders BOOLEAN DEFAULT 0,
  can_collect_gases BOOLEAN DEFAULT 0,

  -- Safety features
  heat_resistant BOOLEAN DEFAULT 0,      -- Can handle hot items (>100°C)
  cold_resistant BOOLEAN DEFAULT 0,      -- Can handle frozen items (<0°C)
  acid_resistant BOOLEAN DEFAULT 0,      -- Can handle acidic materials
  allows_distance BOOLEAN DEFAULT 0,     -- Tongs, poles keep you at safe distance

  -- Usage
  requires_two_hands BOOLEAN DEFAULT 0,
  requires_proficiency BOOLEAN DEFAULT 0,

  -- Item reference (if tool is also an inventory item)
  item_id TEXT,                     -- FK to items table

  description TEXT,
  source_book TEXT,
  page INTEGER,
  srd BOOLEAN DEFAULT 1,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (item_id) REFERENCES items(id)
);


-- ============================================================
-- SIZE MULTIPLIERS (Serving size by creature size)
-- ============================================================
CREATE TABLE IF NOT EXISTS size_multipliers (
  size TEXT PRIMARY KEY,            -- 'tiny', 'small', 'medium', 'large', 'huge', 'gargantuan'
  serving_multiplier REAL,          -- Relative to medium (1.0)
  weight_kg INTEGER,                -- Average weight
  space_feet INTEGER,               -- Space occupied

  -- Consumption rates
  food_per_day_multiplier REAL,     -- Relative to medium (1.0 = 1 lb food/day)
  water_per_day_multiplier REAL     -- Relative to medium (1.0 = 1 gallon/day)
);

-- Populate size multipliers
INSERT INTO size_multipliers (size, serving_multiplier, weight_kg, space_feet, food_per_day_multiplier, water_per_day_multiplier) VALUES
  ('tiny', 0.25, 1, 2.5, 0.25, 0.25),
  ('small', 0.5, 30, 5, 0.5, 0.5),
  ('medium', 1.0, 80, 5, 1.0, 1.0),
  ('large', 2.0, 250, 10, 2.0, 2.0),
  ('huge', 4.0, 2000, 15, 4.0, 4.0),
  ('gargantuan', 8.0, 16000, 20, 8.0, 8.0);


-- ============================================================
-- EFFECT TEMPLATES (Universal effect templates)
-- ============================================================
CREATE TABLE IF NOT EXISTS effect_templates (
  id TEXT PRIMARY KEY,              -- 'effect:restore_thirst', 'effect:restore_hp'
  name TEXT NOT NULL,
  effect_category TEXT NOT NULL,    -- 'restoration', 'damage', 'buff', 'debuff'

  -- Base Values (can be overridden by items/materials)
  base_value INTEGER DEFAULT 1,     -- Base amount (1 hour of thirst quenched, 1 HP, etc.)
  scales_with TEXT,                 -- 'character_level', 'proficiency_bonus', 'creature_size', NULL

  -- Target Resource
  affects_resource TEXT,            -- 'thirst', 'hunger', 'hp', 'spell_slots', 'exhaustion'

  -- Application Type
  instantaneous BOOLEAN DEFAULT 1,
  duration_minutes INTEGER,

  description TEXT,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Populate base effect templates
INSERT INTO effect_templates (id, name, effect_category, base_value, scales_with, affects_resource, instantaneous, description) VALUES
  ('effect:restore_thirst', 'Restore Thirst', 'restoration', 1, 'creature_size', 'thirst', 1, 'Quenches thirst for N hours'),
  ('effect:restore_hunger', 'Restore Hunger', 'restoration', 1, 'creature_size', 'hunger', 1, 'Satisfies hunger for N hours'),
  ('effect:restore_hp', 'Restore Hit Points', 'restoration', 1, NULL, 'hp', 1, 'Heals damage'),
  ('effect:restore_spell_slot', 'Restore Spell Slot', 'restoration', 1, NULL, 'spell_slots', 1, 'Restores expended spell slot'),
  ('effect:damage', 'Damage', 'damage', 1, NULL, 'hp', 1, 'Deals damage'),
  ('effect:buff', 'Buff', 'buff', 1, NULL, 'ability_score', 0, 'Temporary bonus to ability'),
  ('effect:remove_exhaustion', 'Remove Exhaustion', 'restoration', 1, NULL, 'exhaustion', 1, 'Removes exhaustion level');
-- ============================================================
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
