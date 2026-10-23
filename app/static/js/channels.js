/**
 * Channel management functionality for Acestream Scraper
 */

// Handle form submission for adding a channel
async function handleAddChannel(e) {
    e.preventDefault();
    
    const channelId = document.getElementById('channelId').value.trim();
    const channelName = document.getElementById('channelName').value.trim();
    const channelGroup = document.getElementById('channelGroup').value.trim();
    
    // Advanced fields
    const channelLogo = document.getElementById('channelLogo').value.trim();
    const channelTvgId = document.getElementById('channelTvgId').value.trim();
    const channelTvgName = document.getElementById('channelTvgName').value.trim();
    const channelOriginalUrl = document.getElementById('channelOriginalUrl').value.trim();
    const channelM3uSource = document.getElementById('channelM3uSource').value.trim();
    
    if (!channelId) {
        showAlert('warning', 'Please enter a channel ID');
        return;
    }
    
    try {
        showLoading();
        
        // Create the channel data object with all fields
        const channelData = {
            id: channelId,
            name: channelName || `Channel ${channelId}`,
            manual_add: true, // Flag indicating this is a manually added channel
            group: channelGroup || '',
            current_url: window.location.href // Send the current browser URL
        };
        
        // Only add the advanced fields if they are provided
        if (channelLogo) channelData.logo = channelLogo;
        if (channelTvgId) channelData.tvg_id = channelTvgId;
        if (channelTvgName) channelData.tvg_name = channelTvgName;
        if (channelOriginalUrl) channelData.original_url = channelOriginalUrl;
        if (channelM3uSource) channelData.m3u_source = channelM3uSource;
        
        // Corregido con barra final obligatoria para evitar redirección 308
        const response = await fetch('/api/channels/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(channelData)
        });
        
        if (response.ok) {
            showAlert('success', 'Channel added successfully');
            document.getElementById('addChannelForm').reset();
            
            // Refresh the channels list
            if (typeof refreshChannelList === 'function') {
                await refreshChannelList();
            }
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to add channel');
        }
    } catch (error) {
        console.error('Error adding channel:', error);
        showAlert('danger', error.message || 'Error adding channel');
    } finally {
        hideLoading();
    }
}

// Add event listener for form submission and automatic list loading
document.addEventListener('DOMContentLoaded', function() {
    const addChannelForm = document.getElementById('addChannelForm');
    if (addChannelForm) {
        addChannelForm.addEventListener('submit', handleAddChannel);
        console.log('Add channel form handler set up');
    }
    
    const saveButton = document.getElementById('saveEditChannelBtn');
    if (saveButton) {
        saveButton.addEventListener('click', saveChannelChanges);
    }

    const editStatusField = document.getElementById('editChannelStatus');
    if (editStatusField) {
        editStatusField.addEventListener('change', function() {
            const statusLabel = document.getElementById('statusLabelText');
            if (statusLabel) {
                if (this.checked) {
                    statusLabel.textContent = 'Active';
                    statusLabel.className = 'fw-bold text-success';
                } else {
                    statusLabel.textContent = 'Disabled';
                    statusLabel.className = 'fw-bold text-danger';
                }
            }
        });
    }
    
    // Carga automática de la lista de canales al abrir el dashboard
    if (document.getElementById('channelsList')) {
        refreshChannelList();
    }
});

// Delete a channel
async function deleteChannel(channelId) {
    if (!confirm('Are you sure you want to delete this channel?')) {
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/channels/${encodeURIComponent(channelId)}`, {
            method: 'DELETE'
        });
        
        if (await handleApiResponse(response, 'Channel deleted successfully')) {
            if (typeof refreshData === 'function') {
                await refreshData();
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'Network error while deleting channel');
    } finally {
        hideLoading();
    }
}

// Check status for all channels
async function checkChannelsStatus() {
    if (!confirm('Check status of all channels? This might take a while.')) {
        return;
    }
    
    showLoading();
    try {
        const response = await fetch('/api/channels/check-status', {
            method: 'POST'
        });
        
        const data = await response.json();
        if (response.ok) {
            if (typeof refreshData === 'function') {
                await refreshData();
            }
        } else {
            alert(data.message || data.error || 'Error checking channel status');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error while checking channel status');
    } finally {
        hideLoading();
    }
}

// Enable or disable the channel
function toggleChannelStatus(channelId, currentStatus) {
    const newStatus = (currentStatus === 'active') ? 'disabled' : 'active';
    
    fetch(`/api/channels/${channelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
    })
    .then(response => {
        if (response.ok) refreshChannelList();
        else alert('Error updating status');
    })
    .catch(err => console.error('Error:', err));
}

// Refresh channels list with optional search term and URL filter
async function refreshChannelList(searchTerm = '', urlId = '') {
    try {
        const params = new URLSearchParams();
        if (searchTerm) {
            params.append('search', searchTerm);
        }
        if (urlId) {
            params.append('url_id', urlId);
        }
        
        const queryString = params.toString() ? `?${params.toString()}` : '';
        const response = await fetch(`/api/channels/${queryString}`);
        const channels = await response.json();
        
        const channelsList = document.getElementById('channelListContent') || document.getElementById('channelsList');
        if (channelsList) {
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
                const logoHtml = channel.logo ? `<img src="${channel.logo}" alt="Logo" class="channel-logo me-2" style="max-height:40px; max-width:40px;">` : '';

                return `
                <tr ${rowStyle}>
                    <td class="align-middle ps-4 py-3">
                        <div class="d-flex align-items-center" ${textStyle}>
                            ${logoHtml}
                            <span class="fw-semibold">${channel.name}</span>
                        </div>
                    </td>
                    <td class="align-middle py-3">
                        <a href="acestream://${channel.id}" class="text-decoration-none font-monospace small" title="Open in Acestream player">
                            <code>${channel.id}</code>
                        </a>
                    </td>
                    <td class="align-middle py-3">
                        <span class="badge ${!isActive ? 'bg-secondary' : (channel.is_online ? 'bg-success' : 'bg-danger')}">
                            ${!isActive ? 'Disabled' : (channel.is_online ? 'Online' : 'Offline')}
                        </span>
                        ${channel.check_error ? `<br><small class="text-danger">${channel.check_error}</small>` : ''}
                    </td>
                    <td class="align-middle py-3 small text-muted">
                        ${formatLocalDate(channel.last_checked || channel.last_processed)}
                    </td>
                    <td class="align-middle text-end pe-4 py-3">
                        <div class="btn-group">
                            <button class="btn btn-sm ${isActive ? 'btn-outline-secondary' : 'btn-secondary'}" onclick="toggleChannelStatus('${channel.id}', '${channel.status}')" title="Toggle status"><i class="bi bi-power"></i></button>
                            <button class="btn btn-sm btn-info text-white" onclick="checkChannelStatus('${channel.id}')" title="Check status">
                                <i class="bi bi-shield-check"></i>
                            </button>
                            <button class="btn btn-sm btn-${metadataClass}" onclick="editChannel('${channel.id}')" title="${tooltipText}"><i class="bi bi-pencil-square"></i></button>
                            <button class="btn btn-sm btn-danger" onclick="deleteChannel('${channel.id}')" title="Delete channel">
                                <i class="bi bi-trash"></i>
                            </button>
                            ${typeof showPlayerOptions === 'function' ? `<button class="btn btn-success btn-sm" onclick="showPlayerOptions('${channel.id}')" title="Play"><i class="bi bi-play-fill"></i></button>` : ''}
                        </div>
                    </td>
                </tr>
            `;
            }).join('');
        }
        
        const displayedChannels = document.getElementById('displayedChannels');
        if (displayedChannels) {
            displayedChannels.textContent = channels.length;
        }
    } catch (error) {
        console.error('Error refreshing channels list:', error);
    }
}

// Search channels by name with optional URL filter
async function searchChannels(searchTerm, urlId = '') {
    try {
        showLoading();
        
        const params = new URLSearchParams();
        if (searchTerm) {
            params.append('search', searchTerm);
        }
        if (urlId) {
            params.append('url_id', urlId);
        }
        
        if (!urlId) {
            const urlFilter = document.getElementById('urlFilter');
            if (urlFilter && urlFilter.value) {
                params.append('url_id', urlFilter.value);
            }
        }
        
        const queryString = params.toString() ? `?${params.toString()}` : '';
        const response = await fetch(`/api/channels/${queryString}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to search channels');
        }
        
        return data;
    } catch (error) {
        console.error('Error searching channels:', error);
        showAlert('error', 'Error searching channels');
        return [];
    } finally {
        hideLoading();
    }
}

// Check status of a specific channel
async function checkChannelStatus(channelId) {
    try {
        showLoading();
        const response = await fetch(`/api/channels/${encodeURIComponent(channelId)}/check-status`, {
            method: 'POST'
        });
        
        await handleApiResponse(response);
    } catch (error) {
        console.error('Error:', error);
        alert('Network error while checking channel status');
    } finally {
        hideLoading();
    }
}

// Edit a channel - load data and show modal
async function editChannel(channelId) {
    try {
        showLoading();
        const response = await fetch(`/api/channels/${channelId}`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch channel data');
        }
        
        const channel = await response.json();
        const statusField = document.getElementById('editChannelStatus');
        const statusLabel = document.getElementById('statusLabelText');
        if (statusField && statusLabel) {
            const isActive = (channel.status === 'active');
            statusField.checked = isActive;
            statusLabel.textContent = isActive ? 'Active' : 'Disabled';
            statusLabel.className = isActive ? 'fw-bold text-success' : 'fw-bold text-danger';
        }
        
        document.getElementById('editChannelId').value = channel.id;
        document.getElementById('editChannelName').value = channel.name || '';
        document.getElementById('editChannelGroup').value = channel.group || '';
        document.getElementById('editChannelLogo').value = channel.logo || '';
        document.getElementById('editChannelTvgId').value = channel.tvg_id || '';
        document.getElementById('editChannelTvgName').value = channel.tvg_name || '';
        document.getElementById('editChannelOriginalUrl').value = channel.original_url || '';
        document.getElementById('editChannelM3uSource').value = channel.source_url || '';
        const epgLockedField = document.getElementById('editChannelEpgLocked');
        if (epgLockedField) {
            epgLockedField.checked = Boolean(channel.epg_update_protected || false);
        }
        
        const editModal = new bootstrap.Modal(document.getElementById('editChannelModal'));
        editModal.show();
        
    } catch (error) {
        console.error('Error loading channel data:', error);
        showAlert('danger', 'Failed to load channel data');
    } finally {
        hideLoading();
    }
}

// Save changes to an edited channel
async function saveChannelChanges() {
    try {
        showLoading();
        
        const channelId = document.getElementById('editChannelId').value;
        const channelName = document.getElementById('editChannelName').value;
        const channelGroup = document.getElementById('editChannelGroup').value;
        const channelLogo = document.getElementById('editChannelLogo').value;
        const channelTvgId = document.getElementById('editChannelTvgId').value;
        const channelTvgName = document.getElementById('editChannelTvgName').value;
        const channelOriginalUrl = document.getElementById('editChannelOriginalUrl').value;
        const channelM3uSource = document.getElementById('editChannelM3uSource').value;
        const epgLocked = document.getElementById('editChannelEpgLocked').checked;
        const isEnabled = document.getElementById('editChannelStatus').checked;
        
        const channelData = {
            name: channelName,
            group: channelGroup,
            epg_update_protected: epgLocked,
            status: isEnabled ? 'active' : 'disabled'
        };
        
        if (channelLogo) channelData.logo = channelLogo;
        if (channelTvgId) channelData.tvg_id = channelTvgId;
        if (channelTvgName) channelData.tvg_name = channelTvgName;
        if (channelOriginalUrl) channelData.original_url = channelOriginalUrl;
        if (channelM3uSource) channelData.m3u_source = channelM3uSource;
        
        const response = await fetch(`/api/channels/${channelId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(channelData)
        });
        
        if (response.ok) {
            const editModal = bootstrap.Modal.getInstance(document.getElementById('editChannelModal'));
            editModal.hide();
            
            showAlert('success', 'Channel updated successfully');
            
            if (typeof refreshChannelList === 'function') {
                await refreshChannelList();
            }
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to update channel');
        }
    } catch (error) {
        console.error('Error updating channel:', error);
        showAlert('danger', error.message || 'Error updating channel');
    } finally {
        hideLoading();
    }
}