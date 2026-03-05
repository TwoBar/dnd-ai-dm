-- ============================================================
-- WEARABLE SYSTEM (Reference DB portion)
-- Equipment slots, body types, and item wearable properties
-- ============================================================

-- ============================================================
-- BODY TYPES
-- Different anatomical configurations
-- ============================================================
CREATE TABLE IF NOT EXISTS body_types (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  base_slot_count INTEGER DEFAULT 20,
  notes TEXT
);

INSERT INTO body_types (id, name, description, notes) VALUES
  ('humanoid', 'Humanoid', 'Two arms, two legs, upright posture', 'Standard human-like anatomy'),
  ('quadruped', 'Quadruped', 'Four legs, animal-like', 'Horses, dogs, etc.'),
  ('avian', 'Avian', 'Two legs, two wings', 'Birds, some dragons'),
  ('serpentine', 'Serpentine', 'No limbs, snake-like', 'Snakes, some aberrations'),
  ('arachnid', 'Arachnid', 'Eight legs, spider-like', 'Spiders, driders'),
  ('aberrant', 'Aberrant', 'Unusual anatomy', 'Beholders, oozes, etc.');

-- ============================================================
-- EQUIPMENT SLOTS
-- All possible equipment slots with properties
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment_slots (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slot_category TEXT NOT NULL,  -- 'clothing', 'jewelry', 'held', 'carried'
  body_part TEXT,               -- 'head', 'torso', 'legs', 'feet', 'hands', 'ears', 'neck', 'finger', 'waist', 'back'

  -- Layering system
  layer_level INTEGER DEFAULT 1,  -- 1=innermost (underwear), 5=outermost (cloak)

  -- Conflicts with other slots
  conflicts_with JSON,  -- Array of slot IDs that conflict

  -- Properties
  is_paired BOOLEAN DEFAULT 0,  -- If true, comes in pairs (earrings, hands)
  is_dynamic BOOLEAN DEFAULT 0, -- If true, can be added in-game
  display_order INTEGER,

  description TEXT
);

-- Base clothing slots (layer system)
INSERT INTO equipment_slots (id, name, slot_category, body_part, layer_level, display_order, description) VALUES
  -- Layer 1: Underwear
  ('underwear_top', 'Underwear (Top)', 'clothing', 'torso', 1, 10, 'Undergarment for torso'),
  ('underwear_bottom', 'Underwear (Bottom)', 'clothing', 'legs', 1, 11, 'Undergarment for legs'),

  -- Layer 2: Base layer
  ('undershirt', 'Undershirt', 'clothing', 'torso', 2, 20, 'Base layer shirt'),
  ('trousers', 'Trousers', 'clothing', 'legs', 2, 21, 'Pants or trousers'),
  ('socks', 'Socks', 'clothing', 'feet', 2, 22, 'Foot covering'),

  -- Layer 3: Main clothing
  ('shirt', 'Shirt', 'clothing', 'torso', 3, 30, 'Main shirt or tunic'),
  ('belt', 'Belt', 'clothing', 'waist', 3, 31, 'Waist belt'),
  ('shoes', 'Shoes', 'clothing', 'feet', 3, 32, 'Footwear'),
  ('boots', 'Boots', 'clothing', 'feet', 3, 33, 'Tall footwear'),

  -- Layer 4: Outer clothing
  ('jacket', 'Jacket', 'clothing', 'torso', 4, 40, 'Outer jacket or vest'),
  ('robe', 'Robe', 'clothing', 'torso', 4, 41, 'Full-body robe'),
  ('gloves', 'Gloves', 'clothing', 'hands', 4, 42, 'Hand covering'),

  -- Layer 5: Outermost
  ('cloak', 'Cloak', 'clothing', 'back', 5, 50, 'Outer cloak or cape'),
  ('hat', 'Hat', 'clothing', 'head', 5, 51, 'Head covering'),
  ('hood', 'Hood', 'clothing', 'head', 5, 52, 'Hood (part of cloak)');

-- Jewelry slots
INSERT INTO equipment_slots (id, name, slot_category, body_part, is_paired, display_order, description) VALUES
  ('earring_left', 'Left Earring', 'jewelry', 'ears', 1, 60, 'Left ear jewelry'),
  ('earring_right', 'Right Earring', 'jewelry', 'ears', 1, 61, 'Right ear jewelry'),
  ('necklace', 'Necklace', 'jewelry', 'neck', 0, 62, 'Neck jewelry'),
  ('amulet', 'Amulet', 'jewelry', 'neck', 0, 63, 'Magical neck item'),
  ('ring_left', 'Left Ring', 'jewelry', 'finger', 1, 64, 'Left hand ring'),
  ('ring_right', 'Right Ring', 'jewelry', 'finger', 1, 65, 'Right hand ring'),
  ('bracelet_left', 'Left Bracelet', 'jewelry', 'wrists', 1, 66, 'Left wrist jewelry'),
  ('bracelet_right', 'Right Bracelet', 'jewelry', 'wrists', 1, 67, 'Right wrist jewelry'),
  ('wristband_left', 'Left Wristband', 'jewelry', 'wrists', 1, 68, 'Left wrist band'),
  ('wristband_right', 'Right Wristband', 'jewelry', 'wrists', 1, 69, 'Right wrist band');

-- Held items
INSERT INTO equipment_slots (id, name, slot_category, body_part, is_paired, display_order, description) VALUES
  ('hand_main', 'Main Hand', 'held', 'hands', 1, 70, 'Primary weapon or tool'),
  ('hand_off', 'Off Hand', 'held', 'hands', 1, 71, 'Secondary weapon or shield');

-- Carried items (don't occupy body parts, but have weight)
INSERT INTO equipment_slots (id, name, slot_category, body_part, display_order, description) VALUES
  ('backpack', 'Backpack', 'carried', 'back', 80, 'Main backpack'),
  ('pouch_1', 'Pouch 1', 'carried', 'waist', 81, 'Belt pouch'),
  ('pouch_2', 'Pouch 2', 'carried', 'waist', 82, 'Belt pouch'),
  ('pouch_3', 'Pouch 3', 'carried', 'waist', 83, 'Belt pouch'),
  ('quiver', 'Quiver', 'carried', 'back', 84, 'Arrow/bolt container');

-- Armor slots (for D&D armor system)
INSERT INTO equipment_slots (id, name, slot_category, body_part, layer_level, display_order, description, conflicts_with) VALUES
  ('armor_light', 'Light Armor', 'clothing', 'torso', 3, 90, 'Light armor (leather, padded)', '["armor_medium", "armor_heavy"]'),
  ('armor_medium', 'Medium Armor', 'clothing', 'torso', 3, 91, 'Medium armor (chain shirt, breastplate)', '["armor_light", "armor_heavy"]'),
  ('armor_heavy', 'Heavy Armor', 'clothing', 'torso', 3, 92, 'Heavy armor (plate, chain mail)', '["armor_light", "armor_medium"]'),
  ('shield', 'Shield', 'held', 'hands', 0, 93, 'Shield (held item)', NULL);

-- ============================================================
-- BODY TYPE SLOTS
-- Which slots are available for each body type
-- ============================================================
CREATE TABLE IF NOT EXISTS body_type_slots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  body_type_id TEXT NOT NULL,
  slot_id TEXT NOT NULL,
  is_available BOOLEAN DEFAULT 1,
  notes TEXT,

  FOREIGN KEY (body_type_id) REFERENCES body_types(id),
  FOREIGN KEY (slot_id) REFERENCES equipment_slots(id),
  UNIQUE(body_type_id, slot_id)
);

-- Humanoid body type gets all standard slots
INSERT INTO body_type_slots (body_type_id, slot_id, is_available)
SELECT 'humanoid', id, 1
FROM equipment_slots
WHERE id NOT LIKE '%_dynamic_%';

-- Quadruped body type (limited slots)
INSERT INTO body_type_slots (body_type_id, slot_id, is_available, notes)
SELECT 'quadruped', id, 1, 'Saddle-mounted'
FROM equipment_slots
WHERE id IN ('backpack', 'pouch_1', 'pouch_2', 'hat', 'necklace', 'cloak');

-- Avian body type (no hands, wings instead)
INSERT INTO body_type_slots (body_type_id, slot_id, is_available, notes)
SELECT 'avian', id, 1, 'Modified for wings'
FROM equipment_slots
WHERE slot_category IN ('jewelry', 'carried')
   OR id IN ('cloak', 'hat', 'hood');

-- Serpentine (very limited)
INSERT INTO body_type_slots (body_type_id, slot_id, is_available)
SELECT 'serpentine', id, 1
FROM equipment_slots
WHERE id IN ('necklace', 'amulet', 'hat', 'hood', 'cloak');

-- ============================================================
-- ITEM WEARABLE PROPERTIES
-- Add wearable fields to items table
-- ============================================================
ALTER TABLE items ADD COLUMN is_wearable BOOLEAN DEFAULT 0;
ALTER TABLE items ADD COLUMN equipment_slot_id TEXT REFERENCES equipment_slots(id);
ALTER TABLE items ADD COLUMN occupies_slots JSON;  -- Array of slot IDs this item occupies
ALTER TABLE items ADD COLUMN armor_class INTEGER;   -- AC bonus if armor
ALTER TABLE items ADD COLUMN armor_type TEXT;       -- 'light', 'medium', 'heavy', 'shield'
ALTER TABLE items ADD COLUMN requires_proficiency TEXT;  -- Proficiency needed
ALTER TABLE items ADD COLUMN stat_bonuses JSON;     -- {stat: bonus, ...}
ALTER TABLE items ADD COLUMN magical_properties JSON;  -- Magical item properties

-- ============================================================
-- CARRYING CAPACITY RULES
-- Based on D&D 5e rules
-- ============================================================
CREATE TABLE IF NOT EXISTS encumbrance_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_name TEXT NOT NULL,
  threshold_formula TEXT NOT NULL,  -- e.g., "STR * 5", "STR * 10"
  speed_penalty INTEGER DEFAULT 0,   -- Feet reduction
  has_disadvantage BOOLEAN DEFAULT 0,
  affected_checks TEXT,              -- Which ability checks get disadvantage
  description TEXT
);

INSERT INTO encumbrance_rules (rule_name, threshold_formula, speed_penalty, has_disadvantage, affected_checks, description) VALUES
  ('Normal', 'STR * 15', 0, 0, NULL, 'Under carrying capacity - no penalties'),
  ('Encumbered', 'STR * 5', 10, 0, NULL, 'Speed reduced by 10 feet (variant rule)'),
  ('Heavily Encumbered', 'STR * 10', 20, 1, 'STR,DEX,CON', 'Speed -20, disadvantage on STR/DEX/CON checks (variant rule)');
