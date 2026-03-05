-- ============================================================
-- UPDATE CREATURE_INVENTORY FOR CONTAINER STATE TRACKING
-- ============================================================

-- Drop old table
DROP TABLE IF EXISTS creature_inventory;

-- Recreate with container support
CREATE TABLE IF NOT EXISTS creature_inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  item_id TEXT NOT NULL,            -- FK to reference.items

  -- Basic Item State
  quantity INTEGER DEFAULT 1,
  equipped BOOLEAN DEFAULT 0,
  attuned BOOLEAN DEFAULT 0,

  -- For regular charged items (wands, magic items)
  charges_remaining INTEGER,

  -- For CONTAINERS with contents
  is_filled BOOLEAN DEFAULT 0,
  contains_material_id TEXT,        -- FK to material_properties ('content:water', 'content:lava')
  content_volume_ml REAL,           -- ACTUAL volume remaining (source of truth!)
  content_weight_kg REAL,           -- ACTUAL content weight (computed from volume)

  -- CURRENT STATE of contents (changes over time!)
  current_temperature REAL,         -- Current temp in Celsius
  current_ph REAL,                  -- Current pH (0-14)
  current_salinity_ppm INTEGER,     -- Current salinity
  is_burning BOOLEAN DEFAULT 0,     -- Is it on fire?

  -- Time tracking for decay/state changes
  last_state_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  -- Cached display values (recomputed when accessed)
  current_weight_kg REAL,           -- Total: item + content
  charges_for_owner REAL,           -- Displayed charges for owner's size

  -- Instance Properties
  custom_name TEXT,
  custom_properties JSON,
  notes TEXT,

  -- Timestamps
  acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE,
  FOREIGN KEY (contains_material_id) REFERENCES material_properties(id)
);

CREATE INDEX IF NOT EXISTS idx_creature_inventory_creature ON creature_inventory(creature_id);
CREATE INDEX IF NOT EXISTS idx_creature_inventory_equipped ON creature_inventory(creature_id, equipped);
CREATE INDEX IF NOT EXISTS idx_creature_inventory_filled ON creature_inventory(is_filled);
