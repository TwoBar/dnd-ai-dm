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
