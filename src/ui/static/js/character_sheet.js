/**
 * Character Sheet Client-Side Logic
 *
 * Handles:
 * - Opening/closing character sheet modal
 * - Tab switching
 * - SocketIO communication for real-time updates
 * - Modifier breakdown display
 */

// Current character data
let currentCharacter = null;

/**
 * Open character sheet for a specific entity
 */
function openCharacterSheet(entityId) {
    // Show modal
    document.getElementById('characterSheetModal').style.display = 'flex';

    // Request character data from server
    if (typeof socket !== 'undefined') {
        socket.emit('get_character_sheet', { entity_id: entityId });
    } else {
        console.error('Socket not available');
        // Load mock data for testing
        loadMockCharacterData();
    }
}

/**
 * Close character sheet modal
 */
function closeCharacterSheet() {
    document.getElementById('characterSheetModal').style.display = 'none';
    currentCharacter = null;
}

/**
 * Switch between tabs
 */
function switchTab(tabName) {
    // Hide all tabs
    const tabs = document.querySelectorAll('.tab-pane');
    tabs.forEach(tab => tab.classList.remove('active'));

    // Deactivate all tab buttons
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => btn.classList.remove('active'));

    // Show selected tab
    const selectedTab = document.getElementById(tabName + 'Tab');
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activate corresponding button
    const btnIndex = tabName === 'core' ? 0 : tabName === 'combat' ? 1 : 2;
    if (tabBtns[btnIndex]) {
        tabBtns[btnIndex].classList.add('active');
    }
}

/**
 * Update character sheet with data from server
 */
function updateCharacterSheet(data) {
    currentCharacter = data;

    // Update header
    document.getElementById('characterName').textContent = data.name || 'Character Sheet';
    document.getElementById('characterTitle').textContent =
        `Level ${data.level || 1} ${data.class || 'Adventurer'}`;

    // Update HP
    const hp = data.hp || 0;
    const maxHp = data.max_hp || 1;
    document.getElementById('hpDisplay').textContent = `${hp} / ${maxHp}`;
    const hpPercent = (hp / maxHp) * 100;
    document.getElementById('hpBar').style.width = `${hpPercent}%`;

    // Update basic stats
    document.getElementById('acDisplay').textContent = data.ac || '10';
    document.getElementById('initiativeDisplay').textContent = formatBonus(data.initiative_mod || data.dex_mod || 0);
    document.getElementById('proficiencyDisplay').textContent = formatBonus(data.proficiency_bonus || 2);

    // Update ability scores
    if (data.abilities) {
        ['str', 'dex', 'con', 'int', 'wis', 'cha'].forEach(ability => {
            const score = data.abilities[ability] || 10;
            const mod = Math.floor((score - 10) / 2);
            document.getElementById(ability + 'Score').textContent = score;
            document.getElementById(ability + 'Mod').textContent = formatBonus(mod);
        });
    }

    // Update combat stats
    if (data.spell_save_dc) {
        document.getElementById('spellSaveDC').textContent = data.spell_save_dc.total || '--';
    }
    if (data.spell_attack_bonus) {
        document.getElementById('spellAttack').textContent = formatBonus(data.spell_attack_bonus.total || 0);
    }
    if (data.melee_attack_bonus) {
        document.getElementById('meleeAttack').textContent = formatBonus(data.melee_attack_bonus.total || 0);
    }
    if (data.ranged_attack_bonus) {
        document.getElementById('rangedAttack').textContent = formatBonus(data.ranged_attack_bonus.total || 0);
    }

    // Update conditions
    updateConditions(data.conditions || []);

    // Update proficiencies
    updateProficiencies(data.proficiencies || []);

    // Update equipment
    updateEquipment(data.equipment || []);

    // Update inventory
    updateInventory(data.inventory || []);

    // Update currency
    if (data.currency) {
        document.getElementById('copper').textContent = data.currency.copper || 0;
        document.getElementById('silver').textContent = data.currency.silver || 0;
        document.getElementById('electrum').textContent = data.currency.electrum || 0;
        document.getElementById('gold').textContent = data.currency.gold || 0;
        document.getElementById('platinum').textContent = data.currency.platinum || 0;
    }

    // Update spell slots
    updateSpellSlots(data.spell_slots || {});

    // Update spells
    updateSpells(data.spells || []);

    // Update class features
    updateFeatures(data.class_features || []);

    // Update class resources
    updateResources(data.class_resources || {});
}

/**
 * Format number as bonus (+2, -1, etc.)
 */
function formatBonus(value) {
    const num = parseInt(value) || 0;
    return num >= 0 ? `+${num}` : `${num}`;
}

/**
 * Update conditions list
 */
function updateConditions(conditions) {
    const container = document.getElementById('conditionsList');
    if (conditions.length === 0) {
        container.innerHTML = '<span class="no-data">No active conditions</span>';
        return;
    }

    container.innerHTML = conditions.map(c =>
        `<span class="condition-badge">${c.name || c}</span>`
    ).join('');
}

/**
 * Update proficiencies list
 */
function updateProficiencies(proficiencies) {
    const container = document.getElementById('proficienciesList');
    if (proficiencies.length === 0) {
        container.innerHTML = '<span class="no-data">No proficiencies</span>';
        return;
    }

    container.innerHTML = proficiencies.map(p =>
        `<span class="proficiency-badge">${p.name || p}</span>`
    ).join('');
}

/**
 * Update equipped items
 */
function updateEquipment(equipment) {
    const container = document.getElementById('equippedItems');
    if (equipment.length === 0) {
        container.innerHTML = '<span class="no-data">No equipped items</span>';
        return;
    }

    container.innerHTML = equipment.map(item =>
        `<span class="item-badge">${item.name || item}</span>`
    ).join('');
}

/**
 * Update inventory
 */
function updateInventory(inventory) {
    const container = document.getElementById('inventoryList');
    if (inventory.length === 0) {
        container.innerHTML = '<span class="no-data">Empty inventory</span>';
        return;
    }

    container.innerHTML = inventory.map(item =>
        `<span class="item-badge">${item.name || item} ${item.quantity ? `(${item.quantity})` : ''}</span>`
    ).join('');
}

/**
 * Update spell slots
 */
function updateSpellSlots(spellSlots) {
    const container = document.getElementById('spellSlots');

    if (Object.keys(spellSlots).length === 0) {
        container.innerHTML = '<span class="no-data">No spell slots</span>';
        return;
    }

    let html = '';
    for (let level = 1; level <= 9; level++) {
        const slots = spellSlots[level];
        if (slots && slots.total > 0) {
            const used = slots.used || 0;
            const available = slots.total - used;

            html += '<div class="spell-slot-level">';
            html += `<span class="spell-slot-label">Level ${level}:</span>`;
            html += '<div class="spell-slot-dots">';

            for (let i = 0; i < slots.total; i++) {
                const className = i < available ? 'available' : 'used';
                html += `<div class="spell-slot-dot ${className}"></div>`;
            }

            html += '</div>';
            html += `<span class="spell-slot-count">${available}/${slots.total}</span>`;
            html += '</div>';
        }
    }

    container.innerHTML = html || '<span class="no-data">No spell slots</span>';
}

/**
 * Update spells list
 */
function updateSpells(spells) {
    const cantripsContainer = document.getElementById('cantripsList');
    const spellsContainer = document.getElementById('spellsList');

    const cantrips = spells.filter(s => s.level === 0);
    const leveled = spells.filter(s => s.level > 0);

    // Cantrips
    if (cantrips.length === 0) {
        cantripsContainer.innerHTML = '<span class="no-data">No cantrips</span>';
    } else {
        cantripsContainer.innerHTML = cantrips.map(s =>
            `<span class="spell-badge">${s.name}</span>`
        ).join('');
    }

    // Leveled spells
    if (leveled.length === 0) {
        spellsContainer.innerHTML = '<span class="no-data">No spells known</span>';
    } else {
        let html = '';
        for (let level = 1; level <= 9; level++) {
            const levelSpells = leveled.filter(s => s.level === level);
            if (levelSpells.length > 0) {
                html += `<div class="spell-level-group">`;
                html += `<h5>Level ${level}</h5>`;
                html += levelSpells.map(s => `<span class="spell-badge">${s.name}</span>`).join('');
                html += `</div>`;
            }
        }
        spellsContainer.innerHTML = html;
    }
}

/**
 * Update class features
 */
function updateFeatures(features) {
    const container = document.getElementById('featuresList');
    if (features.length === 0) {
        container.innerHTML = '<span class="no-data">No class features</span>';
        return;
    }

    container.innerHTML = features.map(f =>
        `<span class="feature-badge">${f.name || f}</span>`
    ).join('');
}

/**
 * Update class resources
 */
function updateResources(resources) {
    const container = document.getElementById('resourcesList');

    if (Object.keys(resources).length === 0) {
        container.innerHTML = '<span class="no-data">No class resources</span>';
        return;
    }

    let html = '';
    for (const [name, data] of Object.entries(resources)) {
        const current = data.current || data.remaining || 0;
        const max = data.max || data.total || 0;
        html += `<span class="resource-badge">${name}: ${current}/${max}</span>`;
    }

    container.innerHTML = html;
}

/**
 * Show modifier breakdown for a specific formula
 */
function showModifierBreakdown(formulaName) {
    if (!currentCharacter) {
        return;
    }

    // Show modal
    document.getElementById('modifierBreakdownModal').style.display = 'flex';
    document.getElementById('breakdownTitle').textContent =
        formulaName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

    // Request breakdown from server
    if (typeof socket !== 'undefined') {
        socket.emit('get_modifier_breakdown', {
            entity_id: currentCharacter.id,
            formula: formulaName
        });
    } else {
        // Mock breakdown for testing
        displayModifierBreakdown({
            formula: formulaName,
            total: 14,
            base: 11,
            modifiers: [
                { source: 'Base Calculation', type: 'base', value: 11 },
                { source: 'Proficiency Bonus', type: 'flat', value: 3 },
                { source: 'Charisma Modifier', type: 'flat', value: 0 }
            ]
        });
    }
}

/**
 * Close modifier breakdown modal
 */
function closeModifierBreakdown() {
    document.getElementById('modifierBreakdownModal').style.display = 'none';
}

/**
 * Display modifier breakdown data
 */
function displayModifierBreakdown(data) {
    const container = document.getElementById('breakdownContent');

    let html = '';
    if (data.modifiers && data.modifiers.length > 0) {
        data.modifiers.forEach(mod => {
            html += `<div class="breakdown-item">`;
            html += `<strong>${mod.source}</strong>: `;
            html += mod.type === 'base' ? `${mod.value}` : formatBonus(mod.value);
            html += `</div>`;
        });
    }

    html += `<div class="breakdown-total">Total: ${data.total}</div>`;

    container.innerHTML = html;
}

/**
 * Load mock character data for testing
 */
function loadMockCharacterData() {
    updateCharacterSheet({
        id: 'creature:test-1',
        name: 'Test Character',
        level: 5,
        class: 'Bard',
        hp: 32,
        max_hp: 38,
        ac: 14,
        proficiency_bonus: 3,
        abilities: {
            str: 10,
            dex: 14,
            con: 12,
            int: 13,
            wis: 8,
            cha: 16
        },
        spell_save_dc: { total: 14, base: 14, modifiers: [] },
        spell_attack_bonus: { total: 6, base: 6, modifiers: [] },
        melee_attack_bonus: { total: 3, base: 3, modifiers: [] },
        ranged_attack_bonus: { total: 5, base: 5, modifiers: [] },
        conditions: [],
        proficiencies: ['Acrobatics', 'Deception', 'Performance', 'Persuasion'],
        equipment: ['Rapier', 'Leather Armor', 'Lute'],
        inventory: [],
        currency: { copper: 0, silver: 0, electrum: 0, gold: 75, platinum: 0 },
        spell_slots: {
            1: { total: 4, used: 0 },
            2: { total: 3, used: 1 },
            3: { total: 2, used: 0 }
        },
        spells: [
            { name: 'Vicious Mockery', level: 0 },
            { name: 'Mage Hand', level: 0 },
            { name: 'Healing Word', level: 1 },
            { name: 'Thunderwave', level: 1 },
            { name: 'Charm Person', level: 1 }
        ],
        class_features: ['Bardic Inspiration', 'Jack of All Trades', 'Song of Rest'],
        class_resources: {
            'Bardic Inspiration': { current: 5, max: 5 }
        }
    });
}

// SocketIO event listeners (if socket is available)
if (typeof socket !== 'undefined') {
    // Character sheet data received
    socket.on('character_sheet_data', function(data) {
        updateCharacterSheet(data);
    });

    // Real-time HP update
    socket.on('hp_updated', function(data) {
        if (currentCharacter && data.entity_id === currentCharacter.id) {
            currentCharacter.hp = data.hp;
            currentCharacter.max_hp = data.max_hp;
            document.getElementById('hpDisplay').textContent = `${data.hp} / ${data.max_hp}`;
            const hpPercent = (data.hp / data.max_hp) * 100;
            document.getElementById('hpBar').style.width = `${hpPercent}%`;
        }
    });

    // Modifier changed
    socket.on('modifier_changed', function(data) {
        if (currentCharacter && data.entity_id === currentCharacter.id) {
            // Refresh character sheet
            socket.emit('get_character_sheet', { entity_id: currentCharacter.id });
        }
    });

    // Modifier breakdown received
    socket.on('modifier_breakdown', function(data) {
        displayModifierBreakdown(data);
    });
}

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCharacterSheet();
        closeModifierBreakdown();
    }
});

// Close modals when clicking outside
document.getElementById('characterSheetModal')?.addEventListener('click', function(e) {
    if (e.target === this) {
        closeCharacterSheet();
    }
});

document.getElementById('modifierBreakdownModal')?.addEventListener('click', function(e) {
    if (e.target === this) {
        closeModifierBreakdown();
    }
});
