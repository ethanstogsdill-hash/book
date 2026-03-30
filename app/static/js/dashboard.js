/* Overview tab — stat cards and recent alerts */

tabLoaders['overview'] = loadOverview;

async function loadOverview() {
    const data = await apiJson('/api/dashboard/summary');
    if (!data) return;

    const el = document.getElementById('tab-overview');
    el.innerHTML = `
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
            <div class="stat-card">
                <div class="label">Total Players</div>
                <div class="value text-blue-400">${data.total_players}</div>
            </div>
            <div class="stat-card">
                <div class="label">Sub-Agents</div>
                <div class="value text-purple-400">${data.total_sub_agents}</div>
            </div>
            <div class="stat-card">
                <div class="label">Net Position</div>
                <div class="value ${data.net_position >= 0 ? 'balance-positive' : 'balance-negative'}">
                    ${fmt(data.net_position)}
                </div>
            </div>
            <div class="stat-card">
                <div class="label">Outstanding</div>
                <div class="value text-slate-300">${fmt(data.total_outstanding)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Flagged</div>
                <div class="value ${data.flagged_players > 0 ? 'text-red-400' : 'text-slate-500'}">
                    ${data.flagged_players}
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
                <div class="stat-card">
                    <div class="label">Owed To Me</div>
                    <div class="value balance-positive">${fmt(data.total_owed_to_me)}</div>
                </div>
            </div>
            <div>
                <div class="stat-card">
                    <div class="label">I Owe</div>
                    <div class="value balance-negative">${fmt(data.total_i_owe)}</div>
                </div>
            </div>
        </div>

        <div class="mt-6">
            <h3 class="section-header">Recent Alerts</h3>
            <div id="overviewAlerts">
                ${data.recent_alerts && data.recent_alerts.length > 0
                    ? data.recent_alerts.map(a => `
                        <div class="alert-item ${a.alert_type === 'scrape_error' ? 'alert-error' : a.alert_type === 'balance_threshold' ? 'alert-warning' : ''}">
                            <div class="text-sm text-white">${esc(a.message)}</div>
                            <div class="text-xs text-slate-400 mt-1">${timeAgo(a.timestamp)} &middot; ${esc(a.alert_type)}</div>
                        </div>
                    `).join('')
                    : '<p class="text-slate-500 text-sm">No recent alerts</p>'
                }
            </div>
        </div>

        <div class="mt-4 text-xs text-slate-500">
            Last sync: ${data.last_scrape ? timeAgo(data.last_scrape) : 'Never'}
        </div>
    `;
}
