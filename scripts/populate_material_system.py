#!/usr/bin/env python3
"""Populate Material System Data"""

import sqlite3
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
REFERENCE_DB_PATH = project_root / "data" / "reference.db"


def populate_container_types(conn):
    """Populate container types with spillage properties"""
    print("\n📦 Populating container types...")

    container_types_data = [
        {
            'id': 'container_type:open',
            'name': 'Open Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 0,
            'can_hold_powder': 1,
            'is_watertight': 0,
            'is_airtight': 0,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 100.0,
            'min_temperature': -20.0,
            'acid_resistant': 0,
            'corrosive_resistant': 0,
            'security_level': 0,
            'can_be_closed': 0,
            'spillage_rate_multiplier': 5.0,
            'description': 'Open container like bowl or plate - spills easily when moving',
        },
        {
            'id': 'container_type:semi_open',
            'name': 'Semi-Open Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 0,
            'can_hold_powder': 1,
            'is_watertight': 0,
            'is_airtight': 0,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 100.0,
            'min_temperature': -20.0,
            'acid_resistant': 0,
            'corrosive_resistant': 0,
            'security_level': 1,
            'can_be_closed': 0,
            'spillage_rate_multiplier': 2.0,
            'description': 'Cup or mug - spills when moving quickly',
        },
        {
            'id': 'container_type:closeable',
            'name': 'Closeable Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 0,
            'can_hold_powder': 1,
            'is_watertight': 1,
            'is_airtight': 0,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 100.0,
            'min_temperature': -20.0,
            'acid_resistant': 0,
            'corrosive_resistant': 0,
            'security_level': 2,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.5,
            'description': 'Bottle with cork or cap - low spillage when closed',
        },
        {
            'id': 'container_type:sealed',
            'name': 'Sealed Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 0,
            'can_hold_powder': 1,
            'is_watertight': 1,
            'is_airtight': 0,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 150.0,
            'min_temperature': -40.0,
            'acid_resistant': 0,
            'corrosive_resistant': 0,
            'security_level': 3,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.1,
            'description': 'Waterskin or flask - minimal spillage, designed for travel',
        },
        {
            'id': 'container_type:watertight',
            'name': 'Watertight Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 1,
            'can_hold_powder': 1,
            'is_watertight': 1,
            'is_airtight': 1,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 200.0,
            'min_temperature': -50.0,
            'acid_resistant': 1,
            'corrosive_resistant': 1,
            'security_level': 4,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.0,
            'description': 'Metal flask or magical container - no spillage',
        },
        {
            'id': 'container_type:glass',
            'name': 'Glass Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 0,
            'can_hold_powder': 1,
            'is_watertight': 1,
            'is_airtight': 1,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 300.0,
            'min_temperature': -30.0,
            'acid_resistant': 1,
            'corrosive_resistant': 0,
            'security_level': 2,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.5,
            'description': 'Glass vial or bottle - acid-resistant but fragile',
        },
        {
            'id': 'container_type:fireproof',
            'name': 'Fireproof Container',
            'can_hold_solid': 1,
            'can_hold_liquid': 1,
            'can_hold_gas': 1,
            'can_hold_powder': 1,
            'is_watertight': 1,
            'is_airtight': 1,
            'is_fireproof': 1,
            'is_shatterproof': 1,
            'max_temperature': 2000.0,
            'min_temperature': -100.0,
            'acid_resistant': 1,
            'corrosive_resistant': 1,
            'security_level': 4,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.0,
            'description': 'Special container for extreme materials like lava',
        },
        {
            'id': 'container_type:bag',
            'name': 'Bag or Pouch',
            'can_hold_solid': 1,
            'can_hold_liquid': 0,
            'can_hold_gas': 0,
            'can_hold_powder': 0,
            'is_watertight': 0,
            'is_airtight': 0,
            'is_fireproof': 0,
            'is_shatterproof': 0,
            'max_temperature': 100.0,
            'min_temperature': -20.0,
            'acid_resistant': 0,
            'corrosive_resistant': 0,
            'security_level': 2,
            'can_be_closed': 1,
            'spillage_rate_multiplier': 0.0,
            'description': 'Fabric bag - only holds solid items',
        },
    ]

    cursor = conn.cursor()
    for ct in container_types_data:
        cursor.execute("""
            INSERT OR REPLACE INTO container_types (
                id, name, can_hold_solid, can_hold_liquid, can_hold_gas, can_hold_powder,
                is_watertight, is_airtight, is_fireproof, is_shatterproof,
                max_temperature, min_temperature, acid_resistant, corrosive_resistant,
                security_level, can_be_closed, spillage_rate_multiplier, description
            ) VALUES (
                :id, :name, :can_hold_solid, :can_hold_liquid, :can_hold_gas, :can_hold_powder,
                :is_watertight, :is_airtight, :is_fireproof, :is_shatterproof,
                :max_temperature, :min_temperature, :acid_resistant, :corrosive_resistant,
                :security_level, :can_be_closed, :spillage_rate_multiplier, :description
            )
        """, ct)

    conn.commit()
    print(f"   ✓ Added {len(container_types_data)} container types")


def populate_materials(conn):
    """Populate material properties"""
    print("\n🌊 Populating materials...")

    materials_data = [
        # WATER (base)
        {
            'id': 'content:water',
            'name': 'Water',
            'matter_state': 'liquid',
            'base_temperature': 20.0,
            'min_stable_temp': 0.0,
            'max_stable_temp': 100.0,
            'state_change_to_cold': 'content:ice',
            'state_change_to_hot': 'content:steam',
            'ph_level': 7.0,
            'salinity_ppm': 0,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': 'liquid',
            'compatible_containers': json.dumps([
                'container_type:closeable',
                'container_type:sealed',
                'container_type:watertight',
                'container_type:glass',
                'container_type:open',
                'container_type:semi_open'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.001,
            'serving_size_ml': 330,
            'decays_over_time': 0,
            'decay_rate_per_hour': None,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': None,
            'effects': json.dumps([
                {'effect_id': 'effect:restore_thirst', 'multiplier': 1.0}
            ]),
            'description': 'Fresh water',
            'srd': 1,
        },
        # HOT WATER
        {
            'id': 'content:water_hot',
            'name': 'Hot Water',
            'matter_state': 'liquid',
            'base_temperature': 80.0,
            'min_stable_temp': 0.0,
            'max_stable_temp': 100.0,
            'state_change_to_cold': 'content:water',
            'state_change_to_hot': 'content:steam',
            'ph_level': 7.0,
            'salinity_ppm': 0,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': 'liquid',
            'compatible_containers': json.dumps([
                'container_type:sealed',
                'container_type:watertight',
                'container_type:fireproof'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.001,
            'serving_size_ml': 330,
            'decays_over_time': 1,
            'decay_rate_per_hour': -5.0,
            'evaporation_rate_per_hour': 0.01,
            'decay_transforms_to': 'content:water',
            'effects': json.dumps([
                {'effect_id': 'effect:restore_thirst', 'multiplier': 0.5}
            ]),
            'description': 'Hot water - less refreshing, cools over time',
            'srd': 0,
        },
        # SALT WATER
        {
            'id': 'content:water_salt',
            'name': 'Salt Water',
            'matter_state': 'liquid',
            'base_temperature': 20.0,
            'min_stable_temp': -2.0,
            'max_stable_temp': 100.0,
            'state_change_to_cold': 'content:ice_salt',
            'state_change_to_hot': 'content:steam',
            'ph_level': 8.1,
            'salinity_ppm': 35000,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': 'liquid',
            'compatible_containers': json.dumps([
                'container_type:closeable',
                'container_type:sealed',
                'container_type:watertight',
                'container_type:glass',
                'container_type:open',
                'container_type:semi_open'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.00103,
            'serving_size_ml': 330,
            'decays_over_time': 0,
            'decay_rate_per_hour': None,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': None,
            'effects': json.dumps([
                {'effect_id': 'effect:restore_thirst', 'multiplier': -0.5}
            ]),
            'description': 'Ocean water - makes you thirstier!',
            'srd': 0,
        },
        # ICE
        {
            'id': 'content:ice',
            'name': 'Ice',
            'matter_state': 'solid',
            'base_temperature': -5.0,
            'min_stable_temp': -273.15,
            'max_stable_temp': 0.0,
            'state_change_to_cold': None,
            'state_change_to_hot': 'content:water',
            'ph_level': 7.0,
            'salinity_ppm': 0,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': None,
            'compatible_containers': json.dumps([
                'container_type:open',
                'container_type:closeable',
                'container_type:sealed',
                'container_type:bag'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.00092,
            'serving_size_ml': 330,
            'decays_over_time': 1,
            'decay_rate_per_hour': 2.0,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': 'content:water',
            'effects': json.dumps([
                {'effect_id': 'effect:restore_thirst', 'multiplier': 0.9}
            ]),
            'description': 'Ice - melts over time',
            'srd': 0,
        },
        # STEAM (escapes immediately)
        {
            'id': 'content:steam',
            'name': 'Steam',
            'matter_state': 'gas',
            'base_temperature': 100.0,
            'min_stable_temp': 100.0,
            'max_stable_temp': 999.0,
            'state_change_to_cold': 'content:water',
            'state_change_to_hot': None,
            'ph_level': 7.0,
            'salinity_ppm': 0,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': 'gas',
            'compatible_containers': json.dumps([
                'container_type:watertight'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.0006,
            'serving_size_ml': None,
            'decays_over_time': 1,
            'decay_rate_per_hour': -10.0,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': 'content:water',
            'effects': json.dumps([]),
            'description': 'Steam - escapes from non-airtight containers',
            'srd': 0,
        },
        # ACID
        {
            'id': 'content:acid',
            'name': 'Acid',
            'matter_state': 'liquid',
            'base_temperature': 20.0,
            'min_stable_temp': -10.0,
            'max_stable_temp': 80.0,
            'state_change_to_cold': None,
            'state_change_to_hot': None,
            'ph_level': 1.0,
            'salinity_ppm': 0,
            'flammable': 0,
            'currently_burning': 0,
            'toxic': 1,
            'radioactive': 0,
            'explosive': 0,
            'requires_container': 'liquid',
            'compatible_containers': json.dumps([
                'container_type:glass',
                'container_type:watertight',
                'container_type:fireproof'
            ]),
            'collection_tool': 'tool:acid-gloves',
            'content_weight_per_ml': 0.0012,
            'serving_size_ml': None,
            'decays_over_time': 0,
            'decay_rate_per_hour': None,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': None,
            'effects': json.dumps([
                {'effect_id': 'effect:damage', 'multiplier': 1.0, 'damage_type': 'acid', 'formula': '2d6'}
            ]),
            'description': 'Corrosive acid - damages on contact',
            'srd': 1,
        },
        # GUNPOWDER
        {
            'id': 'content:gunpowder',
            'name': 'Gunpowder',
            'matter_state': 'powder',
            'base_temperature': 20.0,
            'min_stable_temp': -50.0,
            'max_stable_temp': 150.0,
            'state_change_to_cold': None,
            'state_change_to_hot': None,
            'ph_level': 7.0,
            'salinity_ppm': 0,
            'flammable': 1,
            'currently_burning': 0,
            'toxic': 0,
            'radioactive': 0,
            'explosive': 1,
            'requires_container': 'powder',
            'compatible_containers': json.dumps([
                'container_type:closeable',
                'container_type:sealed',
                'container_type:watertight',
                'container_type:glass'
            ]),
            'collection_tool': None,
            'content_weight_per_ml': 0.0009,
            'serving_size_ml': None,
            'decays_over_time': 0,
            'decay_rate_per_hour': None,
            'evaporation_rate_per_hour': None,
            'decay_transforms_to': None,
            'effects': json.dumps([]),
            'description': 'Explosive powder - flammable',
            'srd': 1,
        },
    ]

    cursor = conn.cursor()
    for material in materials_data:
        cursor.execute("""
            INSERT OR REPLACE INTO material_properties (
                id, name, matter_state, base_temperature, min_stable_temp, max_stable_temp,
                state_change_to_cold, state_change_to_hot, ph_level, salinity_ppm,
                flammable, currently_burning, toxic, radioactive, explosive,
                requires_container, compatible_containers, collection_tool,
                content_weight_per_ml, serving_size_ml,
                decays_over_time, decay_rate_per_hour, evaporation_rate_per_hour, decay_transforms_to,
                effects, description, srd
            ) VALUES (
                :id, :name, :matter_state, :base_temperature, :min_stable_temp, :max_stable_temp,
                :state_change_to_cold, :state_change_to_hot, :ph_level, :salinity_ppm,
                :flammable, :currently_burning, :toxic, :radioactive, :explosive,
                :requires_container, :compatible_containers, :collection_tool,
                :content_weight_per_ml, :serving_size_ml,
                :decays_over_time, :decay_rate_per_hour, :evaporation_rate_per_hour, :decay_transforms_to,
                :effects, :description, :srd
            )
        """, material)

    conn.commit()
    print(f"   ✓ Added {len(materials_data)} materials")


def populate_tools(conn):
    """Populate tools"""
    print("\n🔧 Populating tools...")

    tools_data = [
        {
            'id': 'tool:shovel',
            'name': 'Shovel',
            'tool_type': 'digging',
            'can_collect_solids': 1,
            'can_collect_liquids': 0,
            'can_collect_powders': 1,
            'can_collect_gases': 0,
            'heat_resistant': 0,
            'cold_resistant': 0,
            'acid_resistant': 0,
            'allows_distance': 1,
            'requires_two_hands': 1,
            'requires_proficiency': 0,
            'item_id': None,
            'description': 'Used for digging and collecting solids/powders',
            'srd': 1,
        },
        {
            'id': 'tool:tongs',
            'name': 'Tongs',
            'tool_type': 'grabbing',
            'can_collect_solids': 1,
            'can_collect_liquids': 0,
            'can_collect_powders': 0,
            'can_collect_gases': 0,
            'heat_resistant': 1,
            'cold_resistant': 1,
            'acid_resistant': 0,
            'allows_distance': 1,
            'requires_two_hands': 0,
            'requires_proficiency': 0,
            'item_id': None,
            'description': 'Metal tongs for handling hot or cold items safely',
            'srd': 1,
        },
        {
            'id': 'tool:acid-gloves',
            'name': 'Acid-Resistant Gloves',
            'tool_type': 'protection',
            'can_collect_solids': 1,
            'can_collect_liquids': 1,
            'can_collect_powders': 1,
            'can_collect_gases': 0,
            'heat_resistant': 0,
            'cold_resistant': 0,
            'acid_resistant': 1,
            'allows_distance': 0,
            'requires_two_hands': 0,
            'requires_proficiency': 0,
            'item_id': None,
            'description': 'Special gloves for handling corrosive materials',
            'srd': 0,
        },
    ]

    cursor = conn.cursor()
    for tool in tools_data:
        cursor.execute("""
            INSERT OR REPLACE INTO tools (
                id, name, tool_type,
                can_collect_solids, can_collect_liquids, can_collect_powders, can_collect_gases,
                heat_resistant, cold_resistant, acid_resistant, allows_distance,
                requires_two_hands, requires_proficiency, item_id, description, srd
            ) VALUES (
                :id, :name, :tool_type,
                :can_collect_solids, :can_collect_liquids, :can_collect_powders, :can_collect_gases,
                :heat_resistant, :cold_resistant, :acid_resistant, :allows_distance,
                :requires_two_hands, :requires_proficiency, :item_id, :description, :srd
            )
        """, tool)

    conn.commit()
    print(f"   ✓ Added {len(tools_data)} tools")


def main():
    """Main population function"""
    print("=" * 60)
    print("🎲 D&D AI DM - Populate Material System")
    print("=" * 60)

    conn = sqlite3.connect(REFERENCE_DB_PATH)

    populate_container_types(conn)
    populate_materials(conn)
    populate_tools(conn)

    conn.close()

    print("\n" + "=" * 60)
    print("✅ Material system population complete!")
    print("=" * 60)
    print("\nPopulated:")
    print("  • 8 Container Types (open, closeable, sealed, watertight, etc.)")
    print("  • 7 Materials (water, ice, salt water, hot water, steam, acid, gunpowder)")
    print("  • 3 Tools (shovel, tongs, acid gloves)")


if __name__ == '__main__':
    main()
