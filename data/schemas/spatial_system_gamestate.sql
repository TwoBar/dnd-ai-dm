-- ============================================================
-- SPATIAL SYSTEM (Game State DB portion)
-- Persistent spatial model with absolute coordinates
-- ============================================================

-- ============================================================
-- SPATIAL LOCATIONS
-- Hierarchical semantic locations (renamed from "zones")
-- ============================================================
CREATE TABLE IF NOT EXISTS spatial_locations (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,

  -- Hierarchy
  name TEXT NOT NULL,
  parent_location_id TEXT,
  location_type TEXT NOT NULL,  -- references location_types(type_id)

  -- Bounding box (absolute coordinates)
  x_min REAL NOT NULL,
  y_min REAL NOT NULL,
  z_min REAL DEFAULT 0,
  x_max REAL NOT NULL,
  y_max REAL NOT NULL,
  z_max REAL DEFAULT 3,  -- Default ceiling height

  -- Scale information
  scale_band TEXT NOT NULL,  -- references scale_bands(band_id)
  tile_size_meters REAL NOT NULL,

  -- Generation state
  is_generated BOOLEAN DEFAULT 0,
  generated_at TIMESTAMP,
  generation_context JSON,  -- LLM context used for generation

  -- Metadata
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (parent_location_id) REFERENCES spatial_locations(id)
);

CREATE INDEX IF NOT EXISTS idx_spatial_locations_session ON spatial_locations(session_id);
CREATE INDEX IF NOT EXISTS idx_spatial_locations_parent ON spatial_locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_spatial_locations_type ON spatial_locations(location_type);

-- ============================================================
-- SPATIAL ENTITIES
-- Objects in space with absolute coordinates
-- Links to existing game entities (creatures, items, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS spatial_entities (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,

  -- Entity reference (one of these will be set)
  creature_id TEXT,           -- references creatures(id)
  item_id TEXT,              -- references items(id)
  inventory_item_id INTEGER, -- references creature_inventory(id) for placed items
  furniture_id TEXT,         -- custom furniture entities

  -- Spatial properties
  location_id TEXT NOT NULL,  -- references spatial_locations(id)
  x REAL NOT NULL,
  y REAL NOT NULL,
  z REAL DEFAULT 0,

  -- Physical properties
  volume_m3 REAL NOT NULL,
  footprint_width REAL,
  footprint_depth REAL,
  height REAL,
  orientation_degrees REAL DEFAULT 0,

  -- Multi-tile occupancy (JSON array of [dx, dy] offsets)
  footprint_tiles JSON,

  -- State
  is_blocking BOOLEAN DEFAULT 1,
  is_visible BOOLEAN DEFAULT 1,
  is_interactive BOOLEAN DEFAULT 1,

  -- Metadata
  entity_name TEXT NOT NULL,
  entity_description TEXT,
  sprite_id TEXT,  -- references tile_sprites(sprite_id)

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (location_id) REFERENCES spatial_locations(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id),
  FOREIGN KEY (item_id) REFERENCES items(id),
  FOREIGN KEY (inventory_item_id) REFERENCES creature_inventory(id)
);

CREATE INDEX IF NOT EXISTS idx_spatial_entities_session ON spatial_entities(session_id);
CREATE INDEX IF NOT EXISTS idx_spatial_entities_location ON spatial_entities(location_id);
CREATE INDEX IF NOT EXISTS idx_spatial_entities_creature ON spatial_entities(creature_id);
CREATE INDEX IF NOT EXISTS idx_spatial_entities_position ON spatial_entities(location_id, x, y);

-- ============================================================
-- SPATIAL EVENTS
-- Event-driven mutation log for all spatial changes
-- Authoritative record of what happened
-- ============================================================
CREATE TABLE IF NOT EXISTS spatial_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  event_type TEXT NOT NULL,  -- 'location_created', 'entity_placed', 'entity_moved', 'entity_removed', etc.

  -- Affected entities
  location_id TEXT,
  entity_id TEXT,
  creature_id TEXT,

  -- Event data
  event_data JSON NOT NULL,  -- Flexible event-specific data

  -- Causation
  caused_by TEXT,  -- 'player_action', 'combat_round', 'narrative_event', 'zone_generation'
  triggering_action TEXT,

  -- Timing
  game_time TIMESTAMP,
  real_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (location_id) REFERENCES spatial_locations(id),
  FOREIGN KEY (entity_id) REFERENCES spatial_entities(id),
  FOREIGN KEY (creature_id) REFERENCES creatures(id)
);

CREATE INDEX IF NOT EXISTS idx_spatial_events_session ON spatial_events(session_id);
CREATE INDEX IF NOT EXISTS idx_spatial_events_location ON spatial_events(location_id);
CREATE INDEX IF NOT EXISTS idx_spatial_events_type ON spatial_events(event_type);
CREATE INDEX IF NOT EXISTS idx_spatial_events_time ON spatial_events(real_time);

-- ============================================================
-- COMBAT MAPS
-- Cached grid projections from spatial state
-- Can be regenerated from spatial_entities on demand
-- ============================================================
CREATE TABLE IF NOT EXISTS combat_maps (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  location_id TEXT NOT NULL,

  -- Grid properties
  grid_width INTEGER NOT NULL,
  grid_height INTEGER NOT NULL,
  tile_size_meters REAL NOT NULL,
  origin_x REAL NOT NULL,  -- World coordinate of grid origin
  origin_y REAL NOT NULL,

  -- Grid data (2D array of tile types)
  tile_grid JSON NOT NULL,  -- [[sprite_id, sprite_id, ...], ...]

  -- Entity positions on grid
  entity_positions JSON NOT NULL,  -- [{entity_id, grid_x, grid_y, ...}, ...]

  -- Generation metadata
  generated_from_event_id INTEGER,  -- Last spatial_event processed
  generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_stale BOOLEAN DEFAULT 0,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (location_id) REFERENCES spatial_locations(id),
  FOREIGN KEY (generated_from_event_id) REFERENCES spatial_events(id)
);

CREATE INDEX IF NOT EXISTS idx_combat_maps_session ON combat_maps(session_id);
CREATE INDEX IF NOT EXISTS idx_combat_maps_location ON combat_maps(location_id);

-- ============================================================
-- DRAW DISTANCE CONFIGURATION
-- Semantic draw distance (not tile-based)
-- ============================================================
CREATE TABLE IF NOT EXISTS draw_distance_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,

  -- Player perspective
  current_location_id TEXT NOT NULL,

  -- Visibility rules (semantic, not spatial)
  visible_locations JSON NOT NULL,  -- [location_id, location_id, ...]

  -- Reasoning
  visibility_reason JSON,  -- {location_id: "player mentioned", location_id: "connected room", ...}

  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (current_location_id) REFERENCES spatial_locations(id)
);

-- ============================================================
-- LAZY GENERATION QUEUE
-- Tracks locations that need generation
-- ============================================================
CREATE TABLE IF NOT EXISTS generation_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  location_id TEXT NOT NULL,

  -- Priority
  priority INTEGER DEFAULT 5,  -- 1-10, higher = generate sooner
  reason TEXT,  -- Why generation was triggered

  -- Generation context
  context JSON,  -- Parent location info, narrative context

  -- State
  status TEXT DEFAULT 'pending',  -- 'pending', 'generating', 'completed', 'failed'
  queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (location_id) REFERENCES spatial_locations(id)
);

CREATE INDEX IF NOT EXISTS idx_generation_queue_status ON generation_queue(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_generation_queue_session ON generation_queue(session_id);
