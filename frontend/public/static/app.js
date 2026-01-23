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
    document.getElementById('organization-field').classList.add('hidden');
    document.getElementById('confirm-password-field').classList.add('hidden');
    document.getElementById('password-strength').classList.add('hidden');
}

function showRegister() {
    isLoginMode = false;
    document.getElementById('auth-modal').classList.remove('hidden');
    document.getElementById('auth-title').textContent = 'Register';
    document.getElementById('auth-btn-text').textContent = 'Register';
    document.getElementById('auth-switch-text').textContent = 'Already have an account?';
    document.getElementById('auth-switch-btn').textContent = 'Login';
    document.getElementById('name-field').classList.remove('hidden');
    document.getElementById('organization-field').classList.remove('hidden');
    document.getElementById('confirm-password-field').classList.remove('hidden');
    document.getElementById('password-strength').classList.remove('hidden');
    
    // Add password strength checker
    const passwordInput = document.getElementById('password');
    passwordInput.addEventListener('input', checkPasswordStrength);
    
    // Add password match checker
    const confirmInput = document.getElementById('confirm_password');
    confirmInput.addEventListener('input', checkPasswordMatch);
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
    document.getElementById('password-strength').innerHTML = '';
    document.getElementById('password-match').innerHTML = '';
}

// Toggle password visibility
function togglePasswordVisibility(fieldId) {
    const field = document.getElementById(fieldId);
    const icon = document.getElementById(`${fieldId}-icon`);
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Check password strength
function checkPasswordStrength() {
    const password = document.getElementById('password').value;
    const strengthDiv = document.getElementById('password-strength');
    
    if (!password) {
        strengthDiv.innerHTML = '';
        return;
    }
    
    let strength = 0;
    let feedback = [];
    
    // Length check
    if (password.length >= 8) strength++;
    else feedback.push('At least 8 characters');
    
    // Uppercase check
    if (/[A-Z]/.test(password)) strength++;
    else feedback.push('One uppercase letter');
    
    // Lowercase check
    if (/[a-z]/.test(password)) strength++;
    else feedback.push('One lowercase letter');
    
    // Number check
    if (/[0-9]/.test(password)) strength++;
    else feedback.push('One number');
    
    // Special character check
    if (/[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/`~]/.test(password)) strength++;
    else feedback.push('One special character');
    
    // Display strength
    let color, text;
    if (strength <= 2) {
        color = 'text-red-600';
        text = '❌ Weak';
    } else if (strength <= 3) {
        color = 'text-orange-600';
        text = '⚠️ Fair';
    } else if (strength <= 4) {
        color = 'text-yellow-600';
        text = '✓ Good';
    } else {
        color = 'text-green-600';
        text = '✅ Strong';
    }
    
    strengthDiv.className = `mt-2 text-sm ${color}`;
    strengthDiv.innerHTML = `<strong>${text}</strong>`;
    if (feedback.length > 0) {
        strengthDiv.innerHTML += `<br>Needs: ${feedback.join(', ')}`;
    }
}

// Check if passwords match
function checkPasswordMatch() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const matchDiv = document.getElementById('password-match');
    
    if (!confirmPassword) {
        matchDiv.innerHTML = '';
        return;
    }
    
    if (password === confirmPassword) {
        matchDiv.className = 'mt-2 text-sm text-green-600';
        matchDiv.innerHTML = '✅ Passwords match';
    } else {
        matchDiv.className = 'mt-2 text-sm text-red-600';
        matchDiv.innerHTML = '❌ Passwords do not match';
    }
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
                    ${entity.resolution_status === 'multiple_matches' || entity.resolution_status === 'manual_review' ? `
                        <button onclick="showResolutions('${entity.id}')" class="bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded text-sm">
                            <i class="fas fa-search mr-1"></i>Review Matches
                        </button>
                    ` : `
                        <button onclick="showEntityDetail('${entity.id}')" class="text-blue-600 hover:text-blue-700">
                            <i class="fas fa-eye mr-1"></i>View
                        </button>
                    `}
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

// ============================================
// ADMIN PANEL & 2FA FUNCTIONALITY
// ============================================

let currentUser = null;

// Check if user needs 2FA setup (MANDATORY)
async function check2FARequired() {
    try {
        const response = await api.get('/auth/2fa/status');
        const userResponse = await api.get('/auth/me');
        currentUser = userResponse.data;
        
        // If 2FA is not enabled and not in setup, force setup
        if (!response.data.enabled && !window.location.hash.includes('2fa-setup')) {
            show2FAMandatorySetup();
            return true;
        }
        return false;
    } catch (error) {
        console.error('2FA status check failed:', error);
        return false;
    }
}

// Show mandatory 2FA setup modal
function show2FAMandatorySetup() {
    const modal = document.createElement('div');
    modal.id = '2fa-mandatory-modal';
    modal.className = 'fixed inset-0 bg-black/70 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-8 max-w-md w-full mx-4 card-shadow">
            <div class="text-center mb-6">
                <div class="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-shield-alt text-red-600 text-2xl"></i>
                </div>
                <h2 class="text-2xl font-bold text-gray-800">Two-Factor Authentication Required</h2>
                <p class="text-gray-600 mt-2">For security, all users must enable 2FA to continue.</p>
            </div>
            <button onclick="initiate2FASetup()" class="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium transition">
                <i class="fas fa-lock mr-2"></i>Set Up 2FA Now
            </button>
            <p class="text-center text-sm text-gray-500 mt-4">You cannot access the application without 2FA.</p>
        </div>
    `;
    document.body.appendChild(modal);
}

// Initiate 2FA setup
async function initiate2FASetup() {
    try {
        const response = await api.post('/auth/2fa/setup');
        const { qr_code, backup_codes } = response.data;
        
        show2FASetupWizard(qr_code, backup_codes);
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to initiate 2FA setup');
    }
}

// Show 2FA setup wizard
function show2FASetupWizard(qrCode, backupCodes) {
    const existingModal = document.getElementById('2fa-mandatory-modal');
    if (existingModal) existingModal.remove();
    
    const modal = document.createElement('div');
    modal.id = '2fa-setup-wizard';
    modal.className = 'fixed inset-0 bg-black/70 flex items-center justify-center z-50 overflow-y-auto';
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-8 max-w-2xl w-full mx-4 my-8 card-shadow">
            <h2 class="text-2xl font-bold text-gray-800 mb-6">
                <i class="fas fa-mobile-alt mr-2 text-blue-600"></i>Set Up Two-Factor Authentication
            </h2>
            
            <!-- Step 1: Scan QR Code -->
            <div class="mb-6">
                <h3 class="font-bold text-lg mb-3">Step 1: Scan QR Code</h3>
                <p class="text-gray-600 mb-4">Use Google Authenticator, Authy, or any TOTP app:</p>
                <div class="bg-gray-50 p-4 rounded-lg text-center">
                    <img src="${qrCode}" alt="QR Code" class="mx-auto" style="max-width: 250px;">
                </div>
            </div>
            
            <!-- Step 2: Save Backup Codes -->
            <div class="mb-6">
                <h3 class="font-bold text-lg mb-3">Step 2: Save Backup Codes</h3>
                <p class="text-gray-600 mb-3">Store these codes securely. Each can only be used once:</p>
                <div class="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-4">
                    <div class="grid grid-cols-2 gap-2 font-mono text-sm">
                        ${backupCodes.map(code => `<div class="bg-white p-2 rounded">${code}</div>`).join('')}
                    </div>
                    <button onclick="copyBackupCodes('${backupCodes.join(', ')}')" 
                            class="mt-3 text-sm text-blue-600 hover:underline">
                        <i class="fas fa-copy mr-1"></i>Copy All Codes
                    </button>
                </div>
                <p class="text-sm text-red-600 mt-2">
                    <i class="fas fa-exclamation-triangle mr-1"></i>
                    Warning: You won't be able to see these codes again!
                </p>
            </div>
            
            <!-- Step 3: Verify -->
            <div class="mb-6">
                <h3 class="font-bold text-lg mb-3">Step 3: Verify Code</h3>
                <p class="text-gray-600 mb-3">Enter the 6-digit code from your authenticator app:</p>
                <input type="text" 
                       id="2fa-verify-code" 
                       placeholder="123456" 
                       maxlength="6"
                       class="w-full px-4 py-3 border-2 border-gray-300 rounded-lg text-center text-2xl font-mono tracking-widest focus:ring-2 focus:ring-blue-500">
            </div>
            
            <button onclick="verify2FASetup()" 
                    class="w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg font-medium transition">
                <i class="fas fa-check-circle mr-2"></i>Enable 2FA
            </button>
        </div>
    `;
    document.body.appendChild(modal);
}

// Copy backup codes
function copyBackupCodes(codes) {
    navigator.clipboard.writeText(codes).then(() => {
        alert('Backup codes copied to clipboard!');
    });
}

// Verify and enable 2FA
async function verify2FASetup() {
    const code = document.getElementById('2fa-verify-code').value;
    
    if (!code || code.length !== 6) {
        alert('Please enter a 6-digit code');
        return;
    }
    
    try {
        await api.post('/auth/2fa/verify', { token: code });
        
        const modal = document.getElementById('2fa-setup-wizard');
        if (modal) modal.remove();
        
        alert('✅ 2FA enabled successfully! You can now access the application.');
        location.reload();
    } catch (error) {
        alert(error.response?.data?.detail || 'Invalid verification code. Please try again.');
    }
}

// Show Admin Panel
function showAdminPanel() {
    if (!currentUser?.is_superuser) {
        alert('Access denied. Admin privileges required.');
        return;
    }
    
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('batch-detail').classList.add('hidden');
    document.getElementById('landing').classList.add('hidden');
    
    let adminPanel = document.getElementById('admin-panel');
    if (!adminPanel) {
        adminPanel = document.createElement('div');
        adminPanel.id = 'admin-panel';
        document.querySelector('main .container').appendChild(adminPanel);
    }
    
    adminPanel.classList.remove('hidden');
    adminPanel.innerHTML = `
        <div class="mb-6 flex items-center justify-between">
            <div>
                <button onclick="showDashboard()" class="text-blue-600 hover:text-blue-700 mb-2">
                    <i class="fas fa-arrow-left mr-2"></i>Back to Dashboard
                </button>
                <h2 class="text-3xl font-bold text-gray-800">
                    <i class="fas fa-cog mr-2 text-blue-600"></i>Admin Panel
                </h2>
            </div>
        </div>
        
        <!-- Tab Navigation -->
        <div class="mb-6 border-b border-gray-200">
            <nav class="flex space-x-8">
                <button onclick="showAdminTab('users')" id="admin-tab-users" 
                        class="admin-tab py-4 px-2 border-b-2 border-blue-600 font-medium text-blue-600">
                    <i class="fas fa-users mr-2"></i>User Management
                </button>
                <button onclick="showAdminTab('settings')" id="admin-tab-settings" 
                        class="admin-tab py-4 px-2 border-b-2 border-transparent font-medium text-gray-500 hover:text-gray-700">
                    <i class="fas fa-shield-alt mr-2"></i>Security Settings
                </button>
                <button onclick="showAdminTab('my2fa')" id="admin-tab-my2fa" 
                        class="admin-tab py-4 px-2 border-b-2 border-transparent font-medium text-gray-500 hover:text-gray-700">
                    <i class="fas fa-mobile-alt mr-2"></i>My 2FA
                </button>
            </nav>
        </div>
        
        <!-- Tab Content -->
        <div id="admin-tab-content"></div>
    `;
    
    showAdminTab('users');
}

// Show admin tab
function showAdminTab(tab) {
    // Update tab styling
    document.querySelectorAll('.admin-tab').forEach(btn => {
        btn.classList.remove('border-blue-600', 'text-blue-600');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    document.getElementById(`admin-tab-${tab}`).classList.add('border-blue-600', 'text-blue-600');
    document.getElementById(`admin-tab-${tab}`).classList.remove('border-transparent', 'text-gray-500');
    
    const content = document.getElementById('admin-tab-content');
    
    if (tab === 'users') {
        showUserManagement(content);
    } else if (tab === 'settings') {
        showSecuritySettings(content);
    } else if (tab === 'my2fa') {
        showMy2FASettings(content);
    }
}

// User Management Tab
function showUserManagement(container) {
    container.innerHTML = `
        <div class="bg-white rounded-xl p-6 card-shadow mb-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-bold text-gray-800">
                    <i class="fas fa-user-plus mr-2 text-green-600"></i>Add New User
                </h3>
            </div>
            <form onsubmit="createUser(event)" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Email *</label>
                    <input type="email" id="new-user-email" required 
                           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                    <input type="text" id="new-user-name" 
                           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Password *</label>
                    <input type="password" id="new-user-password" required minlength="8"
                           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                    <p class="text-xs text-gray-500 mt-1">Min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Organization</label>
                    <input type="text" id="new-user-org" 
                           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="md:col-span-2">
                    <label class="flex items-center">
                        <input type="checkbox" id="new-user-admin" class="mr-2">
                        <span class="text-sm font-medium text-gray-700">Make this user an administrator</span>
                    </label>
                </div>
                <div class="md:col-span-2">
                    <button type="submit" class="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-medium transition">
                        <i class="fas fa-user-plus mr-2"></i>Create User
                    </button>
                </div>
            </form>
        </div>
        
        <div class="bg-white rounded-xl p-6 card-shadow">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-bold text-gray-800">
                    <i class="fas fa-users mr-2 text-blue-600"></i>All Users
                </h3>
                <button onclick="loadAllUsers()" class="text-blue-600 hover:text-blue-700">
                    <i class="fas fa-sync-alt mr-1"></i>Refresh
                </button>
            </div>
            <div id="users-list">
                <div class="text-center py-8">
                    <div class="loader mx-auto mb-2"></div>
                    <p class="text-gray-500">Loading users...</p>
                </div>
            </div>
        </div>
    `;
    
    loadAllUsers();
}

// Create new user
async function createUser(event) {
    event.preventDefault();
    
    const email = document.getElementById('new-user-email').value;
    const password = document.getElementById('new-user-password').value;
    const fullName = document.getElementById('new-user-name').value;
    const organization = document.getElementById('new-user-org').value;
    const isAdmin = document.getElementById('new-user-admin').checked;
    
    try {
        await api.post('/auth/register', {
            email,
            password,
            full_name: fullName || null,
            organization: organization || null
        });
        
        // If admin, promote them
        if (isAdmin) {
            // Note: We'd need a backend endpoint for this
            // For now, show message
            alert('✅ User created! Use CLI to make them admin: python scripts/manage_users.py make-superuser --email ' + email);
        } else {
            alert('✅ User created successfully!');
        }
        
        // Clear form
        event.target.reset();
        
        // Reload users list
        loadAllUsers();
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to create user');
    }
}

// Load all users (Note: This requires a backend endpoint)
async function loadAllUsers() {
    const container = document.getElementById('users-list');
    
    // Note: We need to create a /users endpoint in the backend
    // For now, show a message
    container.innerHTML = `
        <div class="text-center py-8">
            <p class="text-gray-600 mb-4">User listing requires backend endpoint: <code class="bg-gray-100 px-2 py-1 rounded">GET /api/v1/users</code></p>
            <p class="text-sm text-gray-500">Use CLI for now: <code class="bg-gray-100 px-2 py-1 rounded">python scripts/manage_users.py list-users</code></p>
        </div>
    `;
    
    // TODO: Uncomment when backend endpoint is ready
    /*
    try {
        const response = await api.get('/users');
        const users = response.data;
        
        container.innerHTML = `
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Email</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Name</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Status</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Role</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">2FA</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${users.map(user => `
                        <tr class="border-t hover:bg-gray-50">
                            <td class="px-4 py-3 text-sm">${escapeHtml(user.email)}</td>
                            <td class="px-4 py-3 text-sm">${escapeHtml(user.full_name || '-')}</td>
                            <td class="px-4 py-3 text-sm">
                                <span class="px-2 py-1 rounded text-xs ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                    ${user.is_active ? 'Active' : 'Disabled'}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-sm">
                                <span class="px-2 py-1 rounded text-xs ${user.is_superuser ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'}">
                                    ${user.is_superuser ? 'Admin' : 'User'}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-sm">
                                ${user.two_factor_enabled ? '<i class="fas fa-check-circle text-green-600"></i>' : '<i class="fas fa-times-circle text-red-600"></i>'}
                            </td>
                            <td class="px-4 py-3 text-sm">
                                <button onclick="toggleUserStatus('${user.id}', ${user.is_active})" 
                                        class="text-blue-600 hover:underline mr-2">
                                    ${user.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        container.innerHTML = '<p class="text-center text-red-600 py-4">Failed to load users</p>';
    }
    */
}

// Security Settings Tab
function showSecuritySettings(container) {
    container.innerHTML = `
        <div class="bg-white rounded-xl p-6 card-shadow mb-6">
            <h3 class="text-xl font-bold text-gray-800 mb-4">
                <i class="fas fa-shield-alt mr-2 text-blue-600"></i>Two-Factor Authentication Policy
            </h3>
            <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
                <div class="flex items-start">
                    <i class="fas fa-info-circle text-blue-600 mt-1 mr-3"></i>
                    <div>
                        <p class="font-medium text-blue-900">2FA is MANDATORY for all users</p>
                        <p class="text-sm text-blue-800 mt-1">All users must enable two-factor authentication before accessing the application.</p>
                    </div>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="border rounded-lg p-4">
                    <h4 class="font-bold text-gray-800 mb-2">
                        <i class="fas fa-lock mr-2 text-green-600"></i>Current Status
                    </h4>
                    <p class="text-sm text-gray-600 mb-3">2FA enforcement: <span class="font-bold text-green-600">ENABLED</span></p>
                    <p class="text-sm text-gray-600">New users must enable 2FA on first login</p>
                </div>
                
                <div class="border rounded-lg p-4">
                    <h4 class="font-bold text-gray-800 mb-2">
                        <i class="fas fa-users mr-2 text-blue-600"></i>User Compliance
                    </h4>
                    <p class="text-sm text-gray-600 mb-3">Check compliance in user list</p>
                    <button onclick="showAdminTab('users')" class="text-sm text-blue-600 hover:underline">
                        View Users →
                    </button>
                </div>
            </div>
        </div>
        
        <div class="bg-white rounded-xl p-6 card-shadow">
            <h3 class="text-xl font-bold text-gray-800 mb-4">
                <i class="fas fa-tachometer-alt mr-2 text-orange-600"></i>Rate Limiting
            </h3>
            <div class="space-y-3">
                <div class="flex justify-between items-center py-2 border-b">
                    <span class="text-gray-700">Login Attempts</span>
                    <span class="font-bold">5 per minute</span>
                </div>
                <div class="flex justify-between items-center py-2 border-b">
                    <span class="text-gray-700">API Requests</span>
                    <span class="font-bold">60 per minute</span>
                </div>
                <div class="flex justify-between items-center py-2 border-b">
                    <span class="text-gray-700">File Uploads</span>
                    <span class="font-bold">10 per minute</span>
                </div>
                <div class="flex justify-between items-center py-2">
                    <span class="text-gray-700">Account Lockout</span>
                    <span class="font-bold">15 minutes</span>
                </div>
            </div>
        </div>
    `;
}

// My 2FA Settings Tab
function showMy2FASettings(container) {
    container.innerHTML = `
        <div class="bg-white rounded-xl p-6 card-shadow">
            <h3 class="text-xl font-bold text-gray-800 mb-4">
                <i class="fas fa-mobile-alt mr-2 text-green-600"></i>My Two-Factor Authentication
            </h3>
            <div id="my-2fa-status">
                <div class="text-center py-4">
                    <div class="loader mx-auto"></div>
                    <p class="text-gray-500 mt-2">Loading 2FA status...</p>
                </div>
            </div>
        </div>
    `;
    
    load2FAStatus();
}

// Load current user's 2FA status
async function load2FAStatus() {
    const container = document.getElementById('my-2fa-status');
    
    try {
        const response = await api.get('/auth/2fa/status');
        const { enabled } = response.data;
        
        container.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center justify-between p-4 border rounded-lg ${enabled ? 'bg-green-50 border-green-300' : 'bg-yellow-50 border-yellow-300'}">
                    <div class="flex items-center">
                        <i class="fas ${enabled ? 'fa-check-circle text-green-600' : 'fa-exclamation-circle text-yellow-600'} text-2xl mr-3"></i>
                        <div>
                            <p class="font-bold text-gray-800">2FA Status: ${enabled ? 'Enabled' : 'Not Enabled'}</p>
                            <p class="text-sm text-gray-600">${enabled ? 'Your account is protected with 2FA' : 'You must enable 2FA'}</p>
                        </div>
                    </div>
                </div>
                
                ${enabled ? `
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p class="text-sm text-gray-700 mb-3">
                            <i class="fas fa-info-circle text-blue-600 mr-2"></i>
                            To reset your 2FA, you'll need to disable it first (requires password + current 2FA code).
                        </p>
                        <button onclick="disable2FA()" class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
                            <i class="fas fa-times-circle mr-2"></i>Disable 2FA
                        </button>
                    </div>
                ` : `
                    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p class="text-sm text-red-700 font-medium mb-3">
                            <i class="fas fa-exclamation-triangle mr-2"></i>
                            2FA is mandatory. Please set it up now.
                        </p>
                        <button onclick="initiate2FASetup()" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
                            <i class="fas fa-lock mr-2"></i>Set Up 2FA
                        </button>
                    </div>
                `}
            </div>
        `;
    } catch (error) {
        container.innerHTML = '<p class="text-center text-red-600 py-4">Failed to load 2FA status</p>';
    }
}

// Disable 2FA (requires verification)
async function disable2FA() {
    const password = prompt('Enter your password to disable 2FA:');
    if (!password) return;
    
    const token = prompt('Enter current 2FA code or backup code:');
    if (!token) return;
    
    try {
        await api.post('/auth/2fa/disable', { password, token });
        alert('✅ 2FA disabled successfully. You must enable it again immediately.');
        load2FAStatus();
        
        // Force re-setup
        setTimeout(() => initiate2FASetup(), 1000);
    } catch (error) {
        alert(error.response?.data?.detail || 'Failed to disable 2FA');
    }
}

// Update auth section to show admin link
const originalUpdateAuthSection = window.updateAuthSection;
window.updateAuthSection = function(user) {
    if (originalUpdateAuthSection) originalUpdateAuthSection(user);
    
    currentUser = user;
    const authSection = document.getElementById('auth-section');
    
    if (user.is_superuser) {
        const adminBtn = document.createElement('button');
        adminBtn.onclick = showAdminPanel;
        adminBtn.className = 'bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg transition mr-2';
        adminBtn.innerHTML = '<i class="fas fa-cog mr-2"></i>Admin';
        authSection.insertBefore(adminBtn, authSection.firstChild);
    }
};

// Override login to check 2FA on success
const originalHandleAuth = window.handleAuth;
window.handleAuth = async function(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const fullName = document.getElementById('full_name')?.value;
    const organization = document.getElementById('organization')?.value;
    
    // Validate password confirmation for registration
    if (!isLoginMode) {
        const confirmPassword = document.getElementById('confirm_password').value;
        if (password !== confirmPassword) {
            alert('❌ Passwords do not match!');
            return;
        }
        
        // Validate password strength
        if (password.length < 8) {
            alert('❌ Password must be at least 8 characters long');
            return;
        }
        if (!/[A-Z]/.test(password)) {
            alert('❌ Password must contain at least one uppercase letter');
            return;
        }
        if (!/[a-z]/.test(password)) {
            alert('❌ Password must contain at least one lowercase letter');
            return;
        }
        if (!/[0-9]/.test(password)) {
            alert('❌ Password must contain at least one number');
            return;
        }
        if (!/[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/`~]/.test(password)) {
            alert('❌ Password must contain at least one special character');
            return;
        }
    }
    
    try {
        let response;
        if (isLoginMode) {
            // Login
            response = await axios.post(`${API_BASE}/auth/login`, { email, password });
            accessToken = response.data.access_token;
            refreshToken = response.data.refresh_token;
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('refreshToken', refreshToken);
            
            closeAuthModal();
            
            // Check if 2FA is required
            const needs2FA = await check2FARequired();
            if (!needs2FA) {
                await checkAuth();
            }
        } else {
            // Register
            response = await axios.post(`${API_BASE}/auth/register`, {
                email,
                password,
                full_name: fullName,
                organization: organization
            });
            
            alert('✅ Registration successful! Please login.');
            showLogin();
        }
    } catch (error) {
        if (error.response?.status === 403 && error.response?.headers?.['x-require-2fa']) {
            // 2FA required
            const code = prompt('Enter your 6-digit 2FA code:');
            if (code) {
                try {
                    const response = await axios.post(`${API_BASE}/auth/login`, {
                        email,
                        password,
                        totp_code: code
                    });
                    accessToken = response.data.access_token;
                    refreshToken = response.data.refresh_token;
                    localStorage.setItem('accessToken', accessToken);
                    localStorage.setItem('refreshToken', refreshToken);
                    
                    closeAuthModal();
                    await checkAuth();
                } catch (error2) {
                    alert(error2.response?.data?.detail || 'Invalid 2FA code');
                }
            }
        } else {
            // Better error messages
            let errorMsg = 'Authentication failed';
            if (error.response?.data?.detail) {
                errorMsg = error.response.data.detail;
            } else if (error.response?.status === 401) {
                errorMsg = 'Invalid email or password';
            } else if (error.response?.status === 422) {
                errorMsg = 'Invalid input. Please check your information.';
            } else if (error.response?.status === 400) {
                errorMsg = error.response?.data?.detail || 'Bad request. Please check your input.';
            } else if (!error.response) {
                errorMsg = '❌ Cannot connect to server. Please check:

1. Backend is running at: ' + API_BASE + '
2. CORS is properly configured
3. Your internet connection

Try again in a few moments.';
            }
            alert(errorMsg);
        }
    }
};

// Expose functions globally for onclick handlers (MUST be before DOMContentLoaded)
window.showLogin = showLogin;
window.showRegister = showRegister;
window.toggleAuthMode = toggleAuthMode;
window.closeAuthModal = closeAuthModal;
window.togglePasswordVisibility = togglePasswordVisibility;
window.handleAuth = handleAuth;
window.showDashboard = showDashboard;
window.loadBatches = loadBatches;
window.processBatch = processBatch;
window.exportBatch = exportBatch;
window.closeEntityModal = closeEntityModal;
window.showAdminPanel = showAdminPanel;
window.showSettings = showSettings;
window.appJsLoaded = true;

console.log('✅ Admin Panel & Mandatory 2FA Loaded');
console.log('✅ app.js fully loaded - real functions now active');

// Check 2FA on page load
document.addEventListener('DOMContentLoaded', () => {
    if (accessToken) {
        check2FARequired().then(needs2FA => {
            if (!needs2FA) {
                checkAuth();
            }
        });
    } else {
        showLanding();
    }
});
