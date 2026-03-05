-- Add missing creature stat fields for wearable system

-- Size category (for carrying capacity)
ALTER TABLE creatures ADD COLUMN size TEXT DEFAULT 'Medium';

-- Ability score modifiers (cached for performance)
ALTER TABLE creatures ADD COLUMN str_mod INTEGER DEFAULT 0;
ALTER TABLE creatures ADD COLUMN dex_mod INTEGER DEFAULT 0;
ALTER TABLE creatures ADD COLUMN con_mod INTEGER DEFAULT 0;
ALTER TABLE creatures ADD COLUMN int_mod INTEGER DEFAULT 0;
ALTER TABLE creatures ADD COLUMN wis_mod INTEGER DEFAULT 0;
ALTER TABLE creatures ADD COLUMN cha_mod INTEGER DEFAULT 0;

-- Body type for equipment slots
ALTER TABLE creatures ADD COLUMN body_type TEXT DEFAULT 'humanoid';
