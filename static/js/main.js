// Auto-save functionality
let autoSaveTimeout;
let isSaving = false;
let isPolling = false;
let lastTotals = { modal: 0, balance: 0, income: 0, estimation: 0 };
let lastAccountStats = {}; // Map: phone -> {modal, balance, withdrawal, estimation}


async function forceResetApp() {
  if (confirm("Reset & Update Aplikasi? \n\nIni akan menghapus cache dan memaksa download versi terbaru.")) {
    // Deprecated for Telegram migration
    window.location.reload(true);
  }
}

function autoSave() {
  if (isSaving) return;

  const indicator = document.getElementById('save-indicator');
  if (indicator) {
    indicator.style.opacity = '1';
    indicator.querySelector('span').textContent = 'Saving...';
    indicator.querySelector('svg').style.display = 'none';
  }

  clearTimeout(autoSaveTimeout);
  autoSaveTimeout = setTimeout(() => {
    isSaving = true;
    const form = document.getElementById('automation-form');
    const formData = new FormData(form);
    formData.set('action', 'save');

    fetch(form.action || '/', {
      method: 'POST',
      body: formData
    }).then(response => {
      isSaving = false;
      if (response.ok) {
        if (indicator) {
          indicator.querySelector('span').textContent = 'Saved';
          indicator.querySelector('svg').style.display = 'inline';
          setTimeout(() => { indicator.style.opacity = '0'; }, 2000);
        }
      } else {
        console.error('Auto-save failed:', response.status);
        if (indicator) indicator.style.opacity = '0';
      }
    }).catch(err => {
      isSaving = false;
      console.error('Auto-save error:', err);
      if (indicator) indicator.style.opacity = '0';
    });
  }, 1500);
}

// Attach auto-save to all inputs
document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('automation-form');
  if (form) {
    form.addEventListener('input', autoSave);
    form.addEventListener('change', autoSave);
    // console.log('Auto-save enabled');
  }

  // Settings dropdown toggle
  const settingsToggle = document.getElementById('settings-toggle');
  const settingsMenu = document.getElementById('settings-menu');

  if (settingsToggle && settingsMenu) {
    settingsToggle.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      settingsMenu.style.display = settingsMenu.style.display === 'none' ? 'block' : 'none';
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
      if (!settingsToggle.contains(e.target) && !settingsMenu.contains(e.target)) {
        settingsMenu.style.display = 'none';
      }
    });
  }
});

function removeRow(btn) {
  const row = btn.closest('.row-item');
  if (!row) return;

  const rows = document.querySelectorAll('.row-item');
  // minimal 1 row harus tersisa
  if (rows.length <= 1) {
    alert('Minimal satu akun harus ada!');
    return;
  }

  // Cek apakah akun sudah tersimpan (punya data phone)
  const phoneInput = row.querySelector('input[name="phone[]"]');
  const phone = phoneInput ? phoneInput.value.trim() : '';

  if (phone) {
    // Akun sudah ada phonenya, minta konfirmasi
    if (!confirm('Hapus akun +62' + phone + '?\n\nAkun ini sudah tersimpan. Yakin ingin menghapus?')) {
      return;
    }
  }

  row.remove();
  updateAccountNumbers(); // Re-index after removing
  forceSave(); // Save immediately after removing
}


function updateAccountNumbers() {
  const rows = document.querySelectorAll('.row-item');
  rows.forEach((row, index) => {
    const numDiv = row.querySelector('.account-number');
    if (numDiv) {
      numDiv.textContent = index + 1;
    }
  });
}

function forceSave() {
  const form = document.getElementById('automation-form');
  const formData = new FormData(form);
  formData.set('action', 'save');

  // console.log('Force saving...');
  fetch(form.action || '/', {
    method: 'POST',
    body: formData
  }).then(response => {
    if (response.ok) {
      // console.log('✓ Force saved successfully');
    } else {
      console.error('Force save failed');
    }
  }).catch(err => console.error('Force save error:', err));
}

// Loading state for run-all button
document.getElementById('automation-form').addEventListener('submit', function (e) {
  const btn = document.getElementById('run-all-btn');
  if (e.submitter && e.submitter.name === 'action' && e.submitter.value === 'start') {
    btn.disabled = true;
    btn.querySelector('.play-icon').style.display = 'none';
    btn.querySelector('.spinner-icon').style.display = 'inline';
    document.getElementById('btn-text').textContent = 'Menjalankan...';
  }
});

document.getElementById('add-row').addEventListener('click', function () {
  const template = document.getElementById('account-card-template');
  const rows = document.getElementById('rows');
  const clone = template.content.cloneNode(true);

  // Set the account number
  const count = document.querySelectorAll('.row-item').length + 1;
  const numEl = clone.querySelector('.account-number');
  if (numEl) {
    const pulse = numEl.querySelector('.account-pulse');
    numEl.textContent = count;
    if (pulse) numEl.appendChild(pulse);
  }

  const div = clone.querySelector('.account-card');
  rows.appendChild(clone);

  // Initialize listeners for the new row
  attachToggle(div);
  attachPlayButtons();
  attachSyncButtons();
  attachReviewButtons();
  attachScheduleButtons();
  attachMoreButtons(); // Added this line
});

// ================= MORE ACTIONS DROPDOWN =================
function attachMoreButtons() {
  document.querySelectorAll('.more-btn').forEach(btn => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Close other dropdowns
      document.querySelectorAll('.more-dropdown.show').forEach(d => {
        if (d !== btn.nextElementSibling) d.classList.remove('show');
      });
      btn.nextElementSibling.classList.toggle('show');
    });
  });

  // Close when clicking outside
  document.addEventListener('click', () => {
    document.querySelectorAll('.more-dropdown.show').forEach(d => d.classList.remove('show'));
  });
}
attachMoreButtons(); // Initial attachment for existing buttons

// ================= AUTO SYNC ALL =================
async function performAutoSyncAll() {
  const cards = Array.from(document.querySelectorAll('.account-card[data-phone]'));
  if (cards.length === 0) return;

  const now = new Date();
  const COOLDOWN_MS = 30 * 60 * 1000; // 30 minutes
  let syncCount = 0;

  for (const card of cards) {
    const phone = card.dataset.phone;
    const lastSyncTs = card.dataset.lastSyncTs;
    const isSyncing = card.querySelector('.sync-btn').disabled; // Simple check if already syncing

    if (isSyncing) continue;

    // Check Cooldown
    if (lastSyncTs) {
      const lastSyncDate = new Date(lastSyncTs);
      if (now - lastSyncDate < COOLDOWN_MS) {
        // console.log(`Skipping auto-sync for +62${phone} (Cooldown active)`);
        continue;
      }
    }

    const btn = card.querySelector('.sync-btn');
    if (!btn) continue;

    // Trigger sync
    syncCount++;
    try {
      const formData = new FormData();
      formData.append('phone', phone);
      const res = await fetch('/sync_single', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.ok) {
        showToast('Auto-sync queued: +62' + phone, 'info');
        card.dataset.lastSyncTs = now.toISOString();
        // Pulsing glow is handled by updateStatusRealTime polling
      }
    } catch (err) {
      console.error('Auto-sync failed for', phone, err);
    }

    // Slight delay between queueing each account for gentler sequence
    await new Promise(r => setTimeout(r, 1000));
  }
}

// ================= GLOBAL FUNCTIONS (Moved from index.html) =================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'error') icon = '❌';

  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);

  // Auto remove
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function animateValue(id, start, end, duration = 500) {
  const el = typeof id === 'string' ? document.getElementById(id) : id;
  if (!el) return;
  if (start === end) {
    el.textContent = 'Rp ' + new Intl.NumberFormat('id-ID').format(end);
    return;
  }
  const startTime = performance.now();
  const step = (currentTime) => {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(start + (end - start) * ease);
    el.textContent = 'Rp ' + new Intl.NumberFormat('id-ID').format(current);
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = 'Rp ' + new Intl.NumberFormat('id-ID').format(end);
  };
  requestAnimationFrame(step);
}

function formatNumber(num) {
  return new Intl.NumberFormat('id-ID').format(num);
}

/* Global state moved to top */

function updateStatusRealTime() {
  if (isPolling) return;
  isPolling = true;

  fetch('/api/accounts')
    .then(res => res.json())
    .then(data => {
      const accounts = data.accounts || [];
      const queueSize = data.queue_size || 0;

      // Update Queue Status
      const queueCount = document.getElementById('queue-count');
      const queueBadge = document.getElementById('queue-status');
      if (queueCount) queueCount.textContent = queueSize;
      if (queueBadge) {
        if (queueSize > 0) queueBadge.classList.add('active');
        else queueBadge.classList.remove('active');
      }

      // Update Health Pulse
      const healthPulse = document.querySelector('.system-health-pulse');
      if (healthPulse) {
        healthPulse.style.background = '#10b981';
        healthPulse.title = 'System Monitoring Active';
      }

      let totalModal = 0, totalSaldo = 0, totalPendapatan = 0, totalEstimation = 0;

      accounts.forEach(acc => {
        totalModal += (acc.income || 0);
        totalSaldo += (acc.balance || 0);
        totalPendapatan += (acc.withdrawal || 0);
        totalEstimation += (acc.estimation ? acc.estimation.estimated_balance : 0);

        const card = document.querySelector(`.account-card[data-phone="${acc.phone_display}"]`);
        if (!card) return;

        // Progress
        const fill = card.querySelector('.progress-fill');
        const text = card.querySelector('.progress-value');
        if (fill && text) {
          fill.style.width = (acc.pct || 0) + '%';
          text.textContent = `${acc.completed}/${acc.total}`;
          fill.classList.remove('progress-complete', 'progress-partial', 'progress-low');
          if (acc.status === 'ran') fill.classList.add('progress-complete');
          else if (acc.status === 'due') fill.classList.add('progress-partial');
          else fill.classList.add('progress-low');
        }

        // Badge
        const badge = card.querySelector('.status-badge');
        if (badge) {
          badge.className = 'status-badge status-' + (acc.status_raw || 'idle');
          badge.textContent = acc.status_label || 'Idle';
          if (acc.status_raw === 'running' || acc.status_raw === 'queued') card.classList.add('card-active-pulse');
          else card.classList.remove('card-active-pulse');
        }

        // Stats (Animated)
        const phone = acc.phone_display;
        if (!lastAccountStats[phone]) lastAccountStats[phone] = { modal: 0, balance: 0, withdrawal: 0, estimation: 0 };

        const mEl = card.querySelector('.income-display .stat-value');
        const sEl = card.querySelector('.balance-display .stat-value');
        const wEl = card.querySelector('.withdrawal-display .stat-value');
        const eEl = card.querySelector('.estimation-display .stat-value');

        if (mEl) animateValue(mEl, lastAccountStats[phone].modal, acc.income || 0);
        if (sEl) animateValue(sEl, lastAccountStats[phone].balance, acc.balance || 0);
        if (wEl) animateValue(wEl, lastAccountStats[phone].withdrawal, acc.withdrawal || 0);
        if (eEl && acc.estimation) animateValue(eEl, lastAccountStats[phone].estimation, acc.estimation.estimated_balance);

        lastAccountStats[phone] = {
          modal: acc.income || 0,
          balance: acc.balance || 0,
          withdrawal: acc.withdrawal || 0,
          estimation: acc.estimation ? acc.estimation.estimated_balance : 0
        };

        const pEl = card.querySelector('.points-display .stat-value');
        if (pEl) pEl.textContent = formatNumber(acc.points || 0);

        // Sync State
        const syncBtn = card.querySelector('.sync-btn');
        if (syncBtn) {
          const syncIcon = syncBtn.querySelector('.sync-icon');
          const spinnerIcon = syncBtn.querySelector('.spinner-icon');
          const syncLabel = syncBtn.querySelector('span');

          if (acc.is_syncing) {
            if (syncIcon) syncIcon.style.display = 'none';
            if (spinnerIcon) spinnerIcon.style.display = 'inline';
            if (syncLabel) syncLabel.textContent = 'Syncing...';
            syncBtn.disabled = true;
            card.classList.add('is-syncing');
          } else {
            if (spinnerIcon) spinnerIcon.style.display = 'none';
            if (syncIcon) syncIcon.style.display = 'inline';
            syncBtn.disabled = false;
            card.classList.remove('is-syncing');

            if (acc.pct >= 99 && syncLabel) {
              syncLabel.textContent = 'Synced';
            } else if (syncLabel) {
              syncLabel.textContent = 'Sync Manual';
            }
          }
        }

        // Update Calendar Data
        card.dataset.calendar = JSON.stringify(acc.calendar || []);

        // Render Mini Calendar (Current Week)
        const miniCal = card.querySelector('.mini-calendar');
        if (miniCal) renderMiniCalendar(card, miniCal);

        // Refresh full calendar if open
        const calDropdown = card.querySelector('.calendar-dropdown');
        if (calDropdown && calDropdown.style.display !== 'none') {
          const grid = calDropdown.querySelector('.calendar-grid');
          if (grid) renderCalendar(card, grid);
        }

        // Update individual Account Pulse
        const accountPulse = card.querySelector('.account-pulse');
        if (accountPulse) {
          accountPulse.style.background = '#10b981'; // Green on success
          accountPulse.style.boxShadow = '0 0 5px rgba(16, 185, 129, 0.6)';
        }
      });

      // Global Dashboard
      const dash = document.getElementById('global-dashboard');
      if (dash && accounts.length > 0) {
        dash.style.display = 'block';
        animateValue('total-modal', lastTotals.modal, totalModal);
        animateValue('total-balance', lastTotals.balance, totalSaldo);
        animateValue('total-income', lastTotals.income, totalPendapatan);
        animateValue('total-estimation', lastTotals.estimation, totalEstimation);
        lastTotals = { modal: totalModal, balance: totalSaldo, income: totalPendapatan, estimation: totalEstimation };
      } else if (dash) {
        dash.style.display = 'none';
      }

      renderGlobalChart(totalModal, totalSaldo, totalPendapatan);
      isPolling = false;
    })
    .catch(err => {
      console.error('Polling error:', err);
      const healthPulse = document.querySelector('.system-health-pulse');
      if (healthPulse) {
        healthPulse.style.background = '#ef4444';
        healthPulse.title = 'Connection Issue';
      }
      isPolling = false;
    });
}

// Initial setup on load
document.addEventListener('DOMContentLoaded', function () {
  updateStatusRealTime(); // Run immediately on load

  // Auto-sync trigger on load and periodically
  performAutoSyncAll();

  let pollingIntervalId = null;
  let autoSyncIntervalId = setInterval(performAutoSyncAll, 5 * 60 * 1000); // Check every 5 minutes

  const startPolling = (ms) => {
    if (pollingIntervalId) clearInterval(pollingIntervalId);
    pollingIntervalId = setInterval(() => {
      if (!isPolling) updateStatusRealTime();
    }, ms);
  };

  // Start with default 2s polling
  startPolling(2000);

  // SMART POLLING: Slow down when tab is hidden to save battery/thermal
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      console.log("Tab hidden: Entering low-power polling mode (60s)");
      startPolling(60000); // Slow down to 1 minute
      if (autoSyncIntervalId) {
        clearInterval(autoSyncIntervalId);
        autoSyncIntervalId = null;
      }
    } else {
      console.log("Tab visible: Entering high-performance mode (2s)");
      updateStatusRealTime();
      startPolling(2000);
      if (!autoSyncIntervalId) {
        autoSyncIntervalId = setInterval(performAutoSyncAll, 5 * 60 * 1000);
      }
    }
  });


  // Initial progress for existing cards
  document.querySelectorAll('.account-card').forEach(card => {
    const fill = card.querySelector('.progress-fill');
    if (fill && fill.dataset.pct) {
      fill.style.width = fill.dataset.pct + '%';
    }
  });
});

// ================= PASSWORD TOGGLE =================
function attachToggle(root) {
  const btn = root.querySelector('.pwd-toggle');
  if (!btn || btn.dataset.bound) return;

  btn.dataset.bound = '1';
  btn.addEventListener('click', function () {
    const input = root.querySelector('.pwd');
    if (!input) return;

    const eyeIcon = btn.querySelector('.eye-icon');
    const eyeOffIcon = btn.querySelector('.eye-off-icon');

    if (input.type === 'password') {
      input.type = 'text';
      btn.title = 'Sembunyikan Password';
      if (eyeIcon) eyeIcon.style.display = 'none';
      if (eyeOffIcon) eyeOffIcon.style.display = 'block';
    } else {
      input.type = 'password';
      btn.title = 'Tampilkan Password';
      if (eyeIcon) eyeIcon.style.display = 'block';
      if (eyeOffIcon) eyeOffIcon.style.display = 'none';
    }
  });
}

document
  .querySelectorAll('.row-item')
  .forEach(function (row) { attachToggle(row); });

// ================= PLAY BUTTON (RUN SINGLE) =================
function attachPlayButtons() {
  document.querySelectorAll('.play-btn').forEach(function (btn) {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', async function () {
      const row = btn.closest('.row-item');
      if (!row) return;

      const phoneInput = row.querySelector('input[name="phone[]"]');
      if (!phoneInput) return;

      const phone = phoneInput.value.trim();
      if (!phone) {
        showToast('Masukkan nomor HP terlebih dahulu.', 'error');
        return;
      }

      // Show loading state
      const originalIcon = btn.querySelector('.play-icon');
      const spinnerIcon = btn.querySelector('.spinner-icon');

      btn.disabled = true;
      originalIcon.style.display = 'none';
      spinnerIcon.style.display = 'inline';

      try {
        const formData = new FormData();
        formData.append('phone', phone);

        const res = await fetch('/run_single', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();

        if (data.ok) {
          showToast('Automation started for +62' + phone, 'success');
          setTimeout(updateStatusRealTime, 500);

          btn.disabled = false;
          originalIcon.style.display = 'inline';
          spinnerIcon.style.display = 'none';
        } else {
          showToast('Gagal: ' + data.msg, 'error');
          btn.disabled = false;
          originalIcon.style.display = 'inline';
          spinnerIcon.style.display = 'none';
        }
      } catch (err) {
        showToast('Gagal menghubungi server.', 'error');
        console.error(err);
        btn.disabled = false;
        originalIcon.style.display = 'inline';
        spinnerIcon.style.display = 'none';
      }
    });
  });
}
attachPlayButtons();

// ================= SYNC BUTTON =================
function attachSyncButtons() {
  document.querySelectorAll('.sync-btn').forEach(function (btn) {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', async function () {
      const row = btn.closest('.row-item');
      if (!row) return;

      const phoneInput = row.querySelector('input[name="phone[]"]');
      if (!phoneInput) return;

      const phone = phoneInput.value.trim();
      if (!phone) {
        showToast('Masukkan nomor HP terlebih dahulu.', 'error');
        return;
      }

      // Show loading state
      const originalIcon = btn.querySelector('.sync-icon');
      const spinnerIcon = btn.querySelector('.spinner-icon');

      btn.disabled = true;
      originalIcon.style.display = 'none';
      spinnerIcon.style.display = 'inline';

      try {
        const formData = new FormData();
        formData.append('phone', phone);

        const res = await fetch('/sync_single', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();

        if (data.ok) {
          // Smoothly update UI without reload or alert
          setTimeout(updateStatusRealTime, 500);
          showToast('Sync job queued for +62' + phone, 'success');

          btn.disabled = false;
          originalIcon.style.display = 'inline';
          spinnerIcon.style.display = 'none';
        } else {
          showToast('Error: ' + data.msg, 'error');
          btn.disabled = false;
          originalIcon.style.display = 'inline';
          spinnerIcon.style.display = 'none';
        }
      } catch (err) {
        showToast('Gagal menghubungi server.', 'error');
        console.error(err);
        // Reset state
        btn.disabled = false;
        originalIcon.style.display = 'inline';
        spinnerIcon.style.display = 'none';
      }
    });
  });
}
attachSyncButtons();

// ================= REVIEW BUTTON =================
function attachReviewButtons() {
  document.querySelectorAll('.review-btn').forEach(function (btn) {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', function () {
      const row = btn.closest('.row-item');
      if (!row) return;

      const phoneInput = row.querySelector('input[name="phone[]"]');
      if (!phoneInput) return;

      const phone = phoneInput.value.trim();
      if (!phone) {
        showToast('Masukkan nomor HP terlebih dahulu.', 'error');
        return;
      }

      window.location = '/review?phone=' + encodeURIComponent(phone);
    });
  });
}
attachReviewButtons();

// ================= SCHEDULE BUTTON =================
function attachScheduleButtons() {
  document.querySelectorAll('.schedule-btn').forEach(function (btn) {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', function () {
      const row = btn.closest('.row-item');
      if (!row) return;

      const phoneInput = row.querySelector('input[name="phone[]"]');
      if (!phoneInput) return;

      const phone = phoneInput.value.trim();
      if (!phone) {
        showToast('Masukkan nomor HP terlebih dahulu.', 'error');
        return;
      }

      window.location = '/schedule?phone=' + encodeURIComponent(phone);
    });
  });
}
attachScheduleButtons();


// ================= HEADLESS SYNC =================
// ================= SETTINGS LOGIC =================
function initSettings() {
  const settingsInputs = [
    'setting-loglevel',
    'setting-telegram-token',
    'setting-telegram-chat-id'
  ];

  settingsInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', saveSettings);
    }
  });

  // Export
  const btnExport = document.getElementById('btn-export');
  if (btnExport) {
    btnExport.addEventListener('click', function () {
      window.location.href = '/export_accounts';
    });
  }

  // Import
  const btnImportTrigger = document.getElementById('btn-import-trigger');
  const fileImport = document.getElementById('file-import');
  if (btnImportTrigger && fileImport) {
    btnImportTrigger.addEventListener('click', function () {
      fileImport.click();
    });

    fileImport.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        const formData = new FormData();
        formData.append('file', this.files[0]);

        fetch('/import_accounts', {
          method: 'POST',
          body: formData
        })
          .then(res => res.json())
          .then(data => {
            if (data.status === 'success') {
              showToast('Import berhasil! Halaman akan dimuat ulang.', 'success');
              setTimeout(() => window.location.reload(), 2000);
            } else {
              showToast('Import gagal: ' + data.message, 'error');
            }
          })
          .catch(err => {
            console.error('Import error:', err);
            showToast('Terjadi kesalahan saat import.', 'error');
          });
      }
    });
  }

  // Telegram Test
  const btnTestTele = document.getElementById('btn-test-telegram');
  if (btnTestTele) {
    btnTestTele.addEventListener('click', function () {
      const token = document.getElementById('setting-telegram-token').value;
      const chatId = document.getElementById('setting-telegram-chat-id').value;

      if (!token || !chatId) {
        showToast('Token & Chat ID wajib diisi!', 'error');
        return;
      }

      btnTestTele.disabled = true;
      btnTestTele.textContent = 'Mengirim... ⌛';

      fetch('/settings/test_telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_token: token, telegram_chat_id: chatId })
      })
        .then(res => res.json())
        .then(data => {
          btnTestTele.disabled = false;
          btnTestTele.textContent = 'Tes Telegram ✈️';
          if (data.status === 'success') {
            showToast(data.message, 'success');
          } else {
            showToast(data.message, 'error');
          }
        })
        .catch(err => {
          btnTestTele.disabled = false;
          btnTestTele.textContent = 'Tes Telegram ✈️';
          showToast('Error: ' + err, 'error');
        });
    });
  }
}

function saveSettings() {
  const settings = {
    auto_reconnect_wifi: document.getElementById('setting-wifi').checked,
    timeout: parseInt(document.getElementById('setting-timeout').value),
    viewport: document.getElementById('setting-viewport').value,
    log_level: document.getElementById('setting-loglevel').value,
    telegram_token: document.getElementById('setting-telegram-token').value,
    telegram_chat_id: document.getElementById('setting-telegram-chat-id').value
  };

  console.log('Saving settings:', settings);
  fetch('/settings/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(settings)
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        console.log('Settings saved');
      } else {
        console.error('Failed to save settings');
      }
    })
    .catch(err => console.error('Error saving settings:', err));
}

// ================= PWA INSTALL LOGIC =================
let deferredPrompt;

function initPWA() {
  // 1. Register Service Worker (REQUIRED for PWA)
  if ('serviceWorker' in navigator) {
    // Register from ROOT to ensure scope covers the whole app
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => console.log('Service Worker Registered at scope:', reg.scope))
      .catch((err) => console.error('Service Worker Registration Failed:', err));
  }

  const installBtn = document.getElementById('btn-install-app');
  if (!installBtn) return;

  // Show button ALWAYS (don't wait for beforeinstallprompt)
  installBtn.style.display = 'flex';

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    console.log("PWA Install capability detected - prompt ready");
  });

  installBtn.addEventListener('click', (e) => {
    if (deferredPrompt) {
      // Browser supports install prompt
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('User accepted the A2HS prompt');
          showToast('Aplikasi sedang diinstall...', 'success');
        } else {
          console.log('User dismissed the A2HS prompt');
        }
        deferredPrompt = null;
      });
    } else {
      // Fallback: Show manual instructions
      const msg = `CARA INSTALL APLIKASI:

1. Klik tombol titik tiga (⋮) di pojok kanan atas browser
2. Pilih "Install app" atau "Add to Home screen"
3. Ikuti petunjuk yang muncul

CATATAN:
• Pastikan akses via Chrome (bukan browser lain)
• Jika tidak ada opsi install, coba tutup & buka ulang halaman ini
• Aplikasi mungkin sudah terinstall`;

      alert(msg);
      console.log('Manual install instructions shown');
    }
  });

  window.addEventListener('appinstalled', (evt) => {
    console.log('INSTALL: Success');
    showToast('Aplikasi berhasil diinstall!', 'success');
  });
}

// Initialize settings listeners
document.addEventListener('DOMContentLoaded', function () {
  initSettings();
  initPWA();
});

// ================= ADD-ROW MICRO INTERACTION =================
const addRowBtn = document.getElementById('add-row');
if (addRowBtn) {
  addRowBtn.addEventListener('click', function () {
    addRowBtn.classList.add('clicked');
    setTimeout(() => addRowBtn.classList.remove('clicked'), 240);
  });
}
// ================= MASTER CHART TOGGLE =================
function toggleGlobalChart(btn) {
  const chartWrapper = document.getElementById('global-chart-wrapper');
  if (!chartWrapper) return;

  const isHidden = chartWrapper.style.display === 'none';
  chartWrapper.style.display = isHidden ? 'block' : 'none';

  if (isHidden) {
    btn.classList.add('active');
    // The global chart is typically rendered on load/update, 
    // but we can trigger a resize or re-render if needed here.
  } else {
    btn.classList.remove('active');
  }
}
// ================= CHART TOGGLE & RENDER =================
function toggleChart(btn) {
  const row = btn.closest('.account-card');
  if (!row) return;

  const chartWrapper = row.querySelector('.chart-wrapper');
  if (!chartWrapper) return;

  // Toggle display
  const isHidden = chartWrapper.style.display === 'none';
  chartWrapper.style.display = isHidden ? 'block' : 'none';

  // Toggle button active class
  if (isHidden) {
    btn.classList.add('active');
    // Lazy render if canvas empty
    const canvas = chartWrapper.querySelector('canvas');
    if (canvas && !canvas.getAttribute('data-rendered')) {
      renderChart(row, canvas);
      canvas.setAttribute('data-rendered', 'true');
    }
  } else {
    btn.classList.remove('active');
  }
}

// ================= LOG VIEWER LOGIC =================
let logPollInterval;
let currentLogPhone = null;

function openLog(btn) {
  const card = btn.closest('.account-card');
  if (!card) return;

  const phoneDisplay = card.querySelector('.phone-display').textContent.trim();
  if (!phoneDisplay) {
    showToast('Nomor HP tidak ditemukan.', 'error');
    return;
  }

  // Normalized phone from display (e.g. "812..." or "62812...")
  // The API expects whatever is in the UI display
  currentLogPhone = phoneDisplay;

  const modal = document.getElementById('log-modal');
  const title = document.getElementById('terminal-title-text');
  const content = document.getElementById('terminal-content');

  // Set title
  title.textContent = `root@mba-automation:~/logs/${phoneDisplay}.log`;
  content.innerHTML = '<div class="log-line"><span class="log-timestamp">[SYSTEM]</span> Connecting to log stream...</div>';

  modal.classList.add('show');

  // Start polling
  pollLog();
  logPollInterval = setInterval(pollLog, 2000);
}

function closeLog() {
  const modal = document.getElementById('log-modal');
  modal.classList.remove('show');
  clearInterval(logPollInterval);
  currentLogPhone = null;
}

async function pollLog() {
  if (!currentLogPhone) return;

  try {
    const res = await fetch(`/api/logs/${currentLogPhone}`);
    if (res.status === 404) {
      document.getElementById('terminal-content').innerHTML = '<div class="log-line text-yellow-500">[SYSTEM] Log file not found. waiting for process to start...</div>';
      return;
    }

    const text = await res.text();
    const contentDiv = document.getElementById('terminal-content');

    // Simple diff check to avoid unnecessary DOM updates? 
    // For now, full replace is safer to ensure we get new lines correctly, 
    // but implies scrolling to bottom every time.

    // Parse text to HTML lines for styling
    const htmlLines = text.split('\n').map(line => {
      if (!line) return '';
      // Try to extract timestamp if present (Standard python logging)
      // Format: 2024-12-25 23:00:01,123 INFO message
      const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)/);
      if (match) {
        return `<div class="log-line"><span class="log-timestamp">[${match[1]}]</span> ${escapeHtml(match[2])}</div>`;
      }
      return `<div class="log-line">${escapeHtml(line)}</div>`;
    }).join('');

    // Check if user was at bottom before update
    const isAtBottom = contentDiv.scrollHeight - contentDiv.scrollTop <= contentDiv.clientHeight + 50;

    contentDiv.innerHTML = htmlLines;

    if (isAtBottom) {
      contentDiv.scrollTop = contentDiv.scrollHeight;
    }

  } catch (err) {
    console.error("Log poll error", err);
  }
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, function (m) { return map[m]; });
}

// Close log modal on outside click
const logModal = document.getElementById('log-modal');
if (logModal) {
  logModal.addEventListener('click', function (e) {
    if (e.target === this) {
      closeLog();
    }
  });
}

function renderChart(row, canvas) {
  try {
    const historyStr = row.dataset.history;
    if (!historyStr || historyStr === '{}') return;

    const history = JSON.parse(historyStr);
    const dates = Object.keys(history).sort();
    if (dates.length === 0) return;

    // PAGINATION
    let endIndex = parseInt(canvas.dataset.endIndex);
    if (isNaN(endIndex)) endIndex = dates.length;
    if (endIndex > dates.length) endIndex = dates.length;
    if (endIndex < 7) endIndex = 7;

    let startIndex = endIndex - 7;
    if (startIndex < 0) startIndex = 0;

    const slicedDates = dates.slice(startIndex, endIndex);

    // Update nav buttons
    const wrapper = canvas.closest('.chart-wrapper');
    if (wrapper) {
      const prevBtn = wrapper.querySelector('.prev');
      const nextBtn = wrapper.querySelector('.next');
      if (prevBtn) prevBtn.disabled = startIndex <= 0;
      if (nextBtn) nextBtn.disabled = endIndex >= dates.length;
      canvas.dataset.endIndex = endIndex;
    }

    const incomeData = [], balanceData = [], withdrawalData = [];
    slicedDates.forEach(date => {
      const entry = history[date];
      incomeData.push(entry.income || 0);
      balanceData.push(entry.balance || 0);
      withdrawalData.push(entry.withdrawal || 0);
    });

    // Destroy old chart
    if (canvas.chartInstance) canvas.chartInstance.destroy();

    const ctx = canvas.getContext('2d');

    // Create gradients for fill
    const modalGradient = ctx.createLinearGradient(0, 0, 0, 240);
    modalGradient.addColorStop(0, 'rgba(234, 88, 12, 0.2)'); // Industrial Orange
    modalGradient.addColorStop(1, 'rgba(234, 88, 12, 0.01)');

    const saldoGradient = ctx.createLinearGradient(0, 0, 0, 240);
    saldoGradient.addColorStop(0, 'rgba(37, 99, 235, 0.2)'); // Performance Blue
    saldoGradient.addColorStop(1, 'rgba(37, 99, 235, 0.01)');

    const pendapatanGradient = ctx.createLinearGradient(0, 0, 0, 240);
    pendapatanGradient.addColorStop(0, 'rgba(5, 150, 105, 0.2)'); // Tactical Green
    pendapatanGradient.addColorStop(1, 'rgba(5, 150, 105, 0.01)');

    canvas.chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: slicedDates,
        datasets: [
          {
            label: 'Modal',
            data: incomeData,
            borderColor: '#ea580c',
            backgroundColor: modalGradient,
            borderWidth: 3,
            pointRadius: 4,
            pointBackgroundColor: '#ea580c',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.2,
            fill: true
          },
          {
            label: 'Saldo',
            data: balanceData,
            borderColor: '#2563eb',
            backgroundColor: saldoGradient,
            borderWidth: 3,
            pointRadius: 4,
            pointBackgroundColor: '#2563eb',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.2,
            fill: true
          },
          {
            label: 'Pendapatan (Net)',
            data: withdrawalData,
            borderColor: '#059669',
            backgroundColor: pendapatanGradient,
            borderWidth: 3,
            pointRadius: 4,
            pointBackgroundColor: '#059669',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.2,
            fill: true
          }
        ]
      },
      options: {
        animation: {
          duration: 2000,
          easing: 'easeOutQuart',
          loop: false
        },
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              color: '#64748b',
              font: { size: 12, family: "'Inter', sans-serif", weight: 600 },
              usePointStyle: true,
              pointStyle: 'circle',
              padding: 20,
              boxWidth: 8,
              boxHeight: 8
            }
          },
          tooltip: {
            enabled: true,
            backgroundColor: 'rgba(15, 23, 42, 0.98)',
            titleColor: '#fff',
            bodyColor: '#e2e8f0',
            titleFont: { size: 13, weight: 600, family: "'Inter', sans-serif" },
            bodyFont: { size: 12, family: "'Inter', sans-serif" },
            borderColor: '#cbd5e1',
            borderWidth: 1,
            cornerRadius: 12,
            padding: 14,
            displayColors: true,
            usePointStyle: true,
            callbacks: {
              label: function (context) {
                let label = context.dataset.label || '';
                if (label) {
                  label += ': ';
                }
                if (context.parsed.y !== null) {
                  label += 'Rp ' + context.parsed.y.toLocaleString('id-ID');
                }
                return label;
              },
              footer: function (tooltipItems) {
                const chart = tooltipItems[0].chart;
                const index = tooltipItems[0].dataIndex;
                const modal = chart.data.datasets[0].data[index];
                const pendapatan = chart.data.datasets[2].data[index];
                const profit = pendapatan - modal;
                const sign = profit > 0 ? '+' : '';
                return '\nKeuntungan: ' + sign + 'Rp ' + profit.toLocaleString('id-ID');
              }
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#64748b', font: { size: 10, family: "'Inter', sans-serif", weight: 600 } },
            grid: { display: true, color: 'rgba(0,0,0,0.05)', drawBorder: false }
          },
          y: {
            ticks: {
              color: '#64748b',
              padding: 10,
              font: { size: 10, family: "'Inter', sans-serif", weight: 600 },
              callback: function (value) {
                if (value >= 1000000) return (value / 1000000).toFixed(1) + 'jt';
                if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
                return value;
              }
            },
            grid: { color: 'rgba(0,0,0,0.08)', drawBorder: false },
            beginAtZero: true
          }
        }
      }
    });

    canvas.style.height = '240px';
    canvas.style.width = '100%';
  } catch (e) {
    console.error('Chart error:', e);
  }
}

function shiftChartDate(e, btn, direction) {
  e.preventDefault();
  e.stopPropagation();

  const wrapper = btn.closest('.chart-wrapper');
  const canvas = wrapper.querySelector('canvas');
  if (!canvas) return;

  let endIndex = parseInt(canvas.dataset.endIndex);
  if (isNaN(endIndex)) return;

  endIndex += (direction * 7);

  canvas.dataset.endIndex = endIndex;

  const row = wrapper.closest('.account-card');
  renderChart(row, canvas);
}

function fireConfetti() {
  const colors = ['#2e59d9', '#00ba9d', '#ff9f0a', '#ff3b30', '#00c2ff', '#ffffff'];
  const particleCount = 100;

  for (let i = 0; i < particleCount; i++) {
    const p = document.createElement('div');
    p.className = 'confetti-particle';
    p.style.left = Math.random() * 100 + 'vw';
    p.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
    p.style.width = Math.random() * 10 + 5 + 'px';
    p.style.height = p.style.width;
    p.style.animationDelay = Math.random() * 2 + 's';
    p.style.opacity = Math.random();

    document.body.appendChild(p);

    // Cleanup
    setTimeout(() => p.remove(), 5000);
  }
}

function initTilt(card) {
  card.addEventListener('mousemove', e => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    // Calculate rotation (-6 to 6 degrees)
    const rotateX = ((y - centerY) / centerY) * -6;
    const rotateY = ((x - centerX) / centerX) * 6;

    card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-8px) scale(1.03)`;
    card.style.boxShadow = `
      ${-rotateY * 2}px ${rotateX * 2}px 50px rgba(46, 89, 217, 0.15),
      0 20px 50px rgba(0, 0, 0, 0.08)
    `;
    card.style.transition = 'transform 0.1s ease-out, box-shadow 0.1s ease-out';
  });

  card.addEventListener('mouseleave', () => {
    card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0) scale(1)`;
    card.style.boxShadow = '';
    card.style.transition = 'all 0.6s cubic-bezier(0.23, 1, 0.32, 1)';
  });
}

let globalChartInstance = null;
let globalHistoryData = {};

// Fetch global historical data on load
async function fetchGlobalHistory() {
  try {
    const res = await fetch('/api/global_history');
    if (res.ok) {
      globalHistoryData = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch global history:', err);
  }
}

function renderGlobalChart(totalModal, totalSaldo, totalPendapatan) {
  const canvas = document.getElementById('globalChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');

  // If no historical data loaded yet, try to load it
  if (Object.keys(globalHistoryData).length === 0) {
    fetchGlobalHistory().then(() => {
      renderGlobalChart(totalModal, totalSaldo, totalPendapatan);
    });
    return;
  }

  // Update "today" with real-time numbers from polling
  const todayStr = new Date().toISOString().split('T')[0];
  globalHistoryData[todayStr] = {
    income: totalModal,
    balance: totalSaldo,
    withdrawal: totalPendapatan
  };

  const dates = Object.keys(globalHistoryData).sort();

  // PAGINATION (same logic as per-account chart)
  let endIndex = parseInt(canvas.dataset.endIndex);
  if (isNaN(endIndex)) endIndex = dates.length;
  if (endIndex > dates.length) endIndex = dates.length;
  if (endIndex < 7) endIndex = 7;

  let startIndex = endIndex - 7;
  if (startIndex < 0) startIndex = 0;

  const slicedDates = dates.slice(startIndex, endIndex);

  // Update nav buttons
  const wrapper = canvas.closest('.chart-wrapper');
  if (wrapper) {
    const prevBtn = wrapper.querySelector('.prev');
    const nextBtn = wrapper.querySelector('.next');
    if (prevBtn) prevBtn.disabled = startIndex <= 0;
    if (nextBtn) nextBtn.disabled = endIndex >= dates.length;
    canvas.dataset.endIndex = endIndex;
  }

  const incomeData = [], balanceData = [], withdrawalData = [];
  slicedDates.forEach(date => {
    const entry = globalHistoryData[date] || {};
    incomeData.push(entry.income || 0);
    balanceData.push(entry.balance || 0);
    withdrawalData.push(entry.withdrawal || 0);
  });

  // CHECK: If instance exists and configuration (labels) remains same, update WITHOUT DESTROYING
  if (globalChartInstance &&
    JSON.stringify(globalChartInstance.data.labels) === JSON.stringify(slicedDates)) {

    // Check if anything actually changed to avoid redundant updates
    const currentIncome = JSON.stringify(globalChartInstance.data.datasets[0].data);
    const newIncome = JSON.stringify(incomeData);
    const currentBalance = JSON.stringify(globalChartInstance.data.datasets[1].data);
    const newBalance = JSON.stringify(balanceData);
    const currentWith = JSON.stringify(globalChartInstance.data.datasets[2].data);
    const newWith = JSON.stringify(withdrawalData);

    if (currentIncome === newIncome && currentBalance === newBalance && currentWith === newWith) {
      // Nothing changed, skip
      return;
    }

    // Update data in-place
    globalChartInstance.data.datasets[0].data = incomeData;
    globalChartInstance.data.datasets[1].data = balanceData;
    globalChartInstance.data.datasets[2].data = withdrawalData;

    // Update without animation to prevent "jumping"
    globalChartInstance.update('none');
    return;
  }

  // Create gradients matching per-account chart style
  const modalGradient = ctx.createLinearGradient(0, 0, 0, 300);
  modalGradient.addColorStop(0, 'rgba(234, 88, 12, 0.2)');
  modalGradient.addColorStop(1, 'rgba(234, 88, 12, 0.01)');

  const saldoGradient = ctx.createLinearGradient(0, 0, 0, 300);
  saldoGradient.addColorStop(0, 'rgba(37, 99, 235, 0.2)');
  saldoGradient.addColorStop(1, 'rgba(37, 99, 235, 0.01)');

  const pendapatanGradient = ctx.createLinearGradient(0, 0, 0, 300);
  pendapatanGradient.addColorStop(0, 'rgba(5, 150, 105, 0.2)');
  pendapatanGradient.addColorStop(1, 'rgba(5, 150, 105, 0.01)');

  // Destroy old chart if we are re-initializing (e.g., date shift or first load)
  if (globalChartInstance) {
    globalChartInstance.destroy();
  }

  // Create new chart instance with line chart style
  globalChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: slicedDates,
      datasets: [
        {
          label: 'Modal',
          data: incomeData,
          borderColor: '#ea580c',
          backgroundColor: modalGradient,
          borderWidth: 3,
          pointRadius: 4,
          pointBackgroundColor: '#ea580c',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointHoverRadius: 7,
          tension: 0.2,
          fill: true
        },
        {
          label: 'Saldo',
          data: balanceData,
          borderColor: '#2563eb',
          backgroundColor: saldoGradient,
          borderWidth: 3,
          pointRadius: 4,
          pointBackgroundColor: '#2563eb',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointHoverRadius: 7,
          tension: 0.2,
          fill: true
        },
        {
          label: 'Pendapatan',
          data: withdrawalData,
          borderColor: '#059669',
          backgroundColor: pendapatanGradient,
          borderWidth: 3,
          pointRadius: 4,
          pointBackgroundColor: '#059669',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointHoverRadius: 7,
          tension: 0.2,
          fill: true
        }
      ]
    },
    options: {
      animation: {
        duration: 2000,
        easing: 'easeOutQuart',
        loop: false
      },
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            color: '#64748b',
            font: { size: 12, family: "'Inter', sans-serif", weight: 600 },
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 20,
            boxWidth: 8,
            boxHeight: 8
          }
        },
        tooltip: {
          enabled: true,
          backgroundColor: 'rgba(15, 23, 42, 0.98)',
          titleColor: '#fff',
          bodyColor: '#e2e8f0',
          titleFont: { size: 13, weight: 600, family: "'Inter', sans-serif" },
          bodyFont: { size: 12, family: "'Inter', sans-serif" },
          borderColor: '#cbd5e1',
          borderWidth: 1,
          cornerRadius: 12,
          padding: 14,
          displayColors: true,
          usePointStyle: true,
          callbacks: {
            label: function (context) {
              let label = context.dataset.label || '';
              if (label) {
                label += ': ';
              }
              if (context.parsed.y !== null) {
                label += 'Rp ' + context.parsed.y.toLocaleString('id-ID');
              }
              return label;
            },
            footer: function (tooltipItems) {
              const chart = tooltipItems[0].chart;
              const index = tooltipItems[0].dataIndex;
              const modal = chart.data.datasets[0].data[index];
              const pendapatan = chart.data.datasets[2].data[index];
              const profit = pendapatan - modal;
              const sign = profit > 0 ? '+' : '';
              return '\nKeuntungan: ' + sign + 'Rp ' + profit.toLocaleString('id-ID');
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 10, family: "'Inter', sans-serif", weight: 600 } },
          grid: { display: true, color: 'rgba(0,0,0,0.05)', drawBorder: false }
        },
        y: {
          ticks: {
            color: '#64748b',
            padding: 10,
            font: { size: 10, family: "'Inter', sans-serif", weight: 600 },
            callback: function (value) {
              if (value >= 1000000) return (value / 1000000).toFixed(1) + 'jt';
              if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
              return value;
            }
          },
          grid: { color: 'rgba(0,0,0,0.08)', drawBorder: false },
          beginAtZero: true
        }
      }
    }
  });

  canvas.style.height = '300px';
  canvas.style.width = '100%';
}

function shiftGlobalChartDate(e, btn, direction) {
  e.preventDefault();
  e.stopPropagation();

  const wrapper = btn.closest('.chart-wrapper');
  const canvas = wrapper.querySelector('canvas');
  if (!canvas) return;

  let endIndex = parseInt(canvas.dataset.endIndex);
  if (isNaN(endIndex)) return;

  endIndex += (direction * 7);

  canvas.dataset.endIndex = endIndex;

  // Re-render with new index
  renderGlobalChart(0, 0, 0); // Will use historical data
}

// ================= PnL CALENDAR LOGIC =================
let calendarDate = new Date();
let pnlHistory = {};

async function fetchPnLHistory() {
  try {
    const res = await fetch('/api/pnl_history');
    if (res.ok) {
      pnlHistory = await res.json();
      renderPnLCalendar();
    }
  } catch (err) {
    console.error("Failed to fetch PnL History:", err);
  }
}

function renderPnLCalendar() {
  const grid = document.getElementById('pnl-calendar-grid');
  const monthYearLabel = document.getElementById('current-month-year');
  const monthlyTotalLabel = document.getElementById('monthly-total-pnl');

  if (!grid) return;

  // Setup Dates
  const year = calendarDate.getFullYear();
  const month = calendarDate.getMonth();

  const firstDay = new Date(year, month, 1).getDay();
  const lastDate = new Date(year, month + 1, 0).getDate();

  const monthNames = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
  monthYearLabel.textContent = `${monthNames[month]} ${year}`;

  grid.innerHTML = '';
  let monthlyTotal = 0;

  // Empty slots before first day
  for (let i = 0; i < firstDay; i++) {
    const empty = document.createElement('div');
    empty.className = 'calendar-day empty';
    grid.appendChild(empty);
  }

  // Format currency
  const fmt = (val) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(val);

  // Fill days
  for (let d = 1; d <= lastDate; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const income = pnlHistory[dateStr] || 0;
    monthlyTotal += income;

    const dayEl = document.createElement('div');
    dayEl.className = 'calendar-day';
    if (income > 0) dayEl.classList.add('positive');

    const isToday = new Date().toISOString().split('T')[0] === dateStr;
    if (isToday) dayEl.classList.add('today');

    dayEl.innerHTML = `
            <span class="day-num">${d}</span>
            <span class="pnl-value">${income > 0 ? '+' + fmt(income) : ''}</span>
        `;

    grid.appendChild(dayEl);
  }

  monthlyTotalLabel.textContent = `Rp ${fmt(monthlyTotal)}`;
}

/* animateValue removed (consolidated at top) */

document.addEventListener('DOMContentLoaded', () => {
  fetchPnLHistory();
  fetchGlobalHistory(); // Load global chart history

  const prevBtn = document.getElementById('prev-month');
  const nextBtn = document.getElementById('next-month');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      calendarDate.setMonth(calendarDate.getMonth() - 1);
      renderPnLCalendar();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      calendarDate.setMonth(calendarDate.getMonth() + 1);
      renderPnLCalendar();
    });
  }
});

// ================= ATTENDANCE CALENDAR LOGIC =================
function toggleCalendar(btn) {
  const card = btn.closest('.account-card');
  const dropdown = card.querySelector('.calendar-dropdown');
  const grid = dropdown.querySelector('.calendar-grid');

  if (!dropdown || !grid) return;

  const isHidden = dropdown.style.display === 'none';
  if (isHidden) {
    dropdown.style.display = 'block';
    renderCalendar(card, grid);
    btn.classList.add('active');
  } else {
    dropdown.style.display = 'none';
    btn.classList.remove('active');
  }
}

function renderCalendar(card, gridContainer) {
  const rawData = card.dataset.calendar;
  let attendedDays = [];
  try {
    if (rawData) attendedDays = JSON.parse(rawData);
  } catch (e) { attendedDays = []; }

  // STRICTLY CURRENT MONTH DISPLAY
  const now = new Date();
  const currentDay = now.getDate();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();

  // Header for month separation clarity (if not present)
  // Check if header exists, if not create it
  let header = gridContainer.previousElementSibling;

  // Note: Simple solution - just inject a header div if we can, 
  // but better to just rely on the grid and date logic for now 
  // as adding elements might break layout. 
  // Instead, we will strictly filter the data.

  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

  let html = '';
  // Add a simple month label row if desired, or relying on external label
  // For now, let's just fix the "messy" data

  for (let i = 1; i <= daysInMonth; i++) {
    // FIX: Only consider attended if day is <= currentDay
    // This removes "ghost" data from previous months that might appear as future dates (e.g. 30, 31)
    const canBeAttended = (i <= currentDay);
    const isAttended = canBeAttended && attendedDays.includes(i);
    const isPast = (i < currentDay);

    let statusClass = '';
    if (isAttended) {
      statusClass = 'attended';
    } else if (isPast) {
      statusClass = 'missed';
    }

    if (i === currentDay) statusClass += ' today';

    html += `<div class="cal-day ${statusClass}">${i}</div>`;
  }
  gridContainer.innerHTML = html;
}

function renderMiniCalendar(card, container) {
  const rawData = card.dataset.calendar;
  let attendedDays = [];
  try {
    if (rawData) attendedDays = JSON.parse(rawData);
  } catch (e) { attendedDays = []; }

  const now = new Date();
  const todayDate = now.getDate();
  const currentDay = now.getDay(); // 0 (Sun) to 6 (Sat)

  // Calculate start of week (Monday)
  const dayShift = currentDay === 0 ? 6 : currentDay - 1;
  const mondayDate = new Date(now);
  mondayDate.setDate(now.getDate() - dayShift);

  let html = '';

  // Generate Mon-Sun
  const days = ['S', 'S', 'R', 'K', 'J', 'S', 'M'];

  for (let i = 0; i < 7; i++) {
    const workDate = new Date(mondayDate);
    workDate.setDate(mondayDate.getDate() + i);

    const dNum = workDate.getDate();
    const isToday = (dNum === todayDate && workDate.getMonth() === now.getMonth());
    // Only mark attended if it's the current month AND the day number matches
    const isAttended = (workDate.getMonth() === now.getMonth() &&
      workDate.getFullYear() === now.getFullYear() &&
      attendedDays.includes(dNum));
    const isPast = (workDate < now && !isToday);

    let statusClass = '';
    if (isAttended) {
      statusClass = 'attended';
    } else if (isPast && workDate.getMonth() === now.getMonth()) {
      // Mark missed only if it's the same month for visual consistency
      // or just strictly past
      statusClass = 'missed';
    }

    if (isToday) statusClass += ' today';

    // Just showing day number
    html += `
         <div class="mini-day ${statusClass}" title="${days[i]}">
           <span style="font-size: 0.65rem; opacity: 0.7;">${days[i]}</span>
           <span style="font-weight: 700;">${dNum}</span>
         </div>
       `;
  }
  container.innerHTML = html;
}

function renderEstimation(container, est) {
  if (!est) return;

  const fmt = (val) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(val);

  container.innerHTML = `
    <div class="estimation-box tier-${est.tier.toLowerCase()}">
      <div class="est-header">
        <span class="est-title"><i class="fas fa-calculator"></i> Estimasi Penarikan</span>
        <span class="tier-badge">${est.tier}</span>
      </div>
      <div class="est-body">
         <div class="est-target">
            Target: <strong>${est.target_day}</strong> (sisa ${est.days_left} hari)
         </div>
         <div class="est-total">
            <span class="label">Estimasi Saldo</span>
            <span class="value">Rp ${fmt(est.estimated_balance)}</span>
         </div>
         <div class="est-note">*Tidak menghitung hari Minggu (libur).</div>
      </div>
    </div>
  `;
}
