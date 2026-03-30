/* Settlements / Payday tab */

tabLoaders['settlements'] = loadSettlements;

async function loadSettlements() {
    const el = document.getElementById('tab-settlements');
    const weeksData = await apiJson('/api/settlements/weeks');
    const weeks = weeksData?.weeks || [];

    // Also get available result weeks for generation
    const resultWeeks = await apiJson('/api/weeks');

    el.innerHTML = `
        <div class="search-bar">
            <select id="settlementWeek" class="input" style="max-width:200px" onchange="loadSettlementTable()">
                <option value="">All Weeks</option>
                ${weeks.map(w => `<option value="${w}">${w}</option>`).join('')}
            </select>
            <select id="settlementStatus" class="input" style="max-width:140px" onchange="loadSettlementTable()">
                <option value="">All Status</option>
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
                <option value="disputed">Disputed</option>
            </select>
            <div class="flex gap-2 ml-auto">
                <button class="btn btn-blue" onclick="showGenerateDialog()">Generate Payday</button>
            </div>
        </div>
        <div id="settlementTableWrap" class="table-wrap"></div>
    `;
    await loadSettlementTable();
}

async function loadSettlementTable() {
    const params = new URLSearchParams();
    const week = document.getElementById('settlementWeek')?.value;
    const status = document.getElementById('settlementStatus')?.value;
    if (week) params.set('week_ending', week);
    if (status) params.set('status', status);

    const data = await apiJson(`/api/settlements?${params}`);
    if (!data) return;

    const wrap = document.getElementById('settlementTableWrap');
    if (!data.settlements.length) {
        wrap.innerHTML = '<p class="text-slate-500 text-sm mt-4">No settlements found. Use "Generate Payday" to create them.</p>';
        return;
    }

    // Summary
    let totalCollect = 0, totalPay = 0;
    data.settlements.forEach(s => {
        if (s.direction === 'collect') totalCollect += s.amount;
        else totalPay += s.amount;
    });

    wrap.innerHTML = `
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            <div class="stat-card">
                <div class="label">To Collect</div>
                <div class="value balance-positive">${fmt(totalCollect)}</div>
            </div>
            <div class="stat-card">
                <div class="label">To Pay</div>
                <div class="value balance-negative">${fmt(totalPay)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Net</div>
                <div class="value ${totalCollect - totalPay >= 0 ? 'balance-positive' : 'balance-negative'}">
                    ${fmt(totalCollect - totalPay)}
                </div>
            </div>
        </div>

        ${data.settlements.some(s => s.counterparty_type === 'sub_agent' && s.status === 'pending') ?
            `<div class="mb-4">
                <button class="btn btn-blue" onclick="notifySubAgents('${week || ''}')">Send Telegram to Sub-Agents</button>
                ${week ? `<a href="/api/settlements/${week}/pdf" target="_blank" class="btn btn-gray ml-2">Download PDF</a>` : ''}
            </div>` : ''
        }

        <table class="data-table">
            <thead><tr>
                <th>Counterparty</th>
                <th>Type</th>
                <th>Amount</th>
                <th>Direction</th>
                <th>Status</th>
                <th>Actions</th>
            </tr></thead>
            <tbody>
                ${data.settlements.map(s => `
                <tr>
                    <td class="font-medium">${esc(s.counterparty_name)}</td>
                    <td class="text-slate-400">${esc(s.counterparty_type)}</td>
                    <td class="font-semibold ${s.direction === 'collect' ? 'balance-positive' : 'balance-negative'}">${fmt(s.amount)}</td>
                    <td>${s.direction === 'collect'
                        ? '<span class="text-green-400">Collect</span>'
                        : '<span class="text-red-400">Pay</span>'}</td>
                    <td>${badgeHtml(s.status)}</td>
                    <td>
                        ${s.status === 'pending' ? `
                            <button class="btn btn-green text-xs" onclick="markPaid(${s.id})">Mark Paid</button>
                        ` : ''}
                        <button class="btn btn-gray text-xs" onclick="editSettlementNotes(${s.id}, '${esc(s.notes || '')}')">Notes</button>
                    </td>
                </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function markPaid(id) {
    const res = await apiJson(`/api/settlements/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'paid' }),
    });
    if (res?.ok) {
        toast('Settlement marked as paid');
        loadSettlementTable();
    }
}

function editSettlementNotes(id, currentNotes) {
    const notes = prompt('Settlement notes:', currentNotes);
    if (notes === null) return;
    apiJson(`/api/settlements/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notes }),
    }).then(res => { if (res?.ok) toast('Notes saved'); });
}

async function showGenerateDialog() {
    const weeksData = await apiJson('/api/weeks');
    const weeks = weeksData?.weeks || [];
    if (!weeks.length) {
        toast('No weekly data available. Sync first.', 'error');
        return;
    }
    const week = prompt(`Generate settlements for which week?\nAvailable: ${weeks.slice(0, 5).join(', ')}`, weeks[0]);
    if (!week) return;
    const res = await apiJson(`/api/settlements/generate/${week}`, { method: 'POST' });
    if (res?.ok) {
        toast(`Generated ${res.count || 0} settlements`);
        loadSettlements();
    } else {
        toast(res?.error || res?.detail || 'Generation failed', 'error');
    }
}

async function notifySubAgents(weekEnding) {
    if (!weekEnding) {
        toast('Select a specific week first', 'error');
        return;
    }
    if (!confirm('Send Telegram messages to all sub-agents for this week?')) return;
    const res = await apiJson(`/api/settlements/${weekEnding}/notify`, { method: 'POST' });
    if (res?.ok) {
        toast(`Sent ${res.sent || 0} messages`);
    } else {
        toast('Failed to send notifications', 'error');
    }
}
