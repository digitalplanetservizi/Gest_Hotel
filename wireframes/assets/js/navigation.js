/**
 * Navigazione wireframe Hotel Tempio V2
 */
document.addEventListener('DOMContentLoaded', function () {
    var role = sessionStorage.getItem('ht2_role') || 'admin';
    var roleLabel = role === 'admin' ? 'Amministratore' : 'Operatore';
    var avatarLetter = role === 'admin' ? 'A' : 'O';

    var page = document.body.getAttribute('data-page');
    if (page) {
        document.querySelectorAll('[data-nav="' + page + '"]').forEach(function (el) {
            el.classList.add('active');
            el.setAttribute('aria-current', 'page');
        });
    }

    if (role === 'operatore') {
        document.querySelectorAll('.admin-only').forEach(function (el) {
            el.classList.add('disabled');
            if (el.closest('#sidebar')) el.style.display = 'none';
        });
        document.querySelectorAll('.operatore-only').forEach(function (el) {
            el.style.display = '';
        });
    } else {
        document.querySelectorAll('.operatore-only').forEach(function (el) {
            el.style.display = 'none';
        });
    }

    document.querySelectorAll('[data-role-label]').forEach(function (el) {
        el.textContent = roleLabel;
    });
    document.querySelectorAll('[data-role-avatar]').forEach(function (el) {
        el.textContent = avatarLetter;
    });

    var toggleBtn = document.getElementById('sidebar-toggle');
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('-translate-x-full');
            if (overlay) overlay.classList.toggle('hidden');
        });
    }

    var loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var email = (document.getElementById('login-email') || {}).value || '';
            sessionStorage.setItem('ht2_role', email.indexOf('operatore') >= 0 ? 'operatore' : 'admin');
            window.location.href = 'dashboard.html';
        });
    }
});
