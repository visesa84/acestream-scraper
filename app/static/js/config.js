/**
 * Configuration page functionality for Acestream Scraper
 */

async function loadConfigData() {
    showLoading();

    try {
        const stats = await fetchStats();
        if (stats) {
            if (document.getElementById('configStreamMode')) {
                document.getElementById('configStreamMode').textContent = stats.stream_mode ? stats.stream_mode.toUpperCase() : 'TRADITIONAL';
            }
            if (document.getElementById('configRescrapeInterval'))
                document.getElementById('configRescrapeInterval').textContent = (stats.rescrape_interval || 'N/A') + ' hours';
            
            const rescrapeIntervalInput = document.getElementById('rescrapeIntervalInput');
            if (rescrapeIntervalInput && stats.rescrape_interval !== undefined) {
                if (document.activeElement !== rescrapeIntervalInput) {
                    rescrapeIntervalInput.value = stats.rescrape_interval;
                }
            }
            
            if (document.getElementById('configCheckStatusInterval')) {
                const statusSuffix = stats.checkstatus_enabled ? ' (Enabled)' : ' (Disabled)';
                document.getElementById('configCheckStatusInterval').textContent = (stats.checkstatus_interval || 'N/A') + ' hours' + statusSuffix;
            }

            if (document.getElementById('configTotalUrls'))
                document.getElementById('configTotalUrls').textContent = stats.urls?.length || 0;
            if (document.getElementById('configTotalChannels'))
                document.getElementById('configTotalChannels').textContent = stats.total_channels || 0;

            const checkStatusEnabledCheckbox = document.getElementById('checkStatusEnabledCheckbox');
            const checkStatusIntervalInput = document.getElementById('checkStatusIntervalInput');
            const taskBadge = document.getElementById('checkTaskStatusBadge');

            const isEnabled = stats.checkstatus_enabled === true;

            if (taskBadge) {
                taskBadge.className = isEnabled ? 'badge bg-success' : 'badge bg-secondary';
                taskBadge.textContent = isEnabled ? 'Enabled' : 'Disabled';
            }

            if (checkStatusEnabledCheckbox) {
                if (document.activeElement !== checkStatusEnabledCheckbox) {
                    checkStatusEnabledCheckbox.checked = isEnabled;
                    
                    if (checkStatusIntervalInput) {
                        checkStatusIntervalInput.value = stats.checkstatus_interval || 24;
                        checkStatusIntervalInput.disabled = !isEnabled;
                    }
                }
            }

            const streamModeSelect = document.getElementById('streamModeSelect');
            if (streamModeSelect && stats.stream_mode) {
                streamModeSelect.value = stats.stream_mode;
            }
            
            updateStats(stats);
        } 
    } catch (error) {
        console.error('Error loading stats (API 500):', error);
        const totalUrlsEl = document.getElementById('configTotalUrls');
        if (totalUrlsEl) totalUrlsEl.textContent = 'Error';
    }

    try {
        await loadUrlsList();
    } catch (e) { 
        console.error('Error en URL List:', e); 
    }
    
    hideLoading();
}

async function loadUrlsList() {
    const urlsManagementList = document.getElementById('urlsManagementList');
    if (!urlsManagementList) return;

    try {
        const stats = await fetchStats();
        
        if (stats && stats.urls && stats.urls.length > 0) {
            urlsManagementList.innerHTML = stats.urls.map(url => `
                <div class="list-group-item">
                    <div class="row align-items-center">
                        <div class="col-md-7">
                            <div>
                                <strong>${url.url}</strong>
                                <span class="badge bg-info ms-2">${url.url_type}</span>
                            </div>
                            <div class="small text-muted">
                                <span>ID: ${url.id}</span>
                                <span class="ms-2">Status: <span class="status-${(url.status || 'unknown').toLowerCase()}">${url.status}</span></span>
                                <span class="ms-2">Channels: ${url.channel_count}</span>
                                ${url.last_processed ? `<span class="ms-2">Last scraped: ${formatLocalDate(url.last_processed)}</span>` : ''}
                            </div>
                        </div>
                        <div class="col-md-5 text-end">
                            <button class="btn btn-sm ${url.enabled ? 'btn-warning' : 'btn-success'}" 
                                    onclick="toggleUrl('${url.id}', ${!url.enabled})">
                                ${url.enabled ? 'Disable' : 'Enable'}
                            </button>
                            <button class="btn btn-sm btn-info" onclick="refreshUrl('${url.id}')">Refresh</button>
                            <button class="btn btn-sm btn-danger" onclick="deleteUrl('${url.id}')">Delete</button>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            urlsManagementList.innerHTML = '<div class="list-group-item text-center text-muted">No URLs found</div>';
        }
    } catch (error) {
        console.error('Error loading URLs list:', error);
        if (urlsManagementList) {
            urlsManagementList.innerHTML = '<div class="list-group-item text-center text-danger">Error loading URLs</div>';
        }
    }
}

async function refreshUrl(url) {
    try {
        showLoading();
        const response = await fetch(`/api/urls/${encodeURIComponent(url)}/refresh`, { method: 'POST' });
        await handleApiResponse(response, 'URL refresh started');
    } catch (error) {
        console.error('Error refreshing URL:', error);
        alert('Network error while refreshing URL');
    } finally {
        hideLoading();
    }
}

function setupConfigEvents() {
    // Formulario exclusivo para el Modo de Stream (sin Base URL)
    const streamModeForm = document.getElementById('streamModeForm');
    if (streamModeForm) {
        streamModeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const streamModeSelect = document.getElementById('streamModeSelect');
            const streamMode = streamModeSelect ? streamModeSelect.value : 'traditional';

            try {
                showLoading();
                const responseStreamMode = await fetch('/api/config/stream_mode', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stream_mode: streamMode })
                });

                if (await handleApiResponse(responseStreamMode, 'Stream mode updated successfully')) {
                    await loadConfigData();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Network error while updating configuration');
            } finally {
                hideLoading();
            }
        });
    }

    const rescrapeIntervalForm = document.getElementById('rescrapeIntervalForm');
    if (rescrapeIntervalForm) {
        rescrapeIntervalForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const hoursInput = document.getElementById('rescrapeIntervalInput');
            const hours = parseInt(hoursInput.value, 10);

            if (isNaN(hours) || hours < 1) {
                alert('Please enter a valid number of hours (minimum 1)');
                return;
            }

            try {
                showLoading();
                const response = await fetch('/api/config/rescrape_interval', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ hours: hours })
                });

                if (await handleApiResponse(response, 'Rescrape interval updated successfully')) {
                    await loadConfigData();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Network error while updating rescrape interval');
            } finally {
                hideLoading();
            }
        });
    }

    const addUrlForm = document.getElementById('addUrlForm');
    if (addUrlForm) {
        addUrlForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const urlInput = document.getElementById('urlInput');
            const urlTypeSelect = document.getElementById('urlTypeSelect');
            const url = urlInput.value.trim();
            const urlType = urlTypeSelect.value;

            if (!url) {
                showAlert('warning', 'Please enter a URL');
                return;
            }

            try {
                showLoading();
                const success = await addUrl(url, urlType);
                if (success) {
                    urlInput.value = '';
                    await loadUrlsList();
                }
            } finally {
                hideLoading();
            }
        });
    }

    const checkStatusIntervalForm = document.getElementById('checkStatusIntervalForm');
    const checkStatusEnabledCheckbox = document.getElementById('checkStatusEnabledCheckbox');
    const checkStatusIntervalInput = document.getElementById('checkStatusIntervalInput');

    if (checkStatusIntervalForm) {
        checkStatusIntervalForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const hours = parseInt(checkStatusIntervalInput.value, 10);
            const isEnabled = checkStatusEnabledCheckbox ? checkStatusEnabledCheckbox.checked : true;

            if (isNaN(hours) || hours < 1) {
                alert('Please enter a valid number of hours (minimum 1)');
                return;
            }

            try {
                showLoading();
                const response = await fetch('/api/config/checkstatus_interval', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ hours: hours, enabled: isEnabled })
                });

                if (await handleApiResponse(response, 'Check status configuration updated successfully')) {
                    await loadConfigData();
                }
            } catch (error) {
                console.error('Error updating check status config:', error);
                alert('Network error while updating check status configuration');
            } finally {
                hideLoading();
            }
        });
    }

    if (checkStatusEnabledCheckbox) {
        checkStatusEnabledCheckbox.addEventListener('change', async function() {
            const input = document.getElementById('checkStatusIntervalInput');
            const isEnabled = this.checked;
            let hoursValue = input ? parseInt(input.value, 10) : 24;
            if (isNaN(hoursValue)) hoursValue = 24;

            try {
                showLoading();
                const response = await fetch('/api/config/checkstatus_interval', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: Boolean(isEnabled), hours: hoursValue })
                });

                if (await handleApiResponse(response, 'Status updated')) {
                    if (input) input.disabled = !isEnabled;
                    const taskBadge = document.getElementById('checkTaskStatusBadge');
                    if (taskBadge) {
                        taskBadge.className = isEnabled ? 'badge bg-success' : 'badge bg-secondary';
                        taskBadge.textContent = isEnabled ? 'Enabled' : 'Disabled';
                    }
                }
            } catch (error) {
                this.checked = !isEnabled;
                alert('Error updating status');
            } finally {
                hideLoading();
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadConfigData();
    setupConfigEvents();
    setInterval(loadConfigData, 60000);
});