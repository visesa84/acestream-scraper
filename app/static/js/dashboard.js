/**
 * Dashboard functionality for Acestream Scraper
 */

async function refreshData() {
    showLoading();
    
    try {
        await checkServicesStatus();
    } catch (e) {
        console.error('Error checking services status:', e);
    }

    try {
        const stats = await fetchStats();
        if (stats) {
            updateStats(stats);
            const urlsList = document.getElementById('urlsList');
            if (urlsList) {
                renderUrlsList(urlsList, stats);
            }
            updateStatusInfo(stats);
        }
    } catch (error) {
        console.error('Error loading stats (API 500):', error);
    }

    try {
        await populateUrlDropdown();
        if (typeof refreshChannelList === 'function') {
            const urlFilter = document.getElementById('urlFilter');
            const urlId = urlFilter ? urlFilter.value : '';
            const searchInput = document.getElementById('channelSearch');
            const searchTerm = searchInput ? searchInput.value.trim() : '';
            await refreshChannelList(searchTerm, urlId);
        }
    } catch (e) {
        console.error('Error refreshing channel components:', e);
    }

    hideLoading();
}

async function populateUrlDropdown() {
    try {
        const response = await fetch('/api/channels/sources');
        const sources = await response.json();
        const urlDropdown = document.getElementById('urlFilter');
        
        if (!urlDropdown || !sources) return;
        
        while (urlDropdown.options.length > 1) {
            urlDropdown.remove(1);
        }
        
        const sortedSources = [...sources].sort((a, b) => {
            if (b.channel_count !== a.channel_count) {
                return b.channel_count - a.channel_count;
            }
            return a.url.localeCompare(b.url);
        });
        
        sortedSources.forEach(source => {
            if (source.channel_count > 0) {
                const option = document.createElement('option');
                option.value = source.url_id || '';
                let displayUrl = source.url;
                if (displayUrl.length > 40) {
                    displayUrl = displayUrl.substring(0, 37) + '...';
                }
                option.text = `${displayUrl} (${source.channel_count})`;
                option.title = source.url;
                urlDropdown.appendChild(option);
            }
        });
    } catch (error) {
        console.error('Error populating URL dropdown:', error);
    }
}

function renderUrlsList(urlsList, stats) {
    if (!stats || !stats.urls || stats.urls.length === 0) {
        urlsList.innerHTML = `
            <div class="list-group-item text-center">
                <span class="text-muted">No URLs found. Add a URL to start scraping for streams.</span>
            </div>
        `;
        return;
    }
    
    urlsList.innerHTML = stats.urls.map(url => `
        <div class="list-group-item">
            <div class="row align-items-center">
                <div class="col-md-7">
                    <div>
                        <strong>${url.url}</strong>
                        <span class="badge bg-info ms-2">${url.url_type || 'regular'}</span>
                    </div>
                    <div class="small text-muted">
                        <span class="status-badge">Status: <span class="badge ${getStatusBadgeClass(url.status)}">${url.status}</span></span>
                        <span class="ms-2">Streams: ${url.channel_count}</span>
                        ${url.last_processed ? `<span class="ms-2">Last scraped: ${formatLocalDate(url.last_processed)}</span>` : ''}
                    </div>
                </div>
                <div class="col-md-5 text-end">
                    <button class="btn btn-sm ${url.enabled ? 'btn-warning' : 'btn-success'}" onclick="toggleUrl('${url.id}', ${!url.enabled})">
                        ${url.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button class="btn btn-sm btn-info" onclick="refreshUrl('${url.id}')">Refresh</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteUrl('${url.id}')">Delete</button>
                </div>
            </div>
        </div>
    `).join('');
}

function getStatusBadgeClass(status) {
    switch(status.toLowerCase()) {
        case 'pending': return 'bg-warning';
        case 'processing': return 'bg-primary';
        case 'success': case 'ok': return 'bg-success';
        case 'failed': case 'error': return 'bg-danger';
        case 'disabled': return 'bg-secondary';
        default: return 'bg-info';
    }
}

function updateStatusInfo(stats) {
    const rescrapeInfo = document.getElementById('rescrapeInfoContainer');
    if (rescrapeInfo) {
        rescrapeInfo.innerHTML = `
            <h6 class="card-subtitle mb-2">Rescrape Interval</h6>
            <p class="mb-1 text-muted small">URLs are automatically refreshed every ${stats.rescrape_interval || 'N/A'} hours</p>
        `;
    }
}

function formatLocalDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
}

async function handleAddUrl(e) {
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
            await refreshData();
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'Network error while adding URL');
    } finally {
        hideLoading();
    }
}

function downloadPlaylist(refresh = false) {
    const searchTerm = document.getElementById('channelSearch')?.value.trim();
    let url = '/playlist.m3u'; 
    const params = new URLSearchParams();
    
    if (refresh) params.append('refresh', 'true');
    if (searchTerm) params.append('search', searchTerm);
    
    if (params.toString()) url += '?' + params.toString();
    window.location.href = url;
}

document.addEventListener('DOMContentLoaded', function() {
    refreshData();
    const addUrlForm = document.getElementById('addUrlForm');
    if (addUrlForm) addUrlForm.addEventListener('submit', handleAddUrl);
    
    const urlFilter = document.getElementById('urlFilter');
    if (urlFilter) {
        urlFilter.addEventListener('change', function() {
            filterByUrl(this.value);
        });
    }
    setInterval(refreshData, 60000);
});

async function checkServicesStatus() {
    const dashEnableCheckStatus = document.getElementById('dashEnableCheckStatus');
    const dashCheckStatusBadge = document.getElementById('dashCheckStatusBadge');
    const dashCheckIntervalText = document.getElementById('dashCheckIntervalText');

    if (dashEnableCheckStatus) {
        fetch('/api/config/checkstatus_interval')
            .then(response => response.json())
            .then(data => {
                const isEnabled = data.enabled === true;
                dashEnableCheckStatus.checked = isEnabled;
                if (dashCheckStatusBadge) {
                    dashCheckStatusBadge.className = isEnabled ? 'badge bg-success' : 'badge bg-secondary';
                    dashCheckStatusBadge.textContent = isEnabled ? 'Active' : 'Disabled';
                }
                if (dashCheckIntervalText) {
                    dashCheckIntervalText.textContent = data.hours || '24';
                }
            })
            .catch(err => console.error("Error en Dashboard CheckStatus:", err));

        dashEnableCheckStatus.addEventListener('change', async function() {
            const isEnabled = this.checked;
            try {
                const response = await fetch('/api/config/checkstatus_interval', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        enabled: isEnabled,
                        hours: parseInt(dashCheckIntervalText ? dashCheckIntervalText.textContent : 24)
                    })
                });

                if (response.ok && dashCheckStatusBadge) {
                    dashCheckStatusBadge.className = isEnabled ? 'badge bg-success' : 'badge bg-secondary';
                    dashCheckStatusBadge.textContent = isEnabled ? 'Active' : 'Disabled';
                } else {
                    this.checked = !isEnabled;
                }
            } catch (e) {
                this.checked = !isEnabled;
            }
        });
    }
}

async function filterByUrl(urlId) {
    try {
        showLoading();
        const searchInput = document.getElementById('channelSearch');
        const searchTerm = searchInput ? searchInput.value.trim() : '';
        const params = new URLSearchParams();
        if (searchTerm) params.append('search', searchTerm);
        if (urlId) params.append('url_id', urlId);
        
        const queryString = params.toString() ? `?${params.toString()}` : '';
        // CORREGIDO: Añadida la barra final obligatoria para evitar redirección 308 y procesar el JSON
        const response = await fetch(`/api/channels/${queryString}`);
        const channels = await response.json();
        updateChannelList(channels);
    } catch (error) {
        console.error('Error filtering channels:', error);
        showAlert('danger', 'Failed to filter channels');
    } finally {
        hideLoading();
    }
}

function updateChannelList(channels) {
    const channelsList = document.getElementById('channelListContent');
    if (!channelsList) return;
    
    if (channels.length === 0) {
        channelsList.innerHTML = '<tr><td colspan="4" class="text-center">No channels found matching your filter criteria</td></tr>';
        return;
    }
    
    channelsList.innerHTML = channels.map(channel => {
        let metadataClass = 'primary';
        let tooltipText = 'Edit channel - No EPG data';
        
        if (channel.epg_update_protected) {
            metadataClass = 'purple';
            tooltipText = 'Edit channel - EPG locked';
        } else if (channel.tvg_id && channel.tvg_name && channel.logo) {
            metadataClass = 'success';
            tooltipText = 'Edit channel - Complete EPG data';
        } else if (channel.tvg_id || channel.tvg_name || channel.logo) {
            metadataClass = 'warning';
            tooltipText = 'Edit channel - Partial EPG data';
        }
        
        const isActive = channel.status === 'active';
        const rowStyle = !isActive ? 'style="background-color: #f8f9fa; opacity: 0.7;"' : '';
        const textStyle = !isActive ? 'style="text-decoration: line-through; color: #6c757d;"' : '';
        const logoHtml = channel.logo ? `<img src="${channel.logo}" alt="Logo" class="channel-logo me-2" style="max-height:60px; max-width:60px;">` : '';
            
        return `
        <tr ${rowStyle}>
            <td><div class="d-flex align-items-center" ${textStyle}>${logoHtml}${channel.name}</div></td>
            <td><code>${channel.id}</code></td>
            <td>
                ${formatLocalDate(channel.last_processed)}
                ${channel.last_checked ? `<br><small class="text-muted">Status: <span class="badge ${!isActive ? 'bg-secondary' : (channel.is_online ? 'bg-success' : 'bg-danger')}">${!isActive ? 'Disabled' : (channel.is_online ? 'Online' : 'Offline')}</span></small>` : ''}
            </td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm ${isActive ? 'btn-outline-secondary' : 'btn-secondary'}" onclick="toggleChannelStatus('${channel.id}', '${channel.status}')"><i class="bi bi-power"></i></button>
                    <button class="btn btn-sm btn-info" onclick="checkChannelStatus('${channel.id}')"><i class="bi bi-shield-check"></i></button>
                    <button class="btn btn-sm btn-${metadataClass}" onclick="editChannel('${channel.id}')" title="${tooltipText}"><i class="bi bi-pencil-square"></i></button>
                    <button class="btn btn-sm btn-danger" onclick="deleteChannel('${channel.id}')"><i class="bi bi-trash"></i></button>
                    <button class="btn btn-success btn-sm" onclick="showPlayerOptions('${channel.id}')"><i class="bi bi-play-fill"></i></button>
                </div>
            </td>
        </tr>`;
    }).join('');
    
    const displayedChannels = document.getElementById('displayedChannels');
    if (displayedChannels) displayedChannels.textContent = channels.length;
}

function updateChannelListUI(channels) {
    updateChannelList(channels);
}