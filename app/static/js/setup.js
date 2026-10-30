/**
 * Setup wizard functionality for Acestream Scraper
 */

const setupState = {
    currentStep: 1,
    totalSteps: 6,
    adminUser: { username: '', password: '' },
    streamMode: 'traditional',
    rescrapeInterval: 24,
    checkstatus_enabled: true,
    checkstatus_interval: 24,
    sources: []
};

function showLoading() {
    const loading = document.getElementById('loading');
    if (loading) loading.style.display = 'flex';
}

function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) loading.style.display = 'none';
}

function goToStep(stepNumber) {
    const steps = document.querySelectorAll('.step');
    steps.forEach(step => step.classList.remove('active'));
    
    const targetStep = document.getElementById(`step-${stepNumber}`);
    if (targetStep) {
        targetStep.classList.add('active');
    }
    
    const indicators = document.querySelectorAll('.step-dot');
    indicators.forEach(dot => {
        const dotStep = parseInt(dot.dataset.step);
        dot.classList.remove('active', 'completed');
        if (dotStep === stepNumber) {
            dot.classList.add('active');
        } else if (dotStep < stepNumber) {
            dot.classList.add('completed');
        }
    });
    setupState.currentStep = stepNumber;
}

function nextStep() {
    if (setupState.currentStep < setupState.totalSteps) {
        goToStep(setupState.currentStep + 1);
    }
}

function prevStep() {
    if (setupState.currentStep > 1) {
        goToStep(setupState.currentStep - 1);
    }
}

function addSource(url, urlType = 'regular') {
    if (!url || !url.trim()) return false;
    url = url.trim();
    if (setupState.sources.some(source => source.url === url)) return false;
    
    setupState.sources.push({ url: url, url_type: urlType });
    updateSourcesList();
    return true;
}

function removeSource(url) {
    const index = setupState.sources.findIndex(source => source.url === url);
    if (index !== -1) {
        setupState.sources.splice(index, 1);
        updateSourcesList();
    }
}

function updateSourcesList() {
    const sourcesList = document.getElementById('sourcesList');
    const noSourcesMessage = document.getElementById('noSourcesMessage');
    
    if (!sourcesList) return;

    if (setupState.sources.length === 0) {
        if (noSourcesMessage) {
            noSourcesMessage.style.display = 'block';
            sourcesList.innerHTML = '';
            sourcesList.appendChild(noSourcesMessage);
        }
    } else {
        if (noSourcesMessage) noSourcesMessage.style.display = 'none';
        document.querySelectorAll('#sourcesList .source-item').forEach(item => item.remove());
        
        setupState.sources.forEach(source => {
            const item = document.createElement('div');
            item.className = 'list-group-item source-item d-flex justify-content-between align-items-center';
            const isIpfsSource = /^(ipfs|ipns):\/\//i.test(source.url) ||
                /^https?:\/\/[^/?#]+\.(ipfs|ipns)\./i.test(source.url) ||
                /^https?:\/\/[^/?#]+\/(ipfs|ipns)\//i.test(source.url);
            const sourceTypeLabel = isIpfsSource
                ? 'IPFS / IPNS'
                : source.url_type === 'zeronet' ? 'ZeroNet' : 'HTTP';
            item.innerHTML = `
                <span class="text-break">${source.url}</span>
                <span class="badge bg-info me-2">${sourceTypeLabel}</span>
                <button class="btn btn-sm btn-outline-danger remove-source-btn" data-url="${source.url}">
                    <i class="bi bi-trash"></i>
                </button>
            `;
            sourcesList.appendChild(item);
            const removeBtn = item.querySelector('.remove-source-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', function() {
                    removeSource(this.dataset.url);
                });
            }
        });
    }
}

async function saveConfiguration() {
    showLoading();
    try {
        if (setupState.adminUser.username && setupState.adminUser.password) {
            const userResponse = await fetch('/api/users/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username: setupState.adminUser.username,
                    password: setupState.adminUser.password,
					is_admin: true
                })
            });

            if (!userResponse.ok) {
                throw new Error('Failed to create admin user account');
            }
        }

        await fetch('/api/config/stream_mode', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stream_mode: setupState.streamMode })
        });
        
        await fetch('/api/config/rescrape_interval', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hours: setupState.rescrapeInterval })
        });
        
        await fetch('/api/config/checkstatus_interval', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hours: setupState.checkstatus_interval, enabled: setupState.checkstatus_enabled })
        });
        
        const setupResponse = await fetch('/api/config/setup_completed', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ completed: true })
        });

        if (!setupResponse.ok) throw new Error('Failed to mark setup as completed');
        
        for (const source of setupState.sources) {
            await fetch('/api/urls/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: source.url, url_type: source.url_type })
            });
        }
        return true;
    } catch (error) {
        console.error('Error saving configuration:', error);
        alert('There was an error saving your configuration. Please try again.');
        return false;
    } finally {
        hideLoading();
    }
}

async function finishSetup() {
    try {
        showLoading();
        const success = await saveConfiguration();
        if (success) window.location.href = '/';
    } catch (error) {
        console.error('Error finishing setup:', error);
        alert('There was an error completing the setup.');
    } finally {
        hideLoading();
    }
}

document.addEventListener('DOMContentLoaded', function() {    
    document.querySelectorAll('.step-dot').forEach(dot => {
        dot.addEventListener('click', () => {
            const stepNumber = parseInt(dot.dataset.step);
            if (stepNumber <= setupState.currentStep) goToStep(stepNumber);
        });
    });

    // Paso 2: Gestión de cuenta de administrador
    const adminAccountForm = document.getElementById('adminAccountForm');
    if (adminAccountForm) {
        adminAccountForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const usernameInput = document.getElementById('adminUsername');
            const passwordInput = document.getElementById('adminPassword');
            const passwordConfirmInput = document.getElementById('adminPasswordConfirm');

            const username = usernameInput ? usernameInput.value.trim() : '';
            const password = passwordInput ? passwordInput.value : '';
            const passwordConfirm = passwordConfirmInput ? passwordConfirmInput.value : '';

            if (!username || !password) {
                alert('Please enter username and password.');
                return;
            }

            if (password !== passwordConfirm) {
                alert('Passwords do not match.');
                return;
            }

            setupState.adminUser.username = username;
            setupState.adminUser.password = password;
            nextStep(); // Avanza correctamente al paso 3
        });
    }
    
    // Paso 3: Modo de streaming
    const streamModeForm = document.getElementById('streamModeForm');
    if (streamModeForm) {
        streamModeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const streamModeSelect = document.getElementById('streamModeSelect');
            if (streamModeSelect) {
                setupState.streamMode = streamModeSelect.value;
            }
            nextStep();
        });
    }
    
    // Paso 4: Fuentes de scraping
    const addSourceBtn = document.getElementById('addSourceBtn');
    if (addSourceBtn) {
        addSourceBtn.addEventListener('click', function() {
            const sourceUrlInput = document.getElementById('sourceUrl');
            const sourceUrlTypeSelect = document.getElementById('sourceUrlType');
            
            const sourceUrl = sourceUrlInput ? sourceUrlInput.value : '';
            const sourceUrlType = sourceUrlTypeSelect ? sourceUrlTypeSelect.value : 'regular';
            
            if (addSource(sourceUrl, sourceUrlType)) {
                if (sourceUrlInput) sourceUrlInput.value = '';
            } else {
                alert('Please enter a valid URL.');
            }
        });
    }
    
    const scrapingSourcesForm = document.getElementById('scrapingSourcesForm');
    if (scrapingSourcesForm) {
        scrapingSourcesForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const sourceUrlInput = document.getElementById('sourceUrl');
            const sourceUrl = sourceUrlInput ? sourceUrlInput.value : '';
            if (sourceUrl) addSource(sourceUrl);
            
            if (setupState.sources.length === 0) {
                alert('Please add at least one source URL.');
                return;
            }
            const rescrapeIntervalInput = document.getElementById('rescrapeInterval');
            setupState.rescrapeInterval = rescrapeIntervalInput ? (parseInt(rescrapeIntervalInput.value) || 24) : 24;
            nextStep();
        });
    }
    
    // Paso 5: Estado de canales
    const channelCheckForm = document.getElementById('channelCheckForm');
    if (channelCheckForm) {
        channelCheckForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const enableCheckInput = document.getElementById('enableCheck');
            const checkIntervalInput = document.getElementById('checkInterval');

            setupState.checkstatus_enabled = enableCheckInput ? enableCheckInput.checked : true;
            setupState.checkstatus_interval = checkIntervalInput ? (parseInt(checkIntervalInput.value) || 24) : 24;
            nextStep();
        });
    }

    const enableCheck = document.getElementById('enableCheck');
    if (enableCheck) {
        enableCheck.addEventListener('change', function() {
            const checkIntervalInput = document.getElementById('checkInterval');
            if (checkIntervalInput) {
                checkIntervalInput.disabled = !this.checked;
            }
        });
    }
    
    updateSourcesList();
});