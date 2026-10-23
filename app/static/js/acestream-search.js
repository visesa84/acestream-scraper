/**
 * Acestream search functionality for Acestream Scraper
 */

const searchState = {
    currentPage: 1,
    pageSize: 20,
    totalPages: 0,
    query: '',
    results: [],
    isLoading: false
};

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    if (!searchForm) return;

    searchForm.addEventListener('submit', handleSearch);
});

async function handleSearch(e) {
    e.preventDefault();
    const searchQueryInput = document.getElementById('searchQueryInput');
    if (!searchQueryInput) return;

    const query = searchQueryInput.value.trim();
    searchState.query = query;
    searchState.currentPage = 1;

    await performSearch();
}

async function performSearch() {
    const container = document.getElementById('searchResultsContainer');
    const countBadge = document.getElementById('searchResultsCount');
    if (!container) return;

    // Mostrar estado de carga
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="text-muted mt-2 mb-0">Searching streams...</p>
        </div>
    `;

    try {
        const searchUrl = `/api/search?query=${encodeURIComponent(searchState.query)}&page=${searchState.currentPage}&page_size=${searchState.pageSize}`;
        const response = await fetch(searchUrl);
        const data = await response.json();

        if (data.success) {
            searchState.results = data.results || [];
            if (countBadge) {
                countBadge.textContent = `${searchState.results.length} results`;
            }
            displayResults();
        } else {
            container.innerHTML = `<div class="alert alert-danger m-3">${data.message || 'Search failed'}</div>`;
            if (countBadge) countBadge.textContent = '0 results';
        }
    } catch (error) {
        console.error('Error performing search:', error);
        container.innerHTML = `<div class="alert alert-danger m-3">Error connecting to search service</div>`;
        if (countBadge) countBadge.textContent = '0 results';
    }
}

function displayResults() {
    const container = document.getElementById('searchResultsContainer');
    if (!container) return;

    if (searchState.results.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-compass display-4 text-secondary mb-3 d-block"></i>
                No streams found matching your search.
            </div>
        `;
        return;
    }

    let html = `
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead>
                    <tr>
                        <th>Channel Name</th>
                        <th>Stream ID / Hash</th>
                        <th>Categories</th>
                        <th>Bitrate</th>
                        <th class="text-end">Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;

    searchState.results.forEach(result => {
        const categories = result.categories && result.categories.length > 0 ? result.categories.join(', ') : '-';
        const bitrate = result.bitrate ? `${Math.round(result.bitrate / 1000)} Kbps` : '-';

        html += `
            <tr>
                <td class="fw-semibold">${result.name || 'Unnamed Channel'}</td>
                <td><code>${result.id}</code></td>
                <td>${categories}</td>
                <td>${bitrate}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-primary add-channel-btn rounded-pill px-3" data-id="${result.id}" data-name="${result.name}">
                        <i class="bi bi-plus-lg me-1"></i> Add
                    </button>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;

    // Vincular eventos a los botones de añadir
    container.querySelectorAll('.add-channel-btn').forEach(button => {
        button.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            const name = this.getAttribute('data-name');
            addChannel(id, name, this);
        });
    });
}

async function addChannel(id, name, buttonElement) {
    try {
        const response = await fetch('/api/search/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, name: name })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('success', `Channel "${name}" added successfully`);
            if (buttonElement) {
                buttonElement.disabled = true;
                buttonElement.classList.remove('btn-primary');
                buttonElement.classList.add('btn-success');
                buttonElement.innerHTML = '<i class="bi bi-check-lg me-1"></i> Added';
            }
        } else {
            showAlert('warning', data.message || 'Failed to add channel');
        }
    } catch (error) {
        console.error('Error adding channel:', error);
        showAlert('danger', 'Error adding channel');
    }
}