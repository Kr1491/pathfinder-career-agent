/**
 * PathFinder — main frontend JS
 * Handles: chat (SSE streaming), dashboard, skill-gap, roadmap, navigation
 */

/* ═══════════════════════════ STATE ═══════════════════════════════════════ */
const state = {
  currentView: 'chat',
  profile: { name: '', education: '', skills: '', interests: '' },
  demoMode: false,
  roles: [],
  isStreaming: false,
};

/* ═══════════════════════════ DOM REFS ════════════════════════════════════ */
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

/* ═══════════════════════════ INIT ════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  // Check app info
  try {
    const info = await apiFetch('/api/info');
    state.demoMode = info.demo_mode;
    if (info.demo_mode) {
      $$('.demo-badge').forEach(el => el.style.display = 'inline-flex');
    }
  } catch (e) { /* silent */ }

  // Load dashboard data in background
  loadDashboardData();

  // Wire up nav
  $$('.nav-item').forEach(el => {
    el.addEventListener('click', () => switchView(el.dataset.view));
  });

  // Profile fields sync
  ['name', 'education', 'skills', 'interests'].forEach(f => {
    const el = $(`profile-${f}`);
    if (el) el.addEventListener('input', () => { state.profile[f] = el.value; });
  });

  // Chat input
  const input = $('chat-input');
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  input.addEventListener('input', autoResize);

  // Suggestion chips
  $$('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.msg;
      autoResize.call(input);
      sendMessage();
    });
  });

  // Sidebar toggle
  $('sidebar-toggle').addEventListener('click', () => {
    $('sidebar').classList.toggle('collapsed');
  });

  // Clear chat
  $('clear-chat-btn').addEventListener('click', clearChat);

  // Skill-gap analyse button
  $('analyze-btn').addEventListener('click', runSkillGap);

  // Roadmap generate button
  $('gen-roadmap-btn').addEventListener('click', generateRoadmap);

  // Role select listener
  $('role-select').addEventListener('change', () => {
    const id = $('role-select').value;
    if (id) runSkillGapById(id);
  });
});

/* ═══════════════════════════ NAVIGATION ══════════════════════════════════ */
function switchView(view) {
  state.currentView = view;
  $$('.view').forEach(v => v.classList.remove('active'));
  const target = $(`${view}-view`);
  if (target) target.classList.add('active');

  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));

  const titles = { chat: '💬 Career Chat', dashboard: '📊 Dashboard', roadmap: '🗺️ Roadmap Planner' };
  $('view-title').textContent = titles[view] || 'PathFinder';

  // Close sidebar on mobile after nav
  if (window.innerWidth <= 768) {
    $('sidebar').classList.add('collapsed');
  }
}

/* ═══════════════════════════ CHAT ════════════════════════════════════════ */
async function sendMessage() {
  if (state.isStreaming) return;
  const input = $('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  autoResize.call(input);
  hideWelcome();

  appendUserMessage(text);
  const typingId = appendTyping();

  state.isStreaming = true;
  $('send-btn').disabled = true;

  try {
    await streamResponse(text, typingId);
  } catch (err) {
    removeTyping(typingId);
    appendBotMessage(`⚠️ Error: ${err.message}. Please try again.`);
  } finally {
    state.isStreaming = false;
    $('send-btn').disabled = false;
  }
}

async function streamResponse(text, typingId) {
  const body = {
    message: text,
    profile: {
      name: state.profile.name,
      education: state.profile.education,
      skills: state.profile.skills ? state.profile.skills.split(',').map(s => s.trim()) : [],
      interests: state.profile.interests,
    }
  };

  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  removeTyping(typingId);
  const msgId = appendBotMessage('', true);
  const bubble = document.querySelector(`[data-msg-id="${msgId}"] .msg-bubble`);
  let fullText = '';

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);
      if (data === '[DONE]') { renderMarkdown(bubble, fullText); scrollToBottom(); return; }
      try {
        const parsed = JSON.parse(data);
        if (parsed.token) {
          fullText += parsed.token;
          renderMarkdown(bubble, fullText);
          scrollToBottom();
        }
      } catch (_) { /* partial chunk */ }
    }
  }
  renderMarkdown(bubble, fullText);
  scrollToBottom();
}

function hideWelcome() {
  const w = $('welcome');
  if (w) { w.style.display = 'none'; }
}

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'msg-row user';
  row.innerHTML = `
    <div class="msg-avatar">👤</div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble">${escapeHtml(text)}</div>
      <div class="msg-meta">${formatTime()}</div>
    </div>`;
  $('chat-messages').appendChild(row);
  scrollToBottom();
}

let _msgCounter = 0;
function appendBotMessage(text, streaming = false) {
  const id = ++_msgCounter;
  const row = document.createElement('div');
  row.className = 'msg-row bot';
  row.dataset.msgId = id;
  row.innerHTML = `
    <div class="msg-avatar">🧭</div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble">${streaming ? '<span class="cursor-blink">▌</span>' : renderMd(text)}</div>
      <div class="msg-meta">${formatTime()}${state.demoMode ? ' · <span class="demo-badge">Demo Mode</span>' : ' · <span style="color:var(--pf-success)">●</span> Granite'}</div>
    </div>`;
  $('chat-messages').appendChild(row);
  scrollToBottom();
  return id;
}

function appendTyping() {
  const id = ++_msgCounter;
  const row = document.createElement('div');
  row.className = 'msg-row bot';
  row.dataset.msgId = id;
  row.innerHTML = `
    <div class="msg-avatar">🧭</div>
    <div>
      <div class="msg-bubble typing-bubble">
        <span></span><span></span><span></span>
      </div>
    </div>`;
  $('chat-messages').appendChild(row);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const el = document.querySelector(`[data-msg-id="${id}"]`);
  if (el) el.remove();
}

function renderMarkdown(el, md) {
  el.innerHTML = renderMd(md) + '<span class="cursor-blink" style="color:var(--pf-accent);">▌</span>';
}

async function clearChat() {
  await apiFetch('/api/chat/session', { method: 'DELETE' });
  $('chat-messages').innerHTML = '';
  const w = $('welcome');
  if (w) w.style.display = 'flex';
  showToast('Chat cleared', 'success');
}

/* ═══════════════════════════ DASHBOARD ══════════════════════════════════ */
async function loadDashboardData() {
  try {
    const data = await apiFetch('/api/dashboard/overview');
    state.roles = data.roles || [];
    renderTrendingChart(data.trending_skills || []);
    renderRoleCards(data.roles || []);
    populateRoleSelect(data.roles || []);
    renderOutlookStats(data.industry_outlook || {});
    updateStatCards(data);
  } catch (e) {
    console.warn('Dashboard load failed:', e);
  }
}

function updateStatCards(data) {
  const roles = data.roles || [];
  const trending = data.trending_skills || [];
  const outlook = data.industry_outlook || {};

  const vhRoles = roles.filter(r => r.demand === 'very_high').length;
  const topSkill = trending.sort((a, b) => b.demand_score - a.demand_score)[0];
  const booming = Object.entries(outlook).filter(([, v]) => v.hiring_index >= 85).length;

  const el = $('stat-cards');
  if (!el) return;
  el.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Tracked Roles</div>
      <div class="stat-value">${roles.length}</div>
      <div class="stat-sub">${vhRoles} very high demand</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Top Trending Skill</div>
      <div class="stat-value" style="font-size:18px">${topSkill ? topSkill.skill : '—'}</div>
      <div class="stat-sub">Score ${topSkill ? topSkill.demand_score : 0}/100</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">High-growth Industries</div>
      <div class="stat-value">${booming}</div>
      <div class="stat-sub">hiring index ≥ 85/100</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Data Source</div>
      <div class="stat-value" style="font-size:14px;margin-top:4px;">LM Intelligence</div>
      <div class="stat-sub">2025-Q1 · ${roles.length} roles indexed</div>
    </div>`;
}

function renderTrendingChart(skills) {
  const container = $('trending-bars');
  if (!container) return;
  const sorted = [...skills].sort((a, b) => b.demand_score - a.demand_score).slice(0, 10);
  container.innerHTML = sorted.map(s => {
    const pct = s.demand_score;
    const color = pct >= 90 ? 'fill-green' : pct >= 75 ? 'fill-blue' : 'fill-yellow';
    return `
      <div class="trend-bar-row">
        <div class="trend-label">${escapeHtml(s.skill)}</div>
        <div class="trend-bar-outer">
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
          </div>
        </div>
        <div class="trend-score-label">${pct}</div>
      </div>`;
  }).join('');
}

function renderRoleCards(roles) {
  const container = $('role-cards-grid');
  if (!container) return;
  container.innerHTML = roles.map(r => {
    const s = r.salary_usd || {};
    return `
      <div class="role-card" onclick="quickGapFromCard('${r.id}')">
        <div class="role-title">${escapeHtml(r.title)}</div>
        <div class="role-meta">${escapeHtml(r.category)} · ${r.yoy_growth_pct}% YoY growth</div>
        <div class="role-meta" style="margin-top:4px;">
          <span class="demand-badge demand-${r.demand}">${r.demand.replace('_', ' ')}</span>
        </div>
        <div class="role-salary">$${(s.entry||0).toLocaleString()} – $${(s.senior||0).toLocaleString()}</div>
        <div style="margin-top:8px;">${(r.required_skills||[]).slice(0,3).map(sk => `<span class="skill-tag">${escapeHtml(sk)}</span>`).join('')}</div>
      </div>`;
  }).join('');
}

function populateRoleSelect(roles) {
  const sel = $('role-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">— Select target role —</option>' +
    roles.map(r => `<option value="${r.id}">${escapeHtml(r.title)}</option>`).join('');
}

function renderOutlookStats(outlook) {
  const container = $('outlook-bars');
  if (!container) return;
  const entries = Object.entries(outlook).sort((a, b) => b[1].hiring_index - a[1].hiring_index);
  container.innerHTML = entries.map(([industry, data]) => {
    const pct = data.hiring_index;
    const color = pct >= 85 ? 'fill-green' : pct >= 65 ? 'fill-blue' : 'fill-yellow';
    return `
      <div class="trend-bar-row">
        <div class="trend-label" style="font-size:12px;">${escapeHtml(industry)}</div>
        <div class="trend-bar-outer">
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
          </div>
        </div>
        <div class="trend-score-label">${pct}</div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════ SKILL GAP ══════════════════════════════════ */
async function runSkillGap() {
  const skillsInput = $('sg-skills').value.trim();
  const roleId = $('role-select').value;
  if (!skillsInput) { showToast('Enter your skills first', 'error'); return; }
  if (!roleId) { showToast('Select a target role', 'error'); return; }

  const skills = skillsInput.split(',').map(s => s.trim()).filter(Boolean);
  await runSkillGapById(roleId, skills);
}

async function runSkillGapById(roleId, skills) {
  const skillsToUse = skills || ($('sg-skills').value || state.profile.skills || '').split(',').map(s => s.trim()).filter(Boolean);

  try {
    const result = await apiFetch('/api/dashboard/skill-gap', {
      method: 'POST',
      body: JSON.stringify({ skills: skillsToUse, role_id: roleId }),
    });
    renderSkillGapResult(result);
    switchView('dashboard');
    setTimeout(() => $('skill-gap-result').scrollIntoView({ behavior: 'smooth' }), 100);
  } catch (e) {
    showToast('Skill gap analysis failed', 'error');
  }
}

function renderSkillGapResult(data) {
  const container = $('skill-gap-result');
  if (!container || data.error) return;

  const score = data.match_score || 0;
  const color = score >= 70 ? 'fill-green' : score >= 40 ? 'fill-yellow' : 'fill-red';
  const s = data.salary_range || {};

  container.innerHTML = `
    <div style="margin-bottom:14px;">
      <div style="font-size:16px;font-weight:700;margin-bottom:4px;">${escapeHtml(data.role_title)}</div>
      <div style="font-size:13px;color:var(--pf-muted);margin-bottom:10px;">
        Salary: <strong style="color:var(--pf-success)">$${(s.entry||0).toLocaleString()} – $${(s.senior||0).toLocaleString()}</strong>
      </div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span style="font-size:13px;color:var(--pf-muted);">Match score</span>
        <span style="font-size:20px;font-weight:800;color:var(--pf-text);">${score}%</span>
      </div>
      <div class="progress-bar-wrap"><div class="progress-bar-fill ${color}" style="width:${score}%"></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <div>
        <div style="font-size:12px;color:var(--pf-success);font-weight:600;margin-bottom:6px;">✓ Matched Skills (${data.matched_skills.length})</div>
        <div>${(data.matched_skills||[]).map(s => `<span class="skill-tag matched">✓ ${escapeHtml(s)}</span>`).join('')||'<span style="color:var(--pf-muted);font-size:12px;">None yet</span>'}</div>
      </div>
      <div>
        <div style="font-size:12px;color:var(--pf-danger);font-weight:600;margin-bottom:6px;">✗ Skills to Develop (${data.missing_skills.length})</div>
        <div>${(data.missing_skills||[]).map(s => `<span class="skill-tag missing">✗ ${escapeHtml(s)}</span>`).join('')||'<span style="color:var(--pf-success);font-size:12px;">You have all required skills!</span>'}</div>
      </div>
    </div>
    ${data.certifications.length ? `
    <div style="margin-bottom:10px;">
      <div style="font-size:12px;color:var(--pf-accent);font-weight:600;margin-bottom:6px;">🏆 Recommended Certifications</div>
      <div>${data.certifications.map(c => `<span class="skill-tag">${escapeHtml(c)}</span>`).join('')}</div>
    </div>` : ''}
    ${data.entry_paths.length ? `
    <div>
      <div style="font-size:12px;color:var(--pf-muted);font-weight:600;margin-bottom:6px;">🚀 Entry Paths</div>
      <ul style="margin:0;padding-left:16px;font-size:13px;color:var(--pf-muted);">
        ${data.entry_paths.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
      </ul>
    </div>` : ''}`;

  // Sync skills input in dashboard
  if ($('sg-skills') && state.profile.skills) {
    $('sg-skills').value = state.profile.skills;
  }
}

function quickGapFromCard(roleId) {
  $('role-select').value = roleId;
  if (state.profile.skills) {
    runSkillGapById(roleId);
  } else {
    showToast('Enter your skills in the profile bar (chat view) or the skill gap input', 'success');
    switchView('dashboard');
    setTimeout(() => $('role-select').scrollIntoView({ behavior: 'smooth' }), 100);
  }
}

/* ═══════════════════════════ ROADMAP ════════════════════════════════════ */
async function generateRoadmap() {
  const profile = {
    name:       $('rm-name')?.value      || state.profile.name      || 'Student',
    education:  $('rm-edu')?.value       || state.profile.education || '',
    skills:     ($('rm-skills')?.value   || state.profile.skills    || '').split(',').map(s=>s.trim()).filter(Boolean),
    interests:  $('rm-interests')?.value || state.profile.interests || '',
  };

  const output = $('roadmap-output');
  const btn = $('gen-roadmap-btn');
  if (!output) return;

  btn.disabled = true;
  btn.textContent = '⏳ Generating...';
  output.innerHTML = '<span style="color:var(--pf-muted)">Generating your personalised roadmap…</span>';

  try {
    const result = await apiFetch('/api/dashboard/roadmap', {
      method: 'POST',
      body: JSON.stringify({ profile }),
    });
    output.innerHTML = renderMd(result.roadmap || 'No roadmap generated.');
  } catch (e) {
    output.innerHTML = `<span style="color:var(--pf-danger)">Error generating roadmap: ${escapeHtml(e.message)}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🗺️ Generate Roadmap';
  }
}

/* ═══════════════════════════ UTILS ══════════════════════════════════════ */
async function apiFetch(url, opts = {}) {
  const defaults = { headers: { 'Content-Type': 'application/json' } };
  const res = await fetch(url, { ...defaults, ...opts, headers: { ...defaults.headers, ...(opts.headers || {}) } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderMd(text) {
  // Very light markdown renderer (no external dependency)
  let s = escapeHtml(text);
  // Code blocks (must come before any inline replacements)
  s = s.replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // Inline code
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic (only after bold so ** isn't consumed twice)
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  // Headings — longest match first so #### isn't partially caught by ###
  s = s.replace(/^#{5,} (.+)$/gm, '<h3>$1</h3>');  // H5+ → styled as h3
  s = s.replace(/^#### (.+)$/gm,   '<h3>$1</h3>');  // H4  → styled as h3
  s = s.replace(/^### (.+)$/gm,    '<h3>$1</h3>');
  s = s.replace(/^## (.+)$/gm,     '<h2>$1</h2>');
  s = s.replace(/^# (.+)$/gm,      '<h1>$1</h1>');
  // Blockquote
  s = s.replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:3px solid var(--pf-border);margin:6px 0;padding:4px 12px;color:var(--pf-muted);">$1</blockquote>');
  // HR
  s = s.replace(/^---$/gm, '<hr style="border-color:var(--pf-border);margin:12px 0;">');
  // Bullets
  s = s.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>.*<\/li>)/gs, (m) => {
    const items = m.split('\n').filter(Boolean);
    return '<ul>' + items.join('') + '</ul>';
  });
  // Numbered list
  s = s.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // Line breaks for non-block elements
  s = s.replace(/\n\n/g, '</p><p>');
  s = s.replace(/\n/g, '<br>');
  if (!s.startsWith('<')) s = '<p>' + s + '</p>';
  return s;
}

function formatTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function scrollToBottom() {
  const el = $('chat-messages');
  if (el) el.scrollTop = el.scrollHeight;
}

function autoResize() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 140) + 'px';
}

function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast-msg ${type}`;
  toast.textContent = msg;
  $('toast-area').appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

/* expose for inline HTML calls */
window.quickGapFromCard = quickGapFromCard;
window.switchView = switchView;
