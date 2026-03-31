/**
 * Rithmomachia — Canvas 2D Board Renderer & Interaction Handler
 *
 * All game logic lives on the server. This file handles:
 * - Main menu navigation
 * - Drawing the 8x16 board with pieces
 * - Click interaction (select piece -> show legal moves -> click destination)
 * - Animations (move, capture)
 * - Polling for opponent moves
 */

// ── Constants ──
const COLS = 8;
const ROWS = 16;
const COL_LABELS = 'abcdefgh';

const COLORS = {
    boardLight: '#d4b896',
    boardDark: '#b89b7a',
    border: '#5d4037',
    label: '#5d4037',
    frontier: '#8b6914',
    whitePiece: '#f5e6c8',
    whitePieceStroke: '#b8941f',
    whitePieceText: '#3e2723',
    blackPiece: '#8b1a1a',
    blackPieceStroke: '#5c1010',
    blackPieceText: '#fff8e7',
    selected: 'rgba(255, 213, 79, 0.55)',
    legalMove: 'rgba(201, 169, 78, 0.45)',
    captureTarget: 'rgba(220, 50, 50, 0.4)',
    lastMoveFrom: 'rgba(201, 169, 78, 0.25)',
    lastMoveTo: 'rgba(201, 169, 78, 0.35)',
};

// ── State ──
let canvas, ctx;
let cellSize = 0;
let boardOriginX = 0, boardOriginY = 0;

let gameId = null;
let whiteToken = null;
let blackToken = null;
let gameState = null;
let legalActions = null;
let playerColor = 'both'; // 'white', 'black', 'both' (hotseat), 'spectator'
let waitingForOpponent = false;

let selectedPieceId = null;
let selectedMoves = [];
let selectedAssaults = [];
let hoveredCell = null;
let lastMoveFrom = null;
let lastMoveTo = null;

// Animation state
let animating = false;
let animPiece = null;
let animFromX = 0, animFromY = 0;
let animToX = 0, animToY = 0;
let animProgress = 0;
let animCapture = null;
let animCaptureAlpha = 1;

// Visual effects
let particles = [];
let screenShake = 0;
let ringEffects = [];

// ── Profile (localStorage) ──

function getProfile() {
    return {
        username: localStorage.getItem('rithmo_username') || '',
        description: localStorage.getItem('rithmo_description') || '',
    };
}

function getPlayerName() {
    return getProfile().username || 'Player';
}

// ── Initialization ──

function initGame() {
    // Don't auto-start a game — show menu instead
    // Canvas will be initialized when entering game screen
}

function initCanvas() {
    canvas = document.getElementById('board');
    if (!canvas) return;
    ctx = canvas.getContext('2d');

    window.addEventListener('resize', onResize);
    canvas.addEventListener('click', onClick);
    canvas.addEventListener('mousemove', onMouseMove);

    onResize();
}

// ═══════════════════════════════════════
// Menu Navigation
// ═══════════════════════════════════════

let activeMenuPanel = null;

function menuToggle(panel) {
    const areas = ['fight', 'join', 'spectate'];
    for (const a of areas) {
        const el = document.getElementById(`menu-${a}-area`);
        if (el) el.style.display = (a === panel && activeMenuPanel !== panel) ? 'flex' : 'none';
    }
    activeMenuPanel = (activeMenuPanel === panel) ? null : panel;
}

function menuFight() {
    menuToggle('fight');
}

function menuProfile() {
    showScreen('profile');
    // Populate profile fields from localStorage
    const profile = getProfile();
    document.getElementById('profile-username').value = profile.username;
    document.getElementById('profile-description').value = profile.description;
    document.getElementById('profile-saved').style.display = 'none';
    loadGameHistory();
}

function saveProfile() {
    const username = document.getElementById('profile-username').value.trim();
    const description = document.getElementById('profile-description').value.trim();
    localStorage.setItem('rithmo_username', username);
    localStorage.setItem('rithmo_description', description);
    const saved = document.getElementById('profile-saved');
    saved.style.display = 'inline';
    setTimeout(() => saved.style.display = 'none', 2000);
}

function menuLeaderboard() {
    showModal('Leaderboard', '<p>Coming soon.</p>');
}

function menuRules() {
    showModal('Rules', `
<h4>The Board</h4>
<p>Rithmomachia is played on a <strong>8x16</strong> rectangular board. Each player starts with their pieces on the three rows closest to them. White occupies the bottom, Black the top. A frontier line divides the board at the midpoint.</p>

<h4>Pieces & Movement</h4>
<ul>
    <li><strong>Round (Circle)</strong> — moves <strong>1 square</strong> diagonally. Lowest values.</li>
    <li><strong>Triangle</strong> — moves <strong>2 squares</strong> in a straight line (orthogonal or diagonal).</li>
    <li><strong>Square</strong> — moves <strong>3 squares</strong> in a straight line.</li>
    <li><strong>Pyramid</strong> — a composite piece made of stacked shapes. Moves like any of its component shapes.</li>
</ul>
<p>Pieces cannot jump over other pieces. Only one piece occupies a square at a time.</p>

<h4>Capture Types</h4>
<ul>
    <li><strong>Encounter:</strong> Move onto an enemy piece of <em>equal value</em>. The standard capture.</li>
    <li><strong>Assault:</strong> Attack from a distance. Your piece's value multiplied by the number of squares to the target must equal the target's value. You do <em>not</em> move to the target's square.</li>
    <li><strong>Ambush:</strong> Two or more of your pieces that could reach a square have values that <em>sum</em> to an enemy piece's value on that square. The enemy is captured in place.</li>
    <li><strong>Siege:</strong> Surround an enemy piece so it has <em>no legal moves</em>. It is removed from the board.</li>
</ul>

<h4>Victory — Mathematical Progressions</h4>
<p>You win by capturing pieces whose values form <strong>mathematical progressions</strong> of 3 or more numbers:</p>
<ul>
    <li><strong>Arithmetic:</strong> Equal differences between consecutive values. <em>Example: 2, 4, 6 (diff = 2)</em></li>
    <li><strong>Geometric:</strong> Equal ratios between consecutive values. <em>Example: 2, 4, 8 (ratio = 2)</em></li>
    <li><strong>Harmonic:</strong> The reciprocals of the values form an arithmetic progression. <em>Example: 2, 3, 6</em></li>
</ul>

<h4>Victory Tiers</h4>
<ul>
    <li><strong>Victoria Minor:</strong> Achieve any <em>one</em> type of progression.</li>
    <li><strong>Victoria Magna:</strong> Achieve <em>two</em> different progression types simultaneously.</li>
    <li><strong>Victoria Excellentissima:</strong> Achieve all <em>three</em> progression types — the ultimate victory.</li>
</ul>

<h4>Draw</h4>
<p>If <strong>50 consecutive turns</strong> pass without any capture, the game ends in a draw.</p>
    `);
}

function menuHistory() {
    showModal('History of Rithmomachia', `
<h4>The Philosopher's Game</h4>
<p>Rithmomachia — from the Greek <em>arithmos</em> (number) and <em>mache</em> (battle) — is one of the most extraordinary board games ever created. Born in the monasteries of 11th-century Europe, it was not designed for entertainment. It was designed to <strong>teach the soul</strong>.</p>

<h4>Origins: Monks & Mathematics</h4>
<p>Around <strong>1030 AD</strong>, a monk named <strong>Asilo</strong> at the cathedral school in W&uuml;rzburg, Germany, created the game as a teaching tool for Boethian number theory — the mathematical framework that dominated European thought for a thousand years. Boethius had classified numbers into types: equal, multiple, superparticular. Rithmomachia turned those dry classifications into a <em>competitive battle</em>.</p>

<h4>The Game of Kings & Scholars</h4>
<p>For over <strong>500 years</strong>, Rithmomachia was the intellectual game of Europe's elite. While chess was for knights and courtiers, Rithmomachia was for <strong>mathematicians, philosophers, and theologians</strong>. It spread from Germany to France, England, and across the continent. Thomas More reportedly played it. It was taught at Oxford and the great cathedral schools.</p>

<p>Unlike chess, where brute force can prevail, Rithmomachia demanded something deeper: the ability to <strong>see mathematical harmony</strong> in the chaos of a battlefield. Victory required not just capturing pieces, but capturing the <em>right</em> pieces — those whose values formed perfect arithmetic, geometric, or harmonic progressions.</p>

<h4>A Game That Embodied a Worldview</h4>
<p>Medieval Europeans believed the universe was built on mathematical harmony. Music, astronomy, geometry, and arithmetic were the four pillars of the <em>quadrivium</em> — the higher education of the age. Rithmomachia embodied this belief. To win was to literally <strong>construct mathematical beauty</strong> from the spoils of battle.</p>

<p>The three types of victory — Minor, Magna, and Excellentissima — mirrored the medieval hierarchy of understanding. Anyone could grasp arithmetic patterns. Geometric insight was rarer. But to perceive harmonic relationships? That was to glimpse the divine order itself.</p>

<h4>Decline & Rediscovery</h4>
<p>By the <strong>17th century</strong>, the game faded as European mathematics moved beyond Boethian theory. Chess, simpler and more dramatic, claimed the spotlight. Rithmomachia became a footnote — mentioned in old manuscripts, misunderstood, nearly forgotten.</p>

<p>But in the 20th and 21st centuries, historians and game enthusiasts have revived it. What they found was remarkable: a game of <strong>extraordinary strategic depth</strong> hiding behind its medieval origins. A game where mathematics is not just a tool, but the very <em>condition of victory</em>.</p>

<h4>This Version</h4>
<p>This implementation follows the <strong>Fulke 1563 ruleset</strong>, one of the most complete historical sources. Ralph Lever and William Fulke published <em>"The Most Noble Ancient, and Learned Playe"</em> in Elizabethan England — a detailed manual that preserved the game for posterity.</p>

<p><em>You are now part of a tradition nearly a thousand years old. Play well.</em></p>
    `);
}

async function loadGameHistory() {
    const loading = document.getElementById('history-loading');
    const table = document.getElementById('history-table');
    const tbody = document.getElementById('history-tbody');
    const empty = document.getElementById('history-empty');

    loading.style.display = 'block';
    table.style.display = 'none';
    empty.style.display = 'none';

    try {
        const games = await Api.getGameHistory();
        loading.style.display = 'none';

        if (!games || games.length === 0) {
            empty.style.display = 'block';
            return;
        }

        // Compute win/loss/draw stats
        const username = getProfile().username.toLowerCase();
        let wins = 0, losses = 0, draws = 0;
        for (const g of games) {
            const isWhite = g.white_name.toLowerCase() === username;
            const isBlack = g.black_name.toLowerCase() === username;
            if (!isWhite && !isBlack) continue;
            if (g.status === 'draw') { draws++; }
            else if ((g.winner === 'white' && isWhite) || (g.winner === 'black' && isBlack)) { wins++; }
            else if (g.winner) { losses++; }
        }
        document.getElementById('stat-wins').textContent = wins;
        document.getElementById('stat-losses').textContent = losses;
        document.getElementById('stat-draws').textContent = draws;
        document.getElementById('stat-total').textContent = games.length;

        tbody.innerHTML = '';
        for (const g of games) {
            const tr = document.createElement('tr');
            const date = g.started_at ? new Date(g.started_at * 1000).toLocaleDateString() : '—';
            const players = `${g.white_name} (${g.white_type}) vs ${g.black_name} (${g.black_type})`;
            let resultClass = 'result-draw';
            let resultText = g.status;
            if (g.winner === 'white') { resultClass = 'result-win'; resultText = 'White wins'; }
            else if (g.winner === 'black') { resultClass = 'result-loss'; resultText = 'Black wins'; }
            else if (g.status === 'draw') { resultText = 'Draw'; }
            else if (g.status === 'active') { resultText = 'In progress'; resultClass = ''; }

            tr.innerHTML = `
                <td class="game-id-cell">${g.game_id}<br><span style="font-family:Georgia;font-size:11px;color:var(--parchment-dark)">${date}</span></td>
                <td>${players}</td>
                <td class="${resultClass}">${resultText}</td>
                <td>${g.move_count}</td>
                <td>${g.summary || '—'}</td>
            `;
            tbody.appendChild(tr);
        }
        table.style.display = 'table';
    } catch (e) {
        loading.textContent = 'Failed to load history.';
        console.error('History load error:', e);
    }
}

function profileBack() {
    showScreen('menu');
}

function showModal(title, body) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = body;
    document.getElementById('modal-overlay').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal-overlay').style.display = 'none';
}

function showScreen(screen) {
    document.getElementById('main-menu').style.display = screen === 'menu' ? 'flex' : 'none';
    document.getElementById('game-screen').style.display = screen === 'game' ? 'block' : 'none';
    document.getElementById('profile-screen').style.display = screen === 'profile' ? 'block' : 'none';

    if (screen === 'game' && !canvas) {
        initCanvas();
    }
}

function backToMenu() {
    // Reset game state
    gameId = null;
    whiteToken = null;
    blackToken = null;
    gameState = null;
    legalActions = null;
    waitingForOpponent = false;
    selectedPieceId = null;
    lastMoveFrom = null;
    lastMoveTo = null;
    activeMenuPanel = null;

    commentCount = 0;
    commentPolling = false;

    document.getElementById('game-over').classList.remove('visible');
    document.getElementById('history-list').innerHTML = '';
    document.getElementById('commentary-list').innerHTML = '';
    document.getElementById('commentary-panel').style.display = 'none';
    document.getElementById('vote-panel').style.display = 'none';

    // Hide all menu panels
    for (const a of ['fight', 'join', 'spectate']) {
        const el = document.getElementById(`menu-${a}-area`);
        if (el) el.style.display = 'none';
    }

    showScreen('menu');
}

// ── Start game flows ──

async function startFight(mode) {
    try {
        let white, black;
        if (mode === 'hotseat') {
            white = 'human'; black = 'human'; playerColor = 'both';
        } else if (mode === 'vs-ai-white') {
            white = 'human'; black = 'open'; playerColor = 'white';
        } else if (mode === 'vs-ai-black') {
            white = 'open'; black = 'human'; playerColor = 'black';
        } else if (mode === 'ai-vs-ai') {
            white = 'open'; black = 'open'; playerColor = 'spectator';
        }

        const profile = getProfile();
        const pname = profile.username || 'Player';
        const pdesc = profile.description || '';
        const wName = (playerColor === 'white' || playerColor === 'both') ? pname : 'White';
        const bName = (playerColor === 'black' || playerColor === 'both') ? pname : 'Black';
        const wDesc = (playerColor === 'white' || playerColor === 'both') ? pdesc : '';
        const bDesc = (playerColor === 'black' || playerColor === 'both') ? pdesc : '';

        const resp = await Api.newGame(white, black, wName, bName, wDesc, bDesc);
        gameId = resp.id;
        whiteToken = resp.white_token;
        blackToken = resp.black_token;
        waitingForOpponent = false;

        showScreen('game');
        onResize();

        // Show game ID so agents can connect
        showGameId(gameId);

        if (playerColor === 'spectator') {
            await Api.registerSpectator(gameId);
            showSpectatorCount(1);
        }

        await refreshState();
        await refreshLegal();
        render();

        if (playerColor !== 'both' && playerColor !== 'spectator') {
            if (gameState && gameState.current_player !== playerColor) {
                pollForOpponentMove();
            }
        }
        if (playerColor === 'spectator') {
            showStatus(`Spectating game ${gameId} — waiting for agents...`);
            loadVotes();
            pollForOpponentMove();
        }
    } catch (e) {
        console.error('Failed to start game:', e);
    }
}

async function doMenuJoin() {
    const id = document.getElementById('join-game-id').value.trim();
    const color = document.getElementById('join-color').value;
    if (!id) return;

    try {
        const profile = getProfile();
        const resp = await Api.join(id, color, profile.username || 'Player', profile.description);
        gameId = id;
        playerColor = color;
        if (color === 'white') {
            whiteToken = resp.token;
            blackToken = null;
        } else {
            blackToken = resp.token;
            whiteToken = null;
        }
        waitingForOpponent = false;

        showScreen('game');
        onResize();
        showGameId(gameId);

        await refreshState();
        await refreshLegal();
        render();

        if (gameState && gameState.current_player !== playerColor) {
            pollForOpponentMove();
        }
    } catch (e) {
        showModal('Error', `Failed to join: ${e.message}`);
    }
}

async function doMenuSpectate() {
    const id = document.getElementById('spectate-game-id').value.trim();
    if (!id) return;

    try {
        gameId = id;
        playerColor = 'spectator';
        whiteToken = null;
        blackToken = null;
        waitingForOpponent = false;

        showScreen('game');
        onResize();
        showGameId(gameId);

        // Register as spectator
        try {
            const resp = await Api.registerSpectator(gameId);
            showSpectatorCount(resp.spectator_count);
        } catch (_) {}

        await refreshState();
        render();
        showStatus(`Spectating game ${id}`);
        loadVotes();
        pollForOpponentMove();
    } catch (e) {
        showModal('Error', `Failed to spectate: ${e.message}`);
    }
}

function showGameId(id) {
    const panel = document.getElementById('game-id-panel');
    const display = document.getElementById('game-id-display');
    if (panel && display) {
        display.textContent = id;
        panel.style.display = 'block';
    }
}

function showSpectatorCount(count) {
    const panel = document.getElementById('spectator-panel');
    const el = document.getElementById('spectator-count');
    if (panel && el) {
        el.textContent = count;
        panel.style.display = 'block';
    }
}

// ── Volume control ──

let volumeState = 1; // 0=off, 1=half, 2=full

function cycleVolume() {
    volumeState = (volumeState + 1) % 3;
    const icon = document.getElementById('volume-icon');
    if (volumeState === 0) {
        Audio.setVolume(0);
        icon.innerHTML = '&#x1f507;';
    } else if (volumeState === 1) {
        Audio.setVolume(0.5);
        icon.innerHTML = '&#x1f509;';
    } else {
        Audio.setVolume(1);
        icon.innerHTML = '&#x1f50a;';
    }
}

// ── Visual Effects ──

function spawnCaptureEffect(row, col) {
    const { x, y } = cellToPixel(row, col);
    const cx = x + cellSize / 2;
    const cy = y + cellSize / 2;

    // Spawn ring
    ringEffects.push({ x: cx, y: cy, radius: 4, maxRadius: cellSize * 1.2, alpha: 1, color: '#ff4444' });
    ringEffects.push({ x: cx, y: cy, radius: 4, maxRadius: cellSize * 0.8, alpha: 0.8, color: '#ffaa22', delay: 3 });

    // Spawn particles
    for (let i = 0; i < 16; i++) {
        const angle = (Math.PI * 2 / 16) * i + (Math.random() - 0.5) * 0.3;
        const speed = 1.5 + Math.random() * 2.5;
        particles.push({
            x: cx, y: cy,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            life: 1,
            decay: 0.02 + Math.random() * 0.015,
            size: 2 + Math.random() * 3,
            color: Math.random() > 0.5 ? '#ffcc33' : '#ff5533',
        });
    }

    // Screen shake
    screenShake = 6;
}

function spawnMoveTrail(fromRow, fromCol, toRow, toCol) {
    const from = cellToPixel(fromRow, fromCol);
    const to = cellToPixel(toRow, toCol);
    const fx = from.x + cellSize / 2;
    const fy = from.y + cellSize / 2;
    const tx = to.x + cellSize / 2;
    const ty = to.y + cellSize / 2;

    // Trail particles along path
    const steps = 6;
    for (let i = 0; i < steps; i++) {
        const t = i / steps;
        particles.push({
            x: fx + (tx - fx) * t,
            y: fy + (ty - fy) * t,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            life: 0.6 + Math.random() * 0.3,
            decay: 0.025,
            size: 2 + Math.random() * 2,
            color: '#c9a94e',
        });
    }

    // Arrival burst
    ringEffects.push({ x: tx, y: ty, radius: 2, maxRadius: cellSize * 0.5, alpha: 0.5, color: '#c9a94e' });
}

function spawnVictoryEffect() {
    const cw = canvas.width;
    const ch = canvas.height;
    for (let i = 0; i < 40; i++) {
        const cx = Math.random() * cw;
        const cy = ch + 10;
        particles.push({
            x: cx, y: cy,
            vx: (Math.random() - 0.5) * 2,
            vy: -(2 + Math.random() * 4),
            life: 1,
            decay: 0.008 + Math.random() * 0.006,
            size: 3 + Math.random() * 4,
            color: ['#ffd700', '#ff6600', '#ff3333', '#44ff44', '#4488ff'][Math.floor(Math.random() * 5)],
        });
    }
}

function updateParticles() {
    // Update particles
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.03; // gravity
        p.life -= p.decay;
        if (p.life <= 0) particles.splice(i, 1);
    }

    // Update rings
    for (let i = ringEffects.length - 1; i >= 0; i--) {
        const r = ringEffects[i];
        if (r.delay && r.delay > 0) { r.delay--; continue; }
        const expand = (r.maxRadius - 4) * 0.08;
        r.radius += expand;
        r.alpha *= 0.92;
        if (r.alpha < 0.01 || r.radius >= r.maxRadius) ringEffects.splice(i, 1);
    }

    // Update screen shake
    if (screenShake > 0) screenShake *= 0.85;
    if (screenShake < 0.3) screenShake = 0;
}

function drawEffects() {
    // Draw rings
    for (const r of ringEffects) {
        if (r.delay && r.delay > 0) continue;
        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.strokeStyle = r.color;
        ctx.globalAlpha = r.alpha;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    // Draw particles
    for (const p of particles) {
        ctx.globalAlpha = p.life;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalAlpha = 1;
}

let effectsRunning = false;
function runEffectsLoop() {
    if (effectsRunning) return;
    effectsRunning = true;
    function tick() {
        if (particles.length === 0 && ringEffects.length === 0 && screenShake === 0) {
            effectsRunning = false;
            return;
        }
        updateParticles();
        render();
        requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

// ── Commentary ──

let commentCount = 0;
let commentPolling = false;

function showCommentaryPanel(commentatorName) {
    const panel = document.getElementById('commentary-panel');
    const nameEl = document.getElementById('commentator-name');
    if (panel) panel.style.display = 'block';
    if (nameEl) nameEl.textContent = commentatorName || 'Commentator';
}

function addCommentToUI(comment) {
    const list = document.getElementById('commentary-list');
    if (!list) return;
    const div = document.createElement('div');
    div.className = 'comment-entry';
    const turnLabel = comment.turn > 0 ? `Move ${comment.turn}` : 'Pre-game';
    div.innerHTML = `<span class="comment-turn">${turnLabel}</span><span class="comment-text">${escapeHtml(comment.message)}</span>`;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Voting ──

async function castVote(color) {
    if (!gameId) return;
    try {
        const resp = await Api.vote(gameId, color);
        updateVoteBar(resp);
    } catch (e) {
        console.error('Vote error:', e);
    }
}

function updateVoteBar(data) {
    const barW = document.getElementById('vote-bar-white');
    const barB = document.getElementById('vote-bar-black');
    const pctW = document.getElementById('vote-pct-white');
    const pctB = document.getElementById('vote-pct-black');
    const cntW = document.getElementById('vote-count-white');
    const cntB = document.getElementById('vote-count-black');
    if (!barW) return;

    const wp = data.white_pct != null ? data.white_pct : 50;
    const bp = data.black_pct != null ? data.black_pct : 50;
    barW.style.width = wp + '%';
    barB.style.width = bp + '%';
    pctW.textContent = wp + '%';
    pctB.textContent = bp + '%';
    if (cntW) cntW.textContent = data.votes.white;
    if (cntB) cntB.textContent = data.votes.black;

    // Hide percentage text if too narrow
    pctW.style.display = wp < 15 ? 'none' : '';
    pctB.style.display = bp < 15 ? 'none' : '';
}

async function loadVotes() {
    if (!gameId) return;
    try {
        const resp = await Api.getVotes(gameId);
        updateVoteBar(resp);
    } catch (_) {}
}

async function pollForComments() {
    if (!gameId || commentPolling) return;
    commentPolling = true;
    while (gameId) {
        try {
            const resp = await Api.waitForComment(gameId, commentCount);
            if (!gameId) break;
            if (resp.comments && resp.comments.length > 0) {
                // Show panel on first comment if not visible
                if (commentCount === 0) {
                    const panel = document.getElementById('commentary-panel');
                    if (panel) panel.style.display = 'block';
                }
                for (const c of resp.comments) {
                    addCommentToUI(c);
                }
                commentCount = resp.total;
            }
        } catch (e) {
            if (!gameId) break;
            await new Promise(r => setTimeout(r, 3000));
        }
    }
    commentPolling = false;
}

// ── Polling ──

async function pollForOpponentMove() {
    if (!gameId || !gameState || gameState.status !== 'active') return;
    if (playerColor === 'both') return;

    waitingForOpponent = true;
    if (playerColor !== 'spectator') {
        showStatus('Waiting for opponent...');
    }

    try {
        const newState = await Api.waitForMove(gameId, gameState.move_count);

        // Update spectator count from state
        if (newState.spectator_count !== undefined) {
            showSpectatorCount(newState.spectator_count);
        }

        waitingForOpponent = false;

        if (newState.status !== 'active') {
            gameState = newState;
            updateUI();
            render();
            return;
        }

        // Animate opponent's move
        if (newState.last_move && newState.move_count > (gameState?.move_count || 0)) {
            const move = newState.last_move;
            const oldPiece = findPieceAt(move.from_row, move.from_col);
            const capturedPiece = move.capture ? findPieceById(move.capture.captured_piece_id) : null;

            lastMoveFrom = { row: move.from_row, col: move.from_col };
            lastMoveTo = { row: move.to_row, col: move.to_col };

            if (oldPiece && (move.from_row !== move.to_row || move.from_col !== move.to_col)) {
                animateMove(oldPiece, move.from_row, move.from_col, move.to_row, move.to_col, capturedPiece, async () => {
                    gameState = newState;
                    updateUI();
                    await refreshLegal();
                    render();
                    maybeStartPolling();
                });
                return;
            }
        }

        gameState = newState;
        Audio.playTurnChange();
        updateUI();
        await refreshLegal();
        render();
        maybeStartPolling();
    } catch (e) {
        console.error('Poll error:', e);
        waitingForOpponent = false;
        setTimeout(() => pollForOpponentMove(), 2000);
    }
}

// ── Layout ──

function onResize() {
    if (!canvas) return;
    const area = document.getElementById('board-area');
    if (!area) return;
    const w = Math.max(200, area.clientWidth - 40);
    const h = Math.max(200, area.clientHeight - 60);

    const cellW = Math.floor(w / (COLS + 1));
    const cellH = Math.floor(h / (ROWS + 1));
    cellSize = Math.max(12, Math.min(cellW, cellH, 48));

    const canvasW = cellSize * COLS + 32;
    const canvasH = cellSize * ROWS + 24;

    canvas.width = canvasW;
    canvas.height = canvasH;
    boardOriginX = 28;
    boardOriginY = 4;

    render();
}

// ── Coordinate helpers ──

function cellToPixel(row, col) {
    const px = boardOriginX + col * cellSize;
    const py = boardOriginY + (ROWS - row) * cellSize;
    return { x: px, y: py };
}

function pixelToCell(px, py) {
    const col = Math.floor((px - boardOriginX) / cellSize);
    const row = ROWS - Math.floor((py - boardOriginY) / cellSize);
    if (row < 1 || row > ROWS || col < 0 || col >= COLS) return null;
    return { row, col };
}

// ── Rendering ──

function render() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Screen shake offset
    if (screenShake > 0) {
        ctx.save();
        const sx = (Math.random() - 0.5) * screenShake * 2;
        const sy = (Math.random() - 0.5) * screenShake * 2;
        ctx.translate(sx, sy);
    }

    drawBoard();
    drawHighlights();
    drawPieces();
    drawAnimation();
    drawLabels();
    drawEffects();

    if (screenShake > 0) ctx.restore();
}

function drawBoard() {
    for (let r = 1; r <= ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const { x, y } = cellToPixel(r, c);
            const isDark = (r + c) % 2 === 0;
            ctx.fillStyle = isDark ? COLORS.boardDark : COLORS.boardLight;
            ctx.fillRect(x, y, cellSize, cellSize);
        }
    }

    // Frontier line between rows 8 and 9
    const left = cellToPixel(9, 0);
    ctx.strokeStyle = COLORS.frontier;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(boardOriginX, left.y + cellSize);
    ctx.lineTo(boardOriginX + COLS * cellSize, left.y + cellSize);
    ctx.stroke();
    ctx.setLineDash([]);

    // Board border
    ctx.strokeStyle = COLORS.border;
    ctx.lineWidth = 2;
    ctx.strokeRect(boardOriginX, boardOriginY, COLS * cellSize, ROWS * cellSize);
}

function drawLabels() {
    ctx.fillStyle = COLORS.label;
    ctx.font = `${Math.max(10, cellSize * 0.28)}px Georgia`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    for (let c = 0; c < COLS; c++) {
        const x = boardOriginX + c * cellSize + cellSize / 2;
        const y = boardOriginY + ROWS * cellSize + 12;
        ctx.fillText(COL_LABELS[c], x, y);
    }

    ctx.textAlign = 'right';
    for (let r = 1; r <= ROWS; r++) {
        const { y } = cellToPixel(r, 0);
        ctx.fillText(r.toString(), boardOriginX - 6, y + cellSize / 2);
    }
}

function drawHighlights() {
    if (lastMoveFrom) fillCell(lastMoveFrom.row, lastMoveFrom.col, COLORS.lastMoveFrom);
    if (lastMoveTo) fillCell(lastMoveTo.row, lastMoveTo.col, COLORS.lastMoveTo);

    if (selectedPieceId !== null) {
        const piece = findPiece(selectedPieceId);
        if (piece) fillCell(piece.row, piece.col, COLORS.selected);

        for (const m of selectedMoves) {
            if (m.is_capture) {
                fillCell(m.to_row, m.to_col, COLORS.captureTarget);
            } else {
                fillCell(m.to_row, m.to_col, COLORS.legalMove);
            }
        }

        for (const a of selectedAssaults) {
            const target = findPieceById(a.captured_piece_id);
            if (target) fillCell(target.row, target.col, COLORS.captureTarget);
        }
    }
}

function fillCell(row, col, color) {
    const { x, y } = cellToPixel(row, col);
    ctx.fillStyle = color;
    ctx.fillRect(x, y, cellSize, cellSize);
}

function drawPieces() {
    if (!gameState) return;

    for (const p of gameState.board) {
        if (p.captured) continue;
        if (animating && animPiece && animPiece.id === p.id) continue;
        if (animating && animCapture && animCapture.id === p.id) {
            drawPieceAt(p, null, null, animCaptureAlpha);
            continue;
        }
        drawPieceAt(p);
    }
}

function drawPieceAt(piece, overrideX, overrideY, alpha = 1) {
    const { x: cellX, y: cellY } = cellToPixel(piece.row, piece.col);
    const cx = (overrideX !== null && overrideX !== undefined) ? overrideX : cellX + cellSize / 2;
    const cy = (overrideY !== null && overrideY !== undefined) ? overrideY : cellY + cellSize / 2;
    const r = cellSize * 0.38;

    ctx.save();
    ctx.globalAlpha = alpha;

    const isWhite = piece.color === 'white';
    const fill = isWhite ? COLORS.whitePiece : COLORS.blackPiece;
    const stroke = isWhite ? COLORS.whitePieceStroke : COLORS.blackPieceStroke;
    const textColor = isWhite ? COLORS.whitePieceText : COLORS.blackPieceText;

    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1.5;

    if (piece.shape === 'round') {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    } else if (piece.shape === 'triangle') {
        const h = r * 1.8;
        ctx.beginPath();
        ctx.moveTo(cx, cy - h * 0.55);
        ctx.lineTo(cx - r, cy + h * 0.45);
        ctx.lineTo(cx + r, cy + h * 0.45);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
    } else if (piece.shape === 'square') {
        const s = r * 1.5;
        ctx.fillRect(cx - s / 2, cy - s / 2, s, s);
        ctx.strokeRect(cx - s / 2, cy - s / 2, s, s);
    } else if (piece.shape === 'pyramid') {
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 6;
            const px = cx + r * Math.cos(angle);
            const py = cy + r * Math.sin(angle);
            i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
    }

    const fontSize = Math.max(9, cellSize * 0.28);
    ctx.fillStyle = textColor;
    ctx.font = `bold ${fontSize}px Georgia`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const textY = piece.shape === 'triangle' ? cy + r * 0.15 : cy;
    ctx.fillText(piece.value.toString(), cx, textY);

    ctx.restore();
}

function drawAnimation() {
    if (!animating || !animPiece) return;
    const cx = animFromX + (animToX - animFromX) * animProgress;
    const cy = animFromY + (animToY - animFromY) * animProgress;
    drawPieceAt(animPiece, cx, cy);
}

// ── Animation ──

function animateMove(piece, fromRow, fromCol, toRow, toCol, capturedPiece, callback) {
    const from = cellToPixel(fromRow, fromCol);
    const to = cellToPixel(toRow, toCol);

    animPiece = piece;
    animFromX = from.x + cellSize / 2;
    animFromY = from.y + cellSize / 2;
    animToX = to.x + cellSize / 2;
    animToY = to.y + cellSize / 2;
    animProgress = 0;
    animCapture = capturedPiece || null;
    animCaptureAlpha = 1;
    animating = true;

    // VFX: move trail
    spawnMoveTrail(fromRow, fromCol, toRow, toCol);
    Audio.playMove();

    const duration = 250;
    const start = performance.now();
    let captureTriggered = false;

    function step(ts) {
        const elapsed = ts - start;
        animProgress = Math.min(1, elapsed / duration);
        animProgress = 1 - (1 - animProgress) * (1 - animProgress);

        if (animCapture) {
            animCaptureAlpha = Math.max(0, 1 - (elapsed / duration) * 1.5);
            // Trigger capture effects at midpoint
            if (!captureTriggered && animProgress > 0.6) {
                captureTriggered = true;
                spawnCaptureEffect(toRow, toCol);
                Audio.playCapture();
            }
        }

        updateParticles();
        render();

        if (elapsed < duration) {
            requestAnimationFrame(step);
        } else {
            animating = false;
            animPiece = null;
            animCapture = null;
            render();
            runEffectsLoop();
            if (callback) callback();
        }
    }

    requestAnimationFrame(step);
}

// ── Interaction ──

function onClick(e) {
    if (animating) return;
    if (!gameState || gameState.status !== 'active') return;
    if (waitingForOpponent) return;
    if (playerColor === 'spectator') return;
    if (playerColor !== 'both' && gameState.current_player !== playerColor) return;

    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const cell = pixelToCell(px, py);
    if (!cell) return;

    const clickedPiece = findPieceAt(cell.row, cell.col);

    if (selectedPieceId !== null) {
        const move = selectedMoves.find(m => m.to_row === cell.row && m.to_col === cell.col);
        if (move) {
            executeMove(move.notation);
            return;
        }

        const assault = selectedAssaults.find(a => {
            const target = findPieceById(a.captured_piece_id);
            return target && target.row === cell.row && target.col === cell.col;
        });
        if (assault) {
            const piece = findPiece(selectedPieceId);
            const target = findPieceById(assault.captured_piece_id);
            const targetPos = `${COL_LABELS[target.col]}${target.row}`;
            const shapePrefix = { round: 'R', triangle: 'T', square: 'S', pyramid: 'P' }[piece.shape];
            const piecePos = `${COL_LABELS[piece.col]}${piece.row}`;
            const notation = `assault ${shapePrefix}${piece.value} ${piecePos}->${targetPos}`;
            executeMove(notation);
            return;
        }

        if (clickedPiece && clickedPiece.color === gameState.current_player && !clickedPiece.captured) {
            selectPiece(clickedPiece);
            return;
        }

        deselectPiece();
        return;
    }

    if (clickedPiece && clickedPiece.color === gameState.current_player && !clickedPiece.captured) {
        selectPiece(clickedPiece);
    }
}

function onMouseMove(e) {
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const cell = pixelToCell(px, py);

    const tooltip = document.getElementById('tooltip');
    if (cell && gameState) {
        const piece = findPieceAt(cell.row, cell.col);
        if (piece && !piece.captured) {
            const shapes = { round: 'Round (1 sq)', triangle: 'Triangle (2 sq)', square: 'Square (3 sq)', pyramid: 'Pyramid' };
            tooltip.textContent = `${piece.color} ${shapes[piece.shape]} — Value: ${piece.value}`;
            tooltip.style.display = 'block';
            tooltip.style.left = (e.clientX + 12) + 'px';
            tooltip.style.top = (e.clientY - 8) + 'px';
        } else {
            tooltip.style.display = 'none';
        }
    } else {
        tooltip.style.display = 'none';
    }
}

function selectPiece(piece) {
    selectedPieceId = piece.id;
    if (!legalActions) {
        selectedMoves = [];
        selectedAssaults = [];
    } else {
        selectedMoves = legalActions.moves.filter(m => m.piece_id === piece.id);
        selectedAssaults = legalActions.assaults.filter(a =>
            a.capturing_piece_ids.includes(piece.id)
        );
    }
    Audio.playSelect();
    render();
}

function deselectPiece() {
    selectedPieceId = null;
    selectedMoves = [];
    selectedAssaults = [];
    render();
}

async function executeMove(notation) {
    const token = gameState.current_player === 'white' ? whiteToken : blackToken;
    const piece = selectedPieceId ? findPiece(selectedPieceId) : null;
    deselectPiece();

    try {
        const result = await Api.submitMove(gameId, token, notation);

        if (!result.success) {
            showStatus(`Invalid: ${result.error}`);
            return;
        }

        if (piece && result.state) {
            const move = result.state.last_move;
            if (move && (move.from_row !== move.to_row || move.from_col !== move.to_col)) {
                const capturedPiece = move.capture ? findPieceById(move.capture.captured_piece_id) : null;
                lastMoveFrom = { row: move.from_row, col: move.from_col };
                lastMoveTo = { row: move.to_row, col: move.to_col };

                animateMove(piece, move.from_row, move.from_col, move.to_row, move.to_col, capturedPiece, async () => {
                    gameState = result.state;
                    updateUI();
                    await refreshLegal();
                    render();
                    maybeStartPolling();
                });
                return;
            }
        }

        if (result.state) {
            gameState = result.state;
            if (gameState.last_move) {
                lastMoveFrom = { row: gameState.last_move.from_row, col: gameState.last_move.from_col };
                lastMoveTo = { row: gameState.last_move.to_row, col: gameState.last_move.to_col };
            }
        }
        updateUI();
        await refreshLegal();
        render();
        maybeStartPolling();

    } catch (e) {
        showStatus(`Error: ${e.message}`);
    }
}

// ── State management ──

async function refreshState() {
    if (!gameId) return;
    gameState = await Api.getState(gameId);
    updateUI();
}

async function refreshLegal() {
    if (!gameId || !gameState || gameState.status !== 'active') {
        legalActions = null;
        return;
    }
    legalActions = await Api.getLegal(gameId);
}

function updateUI() {
    if (!gameState) return;

    // Turn indicator
    const turnInfo = document.getElementById('turn-info');
    if (turnInfo) {
        const cp = gameState.current_player;
        const dotClass = cp === 'white' ? 'white' : 'black';
        turnInfo.innerHTML = `<span class="color-dot ${dotClass}"></span> ${capitalize(cp)}'s Turn — Move ${gameState.turn}`;
    }

    // Player info
    if (gameState.players) {
        const wp = gameState.players.white;
        const bp = gameState.players.black;
        const wn = document.getElementById('player-white-name');
        const wd = document.getElementById('player-white-desc');
        const bn = document.getElementById('player-black-name');
        const bd = document.getElementById('player-black-desc');
        if (wn) wn.textContent = wp.name || 'White';
        if (wd) wd.textContent = wp.description || '';
        if (bn) bn.textContent = bp.name || 'Black';
        if (bd) bd.textContent = bp.description || '';
    }

    updateCaptures('white', gameState.captures.white);
    updateCaptures('black', gameState.captures.black);
    updateHistory();

    if (gameState.status === 'active') {
        if (playerColor === 'spectator') {
            showStatus(`Spectating — ${capitalize(gameState.current_player)}'s turn — Move ${gameState.turn}`);
        } else {
            showStatus(`${capitalize(gameState.current_player)}'s turn`);
        }
    } else if (gameState.status === 'white_wins') {
        showGameOver('White Wins!', formatVictorySubtitle('white'));
    } else if (gameState.status === 'black_wins') {
        showGameOver('Black Wins!', formatVictorySubtitle('black'));
    } else if (gameState.status === 'draw') {
        showGameOver('Draw', '50 turns without a capture.');
    }

    updateProgressions();
    updateActionButtons();

    // Update spectator count if available
    if (gameState.spectator_count !== undefined) {
        showSpectatorCount(gameState.spectator_count);
    }

    // Show commentator if present
    if (gameState.commentator) {
        showCommentaryPanel(gameState.commentator.name);
        if (!commentPolling) pollForComments();
    }

    // Show vote panel for spectators
    const votePanel = document.getElementById('vote-panel');
    if (votePanel && gameState.status === 'active') {
        votePanel.style.display = 'block';
    }
}

function formatVictorySubtitle(winner) {
    const progs = gameState.progressions[winner];
    if (!progs || progs.length === 0) return 'Victoria achieved!';
    const types = new Set(progs.map(p => p.type));
    if (types.size >= 3) return 'Victoria Excellentissima! All three progression types.';
    if (types.size >= 2) return 'Victoria Magna! Two progression types achieved.';
    const t = progs[0].type;
    return `Victoria Minor via ${t} progression: ${progs[0].values.join(', ')}`;
}

function updateProgressions() {
    const el = document.getElementById('progressions-info');
    if (!el || !gameState) return;

    const wp = gameState.progressions.white;
    const bp = gameState.progressions.black;

    if (wp.length === 0 && bp.length === 0) {
        const wc = gameState.captures.white;
        const bc = gameState.captures.black;
        if (wc.length === 0 && bc.length === 0) {
            el.innerHTML = '<span style="opacity:0.5">No captures yet</span>';
        } else {
            let html = '';
            if (wc.length >= 2) html += `<div>White needs 1 more for progression</div>`;
            if (bc.length >= 2) html += `<div>Black needs 1 more for progression</div>`;
            if (!html) html = '<span style="opacity:0.5">Need 3+ captures for progression</span>';
            el.innerHTML = html;
        }
    } else {
        let html = '';
        for (const p of wp) {
            html += `<div style="color:#c9a94e">W: ${p.type}(${p.values.join(',')})</div>`;
        }
        for (const p of bp) {
            html += `<div style="color:#e57373">B: ${p.type}(${p.values.join(',')})</div>`;
        }
        el.innerHTML = html;
    }
}

function updateCaptures(color, values) {
    const el = document.getElementById(`captures-${color}`);
    if (!el) return;
    if (values.length === 0) {
        el.innerHTML = '<span style="opacity:0.5">None</span>';
    } else {
        el.innerHTML = values.map(v => `<span class="capture-val">${v}</span>`).join('');
    }
}

function updateHistory() {
    const list = document.getElementById('history-list');
    if (!list || !gameState) return;

    if (gameState.last_move) {
        const existing = list.querySelectorAll('.move-entry');
        const moves = gameState.move_count;
        if (existing.length < moves) {
            const m = gameState.last_move;
            const turn = moves;
            const player = turn % 2 === 1 ? 'W' : 'B';
            let entry = `<div class="move-entry"><span class="turn-num">${turn}.</span>${player} ${m.notation}`;
            if (m.capture) {
                entry += ` <span class="capture-note">x ${m.capture.description}</span>`;
            }
            entry += '</div>';
            list.innerHTML += entry;
            list.scrollTop = list.scrollHeight;
        }
    }
}

function updateActionButtons() {
    const ambushBtn = document.getElementById('btn-ambush');
    const siegeBtn = document.getElementById('btn-siege');

    if (!legalActions || playerColor === 'spectator') {
        if (ambushBtn) ambushBtn.disabled = true;
        if (siegeBtn) siegeBtn.disabled = true;
        return;
    }

    if (ambushBtn) ambushBtn.disabled = legalActions.ambushes.length === 0;
    if (siegeBtn) siegeBtn.disabled = legalActions.sieges.length === 0;
}

function showStatus(msg) {
    const bar = document.getElementById('status-bar');
    if (bar) bar.textContent = msg;
}

function showGameOver(title, subtitle) {
    const overlay = document.getElementById('game-over');
    if (overlay) {
        overlay.querySelector('h2').textContent = title;
        overlay.querySelector('p').textContent = subtitle;
        overlay.classList.add('visible');
    }
    Audio.playVictory();
    spawnVictoryEffect();
    runEffectsLoop();
}

// ── Helpers ──

function findPiece(pieceId) {
    if (!gameState) return null;
    return gameState.board.find(p => p.id === pieceId && !p.captured) || null;
}

function findPieceById(pieceId) {
    if (!gameState) return null;
    return gameState.board.find(p => p.id === pieceId) || null;
}

function findPieceAt(row, col) {
    if (!gameState) return null;
    return gameState.board.find(p => p.row === row && p.col === col && !p.captured) || null;
}

function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

// ── Action buttons ──

function declareAmbush() {
    if (!legalActions || legalActions.ambushes.length === 0) return;
    const ambush = legalActions.ambushes[0];
    const target = findPieceById(ambush.captured_piece_id);
    if (target) {
        const pos = `${COL_LABELS[target.col]}${target.row}`;
        executeMove(`ambush ${pos}`);
    }
}

function declareSiege() {
    if (!legalActions || legalActions.sieges.length === 0) return;
    const siege = legalActions.sieges[0];
    const target = findPieceById(siege.captured_piece_id);
    if (target) {
        const pos = `${COL_LABELS[target.col]}${target.row}`;
        executeMove(`siege ${pos}`);
    }
}

function resignGame() {
    if (!gameState || gameState.status !== 'active') return;
    const token = gameState.current_player === 'white' ? whiteToken : blackToken;
    Api.resign(gameId, token).then(() => refreshState().then(() => render()));
}

function maybeStartPolling() {
    if (!gameState || gameState.status !== 'active') return;
    if (playerColor === 'both') return;
    if (playerColor === 'spectator') {
        pollForOpponentMove();
        return;
    }
    if (gameState.current_player !== playerColor) {
        pollForOpponentMove();
    }
}

// ── Boot ──
window.addEventListener('DOMContentLoaded', initGame);
