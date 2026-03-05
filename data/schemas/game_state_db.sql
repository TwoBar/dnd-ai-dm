-- ============================================================
-- GAME STATE DATABASE SCHEMA
-- ============================================================
-- This database contains instances of entities in active game sessions.
-- Each session has its own characters, monsters, items, etc.
-- Templates come from reference.db, instances live here.
--
-- Database: game_state.db
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- SESSIONS (Game Sessions)
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,              -- 'session:uuid'
  name TEXT NOT NULL,               -- 'The Lost Mines of Phandelver'

  -- Session State
  status TEXT DEFAULT 'active',     -- 'active', 'paused', 'completed', 'archived'

  -- Campaign Info
  campaign_name TEXT,
  dm_notes TEXT,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_played ON sessions(last_played_at);

-- ============================================================
-- CREATURES (Base table for all living entities)
-- ============================================================
CREATE TABLE IF NOT EXISTS creatures (
  id TEXT PRIMARY KEY,              -- 'creature:uuid'
  session_id TEXT NOT NULL,

  -- Identity
  name TEXT NOT NULL,
  creature_type TEXT NOT NULL,      -- 'character', 'monster', 'npc', 'summon'
  creature_subtype TEXT,            -- 'player', 'friendly', 'hostile', 'neutral'

  -- Core Ability Scores
  str INTEGER NOT NULL,
  dex INTEGER NOT NULL,
  con INTEGER NOT NULL,
  int INTEGER NOT NULL,
  wis INTEGER NOT NULL,
  cha INTEGER NOT NULL,

  -- Hit Points
  hp INTEGER NOT NULL,
  max_hp INTEGER NOT NULL,
  temp_hp INTEGER DEFAULT 0,

  -- Armor Class
  ac INTEGER NOT NULL,
  ac_formula TEXT,                  -- '10 + dex_mod', 'natural armor'

  -- Speed
  speed JSON DEFAULT '{"walk": 30}', -- {"walk": 30, "fly": 60, "swim": 30}

  -- Combat State
  initiative INTEGER,
  death_saves_success INTEGER DEFAULT 0,
  death_saves_failure INTEGER DEFAULT 0,

  -- Status
  is_alive BOOLEAN DEFAULT 1,
  is_conscious BOOLEAN DEFAULT 1,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_creatures_session ON creatures(session_id);
CREATE INDEX IF NOT EXISTS idx_creatures_type ON creatures(creature_type);
CREATE INDEX IF NOT EXISTS idx_creatures_name ON creatures(session_id, name);

-- ============================================================
-- CHARACTERS (Player Characters & NPCs)
-- ============================================================
CREATE TABLE IF NOT EXISTS characters (
  creature_id TEXT PRIMARY KEY,

  -- Template References (from reference.db)
  race_id TEXT NOT NULL,            -- FK to reference.races
  subrace_id TEXT,                  -- FK to reference.subraces
  background_id TEXT,               -- FK to reference.backgrounds

  -- Character State
  state TEXT DEFAULT 'draft',       -- 'draft', 'finalized'

  -- Total Progression (computed from character_classes)
  total_level INTEGER DEFAULT 1,    -- Sum of all class levels
  xp INTEGER DEFAULT 0,

  -- Proficiency (based on total level)
  proficiency_bonus INTEGER DEFAULT 2,

  -- Personality
  alignment TEXT,
  personality_traits TEXT,
  ideals TEXT,
  bonds TEXT,
  flaws TEXT,

  -- Hit Dice (all classes combined)
  hit_dice JSON,                    -- {"d8": {"total": 3, "remaining": 2}, "d10": {"total": 2, "remaining": 1}}

  -- Class-Specific Resources (all classes combined)
  -- Examples:
  -- Bard: {"class:bard:bardic_inspiration": {"die": "d6", "uses": 2, "remaining": 2}}
  -- Paladin: {"class:paladin:lay_on_hands_pool": 50, "class:paladin:channel_divinity": {"uses": 1, "remaining": 1}}
  class_resources JSON,

  -- Spellcasting (multiclass support)
  multiclass_caster_level INTEGER DEFAULT 0,  -- Computed from all spellcasting classes
  spell_slots JSON,                 -- {"1": {"total": 4, "used": 2}, "2": {"total": 3, "used": 1}}
  pact_magic_slots JSON,            -- Warlock Pact Magic (separate): {"count": 2, "level": 2, "used": 0}

  -- Multiclass Edge Cases
  unarmored_defense_choice TEXT,    -- 'barbarian' or 'monk' (for Barbarian+Monk multiclass)

  -- Currency
  copper INTEGER DEFAULT 0,
  silver INTEGER DEFAULT 0,
  electrum INTEGER DEFAULT 0,
  gold INTEGER DEFAULT 0,
  platinum INTEGER DEFAULT 0,

  -- Inspiration
  inspiration BOOLEAN DEFAULT 0,

  -- Notes
  notes TEXT,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_characters_total_level ON characters(total_level);
CREATE INDEX IF NOT EXISTS idx_characters_state ON characters(state);

-- ============================================================
-- CHARACTER_CLASSES (Multiclass tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_classes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT NOT NULL,
  class_id TEXT NOT NULL,           -- FK to reference.classes

  -- Level in THIS specific class
  class_level INTEGER NOT NULL,

  -- Hit Points Rolled Per Level
  hp_rolls JSON,                    -- {"1": 10, "2": 8, "3": 9} - actual HP rolled at each class level

  -- Subclass
  subclass_id TEXT,                 -- FK to reference.subclasses
  subclass_level INTEGER,           -- Level when subclass was chosen

  -- Spells Known From This Class (for known casters like Bard, Sorcerer)
  spells_from_this_class JSON,      -- ["spell:cure-wounds", "spell:bless"]

  -- Class Order (which class was taken first)
  class_order INTEGER,              -- 1 = primary class, 2 = second class, etc.

  -- Timestamps
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(character_id, class_id),
  FOREIGN KEY (character_id) REFERENCES characters(creature_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_character_classes_char ON character_classes(character_id);
CREATE INDEX IF NOT EXISTS idx_character_classes_class ON character_classes(class_id);

-- ============================================================
-- CHARACTER_ASI (Ability Score Increases & Feats)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_asi (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT NOT NULL,

  -- Which class level granted this ASI
  source_class_id TEXT,             -- 'class:fighter'
  source_class_level INTEGER,       -- 4 (Fighter level 4)
  total_level_when_gained INTEGER,  -- 8 (character's total level when ASI gained)

  -- What the character chose
  asi_type TEXT NOT NULL,           -- 'ability_score' or 'feat'

  -- If ability score increase
  ability_increases JSON,           -- {"str": 1, "cha": 1} or {"str": 2}

  -- If feat
  feat_id TEXT,                     -- FK to reference.feats

  -- Timestamp
  gained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (character_id) REFERENCES characters(creature_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_character_asi_char ON character_asi(character_id);

-- ============================================================
-- MONSTERS (Monster Instances)
-- ============================================================
CREATE TABLE IF NOT EXISTS monsters (
  creature_id TEXT PRIMARY KEY,

  -- Template Reference (from reference.db)
  template_id TEXT NOT NULL,        -- FK to reference.monster_templates

  -- Monster Properties
  cr REAL NOT NULL,
  size TEXT,
  monster_type TEXT,                -- Beast, Humanoid, Dragon, etc.
  alignment TEXT,

  -- Legendary Actions
  legendary_actions_total INTEGER DEFAULT 0,
  legendary_actions_remaining INTEGER DEFAULT 0,

  -- Instance-Specific Traits (can override template)
  traits JSON,                      -- [{"name": "Pack Tactics", "description": "..."}]
  actions JSON,
  reactions JSON,
  legendary_actions JSON,

  -- Loot (drops when defeated)
  loot JSON,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_monsters_template ON monsters(template_id);
CREATE INDEX IF NOT EXISTS idx_monsters_cr ON monsters(cr);

-- ============================================================
-- CHARACTER_SPELLS (Known/Prepared Spells)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_spells (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT NOT NULL,
  spell_id TEXT NOT NULL,           -- FK to reference.spells

  -- Spell State
  is_prepared BOOLEAN DEFAULT 1,    -- For prepared casters (Wizard, Cleric)
  is_always_prepared BOOLEAN DEFAULT 0,  -- Domain spells, racial spells

  -- Source
  source TEXT,                      -- 'class:bard', 'race:tiefling', 'item:staff-of-fire'

  -- Timestamps
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(character_id, spell_id),
  FOREIGN KEY (character_id) REFERENCES characters(creature_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_character_spells_char ON character_spells(character_id);
CREATE INDEX IF NOT EXISTS idx_character_spells_spell ON character_spells(spell_id);

-- ============================================================
-- CREATURE_INVENTORY (Items owned by creatures)
-- ============================================================
CREATE TABLE IF NOT EXISTS creature_inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  item_id TEXT NOT NULL,            -- FK to reference.items

  -- Item State
  quantity INTEGER DEFAULT 1,
  equipped BOOLEAN DEFAULT 0,
  attuned BOOLEAN DEFAULT 0,

  -- Instance Properties (for items that can be modified/damaged)
  charges_remaining INTEGER,
  custom_name TEXT,                 -- "Greatsword of Goblin Slaying"
  custom_properties JSON,           -- Enchantments, modifications, etc.

  -- Timestamps
  acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(creature_id, item_id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_creature_inventory_creature ON creature_inventory(creature_id);
CREATE INDEX IF NOT EXISTS idx_creature_inventory_equipped ON creature_inventory(creature_id, equipped);

-- ============================================================
-- CREATURE_PROFICIENCIES (Skills, Tools, Languages, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS creature_proficiencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,

  proficiency_type TEXT NOT NULL,   -- 'skill', 'save', 'tool', 'language', 'weapon', 'armor'
  proficiency_name TEXT NOT NULL,   -- 'persuasion', 'thieves-tools', 'Common'
  proficiency_level TEXT DEFAULT 'proficient',  -- 'proficient', 'expert', 'half'

  -- Source
  source TEXT,                      -- 'class:bard', 'race:human', 'background:charlatan', 'feat:skilled'

  -- Timestamps
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(creature_id, proficiency_type, proficiency_name),
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_creature_proficiencies_creature ON creature_proficiencies(creature_id);
CREATE INDEX IF NOT EXISTS idx_creature_proficiencies_type ON creature_proficiencies(creature_id, proficiency_type);

-- ============================================================
-- CREATURE_CONDITIONS (Active conditions)
-- ============================================================
CREATE TABLE IF NOT EXISTS creature_conditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  condition_id TEXT NOT NULL,       -- FK to reference.conditions

  -- Duration
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  duration_rounds INTEGER,          -- NULL = indefinite
  rounds_remaining INTEGER,

  -- Saving Throws
  save_dc INTEGER,                  -- DC to remove condition
  save_ability TEXT,                -- 'con', 'wis', etc.

  -- Source
  source TEXT,                      -- 'spell:hold-person', 'poison', 'ability:frightful-presence'

  UNIQUE(creature_id, condition_id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_creature_conditions_creature ON creature_conditions(creature_id);

-- ============================================================
-- CHARACTER_FEATURES (Class features character has)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_features (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT NOT NULL,
  feature_id TEXT NOT NULL,         -- FK to reference.class_features

  -- Resource Tracking
  uses_total INTEGER,               -- Calculated from formula
  uses_remaining INTEGER,

  -- Timestamps
  gained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(character_id, feature_id),
  FOREIGN KEY (character_id) REFERENCES characters(creature_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_character_features_char ON character_features(character_id);

-- ============================================================
-- COMBAT STATE
-- ============================================================
CREATE TABLE IF NOT EXISTS combat_state (
  session_id TEXT PRIMARY KEY,

  -- Combat Status
  is_active BOOLEAN DEFAULT 0,
  round_number INTEGER DEFAULT 0,
  current_turn_creature_id TEXT,    -- FK to creatures.id

  -- Initiative Order (JSON array of creature IDs sorted by initiative)
  initiative_order JSON,            -- ["creature:id1", "creature:id2", ...]

  -- Timestamps
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (current_turn_creature_id) REFERENCES creatures(id) ON DELETE SET NULL
);

-- ============================================================
-- MESSAGES (Conversation History)
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,

  -- Message Content
  speaker TEXT NOT NULL,            -- 'DM', 'Player', 'System', character name
  message TEXT NOT NULL,
  message_type TEXT,                -- 'dm', 'user', 'system', 'error'

  -- Sequence
  sequence INTEGER,                 -- Order within session

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(session_id, created_at);

-- ============================================================
-- DICE ROLLS (Dice Log)
-- ============================================================
CREATE TABLE IF NOT EXISTS dice_rolls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,

  -- Roll Details
  roll_type TEXT,                   -- 'attack', 'damage', 'save', 'check', 'initiative', 'other'
  notation TEXT NOT NULL,           -- '1d20+5', '8d6'
  result INTEGER NOT NULL,
  individual_rolls JSON,            -- [12, 8, 15] for 3d20

  -- Context
  creature_id TEXT,                 -- Who rolled
  description TEXT,                 -- 'Attack roll against Goblin'

  -- Special
  is_critical BOOLEAN DEFAULT 0,
  is_fumble BOOLEAN DEFAULT 0,
  advantage BOOLEAN DEFAULT 0,
  disadvantage BOOLEAN DEFAULT 0,

  -- Sequence
  sequence INTEGER,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_dice_rolls_session ON dice_rolls(session_id, sequence);
CREATE INDEX IF NOT EXISTS idx_dice_rolls_creature ON dice_rolls(creature_id);

-- ============================================================
-- COMBAT EVENTS (Detailed combat log)
-- ============================================================
CREATE TABLE IF NOT EXISTS combat_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,

  -- Event Details
  event_type TEXT NOT NULL,         -- 'attack', 'damage', 'heal', 'condition_applied', 'spell_cast', 'death'
  round_number INTEGER,

  -- Participants
  actor_id TEXT,                    -- FK to creatures.id (who did it)
  target_id TEXT,                   -- FK to creatures.id (who received it)

  -- Event Data
  event_data JSON,                  -- {"damage": 12, "damage_type": "slashing", "weapon": "longsword"}

  -- Description
  description TEXT,                 -- "Goblin #1 attacks Joe with scimitar"

  -- Sequence
  sequence INTEGER,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (actor_id) REFERENCES creatures(id) ON DELETE SET NULL,
  FOREIGN KEY (target_id) REFERENCES creatures(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_combat_events_session ON combat_events(session_id, sequence);
CREATE INDEX IF NOT EXISTS idx_combat_events_round ON combat_events(session_id, round_number);

-- ============================================================
-- ACTIVE MODIFIERS (Temporary bonuses/penalties)
-- ============================================================
CREATE TABLE IF NOT EXISTS active_modifiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,

  -- Modifier Details
  modifier_type TEXT NOT NULL,      -- 'ability_score', 'ac', 'attack', 'damage', 'save', 'skill'
  applies_to TEXT,                  -- 'str', 'dex', 'all_attacks', 'persuasion'
  value INTEGER NOT NULL,           -- +2, -1, etc.

  -- Duration
  duration_rounds INTEGER,
  rounds_remaining INTEGER,

  -- Source
  source TEXT,                      -- 'spell:bless', 'item:ring-of-protection'

  -- Timestamps
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_active_modifiers_creature ON active_modifiers(creature_id);

-- ============================================================
-- LOCATIONS (Places in the game world - optional)
-- ============================================================
CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,              -- 'location:uuid'
  session_id TEXT NOT NULL,

  name TEXT NOT NULL,
  location_type TEXT,               -- 'settlement', 'dungeon', 'region', 'landmark'

  -- Description
  description TEXT,

  -- Properties
  properties JSON,                  -- Location-specific properties

  -- Parent Location (for hierarchy: Room -> Dungeon -> Region)
  parent_location_id TEXT,

  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_location_id) REFERENCES locations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_locations_session ON locations(session_id);
CREATE INDEX IF NOT EXISTS idx_locations_parent ON locations(parent_location_id);

-- ============================================================
-- METADATA
-- ============================================================
CREATE TABLE IF NOT EXISTS game_state_metadata (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO game_state_metadata (key, value) VALUES
  ('schema_version', '1.0.0'),
  ('created_at', datetime('now')),
  ('description', 'D&D 5E Game State Database - Session Instances');
-- ============================================================
-- SPILLAGE SYSTEM
-- Movement-based spillage for non-secure containers
-- ============================================================

-- Add spillage fields to container_types
ALTER TABLE container_types ADD COLUMN security_level INTEGER DEFAULT 3;
  -- 0: Open (bowl, plate) - Spills easily
  -- 1: Semi-open (cup, mug) - Spills when moving
  -- 2: Closeable (bottle with cork) - Low spillage when closed
  -- 3: Sealed (waterskin, flask) - Minimal spillage
  -- 4: Watertight (metal flask, magic) - No spillage

ALTER TABLE container_types ADD COLUMN can_be_closed BOOLEAN DEFAULT 1;
ALTER TABLE container_types ADD COLUMN spillage_rate_multiplier REAL DEFAULT 1.0;
  -- Base spillage rate (percentage per hour at walking speed)

-- Add closure state to inventory
ALTER TABLE creature_inventory ADD COLUMN is_closed BOOLEAN DEFAULT 1;
  -- Whether lid/cork is currently on


-- ============================================================
-- MOVEMENT INTENSITIES
-- Defines spillage multipliers for different movement types
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_intensities (
  movement_type TEXT PRIMARY KEY,
  intensity INTEGER NOT NULL,     -- 0-5 scale
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


-- ============================================================
-- MOVEMENT LOG (Optional - for tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  creature_id TEXT NOT NULL,

  -- Movement type
  movement_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,

  -- Duration
  started_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP,
  hours_duration REAL,

  -- Spillage results
  containers_affected INTEGER DEFAULT 0,
  total_volume_spilled_ml REAL DEFAULT 0,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  FOREIGN KEY (movement_type) REFERENCES movement_intensities(movement_type)
);

CREATE INDEX IF NOT EXISTS idx_movement_log_creature ON movement_log(creature_id);
CREATE INDEX IF NOT EXISTS idx_movement_log_session ON movement_log(session_id);


-- ============================================================
-- Update container_types to allow powders in liquid containers
-- ============================================================

-- Note: Already handled in material_properties.compatible_containers JSON
-- Just ensure container_types properly set can_hold_powder for liquid containers
-- ============================================================
-- SPILLAGE SYSTEM (Game State DB portion)
-- Tracks actual spillage events and container closure state
-- ============================================================

-- Add closure state to inventory (Game State DB)
ALTER TABLE creature_inventory ADD COLUMN is_closed BOOLEAN DEFAULT 1;

-- ============================================================
-- MOVEMENT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS movement_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  creature_id TEXT NOT NULL,

  -- Movement type
  movement_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,

  -- Duration
  started_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP,
  hours_duration REAL,

  -- Spillage results
  containers_affected INTEGER DEFAULT 0,
  total_volume_spilled_ml REAL DEFAULT 0,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id)
);

CREATE INDEX IF NOT EXISTS idx_movement_log_creature ON movement_log(creature_id);
CREATE INDEX IF NOT EXISTS idx_movement_log_session ON movement_log(session_id);
