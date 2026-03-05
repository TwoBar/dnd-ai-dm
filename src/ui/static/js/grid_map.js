/**
 * Grid-Based Tile Map System
 *
 * Subsystems:
 *   A. TileRegistry    — maps tile type IDs to render functions
 *   B. GridState        — converts map_state into a layered 2D grid
 *   C. Camera           — zoom / pan / viewport math
 *   D. RenderPipeline   — layer-based canvas rendering with viewport culling
 *   E. ProceduralTiles  — draws individual tile types
 *   F. InteractionMgr   — hover tooltips, drag-to-pan, scroll-to-zoom
 *
 * Future: TileRegistry.loadSpriteSheet(img, manifest) swaps procedural
 *         renderers with sprite-based ctx.drawImage() calls.
 */

const GridMap = (() => {
    // ========================================================================
    // CONSTANTS
    // ========================================================================
    const GRID_COLS = 20;
    const GRID_ROWS = 20;
    const MAX_CANVAS_PX = 600;

    const ZOOM_MIN = 1.0;
    const ZOOM_MAX = 4.0;
    const ZOOM_STEP = 0.15;        // per wheel tick
    const ZOOM_BTN_STEP = 0.4;     // per button click

    // Dark-fantasy colour palette
    const PAL = {
        bg:            '#1a1a2e',
        floorWood:     '#3b2f1e',
        floorPlank:    '#4a3a28',
        wallStone:     '#2c2c3a',
        wallLine:      '#1e1e2a',
        wallHighlight: '#3d3d50',
        doorFrame:     '#8b6914',
        doorFloor:     '#4a3a28',
        grid:          'rgba(255,255,255,0.06)',
        labelShadow:   '#000',
        playerOwn:     '#4a9eff',
        playerOther:   '#44cc44',
        monster:       '#ff4444',
        monsterDark:   '#991111',
        furniture:     '#7a6840',
        white:         '#fff',
        tooltip_bg:    'rgba(20,20,35,0.92)',
        tooltip_fg:    '#e0d8c8',
    };

    // Emoji-to-tile-type mapping for furniture sprite_ids
    const SPRITE_TILE = {
        '\uD83C\uDF7A': 'furniture_bar',
        '\uD83E\uDE91': 'furniture_table',
        '\uD83D\uDD25': 'furniture_fireplace',
        '\uD83D\uDEAA': 'furniture_entrance',
    };

    // ========================================================================
    // A. TILE REGISTRY
    // ========================================================================
    const _renderers = {};

    function registerTile(tileId, renderFn) {
        _renderers[tileId] = renderFn;
    }

    function renderTile(ctx, tileId, x, y, size) {
        const fn = _renderers[tileId];
        if (fn) fn(ctx, x, y, size);
    }

    function loadSpriteSheet(img, manifest) {
        for (const [tileId, rect] of Object.entries(manifest)) {
            _renderers[tileId] = (ctx, x, y, size) => {
                ctx.drawImage(img, rect.x, rect.y, rect.w, rect.h, x, y, size, size);
            };
        }
    }

    // ========================================================================
    // E. PROCEDURAL TILE RENDERERS
    // ========================================================================

    registerTile('floor_wood', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.floorWood;
        ctx.fillRect(x, y, s, s);
        ctx.strokeStyle = PAL.floorPlank;
        ctx.lineWidth = 0.5;
        const third = s / 3;
        for (let i = 1; i < 3; i++) {
            ctx.beginPath();
            ctx.moveTo(x, y + third * i);
            ctx.lineTo(x + s, y + third * i);
            ctx.stroke();
        }
    });

    registerTile('wall_stone', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.wallStone;
        ctx.fillRect(x, y, s, s);
        ctx.strokeStyle = PAL.wallLine;
        ctx.lineWidth = 1;
        const half = s / 2;
        ctx.beginPath(); ctx.moveTo(x, y + half); ctx.lineTo(x + s, y + half); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + half, y); ctx.lineTo(x + half, y + half); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + s * 0.25, y + half); ctx.lineTo(x + s * 0.25, y + s); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + s * 0.75, y + half); ctx.lineTo(x + s * 0.75, y + s); ctx.stroke();
        ctx.strokeStyle = PAL.wallHighlight;
        ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(x, y + 0.5); ctx.lineTo(x + s, y + 0.5); ctx.stroke();
    });

    registerTile('door_open', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.doorFloor;
        ctx.fillRect(x, y, s, s);
        ctx.strokeStyle = PAL.doorFrame;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x + s / 2, y + s * 0.55, s * 0.35, Math.PI, 0);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x + s * 0.15, y + s * 0.55);
        ctx.lineTo(x + s * 0.85, y + s * 0.55);
        ctx.stroke();
    });

    registerTile('furniture_bar', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.floorWood;
        ctx.fillRect(x, y, s, s);
        const pad = s * 0.12;
        ctx.fillStyle = '#5a3e1e';
        ctx.fillRect(x + pad, y + s * 0.3, s - pad * 2, s * 0.4);
        ctx.strokeStyle = '#3a2610';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + pad, y + s * 0.3, s - pad * 2, s * 0.4);
        ctx.fillStyle = '#cca050';
        ctx.beginPath(); ctx.arc(x + s * 0.35, y + s * 0.5, s * 0.08, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(x + s * 0.65, y + s * 0.5, s * 0.08, 0, Math.PI * 2); ctx.fill();
    });

    registerTile('furniture_table', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.floorWood;
        ctx.fillRect(x, y, s, s);
        const pad = s * 0.2;
        ctx.fillStyle = '#6b4f30';
        ctx.fillRect(x + pad, y + pad, s - pad * 2, s - pad * 2);
        ctx.strokeStyle = '#4a3520';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + pad, y + pad, s - pad * 2, s - pad * 2);
        ctx.fillStyle = '#4a3520';
        const legSize = s * 0.06;
        const inset = pad + legSize;
        ctx.fillRect(x + inset - legSize, y + inset - legSize, legSize, legSize);
        ctx.fillRect(x + s - inset, y + inset - legSize, legSize, legSize);
        ctx.fillRect(x + inset - legSize, y + s - inset, legSize, legSize);
        ctx.fillRect(x + s - inset, y + s - inset, legSize, legSize);
    });

    registerTile('furniture_fireplace', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.floorWood;
        ctx.fillRect(x, y, s, s);
        ctx.fillStyle = '#4a4a55';
        const bx = x + s * 0.15, by = y + s * 0.3;
        ctx.fillRect(bx, by, s * 0.7, s * 0.55);
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.strokeRect(bx, by, s * 0.7, s * 0.55);
        const grd = ctx.createRadialGradient(x + s / 2, y + s * 0.55, 0, x + s / 2, y + s * 0.55, s * 0.25);
        grd.addColorStop(0, 'rgba(255,140,20,0.8)');
        grd.addColorStop(0.6, 'rgba(255,80,0,0.3)');
        grd.addColorStop(1, 'rgba(255,40,0,0)');
        ctx.fillStyle = grd;
        ctx.fillRect(x, y, s, s);
    });

    registerTile('furniture_entrance', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.floorWood;
        ctx.fillRect(x, y, s, s);
        ctx.strokeStyle = PAL.doorFrame;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x + s / 2, y + s * 0.6, s * 0.3, Math.PI, 0);
        ctx.lineTo(x + s * 0.8, y + s * 0.85);
        ctx.lineTo(x + s * 0.2, y + s * 0.85);
        ctx.closePath();
        ctx.stroke();
    });

    registerTile('creature_player_own', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.playerOwn;
        ctx.beginPath(); ctx.arc(x + s / 2, y + s / 2, s * 0.38, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = PAL.white; ctx.lineWidth = 1.5; ctx.stroke();
    });

    registerTile('creature_player_other', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.playerOther;
        ctx.beginPath(); ctx.arc(x + s / 2, y + s / 2, s * 0.38, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#aaffaa'; ctx.lineWidth = 1.5; ctx.stroke();
    });

    registerTile('creature_monster', (ctx, x, y, s) => {
        ctx.fillStyle = PAL.monster;
        ctx.beginPath(); ctx.arc(x + s / 2, y + s / 2, s * 0.38, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = PAL.monsterDark; ctx.lineWidth = 1.5; ctx.stroke();
    });

    // ========================================================================
    // B. GRID STATE
    // ========================================================================

    function buildGridState(mapState) {
        const bbox = mapState.bbox || { min_x: 0, max_x: 10, min_y: 0, max_y: 10 };
        const entities    = mapState.entities    || [];
        const walls       = mapState.walls       || [];
        const connections = mapState.connections  || [];

        const worldW = bbox.max_x - bbox.min_x;
        const worldH = bbox.max_y - bbox.min_y;

        const ground   = Array.from({ length: GRID_ROWS }, () => Array(GRID_COLS).fill(null));
        const features = Array.from({ length: GRID_ROWS }, () => Array(GRID_COLS).fill(null));
        const creatures = Array.from({ length: GRID_ROWS }, () => Array(GRID_COLS).fill(null));
        const entityMap = Array.from({ length: GRID_ROWS }, () => Array(GRID_COLS).fill(null));

        const toGrid = (wx, wy) => {
            const col = Math.floor(((wx - bbox.min_x) / worldW) * GRID_COLS);
            const row = Math.floor(((wy - bbox.min_y) / worldH) * GRID_ROWS);
            const flippedRow = GRID_ROWS - 1 - row;
            return [
                Math.max(0, Math.min(GRID_ROWS - 1, flippedRow)),
                Math.max(0, Math.min(GRID_COLS - 1, col)),
            ];
        };

        // 1. Fill ground
        for (let r = 0; r < GRID_ROWS; r++)
            for (let c = 0; c < GRID_COLS; c++)
                ground[r][c] = 'floor_wood';

        // 2. Perimeter walls
        for (let c = 0; c < GRID_COLS; c++) { ground[0][c] = 'wall_stone'; ground[GRID_ROWS - 1][c] = 'wall_stone'; }
        for (let r = 0; r < GRID_ROWS; r++) { ground[r][0] = 'wall_stone'; ground[r][GRID_COLS - 1] = 'wall_stone'; }

        // 3. Wall entities
        walls.forEach(w => {
            const [r, c] = toGrid(w.x, w.y);
            const tw = Math.max(1, Math.round((w.width || 1) / worldW * GRID_COLS));
            const th = Math.max(1, Math.round((w.height || 1) / worldH * GRID_ROWS));
            for (let dr = 0; dr < th; dr++)
                for (let dc = 0; dc < tw; dc++) {
                    const rr = r + dr, cc = c + dc;
                    if (rr >= 0 && rr < GRID_ROWS && cc >= 0 && cc < GRID_COLS)
                        ground[rr][cc] = 'wall_stone';
                }
        });

        // 4. Connections → doors
        connections.forEach(conn => {
            const [r, c] = toGrid(conn.x, conn.y);
            ground[r][c] = 'door_open';
            entityMap[r][c] = { name: conn.label || 'Exit', type: 'door' };
        });

        // 5 & 6. Entities → feature / creature layers
        entities.forEach(ent => {
            const [r, c] = toGrid(ent.x, ent.y);
            const type = (ent.entity_metadata || {}).type || '';

            if (type === 'furniture' || ent.furniture_id) {
                const tileId = SPRITE_TILE[ent.sprite_id] || 'furniture_table';
                features[r][c] = tileId;
                entityMap[r][c] = { name: ent.entity_name, type: 'furniture', sprite: ent.sprite_id };
            } else if (type === 'monster' || (ent.id && ent.id.startsWith('monster_'))) {
                creatures[r][c] = { tileId: 'creature_monster', entity: ent };
                entityMap[r][c] = { name: ent.entity_name, type: 'monster' };
            } else if (type === 'player_character' || ent.creature_id) {
                const tileId = ent.is_own_session !== false ? 'creature_player_own' : 'creature_player_other';
                creatures[r][c] = { tileId, entity: ent };
                entityMap[r][c] = {
                    name: ent.entity_name || ent.creature_id,
                    type: ent.is_own_session !== false ? 'player (you)' : 'player (other)',
                };
            } else if (type === 'feature') {
                features[r][c] = 'wall_stone';
                entityMap[r][c] = { name: ent.entity_name, type: 'feature' };
            }
        });

        return { ground, features, creatures, entityMap, bbox };
    }

    // ========================================================================
    // C. CAMERA — zoom, pan, viewport
    // ========================================================================

    // Camera stores the world-space coordinate of the viewport's top-left corner.
    // At zoom=1 the entire grid fits exactly in the canvas, so cam x/y = 0.
    const _cam = { x: 0, y: 0, zoom: 1.0 };

    let _canvas       = null;
    let _ctx          = null;
    let _tooltip      = null;
    let _baseTileSize = 0;   // tile size at zoom=1 (fits full grid in canvas)
    let _canvasW      = 0;
    let _canvasH      = 0;
    let _currentGS    = null; // latest GridState for hover lookups
    let _lastMapState = null; // latest mapState for re-render after pan/zoom

    // Drag state
    let _dragging   = false;
    let _dragStartX = 0;
    let _dragStartY = 0;
    let _dragCamX   = 0;
    let _dragCamY   = 0;

    /** Clamp camera so the viewport stays within the world bounds. */
    function _clampCam() {
        const worldPx = _baseTileSize * GRID_COLS; // square grid
        const vpW = _canvasW / _cam.zoom;
        const vpH = _canvasH / _cam.zoom;
        const maxX = Math.max(0, worldPx - vpW);
        const maxY = Math.max(0, worldPx - vpH);
        _cam.x = Math.max(0, Math.min(maxX, _cam.x));
        _cam.y = Math.max(0, Math.min(maxY, _cam.y));
    }

    /** Convert screen px → grid row, col (accounting for camera). */
    function _screenToGrid(sx, sy) {
        const worldX = sx / _cam.zoom + _cam.x;
        const worldY = sy / _cam.zoom + _cam.y;
        const col = Math.floor(worldX / _baseTileSize);
        const row = Math.floor(worldY / _baseTileSize);
        return [row, col];
    }

    /** Return the grid (row, col) of the player's own character, or null. */
    function _findOwnPlayer() {
        if (!_currentGS) return null;
        for (let r = 0; r < GRID_ROWS; r++)
            for (let c = 0; c < GRID_COLS; c++) {
                const cell = _currentGS.creatures[r][c];
                if (cell && cell.tileId === 'creature_player_own') return [r, c];
            }
        return null;
    }

    // ========================================================================
    // D. RENDER PIPELINE — with viewport culling
    // ========================================================================

    function init() {
        _canvas = document.getElementById('spatial-map');
        if (!_canvas) return;
        _ctx = _canvas.getContext('2d');

        // Tooltip
        _tooltip = document.createElement('div');
        _tooltip.id = 'grid-map-tooltip';
        _tooltip.style.display = 'none';
        _canvas.parentElement.appendChild(_tooltip);

        // Zoom controls
        _buildControls();

        // --- Event listeners ---
        _canvas.addEventListener('wheel',     _onWheel,     { passive: false });
        _canvas.addEventListener('mousedown',  _onDragStart);
        _canvas.addEventListener('mousemove',  _onMouseMove);
        _canvas.addEventListener('mouseup',    _onDragEnd);
        _canvas.addEventListener('mouseleave', _onDragEnd);
        // Touch support
        _canvas.addEventListener('touchstart', _onTouchStart, { passive: false });
        _canvas.addEventListener('touchmove',  _onTouchMove,  { passive: false });
        _canvas.addEventListener('touchend',   _onTouchEnd);
    }

    /** Create +/−/center buttons above the canvas. */
    function _buildControls() {
        const bar = document.createElement('div');
        bar.id = 'grid-map-controls';

        const btnZoomIn  = _btn('+',  'Zoom in',          () => { _zoomBy(ZOOM_BTN_STEP); _rerender(); });
        const btnZoomOut = _btn('−', 'Zoom out',          () => { _zoomBy(-ZOOM_BTN_STEP); _rerender(); });
        const btnCenter  = _btn('⊕', 'Center on player', () => { centerOnPlayer(); _rerender(); });
        const btnFit     = _btn('⊞', 'Fit whole map',    () => { resetView(); _rerender(); });

        bar.append(btnZoomIn, btnZoomOut, btnCenter, btnFit);
        _canvas.parentElement.insertBefore(bar, _canvas);
    }

    function _btn(label, title, onClick) {
        const b = document.createElement('button');
        b.className = 'grid-map-btn';
        b.textContent = label;
        b.title = title;
        b.addEventListener('click', onClick);
        return b;
    }

    /** Adjust zoom by delta, clamped. Optionally toward a screen-space point. */
    function _zoomBy(delta, pivotX, pivotY) {
        const oldZoom = _cam.zoom;
        _cam.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, _cam.zoom + delta));
        if (_cam.zoom === oldZoom) return;

        // Pivot: keep the world point under the pivot stationary on screen.
        // Default pivot = centre of canvas.
        const px = pivotX !== undefined ? pivotX : _canvasW / 2;
        const py = pivotY !== undefined ? pivotY : _canvasH / 2;

        // World point under pivot before zoom
        const wx = px / oldZoom + _cam.x;
        const wy = py / oldZoom + _cam.y;

        // Adjust camera so same world point stays under pivot
        _cam.x = wx - px / _cam.zoom;
        _cam.y = wy - py / _cam.zoom;
        _clampCam();
    }

    function centerOnPlayer() {
        const pos = _findOwnPlayer();
        if (!pos) return;
        const [r, c] = pos;
        // Centre of this tile in world-px space
        const wx = (c + 0.5) * _baseTileSize;
        const wy = (r + 0.5) * _baseTileSize;
        // Put that point in the centre of the viewport
        const vpW = _canvasW / _cam.zoom;
        const vpH = _canvasH / _cam.zoom;
        _cam.x = wx - vpW / 2;
        _cam.y = wy - vpH / 2;
        _clampCam();
    }

    function resetView() {
        _cam.x = 0;
        _cam.y = 0;
        _cam.zoom = 1.0;
    }

    /** Re-render with the last known mapState (used after pan/zoom). */
    function _rerender() {
        if (_lastMapState) render(_lastMapState);
    }

    function render(mapState) {
        if (!_canvas || !_ctx) init();
        if (!_canvas) return;

        _lastMapState = mapState;

        const container = _canvas.parentElement;
        const containerWidth = container.clientWidth || 400;

        _baseTileSize = Math.floor(Math.min(containerWidth, MAX_CANVAS_PX) / GRID_COLS);
        _canvasW = _baseTileSize * GRID_COLS;
        _canvasH = _baseTileSize * GRID_ROWS;

        _canvas.width  = _canvasW;
        _canvas.height = _canvasH;
        _canvas.style.width  = _canvasW + 'px';
        _canvas.style.height = _canvasH + 'px';

        if (!mapState || !mapState.entities) {
            _ctx.fillStyle = PAL.bg;
            _ctx.fillRect(0, 0, _canvasW, _canvasH);
            _ctx.fillStyle = '#888';
            _ctx.font = '14px sans-serif';
            _ctx.textAlign = 'center';
            _ctx.fillText('No map data', _canvasW / 2, _canvasH / 2);
            _currentGS = null;
            return;
        }

        _clampCam();

        const gs = buildGridState(mapState);
        _currentGS = gs;

        const zoom = _cam.zoom;
        const ts   = _baseTileSize * zoom;  // effective tile size on screen

        // Visible tile range (viewport culling)
        const rMin = Math.max(0, Math.floor(_cam.y / _baseTileSize));
        const rMax = Math.min(GRID_ROWS - 1, Math.floor((_cam.y + _canvasH / zoom) / _baseTileSize));
        const cMin = Math.max(0, Math.floor(_cam.x / _baseTileSize));
        const cMax = Math.min(GRID_COLS - 1, Math.floor((_cam.x + _canvasW / zoom) / _baseTileSize));

        // Clear
        _ctx.fillStyle = PAL.bg;
        _ctx.fillRect(0, 0, _canvasW, _canvasH);

        // Helper: grid cell → screen px
        const sx = (c) => (c * _baseTileSize - _cam.x) * zoom;
        const sy = (r) => (r * _baseTileSize - _cam.y) * zoom;

        // Layer 1: Ground
        for (let r = rMin; r <= rMax; r++)
            for (let c = cMin; c <= cMax; c++)
                renderTile(_ctx, gs.ground[r][c] || 'floor_wood', sx(c), sy(r), ts);

        // Layer 2: Features
        for (let r = rMin; r <= rMax; r++)
            for (let c = cMin; c <= cMax; c++) {
                const tile = gs.features[r][c];
                if (tile) renderTile(_ctx, tile, sx(c), sy(r), ts);
            }

        // Layer 3: Creatures
        for (let r = rMin; r <= rMax; r++)
            for (let c = cMin; c <= cMax; c++) {
                const cell = gs.creatures[r][c];
                if (!cell) continue;
                const px = sx(c), py = sy(r);
                renderTile(_ctx, cell.tileId, px, py, ts);

                // Initial letter
                const ent = cell.entity;
                const initial = (ent.entity_name || ent.creature_id || '?')[0].toUpperCase();
                _ctx.fillStyle = PAL.white;
                _ctx.font = `bold ${Math.floor(ts * 0.45)}px Arial`;
                _ctx.textAlign = 'center';
                _ctx.textBaseline = 'middle';
                _ctx.fillText(initial, px + ts / 2, py + ts / 2);
            }

        // Layer 4: Grid overlay
        _ctx.strokeStyle = PAL.grid;
        _ctx.lineWidth = 1;
        for (let r = rMin; r <= rMax + 1; r++) {
            const y = sy(r);
            _ctx.beginPath(); _ctx.moveTo(0, y); _ctx.lineTo(_canvasW, y); _ctx.stroke();
        }
        for (let c = cMin; c <= cMax + 1; c++) {
            const x = sx(c);
            _ctx.beginPath(); _ctx.moveTo(x, 0); _ctx.lineTo(x, _canvasH); _ctx.stroke();
        }

        // Layer 5: Creature name labels
        _ctx.textAlign = 'center';
        _ctx.textBaseline = 'top';
        for (let r = rMin; r <= rMax; r++)
            for (let c = cMin; c <= cMax; c++) {
                const cell = gs.creatures[r][c];
                if (!cell) continue;
                const ent = cell.entity;
                const name = ent.entity_name || ent.creature_id;
                if (!name) continue;
                const px = sx(c) + ts / 2;
                const py = sy(r) + ts * 0.78;
                const fontSize = Math.max(8, Math.floor(ts * 0.3));
                _ctx.font = `bold ${fontSize}px sans-serif`;
                _ctx.strokeStyle = PAL.labelShadow;
                _ctx.lineWidth = 2.5;
                _ctx.strokeText(name, px, py);
                const isMonster = cell.tileId === 'creature_monster';
                const isOwn     = cell.tileId === 'creature_player_own';
                _ctx.fillStyle = isMonster ? PAL.monster : isOwn ? PAL.playerOwn : PAL.playerOther;
                _ctx.fillText(name, px, py);
            }

        // Zoom indicator (only when zoomed in)
        if (_cam.zoom > 1.05) {
            _ctx.save();
            _ctx.fillStyle = 'rgba(255,255,255,0.5)';
            _ctx.font = '11px sans-serif';
            _ctx.textAlign = 'right';
            _ctx.textBaseline = 'bottom';
            _ctx.fillText(`${Math.round(_cam.zoom * 100)}%`, _canvasW - 6, _canvasH - 4);
            _ctx.restore();
        }

        _updateInfoBar(mapState, gs);
    }

    function _updateInfoBar(mapState, gs) {
        const info = document.getElementById('map-info');
        if (!info) return;

        let players = 0, monsters = 0, furnitureCount = 0;
        for (let r = 0; r < GRID_ROWS; r++)
            for (let c = 0; c < GRID_COLS; c++) {
                if (gs.creatures[r][c]) {
                    if (gs.creatures[r][c].tileId === 'creature_monster') monsters++;
                    else players++;
                }
                if (gs.features[r][c]) furnitureCount++;
            }

        const loc = mapState.location_id || 'Unknown';
        info.textContent = `${loc} | Players: ${players} | Monsters: ${monsters} | Furniture: ${furnitureCount}`;
    }

    // ========================================================================
    // F. INTERACTION MANAGER — wheel zoom, drag pan, hover tooltip, touch
    // ========================================================================

    function _onWheel(e) {
        e.preventDefault();
        const rect = _canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
        _zoomBy(delta, mx, my);
        _rerender();
    }

    function _onDragStart(e) {
        // Left button only
        if (e.button !== 0) return;
        _dragging   = true;
        _dragStartX = e.clientX;
        _dragStartY = e.clientY;
        _dragCamX   = _cam.x;
        _dragCamY   = _cam.y;
        _canvas.style.cursor = 'grabbing';
        e.preventDefault();
    }

    function _onMouseMove(e) {
        if (_dragging) {
            const dx = e.clientX - _dragStartX;
            const dy = e.clientY - _dragStartY;
            _cam.x = _dragCamX - dx / _cam.zoom;
            _cam.y = _dragCamY - dy / _cam.zoom;
            _clampCam();
            _rerender();
            _tooltip.style.display = 'none';
            return;
        }

        // Hover tooltip
        if (!_currentGS || !_baseTileSize || !_tooltip) return;

        const rect = _canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const [row, col] = _screenToGrid(mx, my);

        if (row < 0 || row >= GRID_ROWS || col < 0 || col >= GRID_COLS) {
            _tooltip.style.display = 'none';
            return;
        }

        const eInfo = _currentGS.entityMap[row][col];
        if (!eInfo) {
            _tooltip.style.display = 'none';
            return;
        }

        _tooltip.textContent = `${eInfo.name} (${eInfo.type})`;
        _tooltip.style.display = 'block';

        const containerRect = _canvas.parentElement.getBoundingClientRect();
        let tx = e.clientX - containerRect.left + 12;
        let ty = e.clientY - containerRect.top - 28;
        const ttW = _tooltip.offsetWidth;
        if (tx + ttW > containerRect.width) tx = containerRect.width - ttW - 4;
        if (ty < 0) ty = 4;
        _tooltip.style.left = tx + 'px';
        _tooltip.style.top  = ty + 'px';
    }

    function _onDragEnd() {
        if (_dragging) {
            _dragging = false;
            _canvas.style.cursor = '';
        }
    }

    // --- Touch support (single-finger pan, pinch zoom) ---
    let _touches = [];
    let _pinchDist = 0;

    function _onTouchStart(e) {
        e.preventDefault();
        _touches = Array.from(e.touches);
        if (_touches.length === 1) {
            _dragging   = true;
            _dragStartX = _touches[0].clientX;
            _dragStartY = _touches[0].clientY;
            _dragCamX   = _cam.x;
            _dragCamY   = _cam.y;
        } else if (_touches.length === 2) {
            _dragging = false;
            _pinchDist = _touchDist(_touches[0], _touches[1]);
        }
    }

    function _onTouchMove(e) {
        e.preventDefault();
        const ts = Array.from(e.touches);

        if (ts.length === 1 && _dragging) {
            const dx = ts[0].clientX - _dragStartX;
            const dy = ts[0].clientY - _dragStartY;
            _cam.x = _dragCamX - dx / _cam.zoom;
            _cam.y = _dragCamY - dy / _cam.zoom;
            _clampCam();
            _rerender();
        } else if (ts.length === 2) {
            const newDist = _touchDist(ts[0], ts[1]);
            if (_pinchDist > 0) {
                const ratio = newDist / _pinchDist;
                const rect = _canvas.getBoundingClientRect();
                const mx = (ts[0].clientX + ts[1].clientX) / 2 - rect.left;
                const my = (ts[0].clientY + ts[1].clientY) / 2 - rect.top;
                const delta = (ratio - 1) * _cam.zoom * 0.5;
                _zoomBy(delta, mx, my);
                _rerender();
            }
            _pinchDist = newDist;
        }
    }

    function _onTouchEnd(e) {
        _touches = Array.from(e.touches);
        if (_touches.length < 2) _pinchDist = 0;
        if (_touches.length === 0) _dragging = false;
    }

    function _touchDist(a, b) {
        const dx = a.clientX - b.clientX;
        const dy = a.clientY - b.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    // ========================================================================
    // PUBLIC API
    // ========================================================================
    return { init, render, loadSpriteSheet, centerOnPlayer, resetView };
})();
