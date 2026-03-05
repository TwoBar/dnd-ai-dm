-- ============================================================
-- WEARABLE SYSTEM (Game State DB portion)
-- Tracks equipped items and carrying capacity status
-- ============================================================

-- ============================================================
-- EQUIPPED ITEMS
-- What creatures have equipped in which slots
-- ============================================================
CREATE TABLE IF NOT EXISTS equipped_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  slot_id TEXT NOT NULL,

  -- Reference to inventory item
  inventory_item_id INTEGER NOT NULL,

  -- Cached properties (for quick access)
  item_id TEXT NOT NULL,
  item_name TEXT,
  armor_class INTEGER,
  stat_bonuses JSON,

  -- State
  is_active BOOLEAN DEFAULT 1,  -- Can be deactivated without unequipping
  equipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  FOREIGN KEY (inventory_item_id) REFERENCES creature_inventory(id),
  FOREIGN KEY (slot_id) REFERENCES equipment_slots(id),

  -- Can only have one item per slot (unless slot allows stacking)
  UNIQUE(creature_id, slot_id, is_active)
);

CREATE INDEX IF NOT EXISTS idx_equipped_items_creature ON equipped_items(creature_id);
CREATE INDEX IF NOT EXISTS idx_equipped_items_slot ON equipped_items(slot_id);
CREATE INDEX IF NOT EXISTS idx_equipped_items_inventory ON equipped_items(inventory_item_id);

-- ============================================================
-- DYNAMIC EQUIPMENT SLOTS
-- Slots added during gameplay (e.g., extra piercings)
-- ============================================================
CREATE TABLE IF NOT EXISTS dynamic_equipment_slots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,

  -- Custom slot definition
  slot_id TEXT NOT NULL,  -- e.g., "earring_left_2", "pouch_4"
  slot_name TEXT NOT NULL,
  slot_category TEXT NOT NULL,
  body_part TEXT,

  -- When created
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  added_reason TEXT,  -- "piercing", "magical_enhancement", "item_grants"

  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  UNIQUE(creature_id, slot_id)
);

CREATE INDEX IF NOT EXISTS idx_dynamic_slots_creature ON dynamic_equipment_slots(creature_id);

-- ============================================================
-- CARRYING CAPACITY STATE
-- Track encumbrance and weight limits
-- ============================================================
CREATE TABLE IF NOT EXISTS carrying_capacity_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL UNIQUE,
  session_id TEXT NOT NULL,

  -- Creature stats
  strength_score INTEGER NOT NULL,
  size_category TEXT NOT NULL,  -- 'Tiny', 'Small', 'Medium', 'Large', etc.

  -- Capacity calculations (in pounds)
  base_carrying_capacity REAL NOT NULL,  -- STR * 15 for Medium
  current_weight_carried REAL DEFAULT 0,

  -- Size modifiers
  size_multiplier REAL DEFAULT 1.0,  -- 0.5 for Small/Tiny, 2.0 for Large, etc.

  -- Encumbrance status
  encumbrance_level TEXT DEFAULT 'Normal',  -- 'Normal', 'Encumbered', 'Heavily Encumbered'
  speed_penalty INTEGER DEFAULT 0,
  has_disadvantage BOOLEAN DEFAULT 0,
  affected_checks TEXT,

  -- Equipment totals
  total_equipped_weight REAL DEFAULT 0,
  total_inventory_weight REAL DEFAULT 0,
  total_container_contents_weight REAL DEFAULT 0,

  -- Last update
  last_calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_carrying_capacity_creature ON carrying_capacity_state(creature_id);
CREATE INDEX IF NOT EXISTS idx_carrying_capacity_session ON carrying_capacity_state(session_id);

-- ============================================================
-- EQUIPMENT EVENTS
-- Log equipment changes for history/debugging
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  creature_id TEXT NOT NULL,

  event_type TEXT NOT NULL,  -- 'equipped', 'unequipped', 'slot_added', 'encumbered'

  -- Event details
  slot_id TEXT,
  item_id TEXT,
  inventory_item_id INTEGER,

  event_data JSON,

  -- Context
  caused_by TEXT,  -- 'player_action', 'loot', 'merchant', 'combat'

  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id)
);

CREATE INDEX IF NOT EXISTS idx_equipment_events_creature ON equipment_events(creature_id);
CREATE INDEX IF NOT EXISTS idx_equipment_events_session ON equipment_events(session_id);
CREATE INDEX IF NOT EXISTS idx_equipment_events_type ON equipment_events(event_type);

-- ============================================================
-- ARMOR CLASS CALCULATION CACHE
-- Cache AC calculations for performance
-- ============================================================
CREATE TABLE IF NOT EXISTS armor_class_cache (
  creature_id TEXT PRIMARY KEY,

  -- Base AC calculation
  base_ac INTEGER DEFAULT 10,

  -- From armor
  armor_ac INTEGER DEFAULT 0,
  armor_type TEXT,  -- 'light', 'medium', 'heavy', 'none'

  -- From shield
  shield_ac INTEGER DEFAULT 0,

  -- Ability modifiers
  dex_modifier INTEGER DEFAULT 0,
  max_dex_bonus INTEGER,  -- NULL = unlimited, else capped

  -- Other bonuses
  misc_ac_bonuses INTEGER DEFAULT 0,
  magical_ac_bonuses INTEGER DEFAULT 0,

  -- Total
  total_ac INTEGER NOT NULL,

  -- Breakdown for display
  ac_breakdown JSON,  -- {"base": 10, "armor": 5, "dex": 2, "shield": 2, "magic": 1}

  last_calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id)
);

CREATE INDEX IF NOT EXISTS idx_armor_class_creature ON armor_class_cache(creature_id);
