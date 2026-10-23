/**
 * TV Channels Management JavaScript
 * Handles interactions for the TV channels management page
 */

// Page state (Protegido contra redeclaración)
if (typeof window.tvChannelsState === 'undefined') {
    window.tvChannelsState = {
        channels: [],
        filters: {
            categories: [],
            countries: [],
            languages: []
        },
        page: 1,
        perPage: 20,
        totalPages: 1,
        isLoading: false,
        selectedChannels: new Set(),
        favoritesOnly: false
    };
}
const tvChannelsState = window.tvChannelsState;

// Document ready handler
document.addEventListener('DOMContentLoaded', function() {
    console.log('TV Channels page initialized');
    
    // Initialize playlist functionality (disponible para todos)
    initializePlaylistFunctions();
    updatePlaylistUrl();
    
    // Si existe la tabla de canales o controles de admin, inicializar el resto de funciones
    if (document.getElementById('tvChannelsTableBody')) {
        loadInitialData();
        setupEventListeners();
        initBulkEditHandlers();
        initializeBulkActions();
        
        // Initialize the global favorites checkbox state on page load
        const favoritesFilter = document.getElementById('favoritesOnlyFilter');
        if (favoritesFilter && favoritesFilter.checked) {
          document.getElementById('globalFavoritesOnly').checked = true;
        }
    }
});

/**
 * Load initial data for the page
 */
async function loadInitialData() {
    showLoading();
    try {
        // Load TV channels with filters and pagination
        await loadTVChannels();
        
        // Update the stats cards
        updateStatCards();
    } catch (error) {
        console.error('Error initializing page:', error);
        showAlert('error', 'Failed to load TV channels data');
    } finally {
        hideLoading();
    }
}

/**
 * Set up event listeners for the page elements
 */
function setupEventListeners() {
    // Add TV Channel button
    const addTVChannelBtn = document.getElementById('addTVChannelBtn');
    if (addTVChannelBtn) {
        addTVChannelBtn.addEventListener('click', showAddTVChannelModal);
    }
    
    // Save new TV channel button
    const saveTVChannelBtn = document.getElementById('saveTVChannelBtn');
    if (saveTVChannelBtn) {
        saveTVChannelBtn.addEventListener('click', saveNewTVChannel);
    }
    
    // Search input
    const searchInput = document.getElementById('tvChannelSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            tvChannelsState.page = 1; // Reset to first page
            loadTVChannels();
        }, 300));
    }
    
    // Filter dropdowns
    const filters = ['category', 'country', 'language'];
    filters.forEach(filter => {
        const element = document.getElementById(`${filter}Filter`);
        if (element) {
            element.addEventListener('change', function() {
                tvChannelsState.page = 1; // Reset to first page
                loadTVChannels();
            });
        }
    });
    
    // Favorites filter
    const favoritesFilter = document.getElementById('favoritesOnlyFilter');
    if (favoritesFilter) {
        favoritesFilter.addEventListener('change', function() {
            tvChannelsState.favoritesOnly = this.checked;
            tvChannelsState.page = 1; // Reset to first page
            loadTVChannels();
        });
    }
    
    // Per page dropdown
    const perPageSelect = document.getElementById('channelsPerPage');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', function() {
            tvChannelsState.perPage = parseInt(this.value);
            tvChannelsState.page = 1; // Reset to first page
            loadTVChannels();
        });
    }
    
    // Batch actions
    document.getElementById('associateByEPGBtn')?.addEventListener('click', associateByEPG);
    document.getElementById('bulkUpdateEPGBtn')?.addEventListener('click', bulkUpdateEPG);
    document.getElementById('generateTVChannelsBtn')?.addEventListener('click', generateTVChannelsFromAcestreams);

    // Add listener for batch assign save button
    document.getElementById('saveBatchAssignBtn')?.addEventListener('click', processBatchAssignment);
    
    // Add listener for add pattern row button
    document.getElementById('addPatternRowBtn')?.addEventListener('click', addAssignmentPatternRow);
}

/**
 * Show the modal for adding a new TV channel
 */
function showAddTVChannelModal() {
    const form = document.getElementById('addTVChannelForm');
    if (form) {
        form.reset();
    }
    
    const selectedAcestreamsContainer = document.getElementById('selectedAcestreams');
    if (selectedAcestreamsContainer) {
        selectedAcestreamsContainer.innerHTML = '';
    }
    
    const modalEl = document.getElementById('addTVChannelModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
        loadUnassignedAcestreams();
    }
}

/**
 * Save a new TV channel
 */
function saveNewTVChannel() {
    const form = document.getElementById('addTVChannelForm');
    if (!form) return;
      
    const formData = {
        name: form.querySelector('[name="name"]').value.trim(),
        description: form.querySelector('[name="description"]').value.trim() || null,
        logo_url: form.querySelector('[name="logo_url"]').value.trim() || null,
        category: form.querySelector('[name="category"]').value.trim() || null,
        country: form.querySelector('[name="country"]').value.trim() || null,
        language: form.querySelector('[name="language"]').value.trim() || null,
        website: form.querySelector('[name="website"]').value.trim() || null,
        epg_id: form.querySelector('[name="epg_id"]').value.trim() || null,
        epg_source_id: form.querySelector('[name="epg_source_id"]').value ? parseInt(form.querySelector('[name="epg_source_id"]').value) : null,
        channel_number: form.querySelector('[name="channel_number"]').value ? parseInt(form.querySelector('[name="channel_number"]').value) : null,
        is_active: form.querySelector('[name="is_active"]').checked,
        is_favorite: form.querySelector('[name="is_favorite"]').checked,
        selected_acestreams: []
    };
    
    if (!formData.name) {
        showAlert('error', 'Channel name is required');
        return;
    }
    
    const selectedContainer = document.getElementById('selectedAcestreams');
    if (selectedContainer) {
        const acestreams = selectedContainer.querySelectorAll('.selected-acestream');
        acestreams.forEach(item => {
            const id = item.getAttribute('data-acestream-id');
            if (id) {
                formData.selected_acestreams.push(id);
            }
        });
    }
    
    showLoading();
    
    fetch('/api/tv-channels/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || 'Failed to create TV channel');
            });
        }
        return response.json();
    })
    .then(data => {
        showAlert('success', 'TV channel created successfully');
        const modalEl = document.getElementById('addTVChannelModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
        loadTVChannels();
    })
    .catch(error => {
        console.error('Error creating TV channel:', error);
        showAlert('error', error.message || 'Failed to create TV channel');
    })
    .finally(() => {
        hideLoading();
    });
}

/**
 * Load unassigned acestreams for selection in the add channel modal
 */
function loadUnassignedAcestreams(searchTerm = '') {
    const container = document.getElementById('unassignedAcestreamsContainer');
    if (!container) return;
    
    container.innerHTML = `
        <div class="text-center p-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading acestreams...</span>
            </div>
            <span class="ms-2">Loading unassigned acestreams...</span>
        </div>
    `;
    
    let url = '/api/tv-channels/unassigned-acestreams';
    if (searchTerm) {
        url += `?search=${encodeURIComponent(searchTerm)}`;
    }
    
    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error('Failed to load unassigned acestreams');
            return response.json();
        })
        .then(data => {
            if (!data.acestreams || data.acestreams.length === 0) {
                container.innerHTML = `<div class="alert alert-info">No unassigned acestreams found</div>`;
                return;
            }
            
            let html = `
                <div class="mb-3">
                    <input type="text" class="form-control form-control-sm" id="acestreamsSearchInput" placeholder="Search acestreams...">
                </div>
                <div class="list-group acestreams-list" style="max-height: 300px; overflow-y: auto;">
            `;
            
            data.acestreams.forEach(acestream => {
                html += `
                    <div class="list-group-item list-group-item-action">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                ${acestream.name || 'Unnamed Stream'}
                                <small class="d-block text-muted">${acestream.id}</small>
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary select-acestream-btn"
                                    data-acestream-id="${acestream.id}" 
                                    data-acestream-name="${acestream.name || 'Unnamed Stream'}">
                                Select
                            </button>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
            
            const searchInput = document.getElementById('acestreamsSearchInput');
            if (searchInput) {
                searchInput.addEventListener('input', debounce(function() {
                    loadUnassignedAcestreams(this.value);
                }, 300));
            }
            
            document.querySelectorAll('.select-acestream-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const id = this.getAttribute('data-acestream-id');
                    const name = this.getAttribute('data-acestream-name');
                    addSelectedAcestream(id, name);
                });
            });
        })
        .catch(error => {
            console.error('Error loading unassigned acestreams:', error);
            container.innerHTML = `<div class="alert alert-danger">Failed to load unassigned acestreams: ${error.message}</div>`;
        });
}

function addSelectedAcestream(id, name) {
    const container = document.getElementById('selectedAcestreams');
    if (!container) return;
    
    if (container.querySelector(`.selected-acestream[data-acestream-id="${id}"]`)) return;
    
    const acestream = document.createElement('div');
    acestream.className = 'selected-acestream alert alert-info alert-dismissible fade show';
    acestream.setAttribute('data-acestream-id', id);
    
    acestream.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <strong>${name}</strong>
                <small class="d-block">${id}</small>
            </div>
            <button type="button" class="btn-close" aria-label="Remove"></button>
        </div>
    `;
    
    acestream.querySelector('.btn-close').addEventListener('click', function() {
        acestream.remove();
    });
    
    container.appendChild(acestream);
}

/**
 * Initialize playlist functionality for TV channels
 */
function initializePlaylistFunctions() {
    const downloadPlaylistBtn = document.getElementById('downloadPlaylistBtn');
    if (downloadPlaylistBtn) {
        downloadPlaylistBtn.addEventListener('click', function() {
            downloadTVChannelsPlaylist(false);
        });
    }
    
    const copyPlaylistUrlBtn = document.getElementById('copyPlaylistUrlBtn');
    if (copyPlaylistUrlBtn) {
        copyPlaylistUrlBtn.addEventListener('click', function() {
            copyToClipboard('#tvChannelsPlaylistUrl');
        });
    }
    
    const playlistFavoritesCheckbox = document.getElementById('playlistFavoritesOnly');
    if (playlistFavoritesCheckbox) {
        playlistFavoritesCheckbox.addEventListener('change', updatePlaylistUrl);
    }
    
    const epgFavoritesCheckbox = document.getElementById('epgFavoritesOnly');
    if (epgFavoritesCheckbox) {
        epgFavoritesCheckbox.addEventListener('change', updateEpgXmlUrl);
    }
}

function updatePlaylistUrl() {
    const urlInput = document.getElementById('tvChannelsPlaylistUrl');
    if (!urlInput) return;
    
    const baseUrl = urlInput.getAttribute('data-base-url');
    if (!baseUrl) return;
    
    const favoritesOnly = document.getElementById('playlistFavoritesOnly')?.checked || false;
    let url = baseUrl;
    if (favoritesOnly) {
        url += (url.includes('?') ? '&' : '?') + 'favorites_only=true';
    }
    urlInput.value = url;
}

function updateEpgXmlUrl() {
    const urlInput = document.getElementById('epgXmlUrl');
    if (!urlInput) return;
    
    const baseUrl = urlInput.getAttribute('data-base-url');
    if (!baseUrl) return;
    
    const favoritesOnly = document.getElementById('epgFavoritesOnly')?.checked || false;
    let url = baseUrl;
    if (favoritesOnly) {
        url += (url.includes('?') ? '&' : '?') + 'favorites_only=true';
    }
    urlInput.value = url;
}

function downloadEpgXml() {
    const urlInput = document.getElementById('epgXmlUrl');
    if (!urlInput) return;
    window.location.href = urlInput.value;
}

function downloadEpgPlaylist() {
    const urlInput = document.getElementById('epgPlaylistUrl');
    if (urlInput) {
        window.location.href = urlInput.value;
    }
}

function updateEpgPlaylistUrl() {
    const urlInput = document.getElementById('epgPlaylistUrl');
    if (!urlInput) return;
    
    const baseUrl = urlInput.getAttribute('data-base-url');
    if (!baseUrl) return;
    
    const favoritesOnly = document.getElementById('epgPlaylistFavoritesOnly')?.checked || false;
    let url = baseUrl;
    if (favoritesOnly) {
        url += (url.includes('?') ? '&' : '?') + 'favorites_only=true';
    }
    urlInput.value = url;
}

function copyToClipboard(elementSelector) {
    const element = document.querySelector(elementSelector);
    if (!element) return;
    
    element.select();
    element.setSelectionRange(0, 99999);
    document.execCommand('copy');
    window.getSelection().removeAllRanges();
    
    const button = document.querySelector(`button[onclick*="copyToClipboard('${elementSelector}')"]`);
    if (button) {
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        setTimeout(() => {
            button.textContent = originalText;
        }, 1500);
    }
}

function downloadTVChannelsPlaylist(refresh = false) {
    const urlInput = document.getElementById('tvChannelsPlaylistUrl');
    if (!urlInput) return;
    
    let url = urlInput.value;
    if (refresh) {
        url += (url.includes('?') ? '&' : '?') + 'refresh=true';
    }
    window.location.href = url;
}

function downloadAllStreamsPlaylist() {
    const urlInput = document.getElementById('allStreamsPlaylistUrl');
    if (!urlInput) return;
    window.location.href = urlInput.value;
}

function downloadOnlinePlaylist() {
    const urlInput = document.getElementById('onlinePlaylistUrl');
    if (!urlInput) return;
    window.location.href = urlInput.value;
}

function toggleAllFavorites(checked) {
    const favoritesFilter = document.getElementById('favoritesOnlyFilter');
    if (favoritesFilter) favoritesFilter.checked = checked;
    
    const playlistFav = document.getElementById('playlistFavoritesOnly');
    if (playlistFav) {
        playlistFav.checked = checked;
        if (playlistFav.onchange) playlistFav.onchange();
    }
    
    const epgFav = document.getElementById('epgFavoritesOnly');
    if (epgFav) {
        epgFav.checked = checked;
        if (epgFav.onchange) epgFav.onchange();
    }
    
    if (favoritesFilter) {
        const event = new Event('change', { bubbles: true });
        favoritesFilter.dispatchEvent(event);
    }
}

function initBulkEditHandlers() {
    const selectAllCheckbox = document.getElementById('selectAllChannels');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('.channel-select-checkbox');
            
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                const channelId = checkbox.value;
                if (isChecked) {
                    tvChannelsState.selectedChannels.add(channelId);
                } else {
                    tvChannelsState.selectedChannels.delete(channelId);
                }
            });
            updateBulkEditToolbar();
        });
    }
    
    document.getElementById('bulkEditBtn')?.addEventListener('click', openBulkEditModal);
    document.getElementById('clearSelectionBtn')?.addEventListener('click', clearSelection);
    document.getElementById('saveBulkEditBtn')?.addEventListener('click', saveBulkEdit);
    
    document.querySelectorAll('.bulk-field-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const fieldName = this.value;
            const fieldGroup = document.getElementById(`${fieldName}FieldGroup`);
            if (fieldGroup) {
                if (this.checked) fieldGroup.classList.remove('d-none');
                else fieldGroup.classList.add('d-none');
            }
        });
    });
}

function openBulkEditModal() {
    const selectedCount = tvChannelsState.selectedChannels.size;
    if (selectedCount === 0) {
        showAlert('warning', 'No channels selected');
        return;
    }
    
    const modalEl = document.getElementById('bulkEditTVChannelsModal');
    if (!modalEl) return;
    
    const form = document.getElementById('bulkEditTVChannelsForm');
    if (form) form.reset();
    
    document.querySelectorAll('.bulk-field-toggle').forEach(toggle => { toggle.checked = false; });
    document.querySelectorAll('.bulk-field').forEach(group => { group.classList.add('d-none'); });
    
    const selectionCountElement = document.getElementById('bulkEditCount');
    if (selectionCountElement) selectionCountElement.textContent = selectedCount;
    
    const bsModal = new bootstrap.Modal(modalEl);
    bsModal.show();
}

function clearSelection() {
    tvChannelsState.selectedChannels.clear();
    document.querySelectorAll('.channel-select-checkbox').forEach(checkbox => { checkbox.checked = false; });
    const selectAllCheckbox = document.getElementById('selectAllChannels');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    updateBulkEditToolbar();
}

function updateBulkEditToolbar() {
    const toolbar = document.getElementById('bulkEditToolbar');
    if (!toolbar) return;
    
    const selectedCount = tvChannelsState.selectedChannels.size;
    if (selectedCount > 0) {
        toolbar.classList.remove('d-none');
        const countBadge = document.getElementById('selectedChannelsCount');
        if (countBadge) countBadge.textContent = selectedCount;
    } else {
        toolbar.classList.add('d-none');
    }
}

function saveBulkEdit() {
    const selectedIds = Array.from(tvChannelsState.selectedChannels);
    if (selectedIds.length === 0) return;
    
    const changes = {};
    let hasChanges = false;
    
    document.querySelectorAll('.bulk-field-toggle:checked').forEach(toggle => {
        const fieldName = toggle.value;
        let fieldValue;
        
        if (fieldName === 'is_active') {
            fieldValue = document.getElementById('bulkEditIsActive')?.checked;
        } else {
            const inputId = 'bulkEdit' + fieldName.charAt(0).toUpperCase() + fieldName.slice(1);
            const input = document.getElementById(inputId);
            if (input) fieldValue = input.value.trim();
        }
        
        if (fieldValue !== undefined) {
            changes[fieldName] = fieldValue;
            hasChanges = true;
        }
    });
    
    if (!hasChanges) {
        showAlert('warning', 'No changes selected');
        return;
    }
    
    showLoading();
    
    fetch('/api/tv-channels/bulk-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            channel_ids: selectedIds,
            update_data: changes
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Failed to update TV channels');
        return response.json();
    })
    .then(data => {
        showAlert('success', `Successfully updated ${data.updated_count} channels`);
        const modalElement = document.getElementById('bulkEditTVChannelsModal');
        if (modalElement) {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) modal.hide();
        }
        loadTVChannels();
        clearSelection();
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', error.message);
    })
    .finally(() => {
        hideLoading();
    });
}

function initializeBulkActions() {
    const selectAllCheckbox = document.getElementById('selectAllChannels');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            const checkboxes = document.querySelectorAll('.channel-select-checkbox');
            
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                const channelId = parseInt(checkbox.getAttribute('data-channel-id'));
                if (isChecked) tvChannelsState.selectedChannels.add(channelId);
                else tvChannelsState.selectedChannels.delete(channelId);
            });
            updateBulkEditToolbar();
        });
    }
    
    document.getElementById('bulkEditBtn')?.addEventListener('click', openBulkEditModal);
    document.getElementById('bulkDeleteBtn')?.addEventListener('click', confirmBulkDelete);
    document.getElementById('clearSelectionBtn')?.addEventListener('click', clearSelection);
    updateBulkEditToolbar();
}

async function associateByEPG() {
    try {
        showLoading();
        const response = await fetch('/api/tv-channels/associate-by-epg', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to associate acestreams by EPG ID');
        }
        const result = await response.json();
        
        const matched = result.stats?.matched || result.matched || 0;
        const unmatched = result.stats?.unmatched || result.unmatched || 0;
        const created = result.stats?.created || result.created || 0;
        const existingAssociations = result.stats?.existing_associations || result.existing_associations || 0;
        
        let message = 'EPG Association complete: ';
        const parts = [];
        if (created > 0) parts.push(`${created} new TV channels created`);
        if (matched > 0) parts.push(`${matched} acestreams matched`);
        if (existingAssociations > 0) parts.push(`${existingAssociations} existing associations`);
        if (unmatched > 0) parts.push(`${unmatched} unmatched`);
        
        message += parts.length > 0 ? parts.join(', ') : 'No changes made';
        showAlert('success', message);
        loadTVChannels();
    } catch (error) {
        console.error('Error associating by EPG:', error);
        showAlert('error', error.message || 'Failed to associate acestreams by EPG ID');
    } finally {
        hideLoading();
    }
}

async function bulkUpdateEPG() {
    try {
        showLoading();
        const response = await fetch('/api/tv-channels/bulk-update-epg', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to update EPG data');
        }
        
        const result = await response.json();
        const updated = result.stats?.updated || result.updated || 0;
        const skipped = result.stats?.skipped || result.skipped || 0;
        const errors = result.stats?.errors || result.errors || 0;
        
        showAlert('success', `EPG update complete: ${updated} channels updated, ${skipped} skipped, ${errors} errors`);
        loadTVChannels();
    } catch (error) {
        console.error('Error updating EPG data:', error);
        showAlert('error', error.message || 'Failed to update EPG data');
    } finally {
        hideLoading();
    }
}

async function generateTVChannelsFromAcestreams() {
    if (!confirm('This will create new TV channels based on unassigned acestreams. Continue?')) return;
    
    try {
        showLoading();
        const response = await fetch('/api/tv-channels/generate-from-acestreams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to generate TV channels');
        }
        
        const result = await response.json();
        const created = result.stats?.created || result.created || 0;
        const matched = result.stats?.matched || result.matched || 0;
        const skipped = result.stats?.skipped || result.skipped || 0;
        const errors = result.stats?.errors || result.errors || 0;
        
        const message = `TV channels generated: ${created} channels created, ${matched} acestreams matched` +
                       (skipped > 0 ? `, ${skipped} skipped` : '') +
                       (errors > 0 ? `, ${errors} errors` : '');
        showAlert('success', message);
        loadTVChannels();
    } catch (error) {
        console.error('Error generating TV channels:', error);
        showAlert('error', error.message || 'Failed to generate TV channels');
    } finally {
        hideLoading();
    }
}

function confirmBulkDelete() {
    const selectedCount = tvChannelsState.selectedChannels.size;
    if (selectedCount === 0) {
        showAlert('warning', 'No channels selected');
        return;
    }
    
    if (confirm(`Are you sure you want to delete ${selectedCount} selected channels? This action cannot be undone.`)) {
        bulkDeleteChannels();
    }
}

async function bulkDeleteChannels() {
    const selectedIds = Array.from(tvChannelsState.selectedChannels);
    if (selectedIds.length === 0) return;
    
    try {
        showLoading();
        const response = await fetch('/api/tv-channels/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_ids: selectedIds })
        });
        
        if (response.ok) {
            const result = await response.json();
            showAlert('success', result.message || `Successfully deleted ${result.deleted_count} channels`);
            clearSelection();
            await loadTVChannels();
        } else {
            const error = await response.json();
            throw new Error(error.message || `Failed to delete channels`);
        }
    } catch (error) {
        console.error('Error deleting channels:', error);
        showAlert('error', error.message || 'An error occurred during bulk deletion');
    } finally {
        hideLoading();
    }
}

async function loadTVChannels() {
    const tableBody = document.getElementById('tvChannelsTableBody');
    if (!tableBody) return; // Si no existe la tabla (modo usuario estándar), salir sin error.
    
    if (tvChannelsState.isLoading) return;
    tvChannelsState.isLoading = true;
    showLoading();
    
    try {
        const category = document.getElementById('categoryFilter')?.value || '';
        const country = document.getElementById('countryFilter')?.value || '';
        const language = document.getElementById('languageFilter')?.value || '';
        const search = document.getElementById('tvChannelSearchInput')?.value || '';
        const favoritesOnly = document.getElementById('favoritesOnlyFilter')?.checked || false;
        
        const params = new URLSearchParams({
            page: tvChannelsState.page,
            per_page: tvChannelsState.perPage
        });
        
        if (category) params.append('category', category);
        if (country) params.append('country', country);
        if (language) params.append('language', language);
        if (search) params.append('search', search);
        if (favoritesOnly) params.append('favorites_only', 'true');
        
        tvChannelsState.favoritesOnly = favoritesOnly;
        
        const response = await fetch(`/api/tv-channels/?${params.toString()}`);
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.message || 'Failed to load TV channels');
        
        tvChannelsState.channels = data.channels;
        tvChannelsState.totalPages = data.total_pages;
        tvChannelsState.filters.categories = data.filters.categories;
        tvChannelsState.filters.countries = data.filters.countries;
        tvChannelsState.filters.languages = data.filters.languages;
        
        updateTVChannelsTable();
        updateFilterDropdowns();
        updatePagination();
        
    } catch (error) {
        console.error('Error loading TV channels:', error);
        showAlert('error', 'Failed to load TV channels data');
    } finally {
        hideLoading();
        tvChannelsState.isLoading = false;
    }
}

function updateTVChannelsTable() {
    const tableBody = document.getElementById('tvChannelsTableBody');
    if (!tableBody) return;
    
    if (tvChannelsState.channels.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No channels found matching your criteria</td></tr>`;
        return;
    }
    
    tableBody.innerHTML = tvChannelsState.channels.map(channel => {
        let favoriteIcon = channel.is_favorite ? '<i class="bi bi-star-fill text-warning me-2" title="Favorite"></i>' : '';
        
        return `
            <tr>
                <td>
                    <div class="form-check">
                        <input class="form-check-input channel-select-checkbox" type="checkbox" value="${channel.id}" data-channel-id="${channel.id}" ${tvChannelsState.selectedChannels.has(channel.id.toString()) ? 'checked' : ''}>
                    </div>
                </td>
                <td>
                    <div class="input-group input-group-sm">
                        <input type="number" class="form-control form-control-sm channel-number-input" value="${channel.channel_number || ''}" min="1" data-channel-id="${channel.id}" placeholder="#" aria-label="Channel number">
                        <button class="btn btn-outline-secondary save-channel-number-btn" type="button" data-channel-id="${channel.id}" title="Save channel number"><i class="bi bi-check"></i></button>
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        ${favoriteIcon}
                        <div><a href="/tv-channels/${channel.id}" class="text-decoration-none">${channel.name}</a></div>
                    </div>
                </td>
                <td>${channel.category || '-'}</td>
                <td>
                    ${channel.country ? `<div>${channel.country}</div>` : ''}
                    ${channel.language ? `<small class="text-muted">${channel.language}</small>` : ''}
                </td>
                <td><span class="badge bg-primary">${channel.acestream_channels_count}</span></td>
                <td>${channel.epg_id || '-'}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary toggle-favorite-btn" onclick="toggleChannelFavorite(${channel.id})" title="${channel.is_favorite ? 'Remove from favorites' : 'Add to favorites'}">
                            <i class="bi ${channel.is_favorite ? 'bi-star-fill' : 'bi-star'}"></i>
                        </button>
                        <a href="/tv-channels/${channel.id}" class="btn btn-primary" title="View details"><i class="bi bi-eye"></i></a>
                        <button class="btn btn-danger" onclick="deleteChannel(${channel.id})" title="Delete channel"><i class="bi bi-trash"></i></button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    document.querySelectorAll('.save-channel-number-btn').forEach(button => {
        button.addEventListener('click', function() {
            const channelId = parseInt(this.getAttribute('data-channel-id'));
            const input = document.querySelector(`.channel-number-input[data-channel-id="${channelId}"]`);
            if (input) {
                const value = parseInt(input.value);
                if (!isNaN(value) && value > 0) setChannelNumber(channelId, value);
                else if (input.value === '') setChannelNumber(channelId, null);
            }
        });
    });
    
    document.querySelectorAll('.channel-number-input').forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const channelId = parseInt(this.getAttribute('data-channel-id'));
                const value = parseInt(this.value);
                if (!isNaN(value) && value > 0) setChannelNumber(channelId, value);
                else if (this.value === '') setChannelNumber(channelId, null);
            }
        });
    });
    
    document.querySelectorAll('.channel-select-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const channelId = this.value;
            if (this.checked) tvChannelsState.selectedChannels.add(channelId);
            else tvChannelsState.selectedChannels.delete(channelId);
            updateBulkEditToolbar();
        });
    });
}

async function setChannelNumber(channelId, channelNumber) {
    try {
        showLoading();
        const response = await fetch(`/api/tv-channels/${channelId}/channel-number`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_number: channelNumber })
        });
        
        if (response.ok) {
            const channelIndex = tvChannelsState.channels.findIndex(c => c.id === channelId);
            if (channelIndex >= 0) {
                tvChannelsState.channels[channelIndex].channel_number = channelNumber;
                showAlert('success', `Channel number updated`);
            }
        } else {
            const error = await response.json();
            throw new Error(error.message || 'Failed to update channel number');
        }
    } catch (error) {
        console.error('Error setting channel number:', error);
        showAlert('error', error.message || 'Error updating channel number');
    } finally {
        hideLoading();
    }
}

function updateFilterDropdowns() {
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        const currentValue = categoryFilter.value;
        while (categoryFilter.options.length > 1) categoryFilter.remove(1);
        if (tvChannelsState.filters.categories) {
            tvChannelsState.filters.categories.forEach(category => {
                if (category) {
                    const option = document.createElement('option');
                    option.value = category;
                    option.textContent = category;
                    categoryFilter.appendChild(option);
                }
            });
        }
        if (currentValue) categoryFilter.value = currentValue;
    }
    
    const countryFilter = document.getElementById('countryFilter');
    if (countryFilter) {
        const currentValue = countryFilter.value;
        while (countryFilter.options.length > 1) countryFilter.remove(1);
        if (tvChannelsState.filters.countries) {
            tvChannelsState.filters.countries.forEach(country => {
                if (country) {
                    const option = document.createElement('option');
                    option.value = country;
                    option.textContent = country;
                    countryFilter.appendChild(option);
                }
            });
        }
        if (currentValue) countryFilter.value = currentValue;
    }
    
    const languageFilter = document.getElementById('languageFilter');
    if (languageFilter) {
        const currentValue = languageFilter.value;
        while (languageFilter.options.length > 1) languageFilter.remove(1);
        if (tvChannelsState.filters.languages) {
            tvChannelsState.filters.languages.forEach(language => {
                if (language) {
                    const option = document.createElement('option');
                    option.value = language;
                    option.textContent = language;
                    languageFilter.appendChild(option);
                }
            });
        }
        if (currentValue) languageFilter.value = currentValue;
    }
}

function updateStatCards() {
    if (!document.getElementById('totalTVChannelsCard')) return;
    
    const params = new URLSearchParams({ page: 1, per_page: 1 });
    fetch(`/api/tv-channels/?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            const totalChannelsCard = document.getElementById('totalTVChannelsCard');
            if (totalChannelsCard) totalChannelsCard.textContent = data.total || 0;
            
            fetch('/api/tv-channels/?is_active=true&per_page=1')
                .then(response => response.json())
                .then(activeData => {
                    const activeChannelsCard = document.getElementById('activeChannelsCard');
                    if (activeChannelsCard) activeChannelsCard.textContent = activeData.total || 0;
                }).catch(() => {});
            
            let withEpgCount = 0;
            if (data.channels && Array.isArray(data.channels)) {
                withEpgCount = data.channels.filter(channel => channel.epg_id).length;
            }
            const withEpgCard = document.getElementById('channelsWithEPGCard');
            if (withEpgCard) withEpgCard.textContent = withEpgCount || '0';
            
            const totalAcestreamsCard = document.getElementById('totalAcestreamsCard');
            if (totalAcestreamsCard) {
                fetch('/api/tv-channels/unassigned-acestreams')
                    .then(response => response.json())
                    .then(unassignedData => {
                        const totalEstimate = (unassignedData.total || 0) + ((data.total || 0) * 2);
                        totalAcestreamsCard.textContent = totalEstimate;
                    }).catch(() => { totalAcestreamsCard.textContent = 'N/A'; });
            }
        }).catch(() => {});
}

function updatePagination() {
    const pagination = document.getElementById('tvChannelsPagination');
    if (!pagination) return;
    
    if (tvChannelsState.totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let pagination_html = '';
    pagination_html += `
        <li class="page-item ${tvChannelsState.page === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${tvChannelsState.page - 1}" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>
        </li>
    `;
    
    const max_pages = Math.min(5, tvChannelsState.totalPages);
    let start_page = Math.max(1, tvChannelsState.page - 2);
    let end_page = Math.min(start_page + max_pages - 1, tvChannelsState.totalPages);
    
    if (end_page - start_page + 1 < max_pages) {
        start_page = Math.max(1, end_page - max_pages + 1);
    }
    
    for (let i = start_page; i <= end_page; i++) {
        pagination_html += `
            <li class="page-item ${i === tvChannelsState.page ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>
        `;
    }
    
    pagination_html += `
        <li class="page-item ${tvChannelsState.page === tvChannelsState.totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${tvChannelsState.page + 1}" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>
        </li>
    `;
    
    pagination.innerHTML = pagination_html;
    
    pagination.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.getAttribute('data-page'));
            if (page && page !== tvChannelsState.page) {
                tvChannelsState.page = page;
                loadTVChannels();
            }
        });
    });
}

function deleteChannel(channelId) {
    if (!confirm('Are you sure you want to delete this TV channel?')) return;
    
    showLoading();
    fetch(`/api/tv-channels/${channelId}`, { method: 'DELETE' })
    .then(response => {
        if (!response.ok) throw new Error('Failed to delete TV channel');
        return response.json();
    })
    .then(() => {
        showAlert('success', 'TV channel deleted successfully');
        loadTVChannels();
    })
    .catch(error => {
        console.error('Error deleting TV channel:', error);
        showAlert('error', error.message || 'Error deleting TV channel');
    })
    .finally(() => { hideLoading(); });
}

function toggleChannelFavorite(channelId) {
    showLoading();
    fetch(`/api/tv-channels/${channelId}/favorite`, { method: 'PUT', headers: { 'Content-Type': 'application/json' } })
    .then(response => {
        if (!response.ok) throw new Error('Failed to toggle favorite status');
        return response.json();
    })
    .then(result => {
        const channelIndex = tvChannelsState.channels.findIndex(c => c.id === channelId);
        if (channelIndex >= 0) {
            tvChannelsState.channels[channelIndex].is_favorite = result.is_favorite;
            const row = document.querySelector(`tr .channel-select-checkbox[data-channel-id="${channelId}"]`)?.closest('tr');
            if (row) {
                const favoriteBtn = row.querySelector('.toggle-favorite-btn');
                const favoriteIcon = favoriteBtn?.querySelector('i');
                if (favoriteIcon) {
                    if (result.is_favorite) {
                        favoriteIcon.className = 'bi bi-star-fill';
                        favoriteBtn.setAttribute('title', 'Remove from favorites');
                        let nameCell = row.cells[2];
                        let nameContent = nameCell.querySelector('div');
                        if (nameContent && !nameContent.querySelector('.bi-star-fill')) {
                            const favoriteIndicator = document.createElement('i');
                            favoriteIndicator.className = 'bi bi-star-fill text-warning me-2';
                            nameContent.insertBefore(favoriteIndicator, nameContent.firstChild);
                        }
                    } else {
                        favoriteIcon.className = 'bi bi-star';
                        favoriteBtn.setAttribute('title', 'Add to favorites');
                        let nameCell = row.cells[2];
                        let favoriteIndicator = nameCell.querySelector('.bi-star-fill');
                        if (favoriteIndicator) favoriteIndicator.remove();
                    }
                }
            }
            if (tvChannelsState.favoritesOnly && !result.is_favorite) loadTVChannels();
        }
        showAlert('success', result.message);
    })
    .catch(error => {
        console.error('Error toggling favorite status:', error);
        showAlert('error', error.message || 'Error toggling favorite status');
    })
    .finally(() => { hideLoading(); });
}

document.addEventListener('change', function(e) {
    if (e.target.classList.contains('bulk-field-toggle')) {
        const fieldName = e.target.value;
        const fieldGroup = document.getElementById(fieldName + 'FieldGroup');
        if (fieldGroup) {
            if (e.target.checked) fieldGroup.classList.remove('d-none');
            else fieldGroup.classList.add('d-none');
        }
    }
});