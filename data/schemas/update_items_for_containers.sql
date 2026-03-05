-- ============================================================
-- UPDATE ITEMS TABLE FOR CONTAINER SYSTEM
-- Adds fields for containers, contents, and material properties
-- ============================================================

-- Container Properties
ALTER TABLE items ADD COLUMN is_container BOOLEAN DEFAULT 0;
ALTER TABLE items ADD COLUMN container_type_id TEXT REFERENCES container_types(id);
ALTER TABLE items ADD COLUMN container_capacity_ml INTEGER;
ALTER TABLE items ADD COLUMN container_weight_kg REAL;  -- Weight when EMPTY

-- Content Properties (for liquids, powders - NOT for containers)
ALTER TABLE items ADD COLUMN is_content BOOLEAN DEFAULT 0;
ALTER TABLE items ADD COLUMN material_id TEXT REFERENCES material_properties(id);

-- Consumable Properties
ALTER TABLE items ADD COLUMN consumable BOOLEAN DEFAULT 0;
ALTER TABLE items ADD COLUMN destroyed_on_use BOOLEAN DEFAULT 0;

-- Multi-target
ALTER TABLE items ADD COLUMN shareable BOOLEAN DEFAULT 0;
ALTER TABLE items ADD COLUMN shares_effect BOOLEAN DEFAULT 1;
ALTER TABLE items ADD COLUMN max_targets INTEGER DEFAULT 1;

-- Usage
ALTER TABLE items ADD COLUMN action_type TEXT DEFAULT 'action';
ALTER TABLE items ADD COLUMN use_range INTEGER DEFAULT 0;
