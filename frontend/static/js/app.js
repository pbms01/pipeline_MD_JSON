/**
 * Pipeline MD/JSON v3 - Frontend Application
 */

// === STATE ===
const state = {
    file: null,
    jobId: null,
    eventSource: null,
    result: null
};

// === DOM ELEMENTS ===
const elements = {
    // Upload
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    clearFile: document.getElementById('clearFile'),

    // Config
    enableSchemaInference: document.getElementById('enableSchemaInference'),
    extractEntities: document.getElementById('extractEntities'),
    preferVisionTables: document.getElementById('preferVisionTables'),
    generateMarkdown: document.getElementById('generateMarkdown'),
    generateJson: document.getElementById('generateJson'),
    includeFrontmatter: document.getElementById('includeFrontmatter'),
    includeToc: document.getElementById('includeToc'),
    chunkSize: document.getElementById('chunkSize'),
    chunkSizeValue: document.getElementById('chunkSizeValue'),
    chunkOverlap: document.getElementById('chunkOverlap'),
    chunkOverlapValue: document.getElementById('chunkOverlapValue'),

    // Actions
    convertBtn: document.getElementById('convertBtn'),
    retryBtn: document.getElementById('retryBtn'),

    // Progress
    progressSection: document.getElementById('progressSection'),
    progressFill: document.getElementById('progressFill'),
    progressStage: document.getElementById('progressStage'),
    progressPercent: document.getElementById('progressPercent'),

    // Results
    resultsSection: document.getElementById('resultsSection'),
    docType: document.getElementById('docType'),
    confidenceFill: document.getElementById('confidenceFill'),
    confidenceValue: document.getElementById('confidenceValue'),
    processingTime: document.getElementById('processingTime'),
    downloadMd: document.getElementById('downloadMd'),
    downloadJson: document.getElementById('downloadJson'),
    markdownPreview: document.getElementById('markdownPreview'),
    jsonPreview: document.getElementById('jsonPreview'),
    entitiesPreview: document.getElementById('entitiesPreview'),
    structuredPreview: document.getElementById('structuredPreview'),

    // Error
    errorSection: document.getElementById('errorSection'),
    errorMessage: document.getElementById('errorMessage'),

    // Tabs
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane')
};

// === UTILITIES ===

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function truncate(str, maxLength = 10000) {
    if (str.length <= maxLength) return str;
    return str.slice(0, maxLength) + '\n\n... (truncado para preview)';
}

// === FILE HANDLING ===

function handleFile(file) {
    if (!file) return;

    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'];
    const validExtensions = ['.pdf', '.docx', '.doc'];

    const extension = '.' + file.name.split('.').pop().toLowerCase();

    if (!validExtensions.includes(extension)) {
        showError('Formato não suportado. Use PDF ou DOCX.');
        return;
    }

    state.file = file;

    // Update UI
    elements.uploadArea.style.display = 'none';
    elements.fileInfo.style.display = 'flex';
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.convertBtn.disabled = false;

    // Hide previous results/errors
    hideResults();
    hideError();
}

function clearFile() {
    state.file = null;
    elements.uploadArea.style.display = 'block';
    elements.fileInfo.style.display = 'none';
    elements.fileInput.value = '';
    elements.convertBtn.disabled = true;
    hideResults();
    hideError();
}

// === CONVERSION ===

async function startConversion() {
    if (!state.file) return;

    // Prepare config
    const config = {
        enable_schema_inference: elements.enableSchemaInference.checked,
        extract_entities: elements.extractEntities.checked,
        prefer_vision_for_tables: elements.preferVisionTables.checked,
        generate_markdown: elements.generateMarkdown.checked,
        generate_json: elements.generateJson.checked,
        include_frontmatter: elements.includeFrontmatter.checked,
        include_toc: elements.includeToc.checked,
        chunk_size: parseInt(elements.chunkSize.value),
        chunk_overlap: parseInt(elements.chunkOverlap.value)
    };

    // Prepare form data
    const formData = new FormData();
    formData.append('file', state.file);
    formData.append('config', JSON.stringify(config));

    // Show progress
    showProgress();
    hideResults();
    hideError();
    elements.convertBtn.disabled = true;

    try {
        // Start conversion
        const response = await fetch('/api/convert', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao iniciar conversão');
        }

        const data = await response.json();
        state.jobId = data.job_id;

        // Start progress streaming
        streamProgress(state.jobId);

    } catch (error) {
        console.error('Conversion error:', error);
        showError(error.message);
        hideProgress();
        elements.convertBtn.disabled = false;
    }
}

function streamProgress(jobId) {
    // Close existing connection
    if (state.eventSource) {
        state.eventSource.close();
    }

    // Create new SSE connection
    state.eventSource = new EventSource(`/api/progress/${jobId}`);

    state.eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // Update progress
        updateProgress(data.progress, data.stage);

        // Handle completion
        if (data.status === 'completed') {
            state.eventSource.close();
            handleCompletion(data.result);
        } else if (data.status === 'failed') {
            state.eventSource.close();
            showError(data.error || 'Erro desconhecido');
            hideProgress();
            elements.convertBtn.disabled = false;
        }
    };

    state.eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        state.eventSource.close();

        // Fallback to polling
        pollStatus(jobId);
    };
}

async function pollStatus(jobId) {
    try {
        const response = await fetch(`/api/status/${jobId}`);
        const data = await response.json();

        updateProgress(data.progress, data.stage);

        if (data.status === 'completed') {
            handleCompletion(data.result);
        } else if (data.status === 'failed') {
            showError(data.error || 'Erro desconhecido');
            hideProgress();
            elements.convertBtn.disabled = false;
        } else {
            // Continue polling
            setTimeout(() => pollStatus(jobId), 500);
        }
    } catch (error) {
        console.error('Polling error:', error);
        showError('Erro ao verificar status');
        hideProgress();
        elements.convertBtn.disabled = false;
    }
}

async function handleCompletion(result) {
    hideProgress();
    elements.convertBtn.disabled = false;

    try {
        // Fetch full result
        const response = await fetch(`/api/result/${state.jobId}`);
        const data = await response.json();

        state.result = data;
        showResults(data, result);
    } catch (error) {
        console.error('Error fetching result:', error);
        showError('Erro ao carregar resultados');
    }
}

// === UI UPDATES ===

function showProgress() {
    elements.progressSection.style.display = 'block';
    updateProgress(0, 'Iniciando...');
}

function hideProgress() {
    elements.progressSection.style.display = 'none';
}

function updateProgress(percent, stage) {
    elements.progressFill.style.width = `${percent}%`;
    elements.progressPercent.textContent = `${percent}%`;
    elements.progressStage.textContent = stage;
}

function showResults(data, result) {
    elements.resultsSection.style.display = 'block';

    // Summary
    elements.docType.textContent = result?.document_type || data.document_type || 'Desconhecido';

    const confidence = (result?.confidence || data.confidence || 0) * 100;
    elements.confidenceFill.style.width = `${confidence}%`;
    elements.confidenceValue.textContent = `${confidence.toFixed(0)}%`;

    const time = result?.processing_time || data.processing_time || 0;
    elements.processingTime.textContent = `${time.toFixed(2)}s`;

    // Download buttons
    elements.downloadMd.disabled = !data.markdown;
    elements.downloadJson.disabled = !data.json_data;

    // Previews
    if (data.markdown) {
        elements.markdownPreview.textContent = truncate(data.markdown);
    }

    if (data.json_data) {
        elements.jsonPreview.textContent = truncate(JSON.stringify(data.json_data, null, 2));

        // Entities
        if (data.json_data.entities) {
            renderEntities(data.json_data.entities);
        }

        // Structured data
        if (data.json_data.structured_data) {
            elements.structuredPreview.textContent = JSON.stringify(data.json_data.structured_data, null, 2);
        }
    }
}

function hideResults() {
    elements.resultsSection.style.display = 'none';
}

function renderEntities(entities) {
    let html = '';

    if (entities.people?.length) {
        html += `
            <div class="entity-group">
                <h4>👤 Pessoas (${entities.people.length})</h4>
                <ul class="entity-list">
                    ${entities.people.map(p => `
                        <li class="entity-item">
                            ${p.name}
                            ${p.role ? `<span class="entity-role"> - ${p.role}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (entities.organizations?.length) {
        html += `
            <div class="entity-group">
                <h4>🏢 Organizações (${entities.organizations.length})</h4>
                <ul class="entity-list">
                    ${entities.organizations.map(o => `
                        <li class="entity-item">${o.name}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (entities.dates?.length) {
        html += `
            <div class="entity-group">
                <h4>📅 Datas (${entities.dates.length})</h4>
                <ul class="entity-list">
                    ${entities.dates.map(d => `
                        <li class="entity-item">
                            ${d.original}
                            ${d.context ? `<span class="entity-role"> - ${d.context}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (entities.monetary_values?.length) {
        html += `
            <div class="entity-group">
                <h4>💰 Valores (${entities.monetary_values.length})</h4>
                <ul class="entity-list">
                    ${entities.monetary_values.map(m => `
                        <li class="entity-item">
                            ${m.original}
                            ${m.context ? `<span class="entity-role"> - ${m.context}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (entities.locations?.length) {
        html += `
            <div class="entity-group">
                <h4>📍 Locais (${entities.locations.length})</h4>
                <ul class="entity-list">
                    ${entities.locations.map(l => `
                        <li class="entity-item">${l.name}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (entities.technical_terms?.length) {
        html += `
            <div class="entity-group">
                <h4>📚 Termos Técnicos (${entities.technical_terms.length})</h4>
                <ul class="entity-list">
                    ${entities.technical_terms.map(t => `
                        <li class="entity-item">${t}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    elements.entitiesPreview.innerHTML = html || '<p>Nenhuma entidade encontrada</p>';
}

function showError(message) {
    elements.errorSection.style.display = 'block';
    elements.errorMessage.textContent = message;
}

function hideError() {
    elements.errorSection.style.display = 'none';
}

// === DOWNLOADS ===

function downloadMarkdown() {
    if (!state.jobId) return;
    window.location.href = `/api/download/${state.jobId}/markdown`;
}

function downloadJson() {
    if (!state.jobId) return;
    window.location.href = `/api/download/${state.jobId}/json`;
}

// === TABS ===

function switchTab(tabName) {
    // Update buttons
    elements.tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update panes
    elements.tabPanes.forEach(pane => {
        pane.classList.toggle('active', pane.id === `tab-${tabName}`);
    });
}

// === EVENT LISTENERS ===

// Upload area
elements.uploadArea.addEventListener('click', () => elements.fileInput.click());

elements.uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.uploadArea.classList.add('dragover');
});

elements.uploadArea.addEventListener('dragleave', () => {
    elements.uploadArea.classList.remove('dragover');
});

elements.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

elements.fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

elements.clearFile.addEventListener('click', clearFile);

// Config sliders
elements.chunkSize.addEventListener('input', (e) => {
    elements.chunkSizeValue.textContent = e.target.value;
});

elements.chunkOverlap.addEventListener('input', (e) => {
    elements.chunkOverlapValue.textContent = e.target.value;
});

// Buttons
elements.convertBtn.addEventListener('click', startConversion);
elements.retryBtn.addEventListener('click', () => {
    hideError();
    startConversion();
});

elements.downloadMd.addEventListener('click', downloadMarkdown);
elements.downloadJson.addEventListener('click', downloadJson);

// Tabs
elements.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// === INIT ===
console.log('Pipeline MD/JSON v3 initialized');
