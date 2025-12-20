// Auto-save functionality
let autoSaveTimeout;
let isSaving = false;
let NOTIFIED_TODAY = new Set(); // Tracks phones notified for 100% completion

// Request notification permission
function requestNotificationPermission() {
  if (!("Notification" in window)) {
    showToast("Browser agan gak support notifikasi ❌", "error");
    return;
  }

  if (Notification.permission === "default") {
    Notification.requestPermission().then(permission => {
      if (permission === "granted") {
        showToast("Izin diberikan! Silakan tes lagi. ✅", "success");
      } else {
        showToast("Izin ditolak. Cek settingan Chrome agan. ❌", "error");
      }
    });
  } else if (Notification.permission === "denied") {
    showToast("Izin diblokir. Riset permission di Chrome gan! ❌", "error");
  }
}

function showNativeNotification(title, body) {
  console.log("Attempting notification:", title);
  if (!("Notification" in window)) {
    console.error("Notification API not supported");
    return;
  }

  if (Notification.permission !== "granted") {
    console.warn("Notification permission not granted:", Notification.permission);
    showToast("Izin notifikasi belum aktif! ❌", "error");
    return;
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then(registration => {
      console.log("ServiceWorker ready, showing notification...");
      registration.showNotification(title, {
        body: body,
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [200, 100, 200],
        tag: 'ternak-uang-alert',
        renotify: true
      }).then(() => {
        console.log("Notification shown successfully via SW");
      }).catch(err => {
        console.error("SW notification error:", err);
        showToast("Error SW: " + err, "error");
      });
    });
  } else {
    console.log("No ServiceWorker, using fallback Notification...");
    try {
      new Notification(title, { body: body, icon: '/static/icon-192.png' });
    } catch (e) {
      console.error("Notification fallback error:", e);
      showToast("Gagal fallback: " + e, "error");
    }
  }
}

function testNotification() {
  if (!window.isSecureContext) {
    showToast("Gagal: Harus pakai HTTPS atau localhost! ❌", "error");
    return;
  }

  if (!("Notification" in window)) {
    showToast("Browser tidak suport Notifikasi ❌", "error");
    return;
  }

  if (Notification.permission === "granted") {
    showToast("Mengirim tes notifikasi... 🔔", "info");
    showNativeNotification("Tes Notifikasi Berhasil! 🚀", "Ganteng banget kan notifikasinya gan? Siap pantau cuan! 🔥");
  } else {
    showToast("Minta izin dulu gan... Klik Izinkan!", "info");
    requestNotificationPermission();
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
  clone.querySelector('.account-number').textContent = count;

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
        console.log(`Skipping auto-sync for +62${phone} (Cooldown active)`);
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
        showToast('Auto-sync queued: +62' + phone, 'success');
        card.dataset.lastSyncTs = now.toISOString();
        card.classList.add('is-syncing'); // Add pulsing glow
        // Wait 1.5s for a gentler sequence
        await new Promise(r => setTimeout(r, 1500));
      }
    } catch (err) {
      console.error('Auto-sync failed for', phone, err);
    }
  }

  if (syncCount > 0) {
    showToast(`Auto-sync started for ${syncCount} accounts`, 'info');
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

function animateValue(el, start, end, duration) {
  if (!el || start === end) return;
  const startTime = performance.now();

  const step = (currentTime) => {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // Elastic Out effect
    const c4 = (2 * Math.PI) / 3;
    const ease = progress === 0 ? 0 : progress === 1 ? 1
      : Math.pow(2, -10 * progress) * Math.sin((progress * 10 - 0.75) * c4) + 1;

    const current = Math.floor(start + (end - start) * ease);

    el.textContent = 'Rp ' + formatNumber(current);

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      el.textContent = 'Rp ' + formatNumber(end);
    }
  };
  requestAnimationFrame(step);
}

function formatNumber(num) {
  return new Intl.NumberFormat('id-ID').format(num);
}

function updateStatusRealTime() {
  fetch('/api/accounts')
    .then(res => res.json())
    .then(data => {
      const accounts = data.accounts || [];
      const queueSize = data.queue_size || 0;

      // Update Queue Status
      const queueBadge = document.getElementById('queue-status');
      const queueCount = document.getElementById('queue-count');
      if (queueCount) queueCount.textContent = queueSize;
      if (queueBadge) {
        if (queueSize > 0) queueBadge.classList.add('active');
        else queueBadge.classList.remove('active');
      }

      accounts.forEach(acc => {
        // Find the card by phone number
        const card = document.querySelector(`.account-card[data-phone="${acc.phone_display}"]`);
        if (!card) return;

        // Toggle Is-Syncing highlight for jobs
        if (acc.is_syncing) {
          card.classList.add('is-syncing');
        } else {
          card.classList.remove('is-syncing');
        }

        // 1. Update status class (ran/due/pending)
        card.classList.remove('ran', 'due', 'pending');
        card.classList.add(acc.status || 'pending');

        // 2. Update Progress Bar
        const progressDiv = card.querySelector('.daily-progress');
        if (progressDiv) {
          const labelEl = progressDiv.querySelector('.progress-label');
          const valueEl = progressDiv.querySelector('.progress-value');
          const percentEl = progressDiv.querySelector('.progress-percent');

          if (labelEl) labelEl.textContent = acc.today_label;
          if (valueEl) valueEl.textContent = `${acc.completed}/${acc.total}`;

          const fillEl = progressDiv.querySelector('.progress-fill');
          if (fillEl) fillEl.style.width = acc.pct + '%';

          progressDiv.classList.remove('progress-complete', 'progress-partial', 'progress-low');
          if (acc.status === 'ran') {
            progressDiv.classList.add('progress-complete');
            if (acc.pct >= 100 && !NOTIFIED_TODAY.has(acc.phone)) {
              NOTIFIED_TODAY.add(acc.phone);
              showNativeNotification("Tugas Selesai! ✅", `Akun ${display} sudah menyelesaikan ${acc.completed}/${acc.total} tugas.`);
            }
          }
          else if (acc.status === 'due') progressDiv.classList.add('progress-partial');
          else progressDiv.classList.add('progress-low');
        }

        // 3. Update Syncing Spinner
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
          } else {
            if (spinnerIcon) spinnerIcon.style.display = 'none';
            if (syncIcon) syncIcon.style.display = 'inline';
            syncBtn.disabled = false;

            if (acc.pct >= 99 && syncLabel) syncLabel.textContent = 'Synced';
          }
        }

        // 4. Update Stats with Animation
        const incomeVal = card.querySelector('.income-display .stat-value');
        if (incomeVal) {
          const oldVal = parseInt(incomeVal.textContent.replace(/[^0-9]/g, '')) || 0;
          if (oldVal !== acc.income) animateValue(incomeVal, oldVal, acc.income, 800);
        }

        const withdrawalVal = card.querySelector('.withdrawal-display .stat-value');
        if (withdrawalVal) {
          const oldVal = parseInt(withdrawalVal.textContent.replace(/[^0-9]/g, '')) || 0;
          if (oldVal !== acc.withdrawal) animateValue(withdrawalVal, oldVal, acc.withdrawal, 800);
        }

        const balanceVal = card.querySelector('.balance-display .stat-value');
        if (balanceVal) {
          const oldVal = parseInt(balanceVal.textContent.replace(/[^0-9]/g, '')) || 0;
          if (oldVal !== acc.balance) animateValue(balanceVal, oldVal, acc.balance, 800);
        }
      });
      // Re-attach action buttons if they were replaced by status updates (template)
      // Note: This is generally not needed if only content is updated, not the buttons themselves.
      // However, if the buttons are dynamically added/removed or their HTML is replaced,
      // these calls ensure event listeners are re-bound.
      attachPlayButtons();
      attachSyncButtons();
      attachMoreButtons(); // Added this line
    })
    .catch(err => {
      console.error('Error polling status:', err);
    });
}

function autoSyncStaleAccounts() {
  const today = new Date().toISOString().slice(0, 10);
  const cards = document.querySelectorAll('.account-card[data-phone]');
  const staleAccounts = [];

  cards.forEach(card => {
    const lastSync = card.dataset.lastSync || '';
    const phone = card.dataset.phone;
    if (phone && lastSync !== today) {
      staleAccounts.push({ card, phone });
    }
  });

  if (staleAccounts.length === 0) return;

  console.log(`Found ${staleAccounts.length} stale accounts. Starting sequential sync...`);

  // Sync sequentially to avoid IP blocks/resource lag
  let p = Promise.resolve();
  staleAccounts.forEach(item => {
    p = p.then(() => performSync(item.phone, item.card));
  });
}

async function performSync(phone, card) {
  console.log(`Auto-syncing +62${phone}...`);
  try {
    const formData = new FormData();
    formData.append('phone', phone);
    const res = await fetch('/sync_single', { method: 'POST', body: formData });
    const data = await res.json();

    // Refresh UI after sync to show queue change
    setTimeout(updateStatusRealTime, 500);

    return data;
  } catch (e) {
    console.error(`Auto-sync failed for ${phone}:`, e);
  }
}

// Initial setup on load
document.addEventListener('DOMContentLoaded', function () {
  autoSyncStaleAccounts();
  updateStatusRealTime(); // Run immediately on load
  setInterval(updateStatusRealTime, 5000); // Poll every 5 seconds (more responsive)

  // Auto-sync all on load
  setTimeout(performAutoSyncAll, 1500);

  // Request permission on first click
  document.addEventListener('click', requestNotificationPermission, { once: true });

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
    'setting-wifi',
    'setting-timeout',
    'setting-viewport',
    'setting-loglevel'
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
}

function saveSettings() {
  const settings = {
    auto_reconnect_wifi: document.getElementById('setting-wifi').checked,
    timeout: parseInt(document.getElementById('setting-timeout').value),
    viewport: document.getElementById('setting-viewport').value,
    log_level: document.getElementById('setting-loglevel').value
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

// Initialize settings listeners
document.addEventListener('DOMContentLoaded', function () {
  initSettings();
});

// ================= ADD-ROW MICRO INTERACTION =================
const addRowBtn = document.getElementById('add-row');
if (addRowBtn) {
  addRowBtn.addEventListener('click', function () {
    addRowBtn.classList.add('clicked');
    setTimeout(() => addRowBtn.classList.remove('clicked'), 240);
  });
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
    modalGradient.addColorStop(0, 'rgba(245, 158, 11, 0.3)');
    modalGradient.addColorStop(1, 'rgba(245, 158, 11, 0.02)');

    const saldoGradient = ctx.createLinearGradient(0, 0, 0, 240);
    saldoGradient.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
    saldoGradient.addColorStop(1, 'rgba(6, 182, 212, 0.02)');

    const pendapatanGradient = ctx.createLinearGradient(0, 0, 0, 240);
    pendapatanGradient.addColorStop(0, 'rgba(249, 115, 22, 0.3)');
    pendapatanGradient.addColorStop(1, 'rgba(249, 115, 22, 0.02)');

    canvas.chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: slicedDates,
        datasets: [
          {
            label: 'Modal',
            data: incomeData,
            borderColor: '#f59e0b',
            backgroundColor: modalGradient,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#f59e0b',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.4,
            fill: true
          },
          {
            label: 'Saldo',
            data: balanceData,
            borderColor: '#06b6d4',
            backgroundColor: saldoGradient,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#06b6d4',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.4,
            fill: true
          },
          {
            label: 'Pendapatan',
            data: withdrawalData,
            borderColor: '#f97316',
            backgroundColor: pendapatanGradient,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#f97316',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointHoverRadius: 7,
            tension: 0.4,
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
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            titleColor: '#f1f5f9',
            bodyColor: '#e2e8f0',
            titleFont: { size: 13, weight: 600, family: "'Inter', sans-serif" },
            bodyFont: { size: 12, family: "'Inter', sans-serif" },
            borderColor: 'rgba(255,255,255,0.05)',
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
            ticks: { color: '#94a3b8', font: { size: 11, family: "'Inter', sans-serif" } },
            grid: { display: false, drawBorder: false }
          },
          y: {
            ticks: {
              color: '#94a3b8',
              font: { size: 11, family: "'Inter', sans-serif" },
              callback: function (value) {
                return value.toLocaleString('id-ID');
              }
            },
            grid: { color: 'rgba(0,0,0,0.03)', borderDash: [5, 5], drawBorder: false },
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
