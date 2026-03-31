/* Live Bets tab — grouped by sub-agent with color coding */

tabLoaders['livebets'] = loadLiveBets;

let liveBetsSort = { by: 'sub_agent_name', dir: 'desc' };
let liveBetsRefreshing = false;

async function loadLiveBets() {
    const el = document.getElementById('tab-livebets');

    const [summaryData, betsData] = await Promise.all([
        apiJson('/api/live-bets/summary'),
        apiJson(`/api/live-bets?sort_by=${liveBetsSort.by}&sort_dir=${liveBetsSort.dir}`),
    ]);

    if (!summaryData || !betsData) return;

    const groups = betsData.groups || [];
    const directs = betsData.direct_bets || [];
    const allBets = betsData.all_bets || [];

    el.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div class="flex items-center gap-3 flex-wrap">
                <button onclick="refreshLiveBets()" id="liveBetsRefreshBtn"
                    class="btn btn-green flex items-center gap-1">
                    <span id="liveBetsRefreshIcon">&#x21bb;</span> Refresh
                </button>
                <select class="input" style="max-width:180px" onchange="liveBetsSortChange(this.value)">
                    <option value="sub_agent_name" ${liveBetsSort.by==='sub_agent_name'?'selected':''}>Sort: Sub-Agent</option>
                    <option value="amount" ${liveBetsSort.by==='amount'?'selected':''}>Sort: Bet Size</option>
                    <option value="time_placed" ${liveBetsSort.by==='time_placed'?'selected':''}>Sort: Time Placed</option>
                    <option value="player_name" ${liveBetsSort.by==='player_name'?'selected':''}>Sort: Player Name</option>
                </select>
            </div>
            <span class="text-xs text-slate-500" id="liveBetsLastRefresh">
                ${summaryData.last_refreshed ? 'Last refreshed: ' + timeAgo(summaryData.last_refreshed) : 'Not yet refreshed'}
            </span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
            <div class="stat-card">
                <div class="label">Open Bets</div>
                <div class="value text-blue-400">${summaryData.total_bets || 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Wagered</div>
                <div class="value text-yellow-400">${fmt(summaryData.total_wagered || 0)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Potential Payout</div>
                <div class="value balance-negative">${fmt(summaryData.total_payout || 0)}</div>
            </div>
        </div>

        <div id="liveBetsContent">
            ${allBets.length === 0
                ? '<p class="text-slate-500 text-sm">No live bets. Click Refresh to scrape current open wagers.</p>'
                : renderLiveBetsGroups(groups, directs)
            }
        </div>
    `;

    if (summaryData.running) {
        liveBetsRefreshing = true;
        document.getElementById('liveBetsRefreshBtn').disabled = true;
        document.getElementById('liveBetsRefreshIcon').classList.add('spinning');
        pollLiveBetsStatus();
    }
}

function renderLiveBetsGroups(groups, directs) {
    let html = '';

    // Sub-agent groups
    groups.forEach(g => {
        html += `
        <div class="bg-slate-800 border border-slate-700 rounded-lg mb-3 overflow-hidden">
            <div class="px-4 py-3 border-b border-slate-700 flex flex-wrap justify-between items-center cursor-pointer gap-2"
                 onclick="this.nextElementSibling.classList.toggle('hidden')">
                <div class="flex items-center gap-3">
                    <span class="font-semibold text-purple-400">${esc(g.name)}</span>
                    <span class="text-xs text-slate-400">${g.bets.length} bet${g.bets.length !== 1 ? 's' : ''}</span>
                </div>
                <div class="flex gap-4 text-sm">
                    <span class="text-yellow-400">At Risk: ${fmt(g.total_amount)}</span>
                    <span class="balance-negative">Payout: ${fmt(g.total_payout)}</span>
                </div>
            </div>
            <div class="p-2">
                ${renderBetsTable(g.bets)}
            </div>
        </div>`;
    });

    // Direct players
    if (directs.length) {
        html += `
        <div class="bg-slate-800 border border-slate-700 rounded-lg mb-3 overflow-hidden">
            <div class="px-4 py-3 border-b border-slate-700 flex flex-wrap justify-between items-center cursor-pointer gap-2"
                 onclick="this.nextElementSibling.classList.toggle('hidden')">
                <div class="flex items-center gap-3">
                    <span class="font-semibold text-blue-400">Direct Players</span>
                    <span class="text-xs text-slate-400">${directs.length} bet${directs.length !== 1 ? 's' : ''}</span>
                </div>
                <div class="flex gap-4 text-sm">
                    <span class="text-yellow-400">At Risk: ${fmt(directs.reduce((s, b) => s + (b.amount || 0), 0))}</span>
                    <span class="balance-negative">Payout: ${fmt(directs.reduce((s, b) => s + (b.potential_payout || 0), 0))}</span>
                </div>
            </div>
            <div class="p-2">
                ${renderBetsTable(directs)}
            </div>
        </div>`;
    }

    return html;
}

function renderBetsTable(bets) {
    if (!bets.length) return '<p class="text-slate-500 text-sm p-2">No bets</p>';

    return `
        <div class="table-wrap">
            <table class="data-table">
                <thead><tr>
                    <th>Player</th>
                    <th>Bet</th>
                    <th>Amount</th>
                    <th class="hide-mobile">Odds</th>
                    <th>Payout</th>
                    <th class="hide-mobile">Time</th>
                </tr></thead>
                <tbody>
                    ${bets.map(b => {
                        const sizeClass = betSizeClass(b.amount, b.credit_limit);
                        return `
                        <tr>
                            <td class="font-medium">${esc(b.player_name || b.player_account)}</td>
                            <td class="text-slate-300" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(b.description)}">
                                ${b.sport ? '<span class="text-xs text-slate-500 mr-1">' + esc(b.sport) + '</span>' : ''}${esc(b.description)}
                            </td>
                            <td class="${sizeClass} font-semibold">${fmt(b.amount)}</td>
                            <td class="hide-mobile text-slate-400">${esc(b.odds)}</td>
                            <td class="balance-negative font-semibold">${fmt(b.potential_payout)}</td>
                            <td class="hide-mobile text-slate-400 text-xs">${esc(b.time_placed)}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function betSizeClass(amount, creditLimit) {
    if (!amount) return 'text-slate-300';
    if (!creditLimit || creditLimit <= 0) {
        // No credit limit set — use absolute thresholds
        if (amount >= 500) return 'balance-negative';  // red - large
        if (amount >= 200) return 'balance-warning';   // yellow - medium
        return 'balance-positive';                      // green - small
    }
    const ratio = amount / creditLimit;
    if (ratio >= 0.3) return 'balance-negative';   // red - large relative to limit
    if (ratio >= 0.1) return 'balance-warning';    // yellow - medium
    return 'balance-positive';                      // green - small
}

function liveBetsSortChange(value) {
    liveBetsSort.by = value;
    liveBetsSort.dir = (value === 'amount' || value === 'time_placed') ? 'desc' : 'asc';
    loadLiveBets();
}

async function refreshLiveBets() {
    const btn = document.getElementById('liveBetsRefreshBtn');
    const icon = document.getElementById('liveBetsRefreshIcon');
    btn.disabled = true;
    icon.classList.add('spinning');
    liveBetsRefreshing = true;

    const data = await apiJson('/api/live-bets/refresh', { method: 'POST' });
    if (data?.ok) {
        toast('Live bets refresh started');
        pollLiveBetsStatus();
    } else {
        toast(data?.error || 'Refresh failed', 'error');
        btn.disabled = false;
        icon.classList.remove('spinning');
        liveBetsRefreshing = false;
    }
}

async function pollLiveBetsStatus() {
    const check = async () => {
        const data = await apiJson('/api/live-bets/status');
        if (data && !data.running) {
            const btn = document.getElementById('liveBetsRefreshBtn');
            const icon = document.getElementById('liveBetsRefreshIcon');
            if (btn) btn.disabled = false;
            if (icon) icon.classList.remove('spinning');
            liveBetsRefreshing = false;

            if (data.last_status === 'success') {
                toast(data.last_message || 'Live bets refreshed');
            } else if (data.last_status === 'error') {
                toast(data.last_message || 'Refresh failed', 'error');
            }
            // Reload the tab data
            loadLiveBets();
            return;
        }
        setTimeout(check, 3000);
    };
    setTimeout(check, 3000);
}
