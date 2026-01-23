/**
 * Charity Commission Data Enrichment Platform - Event Listeners
 * 
 * This file attaches event listeners to DOM elements.
 * Must be loaded after the DOM is ready.
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Setting up event listeners');
    
    // Login/Auth buttons
    var navLoginBtn = document.getElementById('nav-login-btn');
    var getStartedBtn = document.getElementById('get-started-btn');
    var closeAuthModalBtn = document.getElementById('close-auth-modal');
    var authSwitchBtn = document.getElementById('auth-switch-btn');
    var authForm = document.getElementById('auth-form');
    var togglePasswordBtn = document.getElementById('toggle-password');
    var toggleConfirmPasswordBtn = document.getElementById('toggle-confirm-password');
    
    if (navLoginBtn) {
        navLoginBtn.addEventListener('click', function() {
            if (typeof window.showLogin === 'function') {
                window.showLogin();
            }
        });
    }
    
    if (getStartedBtn) {
        getStartedBtn.addEventListener('click', function() {
            if (typeof window.showLogin === 'function') {
                window.showLogin();
            }
        });
    }
    
    if (closeAuthModalBtn) {
        closeAuthModalBtn.addEventListener('click', function() {
            if (typeof window.closeAuthModal === 'function') {
                window.closeAuthModal();
            }
        });
    }
    
    if (authSwitchBtn) {
        authSwitchBtn.addEventListener('click', function() {
            if (typeof window.toggleAuthMode === 'function') {
                window.toggleAuthMode();
            }
        });
    }
    
    if (authForm) {
        authForm.addEventListener('submit', function(e) {
            if (typeof window.handleAuth === 'function') {
                window.handleAuth(e);
            }
        });
    }
    
    if (togglePasswordBtn) {
        togglePasswordBtn.addEventListener('click', function() {
            if (typeof window.togglePasswordVisibility === 'function') {
                window.togglePasswordVisibility('password');
            }
        });
    }
    
    if (toggleConfirmPasswordBtn) {
        toggleConfirmPasswordBtn.addEventListener('click', function() {
            if (typeof window.togglePasswordVisibility === 'function') {
                window.togglePasswordVisibility('confirm_password');
            }
        });
    }
    
    // Dashboard buttons
    var refreshBatchesBtn = document.getElementById('refresh-batches');
    var uploadForm = document.getElementById('upload-form');
    var backToDashboardBtn = document.getElementById('back-to-dashboard');
    var processBtn = document.getElementById('process-btn');
    var exportXlsxBtn = document.getElementById('export-xlsx-btn');
    var exportCsvBtn = document.getElementById('export-csv-btn');
    var closeEntityModalBtn = document.getElementById('close-entity-modal');
    var statusFilter = document.getElementById('status-filter');
    var entitySearch = document.getElementById('entity-search');
    
    if (refreshBatchesBtn) {
        refreshBatchesBtn.addEventListener('click', function() {
            if (typeof window.loadBatches === 'function') {
                window.loadBatches();
            }
        });
    }
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            if (typeof window.handleUpload === 'function') {
                window.handleUpload(e);
            }
        });
    }
    
    if (backToDashboardBtn) {
        backToDashboardBtn.addEventListener('click', function() {
            if (typeof window.showDashboard === 'function') {
                window.showDashboard();
            }
        });
    }
    
    if (processBtn) {
        processBtn.addEventListener('click', function() {
            if (typeof window.processBatch === 'function') {
                window.processBatch();
            }
        });
    }
    
    if (exportXlsxBtn) {
        exportXlsxBtn.addEventListener('click', function() {
            if (typeof window.exportBatch === 'function') {
                window.exportBatch('xlsx');
            }
        });
    }
    
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', function() {
            if (typeof window.exportBatch === 'function') {
                window.exportBatch('csv');
            }
        });
    }
    
    if (closeEntityModalBtn) {
        closeEntityModalBtn.addEventListener('click', function() {
            if (typeof window.closeEntityModal === 'function') {
                window.closeEntityModal();
            }
        });
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            if (typeof window.filterEntities === 'function') {
                window.filterEntities();
            }
        });
    }
    
    if (entitySearch) {
        entitySearch.addEventListener('keyup', function() {
            if (typeof window.filterEntities === 'function') {
                window.filterEntities();
            }
        });
    }
    
    console.log('Event listeners attached');
});
