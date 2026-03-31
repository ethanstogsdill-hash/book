/* Sub-Agents tab — table with book totals and click-through */

tabLoaders['subagents'] = loadSubAgents;

async function loadSubAgents() {
    const data = await apiJson('/api/sub-agents');
    if (!data) return;

    const el = document.getElementById('tab-subagents');
    const subs = data.sub_agents || [];

    el.innerHTML = `
        <div class="search-bar">
            <button class="btn btn-blue" onclick="showAddSubAgentForm()">+ Add Sub-Agent</button>
        </div>
        ${subs.length ? `
        <div class="table-wrap">
            <table class="data-table">
                <thead><tr>
                    <th>Name</th>
                    <th>Players</th>
                    <th>Book Size</th>
                    <th>W/L</th>
                    <th>Balance</th>
                    <th class="hide-mobile">Vig Split</th>
                    <th class="hide-mobile">Status</th>
                </tr></thead>
                <tbody>
                    ${subs.map(s => `
                    <tr class="clickable" onclick="openSubAgentDetail(${s.id})">
                        <td class="font-medium">${esc(s.name)}</td>
                        <td class="text-slate-300">${s.player_count || 0}</td>
                        <td class="text-slate-300">${fmt(s.total_book || 0)}</td>
                        <td class="${(s.total_win_loss||0) <= 0 ? 'balance-positive' : 'balance-negative'} font-semibold">
                            ${fmt(s.total_win_loss || 0)}
                        </td>
                        <td class="${balanceClass(s.balance)} font-semibold">${fmt(s.balance)}</td>
                        <td class="hide-mobile text-slate-400">${s.vig_split || 0}%</td>
                        <td class="hide-mobile">${badgeHtml(s.status)}</td>
                    </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ` : '<p class="text-slate-500 text-sm mt-4">No sub-agents yet. They will be auto-created when you sync data.</p>'}
    `;
}

async function openSubAgentDetail(id) {
    const s = await apiJson(`/api/sub-agents/${id}`);
    if (!s) return;
    const playersData = await apiJson(`/api/sub-agents/${id}/players`);
    const players = playersData?.players || [];

    document.getElementById('subModalTitle').textContent = s.name || s.username;
    document.getElementById('subModalContent').innerHTML = `
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="text-slate-400 text-xs">Name</label>
                <input class="input mt-1" id="subEditName" value="${esc(s.name)}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Username (site)</label>
                <input class="input mt-1" id="subEditUsername" value="${esc(s.username || '')}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Phone</label>
                <input class="input mt-1" id="subEditPhone" value="${esc(s.phone)}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Telegram Username</label>
                <input class="input mt-1" id="subEditTelegramUser" value="${esc(s.telegram_username || '')}" placeholder="@username">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Telegram Chat ID</label>
                <input class="input mt-1" id="subEditTelegram" value="${esc(s.telegram_chat_id)}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Venmo</label>
                <input class="input mt-1" id="subEditVenmo" value="${esc(s.venmo || '')}" placeholder="@venmo-handle">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Credit Limit</label>
                <input class="input mt-1" id="subEditCreditLimit" type="number" step="0.01" value="${s.credit_limit}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Vig Split (%)</label>
                <input class="input mt-1" id="subEditVigSplit" type="number" step="0.1" value="${s.vig_split}">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Status</label>
                <select class="input mt-1" id="subEditStatus">
                    <option value="active" ${s.status==='active'?'selected':''}>Active</option>
                    <option value="inactive" ${s.status==='inactive'?'selected':''}>Inactive</option>
                    <option value="flagged" ${s.status==='flagged'?'selected':''}>Flagged</option>
                </select>
            </div>
        </div>
        <div class="mb-4">
            <label class="text-slate-400 text-xs">Notes</label>
            <textarea class="input mt-1" id="subEditNotes" rows="3">${esc(s.notes)}</textarea>
        </div>
        <button class="btn btn-green" onclick="saveSubAgent(${s.id})">Save Changes</button>

        <div class="mt-6 grid grid-cols-3 gap-3">
            <div class="stat-card">
                <div class="label">Players</div>
                <div class="value text-blue-400">${s.player_count || 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Book Size</div>
                <div class="value text-slate-300">${fmt(s.total_book || 0)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total W/L</div>
                <div class="value ${(s.total_win_loss||0) <= 0 ? 'balance-positive' : 'balance-negative'}">
                    ${fmt(s.total_win_loss || 0)}
                </div>
            </div>
        </div>

        <div class="mt-6">
            <h3 class="section-header">Players Under This Sub-Agent</h3>
            ${players.length ? `
                <table class="data-table">
                    <thead><tr><th>Name</th><th>Account</th><th>Balance</th><th>W/L</th><th>Status</th></tr></thead>
                    <tbody>${players.map(p => `
                        <tr class="clickable" onclick="closeSubAgentModal(); openPlayerDetail(${p.id})">
                            <td class="font-medium">${esc(p.name || p.account_id)}</td>
                            <td class="text-slate-400">${esc(p.account_id)}</td>
                            <td class="${balanceClass(p.balance, p.credit_limit)} font-semibold">${fmt(p.balance)}</td>
                            <td class="${p.win_loss >= 0 ? 'balance-negative' : 'balance-positive'}">${fmt(p.win_loss)}</td>
                            <td>${badgeHtml(p.status)}</td>
                        </tr>
                    `).join('')}</tbody>
                </table>
            ` : '<p class="text-slate-500 text-sm">No players under this sub-agent</p>'}
        </div>
    `;
    document.getElementById('subAgentModal').classList.remove('hidden');
}

async function saveSubAgent(id) {
    const data = {
        name: document.getElementById('subEditName').value,
        username: document.getElementById('subEditUsername').value,
        phone: document.getElementById('subEditPhone').value,
        telegram_username: document.getElementById('subEditTelegramUser').value,
        telegram_chat_id: document.getElementById('subEditTelegram').value,
        venmo: document.getElementById('subEditVenmo').value,
        credit_limit: parseFloat(document.getElementById('subEditCreditLimit').value) || 0,
        vig_split: parseFloat(document.getElementById('subEditVigSplit').value) || 0,
        status: document.getElementById('subEditStatus').value,
        notes: document.getElementById('subEditNotes').value,
    };
    const res = await apiJson(`/api/sub-agents/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
    if (res?.ok) {
        toast('Sub-agent updated');
        closeSubAgentModal();
        loadSubAgents();
    }
}

function showAddSubAgentForm() {
    document.getElementById('subModalTitle').textContent = 'Add Sub-Agent';
    document.getElementById('subModalContent').innerHTML = `
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
                <label class="text-slate-400 text-xs">Name *</label>
                <input class="input mt-1" id="newSubName">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Username (site)</label>
                <input class="input mt-1" id="newSubUsername">
            </div>
            <div>
                <label class="text-slate-400 text-xs">Vig Split (%)</label>
                <input class="input mt-1" id="newSubVigSplit" type="number" step="0.1" value="0">
            </div>
        </div>
        <button class="btn btn-green" onclick="addSubAgent()">Add Sub-Agent</button>
    `;
    document.getElementById('subAgentModal').classList.remove('hidden');
}

async function addSubAgent() {
    const name = document.getElementById('newSubName').value.trim();
    if (!name) { toast('Name required', 'error'); return; }
    const res = await apiJson('/api/sub-agents', {
        method: 'POST',
        body: JSON.stringify({
            name: name,
            username: document.getElementById('newSubUsername').value.trim() || null,
            vig_split: parseFloat(document.getElementById('newSubVigSplit').value) || 0,
        }),
    });
    if (res?.ok) {
        toast('Sub-agent added');
        closeSubAgentModal();
        loadSubAgents();
    }
}
