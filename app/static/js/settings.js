/* Settings tab — thresholds, alerts, password */

tabLoaders['settings'] = loadSettings;

async function loadSettings() {
    const data = await apiJson('/api/settings');
    if (!data) return;
    const s = data.settings || {};

    const el = document.getElementById('tab-settings');
    el.innerHTML = `
        <div class="max-w-2xl">
            <h3 class="section-header">Alert Thresholds</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div>
                    <label class="text-slate-400 text-xs">Player Balance Alert ($)</label>
                    <input class="input mt-1" id="setBalanceThreshold" type="number" value="${s.balance_alert_threshold || 1000}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Sub-Agent Book Threshold ($)</label>
                    <input class="input mt-1" id="setSubBookThreshold" type="number" value="${s.sub_agent_book_threshold || 5000}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Credit Limit Warning (%)</label>
                    <input class="input mt-1" id="setCreditWarning" type="number" value="${s.credit_limit_warning_pct || 80}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Telegram Alerts</label>
                    <select class="input mt-1" id="setTelegramAlerts">
                        <option value="true" ${s.telegram_alerts_enabled === 'true' ? 'selected' : ''}>Enabled</option>
                        <option value="false" ${s.telegram_alerts_enabled === 'false' ? 'selected' : ''}>Disabled</option>
                    </select>
                </div>
            </div>

            <h3 class="section-header">Vig & Payday</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div>
                    <label class="text-slate-400 text-xs">Default Vig Rate (%)</label>
                    <input class="input mt-1" id="setVigRate" type="number" step="0.1" value="${s.default_vig_rate || 10}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Backer Vig Split (%)</label>
                    <input class="input mt-1" id="setBackerSplit" type="number" step="0.1" value="${s.backer_vig_split || 50}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Scrape Interval (minutes)</label>
                    <input class="input mt-1" id="setScrapeInterval" type="number" value="${s.auto_scrape_interval_min || 60}">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">Payday Hour (24h, e.g. 9 = 9am)</label>
                    <input class="input mt-1" id="setPaydayHour" type="number" min="0" max="23" value="${s.payday_hour || 9}">
                </div>
            </div>

            <button class="btn btn-green" onclick="saveSettings()">Save Settings</button>

            <hr class="border-slate-700 my-6">

            <h3 class="section-header">Change Password</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                    <label class="text-slate-400 text-xs">Current Password</label>
                    <input class="input mt-1" id="currentPw" type="password">
                </div>
                <div>
                    <label class="text-slate-400 text-xs">New Password</label>
                    <input class="input mt-1" id="newPw" type="password">
                </div>
            </div>
            <button class="btn btn-blue" onclick="changePassword()">Change Password</button>

            <hr class="border-slate-700 my-6">

            <h3 class="section-header">Telegram Bot Test</h3>
            <p class="text-slate-400 text-sm mb-3">Send a test message to verify your Telegram bot is configured correctly.</p>
            <button class="btn btn-gray" onclick="testTelegram()">Send Test Message</button>
        </div>
    `;
}

async function saveSettings() {
    const settings = {
        balance_alert_threshold: document.getElementById('setBalanceThreshold').value,
        sub_agent_book_threshold: document.getElementById('setSubBookThreshold').value,
        credit_limit_warning_pct: document.getElementById('setCreditWarning').value,
        telegram_alerts_enabled: document.getElementById('setTelegramAlerts').value,
        default_vig_rate: document.getElementById('setVigRate').value,
        backer_vig_split: document.getElementById('setBackerSplit').value,
        auto_scrape_interval_min: document.getElementById('setScrapeInterval').value,
        payday_hour: document.getElementById('setPaydayHour').value,
    };
    const res = await apiJson('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify({ settings }),
    });
    if (res?.ok) toast('Settings saved');
}

async function changePassword() {
    const current = document.getElementById('currentPw').value;
    const newPw = document.getElementById('newPw').value;
    if (!current || !newPw) { toast('Fill in both fields', 'error'); return; }
    if (newPw.length < 4) { toast('Password too short', 'error'); return; }
    const res = await apiJson('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: newPw }),
    });
    if (res?.ok) {
        toast('Password changed');
        document.getElementById('currentPw').value = '';
        document.getElementById('newPw').value = '';
    } else {
        toast(res?.detail || 'Failed to change password', 'error');
    }
}

async function testTelegram() {
    const res = await apiJson('/api/telegram/test');
    if (res?.ok) toast('Test message sent!');
    else toast(res?.error || 'Telegram test failed', 'error');
}
