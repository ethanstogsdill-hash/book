/* Bets tab — filterable list of wagers */

tabLoaders['bets'] = loadBets;

async function loadBets() {
    const el = document.getElementById('tab-bets');

    // Get available sports
    const sportsData = await apiJson('/api/bets/sports');
    const sports = sportsData?.sports || [];
    const statsData = await apiJson('/api/bets/stats');

    el.innerHTML = `
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div class="stat-card">
                <div class="label">Total Bets</div>
                <div class="value text-blue-400">${statsData?.total || 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Pending</div>
                <div class="value text-yellow-400">${statsData?.pending || 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Wins</div>
                <div class="value balance-negative">${statsData?.wins || 0}</div>
            </div>
            <div class="stat-card">
                <div class="label">Losses</div>
                <div class="value balance-positive">${statsData?.losses || 0}</div>
            </div>
        </div>
        <div class="search-bar">
            <select id="betSport" class="input" style="max-width:150px" onchange="loadBetTable()">
                <option value="">All Sports</option>
                ${sports.map(s => `<option value="${s}">${esc(s)}</option>`).join('')}
            </select>
            <select id="betResult" class="input" style="max-width:130px" onchange="loadBetTable()">
                <option value="">All Results</option>
                <option value="pending">Pending</option>
                <option value="win">Win</option>
                <option value="loss">Loss</option>
                <option value="push">Push</option>
            </select>
            <button class="btn btn-gray" onclick="loadBets()">Refresh</button>
        </div>
        <div id="betTableWrap" class="table-wrap"></div>
    `;
    await loadBetTable();
}

async function loadBetTable() {
    const params = new URLSearchParams();
    const sport = document.getElementById('betSport')?.value;
    const result = document.getElementById('betResult')?.value;
    if (sport) params.set('sport', sport);
    if (result) params.set('result', result);
    params.set('limit', '200');

    const data = await apiJson(`/api/bets?${params}`);
    if (!data) return;

    const wrap = document.getElementById('betTableWrap');
    if (!data.bets.length) {
        wrap.innerHTML = '<p class="text-slate-500 text-sm mt-4">No bets found</p>';
        return;
    }

    wrap.innerHTML = `
        <table class="data-table">
            <thead><tr>
                <th>Player</th>
                <th class="hide-mobile">Sport</th>
                <th>Description</th>
                <th>Risk</th>
                <th>Win</th>
                <th>Result</th>
            </tr></thead>
            <tbody>
                ${data.bets.map(b => {
                    const resultClass = b.result === 'win' ? 'balance-negative' :
                                       b.result === 'loss' ? 'balance-positive' :
                                       b.result === 'pending' ? 'text-yellow-400' : 'text-slate-400';
                    return `
                    <tr>
                        <td class="font-medium">${esc(b.player_name || b.player_id)}</td>
                        <td class="hide-mobile text-slate-400">${esc(b.sport)}</td>
                        <td class="text-slate-300" style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(b.description)}">${esc(b.description)}</td>
                        <td class="text-slate-300">${fmt(b.risk)}</td>
                        <td class="text-slate-300">${fmt(b.win_amount)}</td>
                        <td class="${resultClass} font-semibold">${esc(b.result)}</td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}
