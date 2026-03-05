"""
Improvised action adjudication for the reasoning agent.

Determines game mechanics for improvised D&D actions by:
1. Classifying the action type
2. Querying RAG for similar RAW effects
3. Extracting precedent values
4. Applying DM heuristics
5. Proposing balanced mechanics
"""
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


@dataclass
class ImprovisedMechanics:
    """Proposed mechanics for improvised action."""
    damage: str                 # "3d6"
    damage_type: str            # "fire", "bludgeoning", etc.
    aoe_shape: Optional[str]    # "cylinder", "sphere", "cone", or None
    aoe_radius: float           # 10.0 (feet)
    save_ability: str           # "dex", "str", "con"
    save_dc: int                # 15
    save_effect: str            # "half_damage", "no_effect", "prone"
    precedent_sources: List[str]
    reasoning: str


def adjudicate_improvised_action(
    action: str,
    context: Dict[str, Any],
    rag_query
) -> ImprovisedMechanics:
    """
    Determine game mechanics for improvised action.

    Args:
        action: Player's description ("pour boiling oil", "swing from chandelier")
        context: Situation details (height, target count, environment, etc.)
        rag_query: RAG query service for finding precedents

    Returns:
        ImprovisedMechanics with damage, AOE, save DC, etc.
    """
    logger.info(f"Adjudicating improvised action: {action}")

    action_type = _classify_action(action)
    logger.info(f"  Classification: {action_type}")

    precedents = _find_precedents(action, action_type, rag_query)
    logger.info(f"  Found {len(precedents)} precedents")

    damage_precedents = _extract_damage_precedents(precedents)

    mechanics = _synthesize_mechanics(
        action=action,
        action_type=action_type,
        precedents=damage_precedents,
        context=context
    )

    logger.info(f"  Proposed mechanics: {mechanics.damage} {mechanics.damage_type}, DC {mechanics.save_dc}")
    return mechanics


def _classify_action(action: str) -> str:
    """Classify improvised action type using LLM with keyword fallback."""
    try:
        import openai
        import os

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return _classify_action_fallback(action)

        client = openai.OpenAI(api_key=api_key)

        prompt = f"""Classify this D&D 5e improvised action into a category.

Action: {action}

Categories:
- area_damage_fire: Area of effect fire damage
- area_damage_physical: Area of effect physical damage (falling objects, etc.)
- area_damage_other: Area of effect with other damage type
- single_target_damage: Single target damage
- single_target_control: Single target status effect (prone, grappled, etc.)
- area_control: Area control (difficult terrain, etc.)
- utility: Non-combat utility
- environmental_hazard: Creates ongoing hazard

Return ONLY the category name, nothing else."""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a D&D 5e DM who classifies player actions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=50
        )

        return response.choices[0].message.content.strip().lower()

    except Exception as e:
        logger.warning(f"LLM classification failed, using fallback: {e}")
        return _classify_action_fallback(action)


def _classify_action_fallback(action: str) -> str:
    """Simple keyword-based classification fallback."""
    action_lower = action.lower()

    if any(word in action_lower for word in ['fire', 'burn', 'ignite', 'flame', 'oil', 'torch']):
        if any(word in action_lower for word in ['area', 'pour', 'spread', 'multiple']):
            return 'area_damage_fire'
        return 'single_target_damage'

    if any(word in action_lower for word in ['drop', 'throw', 'push', 'fall', 'crush']):
        if any(word in action_lower for word in ['area', 'multiple', 'group']):
            return 'area_damage_physical'
        return 'single_target_damage'

    if any(word in action_lower for word in ['trip', 'shove', 'grapple', 'restrain']):
        return 'single_target_control'

    return 'single_target_damage'


def _find_precedents(action: str, action_type: str, rag_query) -> List:
    """Query RAG for similar effects in D&D rules."""
    try:
        if 'fire' in action_type:
            query = f"D&D 5e fire damage area effect spells {action}"
        elif 'damage' in action_type:
            query = f"D&D 5e damage effects similar to {action}"
        elif 'control' in action_type:
            query = f"D&D 5e control effects status conditions {action}"
        else:
            query = f"D&D 5e {action} mechanics"

        return rag_query.search_rules(query, max_results=5)

    except Exception as e:
        logger.warning(f"Failed to find precedents: {e}")
        return []


def _extract_damage_precedents(precedents: List) -> List[Dict[str, Any]]:
    """Extract damage values from precedent spells/abilities."""
    damage_precedents = []

    for p in precedents:
        content = p.get('content', '') if isinstance(p, dict) else getattr(p, 'content', '')
        name = p.get('name', 'Unknown') if isinstance(p, dict) else getattr(p, 'name', 'Unknown')

        damages = re.findall(r'(\d+d\d+)', content)

        level_match = re.search(r'(?:level|spell\s+level)\s+(\d+)', content, re.IGNORECASE)
        level = int(level_match.group(1)) if level_match else 0

        damage_type = 'fire'
        for dtype in ['fire', 'cold', 'lightning', 'acid', 'poison', 'force',
                       'bludgeoning', 'slashing', 'piercing']:
            if dtype in content.lower():
                damage_type = dtype
                break

        if damages:
            damage_precedents.append({
                'source': name,
                'damage': damages[0],
                'damage_type': damage_type,
                'level': level,
                'content_snippet': content[:200]
            })

    return damage_precedents


def _synthesize_mechanics(
    action: str,
    action_type: str,
    precedents: List[Dict[str, Any]],
    context: Dict[str, Any]
) -> ImprovisedMechanics:
    """Synthesize final mechanics from precedents and context."""
    damage = "1d6"
    damage_type = "bludgeoning"
    aoe_shape = None
    aoe_radius = 0.0
    save_ability = "dex"
    save_dc = 10
    save_effect = "half_damage"

    if precedents:
        suitable = [p for p in precedents if p.get('level', 0) <= 2]
        if not suitable:
            suitable = precedents[:1]

        if suitable:
            selected = suitable[0]
            damage = selected.get('damage', '2d6')
            damage_type = selected.get('damage_type', 'fire')

    if 'area' in action_type:
        aoe_result = _determine_aoe(action)
        aoe_shape = aoe_result['shape']
        aoe_radius = aoe_result['radius']

    save_dc = _determine_save_dc(action, context)

    if 'area' in action_type or 'damage' in action_type:
        save_ability = 'dex'
    elif 'control' in action_type:
        save_ability = 'str'

    return ImprovisedMechanics(
        damage=damage,
        damage_type=damage_type,
        aoe_shape=aoe_shape,
        aoe_radius=aoe_radius,
        save_ability=save_ability,
        save_dc=save_dc,
        save_effect=save_effect,
        precedent_sources=[p['source'] for p in precedents[:3]],
        reasoning=f"Based on {len(precedents)} similar D&D effects. {action_type} action."
    )


def _determine_aoe(action: str) -> Dict[str, Any]:
    """Determine appropriate AOE shape and size."""
    action_lower = action.lower()

    if 'pour' in action_lower or 'drop' in action_lower:
        return {'shape': 'cylinder', 'radius': 10.0}
    elif 'throw' in action_lower or 'toss' in action_lower:
        return {'shape': 'sphere', 'radius': 5.0}
    elif 'swing' in action_lower or 'sweep' in action_lower:
        return {'shape': 'cone', 'radius': 15.0}
    else:
        return {'shape': 'sphere', 'radius': 5.0}


def _determine_save_dc(action: str, context: Dict[str, Any]) -> int:
    """Determine appropriate save DC based on difficulty."""
    height = context.get('height', 0)
    warning = context.get('warning', True)
    precision_required = context.get('precision_required', False)

    dc = 12 if warning else 15

    if height > 30:
        dc += 3

    if precision_required:
        dc += 2

    return min(max(dc, 10), 20)
