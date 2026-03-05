"""
Slash command handlers for the web UI.

Handles /add, /combat, /init, /damage, /heal, /roll, /condition, /spawn, /stats, /help.
"""
from datetime import datetime

from ui.game_state import Character, Monster, DiceRoll
from tools.dice_tools import roll_dice
from ui.workflow_init import get_workflow_stats
from game.game_session import GameSession


def handle_command(command: str, session: GameSession, socketio, emit_fn, serialize_fn):
    """
    Dispatch a slash command.

    Args:
        command: Full command string (e.g., "/add char Lyra Wizard 1 6 12")
        session: Current GameSession
        socketio: SocketIO instance for broadcasting
        emit_fn: Function to emit to current client
        serialize_fn: Function to serialize game state
    """
    parts = command.split()
    cmd = parts[0].lower()

    def send_system(message):
        msg = {
            'timestamp': datetime.now().isoformat(),
            'speaker': 'System',
            'message': message,
            'type': 'system'
        }
        emit_fn('new_message', msg)

    def update_state():
        emit_fn('game_state', serialize_fn(session))

    try:
        if cmd == '/add':
            _handle_add(parts[1:], session, send_system, update_state)
        elif cmd == '/combat':
            _handle_combat(parts[1:], session, send_system, update_state)
        elif cmd == '/init':
            _handle_init(parts[1:], session, send_system, update_state)
        elif cmd == '/damage':
            _handle_damage(parts[1:], session, send_system, update_state)
        elif cmd == '/heal':
            _handle_heal(parts[1:], session, send_system, update_state)
        elif cmd == '/roll':
            _handle_roll(parts[1:], session, send_system, update_state)
        elif cmd == '/next':
            session.game_state.next_turn()
            send_system(f"It's now {session.game_state.current_turn}'s turn!")
            update_state()
        elif cmd == '/condition':
            _handle_condition(parts[1:], session, send_system, update_state)
        elif cmd == '/clear':
            session.message_history.clear()
            emit_fn('clear_messages')
        elif cmd == '/stats':
            _handle_stats(session, send_system)
        elif cmd == '/spawn':
            _handle_spawn(parts[1:], session, send_system, emit_fn, socketio)
        elif cmd == '/help':
            _send_help(send_system)
        else:
            send_system(f"Unknown command: {cmd}")

    except Exception as e:
        send_system(f"Error: {str(e)}")


def _handle_add(args, session, send_system, update_state):
    if len(args) < 2:
        send_system("Usage: /add char <name> <class> <level> <hp> <ac> OR /add monster <name> <hp> <ac> <cr>")
        return

    entity_type = args[0].lower()

    if entity_type in ['char', 'character']:
        if len(args) < 6:
            send_system("Usage: /add char <name> <class> <level> <hp> <ac>")
            return
        char = Character(
            name=args[1], class_name=args[2], level=int(args[3]),
            hp=int(args[4]), max_hp=int(args[4]), ac=int(args[5])
        )
        session.game_state.add_character(char)
        send_system(f"Added character: {char.to_display()}")
        session.add_player_character({'name': char.name, 'hp': char.hp, 'ac': char.ac})

    elif entity_type in ['mon', 'monster']:
        if len(args) < 5:
            send_system("Usage: /add monster <name> <hp> <ac> <cr>")
            return
        monster = Monster(
            name=args[1], hp=int(args[2]), max_hp=int(args[2]),
            ac=int(args[3]), cr=float(args[4])
        )
        session.game_state.add_monster(monster)
        send_system(f"Added monster: {monster.to_display()}")

    update_state()


def _handle_combat(args, session, send_system, update_state):
    if not args:
        send_system("Usage: /combat start|end")
        return
    action = args[0].lower()
    if action == 'start':
        session.game_state.start_combat()
        send_system("Combat started! Roll initiative.")
    elif action == 'end':
        session.game_state.end_combat()
        send_system("Combat ended.")
    update_state()


def _handle_init(args, session, send_system, update_state):
    if len(args) < 2:
        send_system("Usage: /init <name> <roll>")
        return
    name, init_roll = args[0], int(args[1])
    for char in session.game_state.characters:
        if char.name.lower() == name.lower():
            char.initiative = init_roll
            send_system(f"{name} rolled {init_roll} for initiative")
            update_state()
            return
    for monster in session.game_state.monsters:
        if monster.name.lower() == name.lower():
            monster.initiative = init_roll
            send_system(f"{name} rolled {init_roll} for initiative")
            update_state()
            return
    send_system(f"Character or monster '{name}' not found")


def _handle_damage(args, session, send_system, update_state):
    if len(args) < 2:
        send_system("Usage: /damage <name> <amount>")
        return
    name, damage = args[0], int(args[1])
    for char in session.game_state.characters:
        if char.name.lower() == name.lower():
            session.game_state.damage_character(name, damage)
            update_state()
            return
    for monster in session.game_state.monsters:
        if monster.name.lower() == name.lower():
            session.game_state.damage_monster(name, damage)
            update_state()
            return
    send_system(f"Character or monster '{name}' not found")


def _handle_heal(args, session, send_system, update_state):
    if len(args) < 2:
        send_system("Usage: /heal <name> <amount>")
        return
    name, healing = args[0], int(args[1])
    session.game_state.heal_character(name, healing)
    update_state()


def _handle_roll(args, session, send_system, update_state):
    if not args:
        send_system("Usage: /roll <notation>")
        return
    notation = args[0]
    result = roll_dice(notation)
    if 'error' in result:
        send_system(f"Error: {result['error']}")
    else:
        roll = DiceRoll(
            timestamp=datetime.now(), type='manual', notation=notation,
            result=result['total'], description=notation,
            critical=result.get('is_critical', False), fumble=result.get('is_fumble', False)
        )
        session.game_state.log_dice_roll(roll)
        send_system(f"🎲 {result['description']}")
        update_state()


def _handle_condition(args, session, send_system, update_state):
    if len(args) < 3:
        send_system("Usage: /condition add|remove <name> <condition>")
        return
    action, name, condition = args[0].lower(), args[1], args[2]
    entity = None
    for char in session.game_state.characters:
        if char.name.lower() == name.lower():
            entity = char
            break
    if not entity:
        for monster in session.game_state.monsters:
            if monster.name.lower() == name.lower():
                entity = monster
                break
    if not entity:
        send_system(f"Character or monster '{name}' not found")
        return
    if action == 'add':
        if condition not in entity.conditions:
            entity.conditions.append(condition)
            send_system(f"Added condition '{condition}' to {name}")
    elif action == 'remove':
        if condition in entity.conditions:
            entity.conditions.remove(condition)
            send_system(f"Removed condition '{condition}' from {name}")
    update_state()


def _handle_spawn(args, session, send_system, emit_fn, socketio):
    if len(args) < 1:
        send_system("Usage: /spawn <monster_type> [x] [y]")
        send_system("Available types: goblin, orc, dragon, skeleton, wolf, spider")
        return
    monster_name = args[0].lower()
    position = None
    if len(args) >= 3:
        try:
            position = (float(args[1]), float(args[2]))
        except ValueError:
            send_system("Invalid coordinates. Using default position.")
    success = session.spawn_monster(monster_name, position)
    if success:
        send_system(f"Spawned {monster_name}!")
        if session.spatial_agent:
            entities = session.spatial_agent.get_entities_in_location(
                location_id='tavern_main', scale_filter=False
            )
            emit_fn('map_update', {
                'location_id': 'tavern_main',
                'entities': entities,
                'bbox': {'min_x': 0, 'max_x': 10, 'min_y': 0, 'max_y': 10}
            })
    else:
        send_system(f"Failed to spawn {monster_name}")


def _handle_stats(session, send_system):
    if not session.workflow:
        send_system("Workflow system not enabled.")
        return
    stats = get_workflow_stats(session.workflow)
    stats_text = (
        f"Learning Workflow Statistics:\n\n"
        f"Active Patterns:     {stats['active_patterns']}\n"
        f"Pending Approval:    {stats['pending_patterns']}\n"
        f"Total Activations:   {stats['total_activations']}\n"
        f"Successful Uses:     {stats['total_successes']}\n"
        f"Success Rate:        {stats['success_rate']:.1%}\n\n"
        f"Learning Enabled:    {stats['learning_enabled']}\n"
        f"Auto-Approve:        {stats['auto_approve']}"
    )
    send_system(stats_text)


def _send_help(send_system):
    help_text = """Available Commands:
/add char <name> <class> <level> <hp> <ac> - Add character
/add monster <name> <hp> <ac> <cr> - Add monster
/spawn <type> [x] [y] - Spawn monster with spatial positioning
/combat start|end - Start/end combat
/init <name> <roll> - Set initiative
/next - Next turn
/damage <name> <amount> - Apply damage
/heal <name> <amount> - Heal character
/roll <notation> - Roll dice
/condition add|remove <name> <condition> - Manage conditions
/stats - Show learning workflow statistics
/clear - Clear chat
/help - Show this help"""
    send_system(help_text)
