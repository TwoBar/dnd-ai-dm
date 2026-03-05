-- ============================================================
-- SPATIAL SYSTEM (Reference DB portion)
-- Scale bands and container plausibility configuration
-- ============================================================

-- ============================================================
-- SCALE BANDS
-- Defines the multi-scale LOD system
-- ============================================================
CREATE TABLE IF NOT EXISTS scale_bands (
  band_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  tile_size_meters REAL NOT NULL,
  min_entity_volume_m3 REAL NOT NULL,
  description TEXT
);

INSERT INTO scale_bands (band_id, name, tile_size_meters, min_entity_volume_m3, description) VALUES
  ('XXL', 'Extra Extra Large', 5.0, 125.0, 'Regional scale - mountains, forests, towns'),
  ('XL', 'Extra Large', 2.0, 8.0, 'City districts, large buildings'),
  ('L', 'Large', 1.0, 1.0, 'Building interiors, rooms'),
  ('M', 'Medium', 0.5, 0.125, 'Combat standard - D&D 5ft squares'),
  ('S', 'Small', 0.25, 0.015625, 'Fine detail - furniture, small objects');

-- ============================================================
-- LOCATION TYPES
-- Semantic types for spatial locations
-- ============================================================
CREATE TABLE IF NOT EXISTS location_types (
  type_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent_type TEXT,
  typical_scale_band TEXT NOT NULL,
  description TEXT,
  FOREIGN KEY (typical_scale_band) REFERENCES scale_bands(band_id)
);

INSERT INTO location_types (type_id, name, parent_type, typical_scale_band, description) VALUES
  ('region', 'Region', NULL, 'XXL', 'Large geographical area'),
  ('city', 'City', 'region', 'XL', 'Settlement with buildings'),
  ('district', 'District', 'city', 'XL', 'Named area within city'),
  ('building', 'Building', 'district', 'L', 'Structure with rooms'),
  ('room', 'Room', 'building', 'M', 'Indoor enclosed space'),
  ('furniture', 'Furniture', 'room', 'S', 'Objects within rooms');

-- ============================================================
-- CONTAINER PLAUSIBILITY
-- Rules for generating items in containers
-- Minimal ontology approach: container + room + building type
-- ============================================================
CREATE TABLE IF NOT EXISTS container_plausibility_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  container_name TEXT,  -- e.g., "chest", "barrel", "table"
  room_type TEXT,       -- e.g., "bedroom", "kitchen", "storage"
  building_type TEXT,   -- e.g., "tavern", "temple", "warehouse"

  -- Size categories for LLM generation phase
  typical_small_count INTEGER DEFAULT 5,      -- coins, keys, gems
  typical_medium_count INTEGER DEFAULT 2,     -- books, daggers, potions
  typical_large_count INTEGER DEFAULT 1,      -- weapons, armor pieces

  -- Volume thresholds for programmatic phase
  small_item_volume_max_m3 REAL DEFAULT 0.001,    -- < 1L
  medium_item_volume_max_m3 REAL DEFAULT 0.01,    -- 1-10L
  large_item_volume_max_m3 REAL DEFAULT 0.1,      -- 10-100L

  notes TEXT
);

-- Example plausibility rules
INSERT INTO container_plausibility_rules
  (container_name, room_type, building_type, typical_small_count, typical_medium_count, typical_large_count, notes)
VALUES
  ('chest', 'bedroom', 'inn', 3, 2, 0, 'Personal belongings'),
  ('barrel', 'storage', 'tavern', 0, 0, 1, 'Ale or food supplies'),
  ('table', 'common_room', 'tavern', 5, 2, 0, 'Mugs, plates, utensils'),
  ('cabinet', 'kitchen', 'any', 10, 5, 1, 'Cooking supplies and ingredients'),
  ('altar', 'main_hall', 'temple', 2, 1, 1, 'Religious items and offerings');

-- ============================================================
-- TILE SPRITE REGISTRY
-- Maps entity types to visual sprites for rendering
-- (Future use when implementing map renderer)
-- ============================================================
CREATE TABLE IF NOT EXISTS tile_sprites (
  sprite_id TEXT PRIMARY KEY,
  sprite_category TEXT NOT NULL,  -- 'floor', 'wall', 'door', 'furniture', 'creature'
  sprite_name TEXT NOT NULL,
  file_path TEXT,
  blocking BOOLEAN DEFAULT 0,
  description TEXT
);

-- Basic sprite definitions (will expand when implementing renderer)
INSERT INTO tile_sprites (sprite_id, sprite_category, sprite_name, blocking, description) VALUES
  ('floor_stone', 'floor', 'Stone Floor', 0, 'Basic stone flooring'),
  ('floor_wood', 'floor', 'Wood Floor', 0, 'Wooden planks'),
  ('wall_stone', 'wall', 'Stone Wall', 1, 'Solid stone wall'),
  ('wall_wood', 'wall', 'Wood Wall', 1, 'Wooden wall or partition'),
  ('door_closed', 'door', 'Closed Door', 1, 'Standard closed door'),
  ('door_open', 'door', 'Open Door', 0, 'Open doorway'),
  ('table', 'furniture', 'Table', 1, 'Wooden table'),
  ('chair', 'furniture', 'Chair', 1, 'Simple chair'),
  ('barrel', 'furniture', 'Barrel', 1, 'Storage barrel');
