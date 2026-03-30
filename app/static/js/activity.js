/* Activity log panel — sync history and alerts */

async function loadActivityPanel() {
    const data = await apiJson('/api/activity?limit=30');
    if (!data) return;

    const el = document.getElementById('activityContent');

    const logs = data.logs || [];
    const alerts = data.alerts || [];

    let html = '<h3 class="text-sm font-semibold text-slate-400 mb-2 uppercase">Sync History</h3>';

    if (logs.length) {
        html += logs.map(l => `
            <div class="alert-item ${l.status === 'error' ? 'alert-error' : ''}">
                <div class="flex justify-between items-center">
                    <span class="text-sm ${l.status === 'success' ? 'text-green-400' : l.status === 'error' ? 'text-red-400' : 'text-yellow-400'}">
                        ${esc(l.run_type)} — ${esc(l.status)}
                    </span>
                    <span class="text-xs text-slate-500">${timeAgo(l.created_at)}</span>
                </div>
                ${l.message ? `<div class="text-xs text-slate-400 mt-1">${esc(l.message)}</div>` : ''}
                ${l.duration_seconds ? `<div class="text-xs text-slate-500">${l.duration_seconds.toFixed(1)}s</div>` : ''}
            </div>
        `).join('');
    } else {
        html += '<p class="text-slate-500 text-sm mb-4">No sync history</p>';
    }

    html += '<h3 class="text-sm font-semibold text-slate-400 mt-4 mb-2 uppercase">Alerts</h3>';

    if (alerts.length) {
        html += alerts.map(a => `
            <div class="alert-item ${a.alert_type === 'scrape_error' ? 'alert-error' : 'alert-warning'}">
                <div class="text-sm text-white">${esc(a.message)}</div>
                <div class="text-xs text-slate-400 mt-1">
                    ${timeAgo(a.timestamp)} &middot; ${esc(a.alert_type)}
                    ${a.sent_via_telegram ? ' &middot; Sent via Telegram' : ''}
                </div>
            </div>
        `).join('');
    } else {
        html += '<p class="text-slate-500 text-sm">No alerts</p>';
    }

    el.innerHTML = html;
}
