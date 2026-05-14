// ===== Credit Follow-Up Dashboard — Frontend =====

const API = '';

// ===== State =====
let invoicesData = [];
let auditData = [];

// ===== DOM Helpers =====
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
  const container = $('.toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ===== API Helpers =====
async function apiFetch(url, options = {}) {
  try {
    const res = await fetch(API + url, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  } catch (err) {
    showToast(err.message, 'error');
    throw err;
  }
}

// ===== Stage Helpers =====
function getStageName(stage) {
  const names = {
    0: 'Not Due',
    1: 'Friendly',
    2: 'Firm',
    3: 'Serious',
    4: 'Urgent',
    5: 'Escalated'
  };
  return names[stage] || 'Unknown';
}

function formatCurrency(amount) {
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 });
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ===== Config Check =====
async function checkConfig() {
  try {
    const data = await apiFetch('/api/config');
    if (data.configured) {
      $('#setup-wizard').style.display = 'none';
      $('#main-dashboard').style.display = 'block';
      loadDashboard();
    } else {
      $('#setup-wizard').style.display = 'flex';
      $('#main-dashboard').style.display = 'none';
    }
  } catch {
    $('#setup-wizard').style.display = 'flex';
    $('#main-dashboard').style.display = 'none';
  }
}

// ===== Save API Key =====
async function saveApiKey() {
  const input = $('#api-key-input');
  const key = input.value.trim();
  if (!key) { showToast('Please enter an API key', 'error'); return; }
  if (!key.startsWith('sk-')) { showToast('Key should start with "sk-"', 'error'); return; }

  const btn = $('#save-key-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving…';

  try {
    await apiFetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    showToast('Key saved', 'success');
    input.value = '';
    setTimeout(() => checkConfig(), 500);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}

// ===== Load Dashboard =====
async function loadDashboard() {
  await Promise.all([loadInvoices(), loadAuditLogs()]);
}

// ===== Load Invoices =====
async function loadInvoices() {
  try {
    const data = await apiFetch('/api/invoices');
    invoicesData = data.invoices || [];
    renderStats();
    renderInvoices();
  } catch {
    // handled by apiFetch
  }
}

// ===== Render Stats =====
function renderStats() {
  const total = invoicesData.length;
  const overdue = invoicesData.filter(i => i.stage > 0).length;
  const escalated = invoicesData.filter(i => i.stage === 5).length;
  const actionable = invoicesData.filter(i => i.stage >= 1 && i.stage <= 4).length;

  $('#stat-total').textContent = total;
  $('#stat-overdue').textContent = overdue;
  $('#stat-actionable').textContent = actionable;
  $('#stat-escalated').textContent = escalated;
}

// ===== Render Invoice Cards =====
function renderInvoices() {
  const grid = $('#invoice-grid');

  if (invoicesData.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <p>No invoices found. Upload a CSV or reset data to get started.</p>
      </div>`;
    return;
  }

  grid.innerHTML = invoicesData.map((inv, idx) => {
    const daysText = inv.days_overdue > 0
      ? `${inv.days_overdue} days`
      : inv.days_overdue === 0 ? 'Due today' : 'Not due';
    const daysClass = inv.days_overdue > 0 ? 'overdue' : 'not-due';
    const canGenerate = inv.stage >= 1 && inv.stage <= 4;

    return `
      <div class="invoice-card fade-in" style="animation-delay: ${idx * 0.06}s">
        <div class="invoice-card-header">
          <div>
            <div class="invoice-client">${escapeHtml(inv.client)}</div>
            <div class="invoice-number">${escapeHtml(inv.invoice_no)}</div>
          </div>
          <span class="stage-badge stage-${inv.stage}">
            Stage ${inv.stage} · ${getStageName(inv.stage)}
          </span>
        </div>
        <div class="invoice-details">
          <div class="detail-item">
            <div class="detail-label">Amount Due</div>
            <div class="detail-value">${formatCurrency(inv.amount)}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Due Date</div>
            <div class="detail-value">${formatDate(inv.due_date)}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Days Overdue</div>
            <div class="detail-value ${daysClass}">${daysText}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Contact</div>
            <div class="detail-value" style="font-size:0.8rem">${escapeHtml(inv.contact_email)}</div>
          </div>
        </div>
        <div class="invoice-card-actions">
          ${canGenerate
            ? `<button class="btn btn-primary btn-sm" onclick="generateEmail('${escapeHtml(inv.invoice_no)}', this)">Generate email</button>`
            : inv.stage === 5
              ? `<button class="btn btn-danger btn-sm" disabled>Escalated</button>`
              : `<button class="btn btn-secondary btn-sm" disabled>Not yet due</button>`
          }
        </div>
      </div>`;
  }).join('');
}

// ===== Generate Email for Single Invoice =====
async function generateEmail(invoiceNo, btn) {
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Working…';

  try {
    const data = await apiFetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ invoice_no: invoiceNo })
    });

    if (data.email) {
      showEmailModal(data);
      showToast('Email generated', 'success');
      loadAuditLogs();
    } else if (data.status === 'escalated') {
      showToast(`${invoiceNo}: Escalated for review`, 'error');
    } else if (data.status === 'not_due') {
      showToast(`${invoiceNo}: Not yet overdue`, 'info');
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

// ===== Generate All Emails =====
async function generateAll() {
  const btn = $('#btn-generate-all');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Processing…';

  try {
    const data = await apiFetch('/api/generate-all', { method: 'POST' });
    const results = data.results || [];
    const sent = results.filter(r => r.status === 'sent').length;
    const escalated = results.filter(r => r.status === 'escalated').length;
    const skipped = results.filter(r => r.status === 'not_due').length;
    const failed = results.filter(r => r.status === 'error').length;

    showToast(`Done: ${sent} sent, ${escalated} escalated, ${skipped} skipped${failed ? `, ${failed} failed` : ''}`, 'success');
    loadAuditLogs();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Process all';
  }
}

// ===== Email Modal =====
function showEmailModal(data) {
  const email = data.email;
  const inv = data.invoice || {};

  $('#modal-email-to').textContent = inv.contact_email || '-';
  $('#modal-email-tone').textContent = data.tone || '-';
  $('#modal-email-stage').textContent = `Stage ${data.stage || '-'}`;
  $('#modal-email-subject').textContent = email.subject;
  $('#modal-email-body').textContent = email.body;

  const overlay = $('#email-modal');
  overlay.classList.add('active');
}

function closeModal() {
  $('#email-modal').classList.remove('active');
}

function copyEmailToClipboard() {
  const subject = $('#modal-email-subject').textContent;
  const body = $('#modal-email-body').textContent;
  const text = `Subject: ${subject}\n\n${body}`;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard', 'success');
  });
}

// ===== Audit Logs =====
async function loadAuditLogs() {
  try {
    const data = await apiFetch('/api/audit-logs');
    auditData = data.logs || [];
    renderAuditLogs();
  } catch {
    // handled
  }
}

function renderAuditLogs() {
  const tbody = $('#audit-tbody');
  const countEl = $('#audit-count');
  countEl.textContent = `(${auditData.length})`;

  if (auditData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--ink-tertiary)">No records yet. Generate emails to see logs here.</td></tr>`;
    return;
  }

  tbody.innerHTML = auditData.map(log => {
    const ts = new Date(log.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
    return `
      <tr>
        <td>${ts}</td>
        <td style="font-weight:600;color:var(--ink)">${escapeHtml(log.invoice_no)}</td>
        <td>${escapeHtml(log.client_name)}</td>
        <td>${escapeHtml(log.action_taken)}</td>
        <td><span class="stage-badge stage-${toneToStage(log.tone_used)}" style="font-size:0.68rem">${escapeHtml(log.tone_used || '-')}</span></td>
        <td class="truncate">${escapeHtml(log.email_subject || '-')}</td>
      </tr>`;
  }).join('');
}

function toneToStage(tone) {
  if (!tone) return 0;
  const map = {
    'Warm & Friendly': 1,
    'Polite but Firm': 2,
    'Formal & Serious': 3,
    'Stern & Urgent': 4,
    'Escalation Flag': 5
  };
  return map[tone] || 0;
}

// ===== Upload CSV =====
async function handleCsvUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    await apiFetch('/api/upload-csv', { method: 'POST', body: formData });
    showToast('CSV uploaded. Refreshing…', 'success');
    await loadInvoices();
  } catch {
    // handled
  }
  event.target.value = '';
}

// ===== Regenerate Data =====
async function regenerateData() {
  const btn = $('#btn-regen-data');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Resetting…';

  try {
    await apiFetch('/api/regenerate-data', { method: 'POST' });
    showToast('Data reset', 'success');
    await loadInvoices();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Reset data';
  }
}

// ===== Utilities =====
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ===== Keyboard Shortcuts =====
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
  checkConfig();

  // Close modal on overlay click
  $('#email-modal').addEventListener('click', (e) => {
    if (e.target === $('#email-modal')) closeModal();
  });
});
