/* Main app controller — auth check, API wrapper, tab switching, utilities */

// ─── Auth Check ──────────────────────────────────────────
fetch('/api/auth/me').then(r => { if (!r.ok) window.location.href = '/'; });

// ─── API Helper ──────────────────────────────────────────
async function api(path, opts = {}) {
    const res = await fetch(path, {
        ...opts,
        headers: { 'Content-Type': 'application/json', ...opts.headers },
    });
    if (res.status === 401) { window.location.href = '/'; return null; }
    return res;
}

async function apiJson(path, opts = {}) {
    const res = await api(path, opts);
    if (!res) return null;
    return res.json();
}

// ─── Tab Switching ──────────────────────────────────────────
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanels = document.querySelectorAll('.tab-content');

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        tabPanels.forEach(p => p.classList.add('hidden'));
        document.getElementById(`tab-${tab}`).classList.remove('hidden');
        loadTab(tab);
    });
});

const tabLoaders = {};
function loadTab(tab) {
    if (tabLoaders[tab]) tabLoaders[tab]();
}

// ─── Formatting ──────────────────────────────────────────
function fmt(n) {
    if (n == null || isNaN(n)) return '$0.00';
    const abs = Math.abs(n);
    const str = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return n < 0 ? `-$${str}` : `$${str}`;
}

function balanceClass(amount, creditLimit) {
    if (amount == null || amount === 0) return 'balance-zero';
    if (creditLimit && Math.abs(amount) > creditLimit * 0.8) return 'balance-warning';
    return amount > 0 ? 'balance-positive' : 'balance-negative';
}

function badgeHtml(status) {
    const cls = `badge badge-${status || 'active'}`;
    return `<span class="${cls}">${esc(status || 'active')}</span>`;
}

function esc(s) {
    if (s == null) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

function timeAgo(isoStr) {
    if (!isoStr) return 'Never';
    const d = new Date(isoStr + (isoStr.includes('Z') ? '' : 'Z'));
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

// ─── Toast ──────────────────────────────────────────
function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// ─── Sync Now ──────────────────────────────────────────
async function triggerScrape() {
    const btn = document.getElementById('syncBtn');
    const icon = document.getElementById('syncIcon');
    btn.disabled = true;
    icon.classList.add('spinning');

    const data = await apiJson('/api/scrape/trigger', { method: 'POST' });
    if (data?.ok) {
        toast('Scrape started');
        // Poll for completion
        pollScrapeStatus();
    } else {
        toast(data?.error || 'Scrape failed', 'error');
        btn.disabled = false;
        icon.classList.remove('spinning');
    }
}

async function pollScrapeStatus() {
    const check = async () => {
        const data = await apiJson('/api/scrape/status');
        if (data && !data.running) {
            document.getElementById('syncBtn').disabled = false;
            document.getElementById('syncIcon').classList.remove('spinning');
            if (data.last_status === 'success') {
                toast(data.last_message || 'Sync complete');
            } else {
                toast(data.last_message || 'Sync failed', 'error');
            }
            updateLastSync(data.last_success?.created_at);
            // Refresh current tab
            const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
            if (activeTab) loadTab(activeTab);
            return;
        }
        setTimeout(check, 3000);
    };
    setTimeout(check, 3000);
}

function updateLastSync(isoStr) {
    const el = document.getElementById('lastSync');
    if (isoStr) {
        el.textContent = `Last sync: ${timeAgo(isoStr)}`;
        el.classList.remove('hidden');
    }
}

// ─── Logout ──────────────────────────────────────────
async function logout() {
    await api('/api/auth/logout', { method: 'POST' });
    window.location.href = '/';
}

// ─── Player Modal ──────────────────────────────────────────
function closePlayerModal() { document.getElementById('playerModal').classList.add('hidden'); }
function closeSubAgentModal() { document.getElementById('subAgentModal').classList.add('hidden'); }

// ─── Activity Panel ──────────────────────────────────────────
function showActivityPanel() {
    document.getElementById('activityPanel').classList.remove('hidden');
    loadActivityPanel();
}
function hideActivityPanel() { document.getElementById('activityPanel').classList.add('hidden'); }

// ─── Init: Load overview tab ──────────────────────────────────────────
loadTab('overview');

// Check scrape status on load
apiJson('/api/scrape/status').then(data => {
    if (data) {
        updateLastSync(data.last_success?.created_at);
        if (data.running) {
            document.getElementById('syncBtn').disabled = true;
            document.getElementById('syncIcon').classList.add('spinning');
            pollScrapeStatus();
        }
    }
});
