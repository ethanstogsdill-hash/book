/* Weekly view tab — grouped by sub-agent with player breakdowns */

tabLoaders['weekly'] = loadWeekly;

async function loadWeekly() {
    const el = document.getElementById('tab-weekly');
    const weeksData = await apiJson('/api/weeks');
    const weeks = weeksData?.weeks || [];

    if (!weeks.length) {
        el.innerHTML = '<p class="text-slate-500 text-sm mt-4">No weekly data yet. Sync data to populate.</p>';
        return;
    }

    const currentWeek = weeks[0];
    el.innerHTML = `
        <div class="search-bar">
            <select id="weekSelect" class="input" style="max-width:200px" onchange="loadWeekData(this.value)">
                ${weeks.map(w => `<option value="${w}">${w}</option>`).join('')}
            </select>
        </div>
        <div id="weekContent"></div>
    `;
    await loadWeekData(currentWeek);
}

async function loadWeekData(weekEnding) {
    const data = await apiJson(`/api/weeks/${weekEnding}`);
    if (!data) return;

    const wrap = document.getElementById('weekContent');
    const groups = data.sub_agent_groups || [];
    const directs = data.direct_players || [];

    let totalNet = 0;
    groups.forEach(g => totalNet += g.total_net);
    directs.forEach(d => totalNet += (d.net || 0));

    let html = `
        <div class="stat-card mb-4">
            <div class="label">Week Ending ${esc(weekEnding)} — Total Net</div>
            <div class="value ${totalNet <= 0 ? 'balance-positive' : 'balance-negative'}">${fmt(totalNet)}</div>
        </div>
    `;

    // Sub-agent groups
    groups.forEach(g => {
        html += `
        <div class="bg-slate-800 border border-slate-700 rounded-lg mb-3 overflow-hidden">
            <div class="px-4 py-3 bg-slate-750 border-b border-slate-700 flex justify-between items-center cursor-pointer"
                 onclick="this.nextElementSibling.classList.toggle('hidden')">
                <span class="font-semibold text-purple-400">${esc(g.name)}</span>
                <span class="${g.total_net <= 0 ? 'balance-positive' : 'balance-negative'} font-semibold">${fmt(g.total_net)}</span>
            </div>
            <div class="p-2">
                <table class="data-table">
                    <thead><tr><th>Player</th><th>Won/Lost</th><th>Vig</th><th>Net</th></tr></thead>
                    <tbody>
                        ${g.players.map(p => `
                        <tr>
                            <td>${esc(p.player_name || p.player_account || 'Unknown')}</td>
                            <td class="${(p.won_lost||0) <= 0 ? 'balance-positive' : 'balance-negative'}">${fmt(p.won_lost)}</td>
                            <td class="text-slate-400">${fmt(p.vig)}</td>
                            <td class="${(p.net||0) <= 0 ? 'balance-positive' : 'balance-negative'} font-semibold">${fmt(p.net)}</td>
                        </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>`;
    });

    // Direct players
    if (directs.length) {
        html += `
        <div class="bg-slate-800 border border-slate-700 rounded-lg mb-3 overflow-hidden">
            <div class="px-4 py-3 bg-slate-750 border-b border-slate-700">
                <span class="font-semibold text-blue-400">Direct Players</span>
            </div>
            <div class="p-2">
                <table class="data-table">
                    <thead><tr><th>Player</th><th>Won/Lost</th><th>Vig</th><th>Net</th></tr></thead>
                    <tbody>
                        ${directs.map(p => `
                        <tr>
                            <td>${esc(p.player_name || p.player_account || 'Unknown')}</td>
                            <td class="${(p.won_lost||0) <= 0 ? 'balance-positive' : 'balance-negative'}">${fmt(p.won_lost)}</td>
                            <td class="text-slate-400">${fmt(p.vig)}</td>
                            <td class="${(p.net||0) <= 0 ? 'balance-positive' : 'balance-negative'} font-semibold">${fmt(p.net)}</td>
                        </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>`;
    }

    wrap.innerHTML = html;
}
