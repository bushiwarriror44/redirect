// Базовые утилиты для админ-панели
let csrfToken = null;

async function fetchCsrfToken() {
    try {
        const response = await fetch('/api/csrf-token', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        csrfToken = data.csrf_token;
    } catch (error) {
        console.error('Failed to fetch CSRF token:', error);
    }
}

document.addEventListener("DOMContentLoaded", async function () {
    await fetchCsrfToken();
});
