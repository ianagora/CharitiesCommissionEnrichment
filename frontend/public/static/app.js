// Charity Commission Data Enrichment Platform - Frontend JavaScript

// API Configuration - Direct backend URL (CORS enabled)
const API_BASE = 'https://charitiescommissionenrichment-production.up.railway.app/api/v1';
let accessToken = localStorage.getItem('accessToken');
let refreshToken = localStorage.getItem('refreshToken');
let currentBatchId = null;
let currentPage = 1;
let isLoginMode = true;

// Axios instance with auth interceptor
const api = axios.create({
    baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response?.status === 401 && refreshToken) {
            try {
                const response = await axios.post(`${API_BASE}/auth/refresh`, null, {
                    params: { refresh_token: refreshToken }
                });
                accessToken = response.data.access_token;
                refreshToken = response.data.refresh_token;
                localStorage.setItem('accessToken', accessToken);
                localStorage.setItem('refreshToken', refreshToken);
                
                error.config.headers.Authorization = `Bearer ${accessToken}`;
                return axios(error.config);
            } catch (refreshError) {
                logout();
            }
        }
        return Promise.reject(error);
    }
);

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (accessToken) {
        checkAuth();
    } else {
        showLanding();
    }
});

// Authentication functions
async function checkAuth() {
    try {
        const response = await api.get('/auth/me');
        showDashboard();
        updateAuthSection(response.data);
        loadBatches();
    } catch (error) {
        logout();
    }
}

function showLogin() {
    isLoginMode = true;
    document.getElementById('auth-modal').classList.remove('hidden');
    document.getElementById('auth-title').textContent = 'Login';
    document.getElementById('auth-btn-text').textContent = 'Login';
    document.getElementById('auth-switch-text').textContent = "Don't have an account?";
    document.getElementById('auth-switch-btn').textContent = 'Register';
    document.getElementById('name-field').classList.add('hidden');
}

function showRegister() {
    isLoginMode = false;
    document.getElementById('auth-modal').classList.remove('hidden');
    document.getElementById('auth-title').textContent = 'Register';
    document.getElementById('auth-btn-text').textContent = 'Register';
    document.getElementById('auth-switch-text').textContent = 'Already have an account?';
    document.getElementById('auth-switch-btn').textContent = 'Login';
    document.getElementById('name-field').classList.remove('hidden');
}

function toggleAuthMode() {
    if (isLoginMode) {
        showRegister();
    } else {
        showLogin();
    }
}

function closeAuthModal() {
    document.getElementById('auth-modal').classList.add('hidden');
    document.getElementById('auth-form').reset();
}

async function handleAuth(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    try {
        if (isLoginMode) {
            const response = await axios.post(`${API_BASE}/auth/login`, { email, password });
            accessToken = response.data.access_token;
            refreshToken = response.data.refresh_token;
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('refreshToken', refreshToken);
        } else {
            const full_name = document.getElementById('full_name').value;
            await axios.post(`${API_BASE}/auth/register`, { email, password, full_name });
            // Auto-login after registration
            const response = await axios.post(`${API_BASE}/auth/login`, { email, password });
            accessToken = response.data.access_token;
            refreshToken = response.data.refresh_token;
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('refreshToken', refreshToken);
        }
        
        closeAuthModal();
        checkAuth();
    } catch (error) {
        alert(error.response?.data?.detail || 'Authentication failed');
    }
}

function logout() {
    accessToken = null;
    refreshToken = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    showLanding();
}

function updateAuthSection(user) {
    document.getElementById('auth-section').innerHTML = `
        <span class="text-white/80">${user.email}</span>
        <button onclick="logout()" class="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition">
            <i class="fas fa-sign-out-alt mr-2"></i>Logout
        </button>
    `;
}

// View functions
function showLanding() {
    document.getElementById('landing').classList.remove('hidden');
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('batch-detail').classList.add('hidden');
    document.getElementById('auth-section').innerHTML = `
        <button onclick="showLogin()" id="login-btn" class="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition">
            <i class="fas fa-sign-in-alt mr-2"></i>Login
        </button>
    `;
}

function showDashboard() {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('dashboard').classList.remove('hidden');
    document.getElementById('batch-detail').classList.add('hidden');
}

function showBatchDetail(batchId) {
    currentBatchId = batchId;
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('batch-detail').classList.remove('hidden');
    loadBatchDetail(batchId);
    loadEntities(batchId);
}

// Batch functions
// Store dashboard polling interval
let dashboardPollInterval = null;

async function loadBatches() {
    try {
        const response = await api.get('/batches');
        const batches = response.data.batches;
        
        // Update stats
        let totalEntities = 0;
        let totalMatched = 0;
        let totalPending = 0;
        let hasProcessingBatch = false;
        
        batches.forEach(batch => {
            totalEntities += batch.total_records || 0;
            totalMatched += batch.matched_records || 0;
            totalPending += (batch.total_records || 0) - (batch.processed_records || 0);
            if (batch.status === 'processing') {
                hasProcessingBatch = true;
            }
        });
        
        document.getElementById('stat-batches').textContent = batches.length;
        document.getElementById('stat-entities').textContent = totalEntities;
        document.getElementById('stat-matched').textContent = totalMatched;
        document.getElementById('stat-pending').textContent = totalPending;
        
        // Auto-refresh dashboard if any batch is processing
        if (hasProcessingBatch && !dashboardPollInterval) {
            dashboardPollInterval = setInterval(() => {
                loadBatches();
            }, 3000);  // Refresh every 3 seconds
        } else if (!hasProcessingBatch && dashboardPollInterval) {
            clearInterval(dashboardPollInterval);
            dashboardPollInterval = null;
        }
        
        // Render table
        const tbody = document.getElementById('batches-table');
        if (batches.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="px-4 py-8 text-center text-gray-500">
                        <i class="fas fa-folder-open text-4xl mb-2"></i>
                        <p>No batches yet. Upload your first batch above!</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = batches.map(batch => `
            <tr class="border-b hover:bg-gray-50 cursor-pointer" onclick="showBatchDetail('${batch.id}')">
                <td class="px-4 py-3">
                    <div class="font-medium text-gray-800">${escapeHtml(batch.name)}</div>
                    <div class="text-sm text-gray-500">${escapeHtml(batch.original_filename)}</div>
                </td>
                <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium ${getStatusClass(batch.status)}">
                        ${batch.status}${batch.status === 'processing' ? ' <i class="fas fa-spinner fa-spin ml-1"></i>' : ''}
                    </span>
                </td>
                <td class="px-4 py-3">
                    <div class="flex items-center">
                        <div class="w-24 bg-gray-200 rounded-full h-2 mr-2">
                            <div class="bg-green-600 h-2 rounded-full transition-all duration-300" style="width: ${getProgressPercent(batch)}%"></div>
                        </div>
                        <span class="text-sm text-gray-600">${batch.matched_records}/${batch.total_records}</span>
                    </div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-600">
                    ${formatDate(batch.created_at)}
                </td>
                <td class="px-4 py-3">
                    <button onclick="event.stopPropagation(); deleteBatch('${batch.id}')" class="text-red-600 hover:text-red-700">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading batches:', error);
        document.getElementById('batches-table').innerHTML = `
            <tr>
                <td colspan="5" class="px-4 py-8 text-center text-red-500">
                    Error loading batches. Please try again.
                </td>
            </tr>
        `;
    }
}

async function handleUpload(event) {
    event.preventDefault();
    
    const formData = new FormData();
    formData.append('name', document.getElementById('batch-name').value);
    formData.append('description', document.getElementById('batch-description').value);
    formData.append('name_column', document.getElementById('name-column').value);
    formData.append('file', document.getElementById('batch-file').files[0]);
    formData.append('auto_process', 'true');  // Auto-start processing
    
    const btn = document.getElementById('upload-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="loader inline-block mr-2"></div>Uploading & Processing...';
    
    try {
        const response = await api.post('/batches', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        document.getElementById('upload-form').reset();
        loadBatches();
        
        // Show success and open batch detail to show progress
        alert('Batch uploaded! Processing has started automatically. Click on the batch to see progress.');
        
        // Automatically open the batch detail view
        if (response.data && response.data.id) {
            showBatchDetail(response.data.id);
        }
    } catch (error) {
        alert(error.response?.data?.detail || 'Upload failed');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-cloud-upload-alt mr-2"></i>Upload & Create Batch';
    }
}

async function deleteBatch(batchId) {
    if (!confirm('Are you sure you want to delete this batch?')) return;
    
    try {
        await api.delete(`/batches/${batchId}`);
        loadBatches();
    } catch (error) {
        alert(error.response?.data?.detail || 'Delete failed');
    }
}

// Store polling interval globally so we can clear it
let batchPollInterval = null;

async function loadBatchDetail(batchId) {
    // Clear any existing polling
    if (batchPollInterval) {
        clearInterval(batchPollInterval);
        batchPollInterval = null;
    }
    
    try {
        const response = await api.get(`/batches/${batchId}`);
        const batch = response.data;
        
        document.getElementById('batch-detail-title').textContent = batch.name;
        document.getElementById('batch-total').textContent = batch.total_records;
        document.getElementById('batch-matched').textContent = batch.matched_records;
        document.getElementById('batch-pending').textContent = batch.total_records - batch.processed_records;
        
        // Load stats
        try {
            const statsResponse = await api.get(`/entities/batch/${batchId}/stats`);
            const stats = statsResponse.data;
            document.getElementById('batch-no-match').textContent = stats.status_breakdown.no_match || 0;
            document.getElementById('batch-review').textContent = 
                (stats.status_breakdown.multiple_matches || 0) + (stats.status_breakdown.manual_review || 0);
        } catch (e) {
            console.error('Error loading stats:', e);
        }
        
        // Update process button based on status
        const processBtn = document.getElementById('process-btn');
        if (batch.status === 'processing') {
            processBtn.disabled = true;
            processBtn.innerHTML = '<div class="loader inline-block mr-2"></div>Processing...';
            
            // Start polling for updates while processing
            batchPollInterval = setInterval(async () => {
                try {
                    const pollResponse = await api.get(`/batches/${batchId}`);
                    const pollBatch = pollResponse.data;
                    
                    document.getElementById('batch-matched').textContent = pollBatch.matched_records;
                    document.getElementById('batch-pending').textContent = pollBatch.total_records - pollBatch.processed_records;
                    
                    if (pollBatch.status !== 'processing') {
                        clearInterval(batchPollInterval);
                        batchPollInterval = null;
                        loadBatchDetail(batchId);  // Reload full details
                        loadEntities(batchId);     // Reload entities
                    }
                } catch (e) {
                    console.error('Polling error:', e);
                    clearInterval(batchPollInterval);
                    batchPollInterval = null;
                }
            }, 2000);  // Poll every 2 seconds
        } else {
            processBtn.disabled = false;
            processBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Process';
        }
    } catch (error) {
        console.error('Error loading batch detail:', error);
    }
}

async function processBatch() {
    console.log('[processBatch] Called, currentBatchId:', currentBatchId);
    if (!currentBatchId) {
        console.log('[processBatch] No currentBatchId, returning');
        return;
    }
    
    const btn = document.getElementById('process-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="loader inline-block mr-2"></div>Starting...';
    
    try {
        console.log('[processBatch] Calling API:', `/batches/${currentBatchId}/process`);
        const response = await api.post(`/batches/${currentBatchId}/process`, {
            batch_id: currentBatchId,
            use_ai_matching: true,
            build_ownership_tree: true,
            max_ownership_depth: 3
        });
        console.log('[processBatch] API response:', response.data);
        
        alert('Processing started! This may take a few minutes.');
        
        // Poll for updates
        const pollInterval = setInterval(async () => {
            try {
                const response = await api.get(`/batches/${currentBatchId}`);
                if (response.data.status !== 'processing') {
                    clearInterval(pollInterval);
                    loadBatchDetail(currentBatchId);
                    loadEntities(currentBatchId);
                } else {
                    document.getElementById('batch-matched').textContent = response.data.matched_records;
                    document.getElementById('batch-pending').textContent = 
                        response.data.total_records - response.data.processed_records;
                }
            } catch (e) {
                clearInterval(pollInterval);
            }
        }, 3000);
    } catch (error) {
        console.error('[processBatch] Error:', error);
        console.error('[processBatch] Error response:', error.response?.data);
        alert(error.response?.data?.detail || 'Failed to start processing');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-play mr-2"></i>Process';
    }
}

async function exportBatch(format) {
    if (!currentBatchId) return;
    
    try {
        const endpoint = format === 'xlsx' ? '/exports/excel' : '/exports/csv';
        const response = await api.post(endpoint, {
            batch_id: currentBatchId,
            include_resolutions: true,
            include_ownership_tree: true,
            include_financial_data: true,
            include_enriched_data: true,
            format: format
        }, {
            responseType: 'blob'
        });
        
        // Download file
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `export.${format}`);
        document.body.appendChild(link);
        link.click();
        link.remove();
    } catch (error) {
        alert('Export failed');
    }
}

// Entity functions
async function loadEntities(batchId, page = 1, status = '', search = '') {
    currentPage = page;
    
    try {
        let url = `/entities/batch/${batchId}?page=${page}&page_size=20`;
        if (status) url += `&status_filter=${status}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        
        const response = await api.get(url);
        const entities = response.data;
        
        const tbody = document.getElementById('entities-table');
        if (entities.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="px-4 py-8 text-center text-gray-500">
                        No entities found
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = entities.map(entity => `
            <tr class="border-b hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-600">${entity.row_number || '-'}</td>
                <td class="px-4 py-3">
                    <div class="font-medium text-gray-800 truncate max-w-xs" title="${escapeHtml(entity.original_name)}">
                        ${escapeHtml(entity.original_name)}
                    </div>
                </td>
                <td class="px-4 py-3">
                    <div class="truncate max-w-xs" title="${escapeHtml(entity.resolved_name || '')}">
                        ${entity.resolved_name ? escapeHtml(entity.resolved_name) : '<span class="text-gray-400">-</span>'}
                    </div>
                </td>
                <td class="px-4 py-3 text-sm">
                    ${entity.charity_number || '<span class="text-gray-400">-</span>'}
                </td>
                <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium ${getResolutionStatusClass(entity.resolution_status)}">
                        ${formatStatus(entity.resolution_status)}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm">
                    ${entity.resolution_confidence ? Math.round(entity.resolution_confidence * 100) + '%' : '-'}
                </td>
                <td class="px-4 py-3">
                    <button onclick="showEntityDetail('${entity.id}')" class="text-blue-600 hover:text-blue-700 mr-2">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${entity.resolution_status === 'multiple_matches' || entity.resolution_status === 'manual_review' ? `
                        <button onclick="showResolutions('${entity.id}')" class="text-purple-600 hover:text-purple-700">
                            <i class="fas fa-check-double"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `).join('');
        
        // Pagination (simplified)
        const pagination = document.getElementById('pagination');
        pagination.innerHTML = `
            ${page > 1 ? `<button onclick="loadEntities('${batchId}', ${page - 1})" class="px-3 py-1 border rounded hover:bg-gray-100">Previous</button>` : ''}
            <span class="px-3 py-1">Page ${page}</span>
            ${entities.length === 20 ? `<button onclick="loadEntities('${batchId}', ${page + 1})" class="px-3 py-1 border rounded hover:bg-gray-100">Next</button>` : ''}
        `;
    } catch (error) {
        console.error('Error loading entities:', error);
    }
}

function filterEntities() {
    const status = document.getElementById('status-filter').value;
    const search = document.getElementById('entity-search').value;
    loadEntities(currentBatchId, 1, status, search);
}

async function showEntityDetail(entityId) {
    try {
        const response = await api.get(`/entities/${entityId}`);
        const entity = response.data;
        
        const details = document.getElementById('entity-details');
        details.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <h3 class="font-bold text-gray-800 mb-3">Original Data</h3>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p><strong>Name:</strong> ${escapeHtml(entity.original_name)}</p>
                        <p><strong>Row #:</strong> ${entity.row_number || '-'}</p>
                        ${entity.original_data ? `
                            <details class="mt-2">
                                <summary class="cursor-pointer text-blue-600">View all columns</summary>
                                <pre class="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">${JSON.stringify(entity.original_data, null, 2)}</pre>
                            </details>
                        ` : ''}
                    </div>
                </div>
                <div>
                    <h3 class="font-bold text-gray-800 mb-3">Resolution</h3>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p><strong>Status:</strong> <span class="${getResolutionStatusClass(entity.resolution_status)}">${formatStatus(entity.resolution_status)}</span></p>
                        <p><strong>Confidence:</strong> ${entity.resolution_confidence ? Math.round(entity.resolution_confidence * 100) + '%' : '-'}</p>
                        <p><strong>Method:</strong> ${entity.resolution_method || '-'}</p>
                    </div>
                </div>
            </div>
            
            ${entity.charity_number ? `
                <div class="mt-6">
                    <h3 class="font-bold text-gray-800 mb-3">Charity Details</h3>
                    <div class="bg-blue-50 rounded-lg p-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <p><strong>Charity Number:</strong> ${entity.charity_number}</p>
                                <p><strong>Name:</strong> ${escapeHtml(entity.resolved_name || '')}</p>
                                <p><strong>Status:</strong> ${entity.charity_status || '-'}</p>
                                <p><strong>Registered:</strong> ${entity.charity_registration_date ? formatDate(entity.charity_registration_date) : '-'}</p>
                            </div>
                            <div>
                                <p><strong>Website:</strong> ${entity.charity_website ? `<a href="${entity.charity_website}" target="_blank" class="text-blue-600 hover:underline">${entity.charity_website}</a>` : '-'}</p>
                                <p><strong>Email:</strong> ${entity.charity_contact_email || '-'}</p>
                                <p><strong>Address:</strong> ${entity.charity_address || '-'}</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                ${entity.latest_income || entity.latest_expenditure ? `
                    <div class="mt-6">
                        <h3 class="font-bold text-gray-800 mb-3">Financial Data</h3>
                        <div class="bg-green-50 rounded-lg p-4">
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <p class="text-sm text-gray-600">Latest Income</p>
                                    <p class="text-xl font-bold text-green-600">£${formatNumber(entity.latest_income)}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">Latest Expenditure</p>
                                    <p class="text-xl font-bold text-red-600">£${formatNumber(entity.latest_expenditure)}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">Financial Year End</p>
                                    <p class="text-xl font-bold">${entity.latest_financial_year_end ? formatDate(entity.latest_financial_year_end) : '-'}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                ` : ''}
            ` : ''}
            
            ${entity.enriched_data ? `
                <div class="mt-6">
                    <h3 class="font-bold text-gray-800 mb-3">Enriched Data</h3>
                    <div class="bg-purple-50 rounded-lg p-4">
                        ${entity.enriched_data.trustees && entity.enriched_data.trustees.length > 0 ? `
                            <div class="mb-4">
                                <strong>Trustees (${entity.enriched_data.trustees.length}):</strong>
                                <ul class="mt-2 list-disc list-inside">
                                    ${entity.enriched_data.trustees.slice(0, 5).map(t => `<li>${escapeHtml(t.name || 'Unknown')}</li>`).join('')}
                                    ${entity.enriched_data.trustees.length > 5 ? `<li class="text-gray-500">... and ${entity.enriched_data.trustees.length - 5} more</li>` : ''}
                                </ul>
                            </div>
                        ` : ''}
                        ${entity.enriched_data.subsidiaries && entity.enriched_data.subsidiaries.length > 0 ? `
                            <div>
                                <strong>Subsidiaries (${entity.enriched_data.subsidiaries.length}):</strong>
                                <ul class="mt-2 list-disc list-inside">
                                    ${entity.enriched_data.subsidiaries.map(s => `<li>${escapeHtml(s.name || 'Unknown')} ${s.company_number ? `(${s.company_number})` : ''}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            ` : ''}
            
            <div class="mt-6 flex justify-end space-x-2">
                ${entity.resolution_status !== 'confirmed' && entity.resolution_status !== 'matched' ? `
                    <button onclick="confirmEntity('${entity.id}')" class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg">
                        <i class="fas fa-check mr-2"></i>Confirm Match
                    </button>
                ` : ''}
            </div>
        `;
        
        document.getElementById('entity-modal').classList.remove('hidden');
    } catch (error) {
        alert('Error loading entity details');
    }
}

function closeEntityModal() {
    document.getElementById('entity-modal').classList.add('hidden');
}

// Store fetched charity details for resolutions
let resolutionCharityDetails = {};

async function showResolutions(entityId) {
    try {
        const response = await api.get(`/entities/${entityId}/resolutions`);
        const resolutions = response.data;
        
        // Also get the original entity to show what we're matching
        const entityResponse = await api.get(`/entities/${entityId}`);
        const entity = entityResponse.data;
        
        const details = document.getElementById('entity-details');
        details.innerHTML = `
            <div class="mb-4 p-3 bg-gray-100 rounded-lg">
                <p class="text-sm text-gray-600">Matching:</p>
                <p class="font-bold text-lg">${escapeHtml(entity.original_name)}</p>
                ${entity.original_data ? `
                    <p class="text-sm text-gray-500 mt-1">Original data: ${Object.entries(entity.original_data).map(([k,v]) => `${k}: ${v}`).join(', ')}</p>
                ` : ''}
            </div>
            <h3 class="font-bold text-gray-800 mb-4">Select the correct match:</h3>
            <div class="space-y-3" id="resolutions-list">
                ${resolutions.map((res, idx) => `
                    <div class="border rounded-lg overflow-hidden ${res.is_selected ? 'border-green-500 bg-green-50' : ''}" id="resolution-${res.id}">
                        <div class="p-4 hover:bg-gray-50 cursor-pointer" onclick="toggleResolutionDetails('${res.id}', '${res.charity_number}')">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="font-medium">${escapeHtml(res.candidate_name)}</p>
                                    <p class="text-sm text-gray-600">Charity #: ${res.charity_number || '-'}</p>
                                    <p class="text-xs text-gray-400 mt-1"><i class="fas fa-chevron-down mr-1"></i>Click to view details</p>
                                </div>
                                <div class="text-right">
                                    <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                                        ${Math.round(res.confidence_score * 100)}% match
                                    </span>
                                    <p class="text-xs text-gray-500 mt-1">${res.match_method}</p>
                                </div>
                            </div>
                        </div>
                        <div id="details-${res.id}" class="hidden border-t bg-blue-50 p-4">
                            <div class="text-center text-gray-500">
                                <div class="loader inline-block mr-2"></div>Loading details...
                            </div>
                        </div>
                        <div class="border-t p-3 bg-gray-50 flex justify-end">
                            <button onclick="event.stopPropagation(); confirmResolution('${entityId}', '${res.id}')" 
                                    class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm">
                                <i class="fas fa-check mr-2"></i>Confirm This Match
                            </button>
                        </div>
                    </div>
                `).join('')}
                <div class="border rounded-lg p-4 hover:bg-red-50 cursor-pointer border-red-200" 
                     onclick="confirmResolution('${entityId}', null)">
                    <p class="font-medium text-red-600">
                        <i class="fas fa-times mr-2"></i>None of these - Mark as No Match
                    </p>
                </div>
            </div>
        `;
        
        // Clear cached details
        resolutionCharityDetails = {};
        
        document.getElementById('entity-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Error loading resolutions:', error);
        alert('Error loading resolutions');
    }
}

async function toggleResolutionDetails(resolutionId, charityNumber) {
    const detailsDiv = document.getElementById(`details-${resolutionId}`);
    
    if (!detailsDiv.classList.contains('hidden')) {
        detailsDiv.classList.add('hidden');
        return;
    }
    
    detailsDiv.classList.remove('hidden');
    
    // Check if we already fetched this
    if (resolutionCharityDetails[charityNumber]) {
        renderCharityDetails(resolutionId, resolutionCharityDetails[charityNumber]);
        return;
    }
    
    // Fetch charity details from Charity Commission API via our backend
    try {
        const response = await api.get(`/charity/${charityNumber}`);
        const data = response.data;
        resolutionCharityDetails[charityNumber] = data;
        renderCharityDetails(resolutionId, data);
    } catch (error) {
        console.error('Error fetching charity details:', error);
        detailsDiv.innerHTML = `
            <div class="text-gray-600">
                <p><strong>Unable to fetch additional details</strong></p>
                <p class="text-sm">The charity number ${charityNumber} could not be looked up. You can still confirm this match if the name looks correct.</p>
            </div>
        `;
    }
}

function renderCharityDetails(resolutionId, data) {
    const detailsDiv = document.getElementById(`details-${resolutionId}`);
    detailsDiv.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
                <p><strong>Official Name:</strong> ${escapeHtml(data.name || '-')}</p>
                <p><strong>Charity Number:</strong> ${data.charity_number || '-'}</p>
                <p><strong>Status:</strong> <span class="${data.status === 'Registered' ? 'text-green-600' : 'text-red-600'}">${data.status || '-'}</span></p>
                <p><strong>Registration Date:</strong> ${data.registration_date ? formatDate(data.registration_date) : '-'}</p>
            </div>
            <div>
                <p><strong>Website:</strong> ${data.website ? `<a href="${data.website}" target="_blank" class="text-blue-600 hover:underline">${data.website}</a>` : '-'}</p>
                <p><strong>Email:</strong> ${data.contact_email || '-'}</p>
                <p><strong>Latest Income:</strong> ${data.latest_income ? '£' + formatNumber(data.latest_income) : '-'}</p>
                <p><strong>Latest Expenditure:</strong> ${data.latest_expenditure ? '£' + formatNumber(data.latest_expenditure) : '-'}</p>
            </div>
        </div>
        ${data.activities ? `
            <div class="mt-3">
                <p><strong>Activities:</strong></p>
                <p class="text-gray-600 text-sm">${escapeHtml(data.activities).substring(0, 300)}${data.activities.length > 300 ? '...' : ''}</p>
            </div>
        ` : ''}
        ${data.address ? `
            <div class="mt-2">
                <p><strong>Address:</strong> ${escapeHtml(data.address)}</p>
            </div>
        ` : ''}
        ${data.trustees && data.trustees.length > 0 ? `
            <div class="mt-3">
                <p><strong>Trustees (${data.trustees.length}):</strong> ${data.trustees.slice(0, 5).map(t => escapeHtml(t.name || t)).join(', ')}${data.trustees.length > 5 ? '...' : ''}</p>
            </div>
        ` : ''}
    `;
}

async function confirmResolution(entityId, resolutionId) {
    try {
        await api.post(`/entities/${entityId}/confirm`, {
            entity_id: entityId,
            resolution_id: resolutionId
        });
        
        closeEntityModal();
        loadEntities(currentBatchId, currentPage);
        loadBatchDetail(currentBatchId);
        alert('Resolution confirmed!');
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to confirm resolution');
    }
}

async function confirmEntity(entityId) {
    try {
        await api.post(`/entities/${entityId}/confirm`, {
            entity_id: entityId
        });
        
        closeEntityModal();
        loadEntities(currentBatchId, currentPage);
        loadBatchDetail(currentBatchId);
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to confirm');
    }
}

async function buildOwnershipTree(entityId) {
    try {
        const response = await api.get(`/entities/${entityId}/ownership-tree?max_depth=3`);
        const tree = response.data;
        
        const details = document.getElementById('entity-details');
        details.innerHTML = `
            <h3 class="font-bold text-gray-800 mb-4">Ownership Tree</h3>
            <div class="bg-gray-50 rounded-lg p-4">
                <p><strong>Total Entities:</strong> ${tree.total_entities}</p>
                <p><strong>Max Depth:</strong> ${tree.max_depth_reached}</p>
                <div class="mt-4">
                    ${renderTreeNode(tree.root, 0)}
                </div>
                ${tree.children && tree.children.length > 0 ? `
                    <h4 class="font-bold mt-4 mb-2">Subsidiaries & Related Entities:</h4>
                    ${tree.children.map(child => renderTreeNode(child, 1)).join('')}
                ` : ''}
            </div>
        `;
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to build ownership tree');
    }
}

function renderTreeNode(node, level) {
    const indent = level * 24;
    return `
        <div style="margin-left: ${indent}px" class="py-1 border-l-2 border-blue-200 pl-3 my-1">
            <span class="font-medium">${escapeHtml(node.name || node.original_name)}</span>
            ${node.charity_number ? `<span class="text-sm text-gray-500 ml-2">(${node.charity_number})</span>` : ''}
            ${node.ownership_type ? `<span class="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded ml-2">${node.ownership_type}</span>` : ''}
            ${node.children && node.children.length > 0 ? node.children.map(child => renderTreeNode(child, level + 1)).join('') : ''}
        </div>
    `;
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-GB', {
        year: 'numeric', month: 'short', day: 'numeric'
    });
}

function formatNumber(num) {
    if (!num) return '0';
    return new Intl.NumberFormat('en-GB').format(Math.round(num));
}

function getStatusClass(status) {
    const classes = {
        'uploaded': 'bg-blue-100 text-blue-800',
        'processing': 'bg-yellow-100 text-yellow-800',
        'completed': 'bg-green-100 text-green-800',
        'failed': 'bg-red-100 text-red-800',
        'partial': 'bg-orange-100 text-orange-800'
    };
    return classes[status] || 'bg-gray-100 text-gray-800';
}

function getResolutionStatusClass(status) {
    const classes = {
        'matched': 'bg-green-100 text-green-800',
        'confirmed': 'bg-green-100 text-green-800',
        'no_match': 'bg-red-100 text-red-800',
        'rejected': 'bg-red-100 text-red-800',
        'multiple_matches': 'bg-purple-100 text-purple-800',
        'manual_review': 'bg-yellow-100 text-yellow-800',
        'pending': 'bg-gray-100 text-gray-800'
    };
    return classes[status] || 'bg-gray-100 text-gray-800';
}

function formatStatus(status) {
    const labels = {
        'matched': 'Matched',
        'confirmed': 'Confirmed',
        'no_match': 'No Match',
        'rejected': 'Rejected',
        'multiple_matches': 'Review',
        'manual_review': 'Review',
        'pending': 'Pending'
    };
    return labels[status] || status;
}

function getProgressPercent(batch) {
    if (!batch.total_records) return 0;
    return Math.round((batch.matched_records / batch.total_records) * 100);
}
