/* Players tab — searchable, sortable table with color-coded balances */

tabLoaders['players'] = loadPlayers;

let playerSort = { by: 'name', dir: 'asc' };
let playerFilters = { search: '', status: '', sub_agent_id: '' };

async function loadPlayers() {
    const el = document.getElementById('tab-players');

    // Build filter bar
    const subs = await apiJson('/api/sub-agents');
    const subOptions = subs?.sub_agents?.map(s =>
        `<option value="${s.id}">${esc(s.name)}</option>`
    ).join('') || '';

    el.innerHTML = `
        <div class="search-bar">
            <input type="text" id="playerSearch" class="input" style="max-width:220px" placeholder="Search players..."
                value="${esc(playerFilters.search)}" oninput="playerFilters.search=this.value; loadPlayerTable()">
            <select id="playerStatus" class="input" style="max-width:140px" onchange="playerFilters.status=this.value; loadPlayerTable()">
                <option value="">All Status</option>
                <option value="active" ${playerFilters.status==='active'?'selected':''}>Active</option>
                <option value="inactive" ${playerFilters.status==='inactive'?'selected':''}>Inactive</option>
                <option value="flagged" ${playerFilters.status==='flagged'?'selected':''}>Flagged</option>
            </select>
            <select id="playerSub" class="input" style="max-width:160px" onchange="playerFilters.sub_agent_id=this.value; loadPlayerTable()">
                <option value="">All Sub-Agents</option>
                <option value="0" ${playerFilters.sub_agent_id==='0'?'selected':''}>Direct (No Sub)</option>
                ${subOptions}
            </select>
            <button class="btn btn-blue" onclick="showAddPlayerForm()">+ Add Player</button>
        </div>
        <div id="playerTableWrap" class="table-wrap"></div>
    `;
    await loadPlayerTable();
}

async function loadPlayerTable() {
    const params = new URLSearchParams();
    if (playerFilters.search) params.set('search', playerFilters.search);
    if (playerFilters.status) params.set('status', playerFilters.status);
    if (playerFilters.sub_agent_id) params.set('sub_agent_id', playerFilters.sub_agent_id);
    params.set('sort_by', playerSort.by);
    params.set('sort_dir', playerSort.dir);

    const data = await apiJson(`/api/players?${params}`);
    if (!data) return;

    const wrap = document.getElementById('playerTableWrap');
    if (!data.players.length) {
        wrap.innerHTML = '<p class="text-slate-500 text-sm mt-4">No players found</p>';
        return;
    }

    const arrow = (col) => playerSort.by === col ? (playerSort.dir === 'asc' ? ' &#9650;' : ' &#9660;') : '';

    wrap.innerHTML = `
        <table class="data-table">
            <thead><tr>
                <th onclick="sortPlayers('name')">Name${arrow('name')}</th>
                <th onclick="sortPlayers('account_id')" class="hide-mobile">Account${arrow('account_id')}</th>
                <th>Sub-Agent</th>
                <th onclick="sortPlayers('balance')">Balance${arrow('balance')}</th>
                <th onclick="sortPlayers('credit_limit')" class="hide-mobile">Credit Limit${arrow('credit_limit')}</th>
                <th onclick="sortPlayers('win_loss')">W/L${arrow('win_loss')}</th>
                <th class="hide-mobile">Status</th>
            </tr></thead>
            <tbody>
                ${data.players.map(p => {
                    const bClass = balanceClass(p.balance, p.credit_limit);
                    return `
                    <tr class="clickable" onclick="openPlayerDetail(${p.id})">
                        <td class="font-medium">${esc(p.name || p.account_id)}</td>
                        <td class="hide-mobile text-slate-400">${esc(p.account_id)}</td>
                        <td class="text-slate-400">${p.sub_agent_name ? esc(p.sub_agent_name) : '<span class="text-blue-400">Direct</span>'}</td>
                        <td class="${bClass} font-semibold">${fmt(p.balance)}</td>
                        <td class="hide-mobile text-slate-400">${fmt(p.credit_limit)}</td>
                        <td class="${p.win_loss >= 0 ? 'balance-negative' : 'balance-positive'} font-semibold">${fmt(p.win_loss)}</td>
                        <td class="hide-mobile">${badgeHtml(p.status)}</td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

function sortPlayers(col) {
    if (playerSort.by === col) {
        playerSort.dir = playerSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
        playerSort.by = col;
        playerSort.dir = 'asc';
    }
    loadPlayerTable();
}

async function openPlayerDetail(id) {
    const p = await apiJson(`/api/players/${id}`);
    if (!p) return;
    const hist = await apiJson(`/api/players/${id}/history`);

    const subs = await apiJson('/api/sub-agents');
    const subOptions = subs?.sub_agents?.map(s =>
        `<option value="${s.id}" ${p.sub_agent_id===s.id?'selected':''}>${esc(s.name)}</option>`
    ).join('') || '';

    document.getElementById('modalTitle').textContent = p.name || p.account_id;
    document.getElementById('modalContent').innerHTML = `
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="text-slate-400 text-xs">Name</label>
                <input class="input mt-1" id="editName" value="${esc(p.name)}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Account ID</label>
                <input class="input mt-1" value="${esc(p.account_id)}" disabled>
            </div>
            <div>
                <label class="text-slate-400 text-xs">Phone</label>
                <input class="input mt-1" id="editPhone" value="${esc(p.phone)}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Sub-Agent</label>
                <select class="input mt-1" id="editSubAgent">
                    <option value="">Direct (under me)</option>
                    ${subOptions}
                </select>
            </div>
            <div>
                <label class="text-slate-400 text-xs">Credit Limit</label>
                <input class="input mt-1" id="editCreditLimit" type="number" step="0.01" value="${p.credit_limit}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Status</label>
                <select class="input mt-1" id="editStatus">
                    <option value="active" ${p.status==='active'?'selected':''}>Active</option>
                    <option value="inactive" ${p.status==='inactive'?'selected':''}>Inactive</option>
                    <option value="flagged" ${p.status==='flagged'?'selected':''}>Flagged</option>
                </select>
            </div>
        </div>
        <div class="mb-4">
            <label class="text-slate-400 text-xs">Notes</label>
            <textarea class="input mt-1" id="editNotes" rows="3">${esc(p.notes)}</textarea>
        </div>
        <button class="btn btn-green" onclick="savePlayer(${p.id})">Save Changes</button>

        <div class="mt-6 grid grid-cols-3 gap-3">
            <div class="stat-card">
                <div class="label">Balance</div>
                <div class="value ${balanceClass(p.balance, p.credit_limit)}">${fmt(p.balance)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Win/Loss</div>
                <div class="value ${p.win_loss >= 0 ? 'balance-negative' : 'balance-positive'}">${fmt(p.win_loss)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Action</div>
                <div class="value text-slate-300">${fmt(p.action)}</div>
            </div>
        </div>

        <div class="mt-6">
            <h3 class="section-header">Weekly History</h3>
            ${hist?.history?.length ? `
                <table class="data-table">
                    <thead><tr><th>Week Ending</th><th>Won/Lost</th><th>Net</th><th>Settled</th></tr></thead>
                    <tbody>${hist.history.map(h => `
                        <tr>
                            <td>${esc(h.week_ending)}</td>
                            <td class="${h.won_lost <= 0 ? 'balance-positive' : 'balance-negative'}">${fmt(h.won_lost)}</td>
                            <td class="${h.net <= 0 ? 'balance-positive' : 'balance-negative'}">${fmt(h.net)}</td>
                            <td>${h.settled ? badgeHtml('paid') : badgeHtml('pending')}</td>
                        </tr>
                    `).join('')}</tbody>
                </table>
            ` : '<p class="text-slate-500 text-sm">No history yet</p>'}
        </div>
    `;
    document.getElementById('playerModal').classList.remove('hidden');
}

async function savePlayer(id) {
    const data = {
        name: document.getElementById('editName').value,
        phone: document.getElementById('editPhone').value,
        sub_agent_id: document.getElementById('editSubAgent').value ? parseInt(document.getElementById('editSubAgent').value) : null,
        credit_limit: parseFloat(document.getElementById('editCreditLimit').value) || 0,
        status: document.getElementById('editStatus').value,
        notes: document.getElementById('editNotes').value,
    };
    const res = await apiJson(`/api/players/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    if (res?.ok) {
        toast('Player updated');
        closePlayerModal();
        loadPlayerTable();
    }
}

function showAddPlayerForm() {
    document.getElementById('modalTitle').textContent = 'Add Player';
    document.getElementById('modalContent').innerHTML = `
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
                <label class="text-slate-400 text-xs">Account ID *</label>
                <input class="input mt-1" id="newAccountId">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Name</label>
                <input class="input mt-1" id="newName">
            </div>
        </div>
        <button class="btn btn-green" onclick="addPlayer()">Add Player</button>
    `;
    document.getElementById('playerModal').classList.remove('hidden');
}

async function addPlayer() {
    const accountId = document.getElementById('newAccountId').value.trim();
    if (!accountId) { toast('Account ID required', 'error'); return; }
    const res = await apiJson('/api/players', {
        method: 'POST',
        body: JSON.stringify({ account_id: accountId, name: document.getElementById('newName').value }),
    });
    if (res?.ok) {
        toast('Player added');
        closePlayerModal();
        loadPlayerTable();
    } else {
        toast(res?.detail || 'Failed to add player', 'error');
    }
}
