document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const connectionStatusDot = document.getElementById('connectionStatusDot');
  const connectionStatusText = document.getElementById('connectionStatusText');
  
  const settingsForm = document.getElementById('settingsForm');
  const apiProvider = document.getElementById('apiProvider');
  const geminiKeyGroup = document.getElementById('geminiKeyGroup');
  const groqKeyGroup = document.getElementById('groqKeyGroup');
  const geminiKey = document.getElementById('geminiKey');
  const groqKey = document.getElementById('groqKey');
  const rpmLimit = document.getElementById('rpmLimit');
  const rpmVal = document.getElementById('rpmVal');
  
  const telegramToken = document.getElementById('telegramToken');
  const webhookUrl = document.getElementById('webhookUrl');
  
  const singleWebhookForm = document.getElementById('singleWebhookForm');
  const phoneInput = document.getElementById('phoneInput');
  const messageInput = document.getElementById('messageInput');
  const clearQueueBtn = document.getElementById('clearQueueBtn');
  
  const statQueued = document.getElementById('statQueued');
  const statCurrentRpm = document.getElementById('statCurrentRpm');
  const statRpmLimit = document.getElementById('statRpmLimit');
  const statCompleted = document.getElementById('statCompleted');
  const statFailed = document.getElementById('statFailed');
  
  const workerStatusBadge = document.getElementById('workerStatusBadge');
  const workerProgressBar = document.getElementById('workerProgressBar');
  const workerTimerText = document.getElementById('workerTimerText');
  
  const messageLogsBody = document.getElementById('messageLogsBody');
  const filterTabs = document.querySelectorAll('.tab-btn');
  
  let currentFilter = 'all';
  let sseSource = null;
  let throttleTimer = null;

  // Initialize
  fetchSettings();
  fetchMessages();
  connectSSE();
  
  // Real-time Slider label sync
  rpmLimit.addEventListener('input', (e) => {
    rpmVal.textContent = e.target.value;
  });

  // Toggle API Key inputs based on Provider
  apiProvider.addEventListener('change', () => {
    toggleKeyGroups(apiProvider.value);
  });

  function toggleKeyGroups(provider) {
    geminiKeyGroup.classList.add('hidden');
    groqKeyGroup.classList.add('hidden');
    
    if (provider === 'gemini') {
      geminiKeyGroup.classList.remove('hidden');
    } else if (provider === 'groq') {
      groqKeyGroup.classList.remove('hidden');
    }
  }

  // Fetch Settings
  async function fetchSettings() {
    try {
      const res = await fetch('/api/settings');
      const settings = await res.json();
      
      apiProvider.value = settings.api_provider || 'mock';
      rpmLimit.value = settings.rpm_limit || '20';
      rpmVal.textContent = settings.rpm_limit || '20';
      statRpmLimit.textContent = settings.rpm_limit || '20';
      
      geminiKey.value = settings.gemini_key || '';
      groqKey.value = settings.groq_key || '';
      
      telegramToken.value = settings.telegram_token || '';
      webhookUrl.value = settings.webhook_url || '';
      
      toggleKeyGroups(apiProvider.value);
    } catch (err) {
      console.error('Error fetching settings:', err);
    }
  }

  // Update Settings
  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      api_provider: apiProvider.value,
      rpm_limit: parseInt(rpmLimit.value),
      gemini_key: geminiKey.value,
      groq_key: groqKey.value,
      telegram_token: telegramToken.value,
      webhook_url: webhookUrl.value
    };

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        statRpmLimit.textContent = payload.rpm_limit;
        showToast('Configuration saved successfully!', 'success');
      } else {
        showToast('Failed to save configuration', 'error');
      }
    } catch (err) {
      console.error('Error updating settings:', err);
      showToast('Network error saving settings', 'error');
    }
  });

  // Ingest Single Webhook
  singleWebhookForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      phone: phoneInput.value,
      message: messageInput.value
    };

    try {
      const res = await fetch('/api/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        messageInput.value = '';
        showToast('Webhook message ingested instantly!', 'success');
      } else {
        showToast('Webhook ingest failed', 'error');
      }
    } catch (err) {
      console.error('Error sending webhook:', err);
      showToast('Error sending webhook', 'error');
    }
  });

  // Ingest Bulk Simulations
  document.querySelectorAll('.btn-campaign').forEach(btn => {
    btn.addEventListener('click', async () => {
      const count = btn.getAttribute('data-count');
      btn.disabled = true;
      btn.textContent = 'Queueing...';
      
      try {
        const res = await fetch('/api/simulate-bulk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ count: parseInt(count), type: 'mixed' })
        });
        if (res.ok) {
          showToast(`Burst campaign of ${count} messages queued successfully!`, 'success');
        } else {
          showToast('Failed to queue bulk campaign', 'error');
        }
      } catch (err) {
        console.error('Error sending bulk campaign:', err);
        showToast('Error queueing campaign', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = `Burst ${count} Replies`;
      }
    });
  });

  // Clear Database
  clearQueueBtn.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to clear the entire log and queue?')) return;
    try {
      const res = await fetch('/api/clear', { method: 'POST' });
      if (res.ok) {
        messageLogsBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No messages in pipeline database. Trigger a webhook simulation to start.</td></tr>`;
        showToast('Database cleared', 'success');
      }
    } catch (err) {
      console.error('Error clearing queue:', err);
    }
  });

  // Fetch Message Logs
  async function fetchMessages() {
    try {
      const res = await fetch('/api/messages?limit=100');
      const messages = await res.json();
      renderMessages(messages);
    } catch (err) {
      console.error('Error fetching messages:', err);
    }
  }

  // Render list of messages
  function renderMessages(messages) {
    if (messages.length === 0) {
      messageLogsBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No messages in pipeline database. Trigger a webhook simulation to start.</td></tr>`;
      return;
    }
    
    messageLogsBody.innerHTML = '';
    messages.forEach(msg => {
      appendOrUpdateRow(msg, false);
    });
    filterRows();
  }

  // Add a message row to top, or update an existing row in place
  function appendOrUpdateRow(msg, highlight = true) {
    let existingRow = document.getElementById(`row_${msg.id}`);
    
    const tr = existingRow || document.createElement('tr');
    tr.id = `row_${msg.id}`;
    tr.className = `msg-row status-${msg.status}`;
    tr.setAttribute('data-status', msg.status);

    const timeStr = new Date(msg.created_at).toLocaleTimeString();
    
    // Determine intent badge markup
    let intentMarkup = '<span class="text-muted">—</span>';
    if (msg.intent) {
      let intentClass = `intent-${msg.intent}`;
      let intentLabel = msg.intent.replace('_', ' ');
      intentMarkup = `<span class="intent-badge ${intentClass}">${intentLabel}</span>`;
    }

    // Determine urgency badge markup
    let urgencyMarkup = '<span class="text-muted">—</span>';
    if (msg.urgency) {
      let urgencyClass = `urgency-${msg.urgency}`;
      urgencyMarkup = `<span class="urgency-badge ${urgencyClass}">${msg.urgency}</span>`;
    }

    // Entities parsing
    let entitiesMarkup = '<span class="text-muted">—</span>';
    if (msg.extracted_entities) {
      let entities = msg.extracted_entities;
      if (typeof entities === 'string') {
        try { entities = JSON.parse(entities); } catch (_) {}
      }
      
      let items = [];
      if (entities.order_id) items.push(`<div class="meta-item"><span>Order:</span> ${entities.order_id}</div>`);
      if (entities.requested_date) items.push(`<div class="meta-item"><span>Date:</span> ${entities.requested_date}</div>`);
      if (msg.language) items.push(`<div class="meta-item"><span>Lang:</span> ${msg.language}</div>`);
      
      if (items.length > 0) {
        entitiesMarkup = `<div class="meta-container">${items.join('')}</div>`;
      }
    }

    // Response draft markup
    let responseMarkup = '<span class="text-muted">—</span>';
    if (msg.status === 'processing') {
      responseMarkup = '<span class="text-muted">Analyzing customer intent...</span>';
    } else if (msg.draft_response) {
      responseMarkup = `<div class="draft-box">${msg.draft_response}</div>`;
    } else if (msg.error) {
      responseMarkup = `<div class="text-muted" style="color: #f87171 !important; font-size: 0.75rem;">⚠️ ${msg.error}</div>`;
    }

    // Status markup
    let statusMarkup = '';
    if (msg.status === 'queued') {
      statusMarkup = `<span class="status-col queued">⏳ Queued</span>`;
    } else if (msg.status === 'processing') {
      statusMarkup = `<span class="status-col processing"><div class="spinner"></div> Ingesting</span>`;
    } else if (msg.status === 'completed') {
      statusMarkup = `<span class="status-col completed">✅ Done</span>`;
    } else {
      statusMarkup = `<span class="status-col failed">❌ Failed</span>`;
    }

    // Determine platform badge markup
    const platformMarkup = msg.platform === 'telegram'
      ? `<span class="badge" style="background: rgba(0, 136, 204, 0.12); color: #0088cc; border: 1px solid rgba(0, 136, 204, 0.25); padding: 1px 4px; font-size: 0.65rem; margin-right: 4px; border-radius: 4px;">TG</span>`
      : `<span class="badge" style="background: rgba(167, 139, 250, 0.12); color: var(--accent-purple); border: 1px solid rgba(167, 139, 250, 0.25); padding: 1px 4px; font-size: 0.65rem; margin-right: 4px; border-radius: 4px;">SIM</span>`;

    tr.innerHTML = `
      <td>
        <span class="phone-col">${platformMarkup}${msg.phone}</span>
        <span class="time-col">${timeStr}</span>
      </td>
      <td style="font-weight: 500;">${msg.message}</td>
      <td>${intentMarkup}</td>
      <td>${urgencyMarkup}</td>
      <td>${entitiesMarkup}</td>
      <td>${responseMarkup}</td>
      <td>${statusMarkup}</td>
    `;

    if (!existingRow) {
      // Put new rows at the top
      messageLogsBody.insertBefore(tr, messageLogsBody.firstChild);
    }

    if (highlight) {
      tr.style.backgroundColor = 'rgba(167, 139, 250, 0.15)';
      setTimeout(() => {
        tr.style.backgroundColor = '';
      }, 1000);
    }
  }

  // Filter message rows in the browser based on selected tab
  function filterRows() {
    const rows = messageLogsBody.querySelectorAll('tr.msg-row');
    rows.forEach(row => {
      const status = row.getAttribute('data-status');
      if (currentFilter === 'all' || status === currentFilter) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  }

  // Setup tab event listeners
  filterTabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentFilter = tab.getAttribute('data-filter');
      filterRows();
    });
  });

  // Server-Sent Events integration
  function connectSSE() {
    if (sseSource) {
      sseSource.close();
    }

    sseSource = new EventSource('/api/events');

    sseSource.onopen = () => {
      connectionStatusDot.className = 'status-dot green';
      connectionStatusText.textContent = 'Active pipeline sync connected';
    };

    sseSource.onerror = (err) => {
      connectionStatusDot.className = 'status-dot yellow';
      connectionStatusText.textContent = 'Pipeline sync offline. Reconnecting...';
      console.warn('SSE disconnected, retrying:', err);
    };

    // Update stats globally
    sseSource.addEventListener('stats', (e) => {
      const stats = JSON.parse(e.data);
      statQueued.textContent = stats.queued;
      statCurrentRpm.textContent = stats.current_rpm;
      statCompleted.textContent = stats.completed;
      statFailed.textContent = stats.failed;

      // Dynamically update worker badge status
      if (stats.processing > 0) {
        setWorkerStatus('Active', 'badge-active');
        workerProgressBar.style.width = '100%';
        workerTimerText.textContent = 'AI inference active...';
      } else if (stats.queued === 0 && stats.processing === 0 && !throttleTimer) {
        setWorkerStatus('Idle', 'badge-inactive');
        workerProgressBar.style.width = '0%';
        workerTimerText.textContent = 'Waiting for webhooks';
      }
    });

    sseSource.addEventListener('message_queued', (e) => {
      const msg = JSON.parse(e.data);
      // Remove placeholder row if present
      if (messageLogsBody.querySelector('.text-muted') && !messageLogsBody.querySelector('.msg-row')) {
        messageLogsBody.innerHTML = '';
      }
      appendOrUpdateRow(msg, true);
      filterRows();
    });

    sseSource.addEventListener('message_updated', (e) => {
      const msg = JSON.parse(e.data);
      appendOrUpdateRow(msg, true);
      filterRows();
    });

    sseSource.addEventListener('bulk_queued', (e) => {
      const data = JSON.parse(e.data);
      showToast(`Campaign injected: ${data.count} webhooks entered queue!`, 'success');
      fetchMessages();
    });

    // Enforce throttled worker countdown visualization
    sseSource.addEventListener('worker_throttled', (e) => {
      const data = JSON.parse(e.data);
      const delay = data.remainingDelay;
      
      setWorkerStatus('Throttled', 'badge-throttled');
      
      // Stop any existing animation timer
      if (throttleTimer) clearInterval(throttleTimer);
      
      let timeLeft = delay;
      workerProgressBar.style.transition = 'none';
      workerProgressBar.style.width = '100%';
      
      // Forces browser layout reflow before triggering transition
      void workerProgressBar.offsetWidth;
      
      workerProgressBar.style.transition = `width ${delay}ms linear`;
      workerProgressBar.style.width = '0%';

      workerTimerText.textContent = `Enforcing rate-limit delay: ${(timeLeft / 1000).toFixed(1)}s`;
      
      const startTime = Date.now();
      throttleTimer = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, delay - elapsed);
        
        if (remaining <= 0) {
          clearInterval(throttleTimer);
          throttleTimer = null;
          workerTimerText.textContent = 'Ready for next message';
          if (parseInt(statQueued.textContent) === 0) {
            setWorkerStatus('Idle', 'badge-inactive');
          } else {
            setWorkerStatus('Active', 'badge-active');
          }
        } else {
          workerTimerText.textContent = `Enforcing rate-limit delay: ${(remaining / 1000).toFixed(1)}s`;
        }
      }, 100);
    });

    sseSource.addEventListener('cleared', () => {
      messageLogsBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No messages in pipeline database. Trigger a webhook simulation to start.</td></tr>`;
      statQueued.textContent = '0';
      statCurrentRpm.textContent = '0';
      statCompleted.textContent = '0';
      statFailed.textContent = '0';
      setWorkerStatus('Idle', 'badge-inactive');
      workerProgressBar.style.width = '0%';
      workerTimerText.textContent = 'Database cleared';
    });
  }

  function setWorkerStatus(text, badgeClass) {
    workerStatusBadge.textContent = text;
    workerStatusBadge.className = `badge ${badgeClass}`;
  }

  // Simple Notification Toast
  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.background = type === 'success' ? 'var(--status-completed-bg)' : 'var(--status-failed-bg)';
    toast.style.color = type === 'success' ? 'var(--status-completed)' : 'var(--status-failed)';
    toast.style.border = `1px solid ${type === 'success' ? 'var(--status-completed)' : 'var(--status-failed)'}`;
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
    toast.style.fontFamily = 'var(--font-display)';
    toast.style.fontSize = '0.9rem';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '9999';
    toast.style.backdropFilter = 'blur(10px)';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    toast.style.transition = 'all 0.3s ease';

    document.body.appendChild(toast);
    toast.textContent = message;

    // Trigger slide-in
    setTimeout(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    }, 50);

    // Slide-out and remove
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(20px)';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
});
