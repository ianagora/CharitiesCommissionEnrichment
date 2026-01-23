import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/cloudflare-pages'

type Bindings = {
  API_BASE_URL: string
}

const app = new Hono<{ Bindings: Bindings }>()

// Security Headers Middleware
app.use('*', async (c, next) => {
  await next()
  
  // Set security headers
  c.header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self' https://charitiescommissionenrichment-production.up.railway.app; frame-ancestors 'none'; form-action 'self'; base-uri 'self'")
  c.header('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload')
  c.header('X-Frame-Options', 'DENY')
  c.header('X-Content-Type-Options', 'nosniff')
  c.header('Referrer-Policy', 'strict-origin-when-cross-origin')
  c.header('Permissions-Policy', 'geolocation=(), microphone=(), camera=(), payment=(), usb=()')
  // Removed COEP to allow CDN resources
  c.header('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
  c.header('Cross-Origin-Resource-Policy', 'cross-origin')
})

// Enable CORS
app.use('*', cors())

// Serve static files
app.use('/static/*', serveStatic())

// API proxy to backend
app.all('/api/*', async (c) => {
  const apiBaseUrl = c.env.API_BASE_URL || 'http://localhost:8000'
  const path = c.req.path
  const url = `${apiBaseUrl}${path}`
  
  const headers = new Headers(c.req.raw.headers)
  headers.delete('host')
  
  try {
    const response = await fetch(url, {
      method: c.req.method,
      headers,
      body: c.req.method !== 'GET' && c.req.method !== 'HEAD' 
        ? await c.req.raw.clone().arrayBuffer() 
        : undefined,
    })
    
    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    })
  } catch (error) {
    return c.json({ error: 'Backend service unavailable' }, 503)
  }
})

// Main page
app.get('/', (c) => {
  return c.html(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Charity Commission Data Enrichment Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/axios@1.6.0/dist/axios.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <!-- Critical: Define global functions immediately to prevent onclick errors -->
    <script>
        // API Configuration
        const API_BASE = 'https://charitiescommissionenrichment-production.up.railway.app/api/v1';
        let accessToken = localStorage.getItem('accessToken');
        let refreshToken = localStorage.getItem('refreshToken');
        let isLoginMode = true;
        
        // Define showLogin IMMEDIATELY inline (not waiting for external script)
        window.showLogin = function() {
            console.log('✅ showLogin called (inline version)');
            isLoginMode = true;
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.classList.remove('hidden');
                document.getElementById('auth-title').textContent = 'Login';
                document.getElementById('auth-btn-text').textContent = 'Login';
                document.getElementById('auth-switch-text').textContent = "Don't have an account?";
                document.getElementById('auth-switch-btn').textContent = 'Register';
                document.getElementById('name-field').classList.add('hidden');
                document.getElementById('organization-field').classList.add('hidden');
                document.getElementById('confirm-password-field').classList.add('hidden');
                document.getElementById('password-strength').classList.add('hidden');
            } else {
                console.error('auth-modal not found');
            }
        };
        
        window.showRegister = function() {
            console.log('✅ showRegister called (inline version)');
            isLoginMode = false;
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.classList.remove('hidden');
                document.getElementById('auth-title').textContent = 'Register';
                document.getElementById('auth-btn-text').textContent = 'Register';
                document.getElementById('auth-switch-text').textContent = 'Already have an account?';
                document.getElementById('auth-switch-btn').textContent = 'Login';
                document.getElementById('name-field').classList.remove('hidden');
                document.getElementById('organization-field').classList.remove('hidden');
                document.getElementById('confirm-password-field').classList.remove('hidden');
                document.getElementById('password-strength').classList.remove('hidden');
            }
        };
        
        window.toggleAuthMode = function() {
            if (isLoginMode) {
                window.showRegister();
            } else {
                window.showLogin();
            }
        };
        
        window.closeAuthModal = function() {
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.classList.add('hidden');
                document.getElementById('auth-form').reset();
            }
        };
        
        window.togglePasswordVisibility = function(fieldId) {
            const field = document.getElementById(fieldId);
            const icon = document.getElementById(fieldId + '-icon');
            if (field && icon) {
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
        };
        
        // Handle authentication (login/register)
        window.handleAuth = async function(event) {
            event.preventDefault();
            console.log('✅ handleAuth called');
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            try {
                if (isLoginMode) {
                    // Login
                    console.log('Logging in...');
                    const response = await axios.post(API_BASE + '/auth/login', { email, password });
                    accessToken = response.data.access_token;
                    refreshToken = response.data.refresh_token;
                    localStorage.setItem('accessToken', accessToken);
                    localStorage.setItem('refreshToken', refreshToken);
                    console.log('✅ Login successful');
                } else {
                    // Register
                    console.log('Registering...');
                    const full_name = document.getElementById('full_name').value;
                    const organization = document.getElementById('organization')?.value;
                    await axios.post(API_BASE + '/auth/register', { 
                        email, 
                        password, 
                        full_name,
                        organization 
                    });
                    // Auto-login after registration
                    const response = await axios.post(API_BASE + '/auth/login', { email, password });
                    accessToken = response.data.access_token;
                    refreshToken = response.data.refresh_token;
                    localStorage.setItem('accessToken', accessToken);
                    localStorage.setItem('refreshToken', refreshToken);
                    console.log('✅ Registration successful, logged in');
                }
                
                window.closeAuthModal();
                
                // Reload page to initialize app.js with authentication
                console.log('Reloading page...');
                window.location.reload();
                
            } catch (error) {
                console.error('Auth error:', error);
                let errorMsg = 'Authentication failed';
                if (error.response?.data?.detail) {
                    errorMsg = error.response.data.detail;
                } else if (error.response?.status === 401) {
                    errorMsg = 'Invalid email or password';
                } else if (!error.response) {
                    errorMsg = 'Cannot connect to server. Please check your connection.';
                }
                alert(errorMsg);
            }
        };
        
        console.log('✅ Critical inline functions defined');
        console.log('window.showLogin:', typeof window.showLogin);
        console.log('window.handleAuth:', typeof window.handleAuth);
    </script>
    <style>
        .gradient-bg {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        }
        .card-shadow {
            box-shadow: 0 10px 40px -10px rgba(0,0,0,0.1);
        }
        .status-matched { color: #10b981; }
        .status-pending { color: #f59e0b; }
        .status-no-match { color: #ef4444; }
        .status-review { color: #8b5cf6; }
        .animate-fade-in {
            animation: fadeIn 0.3s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .loader {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #3498db;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Navigation -->
    <nav class="gradient-bg text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 py-4">
            <div class="flex justify-between items-center">
                <div class="flex items-center space-x-3">
                    <i class="fas fa-building text-2xl"></i>
                    <h1 class="text-xl font-bold">Charity Commission Data Enrichment</h1>
                </div>
                <div id="auth-section" class="flex items-center space-x-4">
                    <button id="nav-login-btn" class="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition">
                        <i class="fas fa-sign-in-alt mr-2"></i>Login
                    </button>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 py-8">
        <!-- Login/Register Modal -->
        <div id="auth-modal" class="hidden fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div class="bg-white rounded-xl p-8 max-w-md w-full mx-4 card-shadow animate-fade-in">
                <div class="flex justify-between items-center mb-6">
                    <h2 id="auth-title" class="text-2xl font-bold text-gray-800">Login</h2>
                    <button onclick="closeAuthModal()" class="text-gray-500 hover:text-gray-700">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
                <form id="auth-form" onsubmit="handleAuth(event)">
                    <div id="name-field" class="hidden mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                        <input type="text" id="full_name" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div id="organization-field" class="hidden mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Organization (Optional)</label>
                        <input type="text" id="organization" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                        <input type="email" id="email" required class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                        <div class="relative">
                            <input type="password" id="password" required class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 pr-10">
                            <button type="button" onclick="togglePasswordVisibility('password')" class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700">
                                <i id="password-icon" class="fas fa-eye"></i>
                            </button>
                        </div>
                        <div id="password-strength" class="hidden mt-2 text-sm"></div>
                    </div>
                    <div id="confirm-password-field" class="hidden mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Confirm Password</label>
                        <div class="relative">
                            <input type="password" id="confirm_password" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 pr-10">
                            <button type="button" onclick="togglePasswordVisibility('confirm_password')" class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700">
                                <i id="confirm_password-icon" class="fas fa-eye"></i>
                            </button>
                        </div>
                        <div id="password-match" class="mt-2 text-sm"></div>
                    </div>
                    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium transition">
                        <span id="auth-btn-text">Login</span>
                    </button>
                    <p class="text-center mt-4 text-gray-600">
                        <span id="auth-switch-text">Don't have an account?</span>
                        <button type="button" onclick="toggleAuthMode()" class="text-blue-600 hover:underline ml-1" id="auth-switch-btn">Register</button>
                    </p>
                </form>
            </div>
        </div>

        <!-- Dashboard (shown when logged in) -->
        <div id="dashboard" class="hidden">
            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white rounded-xl p-6 card-shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm">Total Batches</p>
                            <p id="stat-batches" class="text-3xl font-bold text-gray-800">0</p>
                        </div>
                        <div class="bg-blue-100 p-3 rounded-lg">
                            <i class="fas fa-folder text-blue-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-xl p-6 card-shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm">Total Entities</p>
                            <p id="stat-entities" class="text-3xl font-bold text-gray-800">0</p>
                        </div>
                        <div class="bg-green-100 p-3 rounded-lg">
                            <i class="fas fa-building text-green-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-xl p-6 card-shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm">Matched</p>
                            <p id="stat-matched" class="text-3xl font-bold text-green-600">0</p>
                        </div>
                        <div class="bg-green-100 p-3 rounded-lg">
                            <i class="fas fa-check-circle text-green-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-xl p-6 card-shadow">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm">Pending Review</p>
                            <p id="stat-pending" class="text-3xl font-bold text-yellow-600">0</p>
                        </div>
                        <div class="bg-yellow-100 p-3 rounded-lg">
                            <i class="fas fa-clock text-yellow-600 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Upload Section -->
            <div class="bg-white rounded-xl p-6 card-shadow mb-8">
                <h2 class="text-xl font-bold text-gray-800 mb-4">
                    <i class="fas fa-upload mr-2 text-blue-600"></i>Upload New Batch
                </h2>
                <form id="upload-form" onsubmit="handleUpload(event)" class="space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Batch Name</label>
                            <input type="text" id="batch-name" required class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Name Column</label>
                            <input type="text" id="name-column" value="name" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">File (CSV/Excel)</label>
                            <input type="file" id="batch-file" accept=".csv,.xlsx,.xls" required class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500">
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Description (optional)</label>
                        <textarea id="batch-description" rows="2" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"></textarea>
                    </div>
                    <button type="submit" id="upload-btn" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition">
                        <i class="fas fa-cloud-upload-alt mr-2"></i>Upload & Create Batch
                    </button>
                </form>
            </div>

            <!-- Batches Table -->
            <div class="bg-white rounded-xl p-6 card-shadow">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-gray-800">
                        <i class="fas fa-list mr-2 text-blue-600"></i>Your Batches
                    </h2>
                    <button onclick="loadBatches()" class="text-blue-600 hover:text-blue-700">
                        <i class="fas fa-sync-alt mr-1"></i>Refresh
                    </button>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Name</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Status</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Progress</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Created</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="batches-table">
                            <tr>
                                <td colspan="5" class="px-4 py-8 text-center text-gray-500">
                                    <div class="loader mx-auto mb-2"></div>
                                    Loading batches...
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Batch Detail View -->
        <div id="batch-detail" class="hidden">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <button onclick="showDashboard()" class="text-blue-600 hover:text-blue-700 mb-2">
                        <i class="fas fa-arrow-left mr-2"></i>Back to Dashboard
                    </button>
                    <h2 id="batch-detail-title" class="text-2xl font-bold text-gray-800"></h2>
                </div>
                <div class="space-x-2">
                    <button onclick="processBatch()" id="process-btn" class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition">
                        <i class="fas fa-play mr-2"></i>Process
                    </button>
                    <button onclick="exportBatch('xlsx')" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition">
                        <i class="fas fa-file-excel mr-2"></i>Export Excel
                    </button>
                    <button onclick="exportBatch('csv')" class="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition">
                        <i class="fas fa-file-csv mr-2"></i>Export CSV
                    </button>
                </div>
            </div>

            <!-- Batch Stats -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
                <div class="bg-white rounded-lg p-4 card-shadow">
                    <p class="text-gray-500 text-sm">Total</p>
                    <p id="batch-total" class="text-2xl font-bold">0</p>
                </div>
                <div class="bg-white rounded-lg p-4 card-shadow">
                    <p class="text-gray-500 text-sm">Matched</p>
                    <p id="batch-matched" class="text-2xl font-bold text-green-600">0</p>
                </div>
                <div class="bg-white rounded-lg p-4 card-shadow">
                    <p class="text-gray-500 text-sm">No Match</p>
                    <p id="batch-no-match" class="text-2xl font-bold text-red-600">0</p>
                </div>
                <div class="bg-white rounded-lg p-4 card-shadow">
                    <p class="text-gray-500 text-sm">Review Needed</p>
                    <p id="batch-review" class="text-2xl font-bold text-yellow-600">0</p>
                </div>
                <div class="bg-white rounded-lg p-4 card-shadow">
                    <p class="text-gray-500 text-sm">Pending</p>
                    <p id="batch-pending" class="text-2xl font-bold text-gray-600">0</p>
                </div>
            </div>

            <!-- Entities Table -->
            <div class="bg-white rounded-xl p-6 card-shadow">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold text-gray-800">Entities</h3>
                    <div class="flex space-x-2">
                        <select id="status-filter" onchange="filterEntities()" class="px-3 py-2 border rounded-lg">
                            <option value="">All Statuses</option>
                            <option value="matched">Matched</option>
                            <option value="confirmed">Confirmed</option>
                            <option value="no_match">No Match</option>
                            <option value="multiple_matches">Multiple Matches</option>
                            <option value="pending">Pending</option>
                        </select>
                        <input type="text" id="entity-search" placeholder="Search..." onkeyup="filterEntities()" class="px-3 py-2 border rounded-lg">
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">#</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Original Name</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Resolved Name</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Charity #</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Status</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Confidence</th>
                                <th class="px-4 py-3 text-left text-sm font-medium text-gray-600">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="entities-table">
                            <tr>
                                <td colspan="7" class="px-4 py-8 text-center text-gray-500">
                                    Select a batch to view entities
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div id="pagination" class="flex justify-center mt-4 space-x-2"></div>
            </div>
        </div>

        <!-- Entity Detail Modal -->
        <div id="entity-modal" class="hidden fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div class="bg-white rounded-xl p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto card-shadow animate-fade-in">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-xl font-bold text-gray-800">Entity Details</h2>
                    <button onclick="closeEntityModal()" class="text-gray-500 hover:text-gray-700">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
                <div id="entity-details"></div>
            </div>
        </div>

        <!-- Landing Page (shown when not logged in) -->
        <div id="landing" class="text-center py-16">
            <div class="max-w-3xl mx-auto">
                <i class="fas fa-building text-6xl text-blue-600 mb-6"></i>
                <h2 class="text-4xl font-bold text-gray-800 mb-4">Charity Commission Data Enrichment Platform</h2>
                <p class="text-xl text-gray-600 mb-8">
                    Upload your entity data, automatically resolve to Charity Commission records, 
                    and build comprehensive ownership trees.
                </p>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                    <div class="bg-white rounded-xl p-6 card-shadow">
                        <div class="bg-blue-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-upload text-2xl text-blue-600"></i>
                        </div>
                        <h3 class="text-lg font-bold text-gray-800 mb-2">Batch Upload</h3>
                        <p class="text-gray-600">Upload CSV or Excel files with entity names for processing</p>
                    </div>
                    <div class="bg-white rounded-xl p-6 card-shadow">
                        <div class="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-magic text-2xl text-green-600"></i>
                        </div>
                        <h3 class="text-lg font-bold text-gray-800 mb-2">Auto Resolution</h3>
                        <p class="text-gray-600">AI-powered matching to Charity Commission records</p>
                    </div>
                    <div class="bg-white rounded-xl p-6 card-shadow">
                        <div class="bg-purple-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-sitemap text-2xl text-purple-600"></i>
                        </div>
                        <h3 class="text-lg font-bold text-gray-800 mb-2">Ownership Trees</h3>
                        <p class="text-gray-600">Build recursive corporate ownership structures</p>
                    </div>
                </div>
                <button id="get-started-btn" class="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-xl font-bold text-lg transition">
                    <i class="fas fa-rocket mr-2"></i>Get Started
                </button>
            </div>
        </div>
    </main>

    <script src="/static/app.js?v=7a53c28"></script>
    <script>
        // Attach event listeners after DOM loads
        document.addEventListener('DOMContentLoaded', () => {
            console.log('✅ Attaching button listeners');
            
            // Login buttons
            const navLoginBtn = document.getElementById('nav-login-btn');
            const getStartedBtn = document.getElementById('get-started-btn');
            
            if (navLoginBtn) {
                navLoginBtn.addEventListener('click', () => {
                    console.log('Nav login clicked');
                    if (typeof window.showLogin === 'function') {
                        window.showLogin();
                    } else {
                        console.error('showLogin not defined');
                    }
                });
            }
            
            if (getStartedBtn) {
                getStartedBtn.addEventListener('click', () => {
                    console.log('Get started clicked');
                    if (typeof window.showLogin === 'function') {
                        window.showLogin();
                    } else {
                        console.error('showLogin not defined');
                    }
                });
            }
            
            console.log('✅ Button listeners attached');
            console.log('window.showLogin type:', typeof window.showLogin);
        });
    </script>
</body>
</html>
  `)
})

// Login page route
app.get('/login', (c) => {
  return c.redirect('/')
})

// Register page route
app.get('/register', (c) => {
  return c.redirect('/')
})

export default app
