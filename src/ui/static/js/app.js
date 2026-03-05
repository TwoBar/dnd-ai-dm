// Socket.IO connection
const socket = io();

// DOM elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.querySelector('.btn-send');
const sessionPicker = document.getElementById('session-picker');

// Session management
let currentSessionId = localStorage.getItem('dnd_session_id');
let isProcessing = false;

// ============================================================================
// CONNECTION & SESSION FLOW
// ============================================================================

socket.on('connect', () => {
    console.log('Connected to server');
    if (currentSessionId) {
        // Try to resume the stored session
        socket.emit('resume_session', { session_id: currentSessionId });
    } else {
        // No stored session — ask server for available sessions
        socket.emit('list_sessions', {});
    }
});

socket.on('session_ready', (data) => {
    currentSessionId = data.session_id;
    localStorage.setItem('dnd_session_id', currentSessionId);
    // Hide picker, show game
    sessionPicker.classList.add('hidden');
    // Show change session button
    const changeBtn = document.getElementById('change-session-btn');
    if (changeBtn) changeBtn.style.display = '';
    console.log('Session ready:', currentSessionId);
});

socket.on('session_list', (data) => {
    console.log('Received session_list:', data);
    showSessionPicker(data.sessions || []);
});

// Server says our stored session_id is stale — clear it
socket.on('session_expired', (data) => {
    console.log('Session expired:', data.session_id);
    localStorage.removeItem('dnd_session_id');
    currentSessionId = null;
});

// When server signals processing is complete
socket.on('processing_done', () => {
    setProcessing(false);
});

// ============================================================================
// SESSION PICKER
// ============================================================================

function showSessionPicker(sessions) {
    const listDiv = document.getElementById('session-list');
    listDiv.innerHTML = '';
    sessionPicker.classList.remove('hidden');

    // Clear chat from any previous session
    chatMessages.innerHTML = '';

    if (sessions.length === 0) {
        listDiv.innerHTML = '<div class="no-sessions">No previous adventures found. Start a new one!</div>';
        return;
    }

    sessions.forEach(s => {
        const card = document.createElement('div');
        card.className = 'session-card';
        const lastPlayed = s.last_played ? new Date(s.last_played).toLocaleString() : 'Unknown';
        const online = s.players_online || 0;
        const onlineBadge = online > 0
            ? `<span class="online-badge">${online} player${online > 1 ? 's' : ''} online</span>`
            : `<span class="offline-badge">No players online</span>`;
        card.innerHTML = `
            <div class="session-card-header">
                <div class="session-card-name">${s.characters || 'Empty session'}</div>
                ${onlineBadge}
            </div>
            <div class="session-card-chars">${s.classes || ''}</div>
            <div class="session-card-time">Last played: ${lastPlayed}</div>
        `;
        card.addEventListener('click', () => {
            socket.emit('select_session', { session_id: s.session_id });
        });
        listDiv.appendChild(card);
    });
}

function createNewSession() {
    // Clear old session ID so we get a fresh one
    localStorage.removeItem('dnd_session_id');
    currentSessionId = null;
    chatMessages.innerHTML = '';
    console.log('Creating new session...');
    socket.emit('new_session', {});

    // Timeout fallback: if no session_ready within 15s, show error
    setTimeout(() => {
        if (!currentSessionId) {
            console.error('New session timed out');
            const listDiv = document.getElementById('session-list');
            listDiv.innerHTML = '<div class="no-sessions" style="color:#dc3545;">Session creation timed out. Check the server logs.</div>';
        }
    }, 15000);
}

function changeSession() {
    // Leave current session gracefully
    if (currentSessionId) {
        socket.emit('leave_session', { session_id: currentSessionId });
    }
    localStorage.removeItem('dnd_session_id');
    currentSessionId = null;
    chatMessages.innerHTML = '';
    // Hide change session button
    const changeBtn = document.getElementById('change-session-btn');
    if (changeBtn) changeBtn.style.display = 'none';
    // Show session picker
    socket.emit('list_sessions', {});
}

// ============================================================================
// INPUT DEBOUNCE
// ============================================================================

function setProcessing(processing) {
    isProcessing = processing;
    messageInput.disabled = processing;
    sendBtn.disabled = processing;
    if (!processing) {
        messageInput.focus();
    }
}

// ============================================================================
// MESSAGING
// ============================================================================

// Receive new message
socket.on('new_message', (msg) => {
    addMessage(msg);
    scrollToBottom();
});

// Receive game state update
socket.on('game_state', (state) => {
    updateGameState(state);
});

// Receive map update
socket.on('map_update', (mapState) => {
    console.log('[Map] Received map update:', mapState);
    updateSpatialMap(mapState);
});

// Clear messages
socket.on('clear_messages', () => {
    chatMessages.innerHTML = '';
});

// Send message
function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isProcessing) return;

    setProcessing(true);
    socket.emit('send_message', { message: message });
    messageInput.value = '';
}

// Add message to chat
function addMessage(msg) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${msg.type}`;

    const timestamp = new Date(msg.timestamp).toLocaleTimeString();

    messageDiv.innerHTML = `
        <div class="message-timestamp">${timestamp}</div>
        <div class="message-speaker">${getMessageIcon(msg.speaker)} ${msg.speaker}</div>
        <div class="message-content">${escapeHtml(msg.message)}</div>
    `;

    chatMessages.appendChild(messageDiv);
}

// Get message icon
function getMessageIcon(speaker) {
    const icons = {
        'You': '🧙',
        'DM': '🎲',
        'System': '⚙️'
    };
    return icons[speaker] || '💬';
}

// Update game state
function updateGameState(state) {
    updateCharacters(state.characters);
    updateMonsters(state.monsters);
    updateCombat(state.combat);
    updateDiceLog(state.dice_rolls);
    updateCacheStats(state.stats);
}

// Update characters list
function updateCharacters(characters) {
    const container = document.getElementById('characters-list');

    if (characters.length === 0) {
        container.innerHTML = '<div style="color: #999; font-size: 13px;">No characters</div>';
        return;
    }

    container.innerHTML = '<h4 style="font-size: 14px; margin-bottom: 8px;">👥 Party</h4>';

    characters.forEach(char => {
        const hpPercent = (char.hp / char.max_hp) * 100;
        const hpClass = hpPercent > 50 ? 'hp-healthy' : hpPercent > 25 ? 'hp-wounded' : 'hp-critical';

        const div = document.createElement('div');
        div.className = 'entity-item';
        div.innerHTML = `
            <div class="entity-name">${char.name}</div>
            <div class="entity-stats">
                Lvl ${char.level} ${char.class} | HP: ${char.hp}/${char.max_hp} | AC: ${char.ac}
            </div>
            <div class="hp-bar">
                <div class="hp-fill ${hpClass}" style="width: ${hpPercent}%"></div>
            </div>
            ${char.conditions.length > 0 ? `<div style="font-size: 12px; color: #dc3545;">[${char.conditions.join(', ')}]</div>` : ''}
        `;
        container.appendChild(div);
    });
}

// Update monsters list
function updateMonsters(monsters) {
    const container = document.getElementById('monsters-list');

    if (monsters.length === 0) {
        container.innerHTML = '<div style="color: #999; font-size: 13px; margin-top: 15px;">No monsters</div>';
        return;
    }

    container.innerHTML = '<h4 style="font-size: 14px; margin: 15px 0 8px 0;">⚔️ Enemies</h4>';

    monsters.forEach(monster => {
        const hpPercent = (monster.hp / monster.max_hp) * 100;
        const hpClass = hpPercent > 50 ? 'hp-healthy' : hpPercent > 25 ? 'hp-wounded' : 'hp-critical';

        const div = document.createElement('div');
        div.className = 'entity-item monster';
        div.innerHTML = `
            <div class="entity-name">${monster.name}</div>
            <div class="entity-stats">
                CR ${monster.cr} | HP: ${monster.hp}/${monster.max_hp} | AC: ${monster.ac}
            </div>
            <div class="hp-bar">
                <div class="hp-fill ${hpClass}" style="width: ${hpPercent}%"></div>
            </div>
            ${monster.conditions.length > 0 ? `<div style="font-size: 12px; color: #dc3545;">[${monster.conditions.join(', ')}]</div>` : ''}
        `;
        container.appendChild(div);
    });
}

// Update combat status
function updateCombat(combat) {
    const statusDiv = document.getElementById('combat-status');
    const initiativeDiv = document.getElementById('initiative-order');

    if (!combat.active) {
        statusDiv.textContent = 'Not in combat';
        statusDiv.className = '';
        initiativeDiv.innerHTML = '';
        return;
    }

    statusDiv.textContent = `Round ${combat.round} | Turn: ${combat.current_turn || 'Roll initiative'}`;
    statusDiv.className = 'active';

    // Initiative order
    initiativeDiv.innerHTML = '';
    combat.initiative_order.forEach(([name, init, type]) => {
        const div = document.createElement('div');
        div.className = 'init-item' + (name === combat.current_turn ? ' current-turn' : '');
        div.innerHTML = `
            <span>${name === combat.current_turn ? '→ ' : ''}${name}</span>
            <span class="init-number">${init}</span>
        `;
        initiativeDiv.appendChild(div);
    });
}

// Update dice log
function updateDiceLog(rolls) {
    const container = document.getElementById('dice-log');

    if (rolls.length === 0) {
        container.innerHTML = '<div style="color: #999; font-size: 13px;">No rolls yet</div>';
        return;
    }

    container.innerHTML = '';

    rolls.slice(-10).reverse().forEach(roll => {
        const div = document.createElement('div');
        let className = 'dice-roll';
        if (roll.critical) className += ' critical';
        if (roll.fumble) className += ' fumble';

        div.className = className;

        const icon = roll.critical ? '🎉' : roll.fumble ? '💀' : '🎲';
        const time = new Date(roll.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        div.innerHTML = `
            <div class="dice-timestamp">${time}</div>
            ${icon} ${roll.notation} = ${roll.result}
            ${roll.critical ? ' [CRIT!]' : roll.fumble ? ' [FUMBLE!]' : ''}
        `;
        container.appendChild(div);
    });
}

// Update cache stats
function updateCacheStats(stats) {
    const container = document.getElementById('cache-stats');
    container.innerHTML = `
        <div style="margin-bottom: 4px;">Cache Hit Rate: <strong>${stats.cache_hit_rate}</strong></div>
        <div>Characters: <strong>${stats.total_characters}</strong> | Monsters: <strong>${stats.total_monsters}</strong></div>
    `;
}

// Helper functions
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function insertCommand(command) {
    messageInput.value = command;
    messageInput.focus();
}

function clearChat() {
    if (confirm('Clear all messages?')) {
        socket.emit('send_message', { message: '/clear' });
    }
}

// Enter key to send
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Auto-focus input on load & initialise grid map
window.addEventListener('load', () => {
    messageInput.focus();
    GridMap.init();
});

// ============================================================================
// SPATIAL MAP RENDERING — delegated to GridMap (grid_map.js)
// ============================================================================

function updateSpatialMap(mapState) {
    console.log('[Map] updateSpatialMap called with:', mapState);
    GridMap.render(mapState);
}
