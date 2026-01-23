/**
 * Charity Commission Data Enrichment Platform - Initialization Script
 * 
 * This file contains critical initialization code that must run before the DOM loads.
 * It defines global functions for authentication and modal handling.
 */

// API Configuration - Use Cloudflare Worker proxy (not direct backend)
const API_BASE = '/api/v1';
let accessToken = localStorage.getItem('accessToken');
let refreshToken = localStorage.getItem('refreshToken');
let isLoginMode = true;

// Define showLogin IMMEDIATELY (not waiting for external script)
window.showLogin = function() {
    console.log('showLogin called');
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
    console.log('showRegister called');
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

// Password validation constants
const PASSWORD_SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:\'",.<>?/';

function validatePassword(password) {
    const errors = [];
    if (password.length < 8) {
        errors.push('Password must be at least 8 characters long');
    }
    if (!/[A-Z]/.test(password)) {
        errors.push('Password must contain at least one uppercase letter');
    }
    if (!/[a-z]/.test(password)) {
        errors.push('Password must contain at least one lowercase letter');
    }
    if (!/[0-9]/.test(password)) {
        errors.push('Password must contain at least one number');
    }
    if (!/[!@#$%^&*()_+\-=\[\]{}|;:"',.<>?/]/.test(password)) {
        errors.push('Password must contain at least one special character');
    }
    return errors;
}

// Handle authentication (login/register)
window.handleAuth = async function(event) {
    event.preventDefault();
    console.log('handleAuth called, mode:', isLoginMode ? 'Login' : 'Register');
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    // Validate for registration
    if (!isLoginMode) {
        const full_name = document.getElementById('full_name').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        
        if (!full_name) {
            alert('Please enter your full name');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('Passwords do not match!');
            return;
        }
        
        // Password strength validation
        const passwordErrors = validatePassword(password);
        if (passwordErrors.length > 0) {
            alert(passwordErrors.join('\n'));
            return;
        }
    }
    
    try {
        if (isLoginMode) {
            // Login
            console.log('Logging in with:', email);
            const response = await axios.post(API_BASE + '/auth/login', { email, password });
            accessToken = response.data.access_token;
            refreshToken = response.data.refresh_token;
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('refreshToken', refreshToken);
            console.log('Login successful');
        } else {
            // Register
            console.log('Registering user:', email);
            const full_name = document.getElementById('full_name').value;
            const organization = document.getElementById('organization');
            const orgValue = organization ? organization.value : null;
            
            await axios.post(API_BASE + '/auth/register', { 
                email, 
                password, 
                full_name,
                organization: orgValue
            });
            console.log('Registration successful, now logging in...');
            
            // Auto-login after registration
            const response = await axios.post(API_BASE + '/auth/login', { email, password });
            accessToken = response.data.access_token;
            refreshToken = response.data.refresh_token;
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('refreshToken', refreshToken);
            console.log('Auto-login successful');
        }
        
        window.closeAuthModal();
        
        // Reload page to initialize app.js with authentication
        console.log('Reloading page to load dashboard...');
        window.location.reload();
        
    } catch (error) {
        console.error('Auth error:', error);
        console.error('Error details:', error.response ? error.response.data : 'No response');
        
        let errorMsg = 'Authentication failed';
        
        if (error.response && error.response.data && error.response.data.detail) {
            errorMsg = error.response.data.detail;
        } else if (error.response && error.response.status === 401) {
            errorMsg = 'Invalid email or password';
        } else if (error.response && error.response.status === 422) {
            errorMsg = 'Invalid input. Please check your information.';
            if (error.response.data && error.response.data.detail) {
                errorMsg += '\n' + JSON.stringify(error.response.data.detail);
            }
        } else if (error.response && error.response.status === 400) {
            errorMsg = (error.response.data && error.response.data.detail) || 'Bad request';
        } else if (!error.response) {
            errorMsg = 'Cannot connect to server. Please check your connection.';
        }
        
        alert(errorMsg);
    }
};

console.log('init.js loaded - critical functions defined');
