// Основной JavaScript для DND Template Creator
document.addEventListener('DOMContentLoaded', function() {
    console.log('DND Template Creator loaded');

    // Простая функция для показа сообщений
    window.showMessage = function(text, type = 'info') {
        const messageEl = document.createElement('div');
        messageEl.className = 'message message-' + type;
        messageEl.textContent = text;
        document.body.appendChild(messageEl);
        setTimeout(() => messageEl.remove(), 5000);
    };

    // Обработка формы входа
    const authForm = document.getElementById('auth-form');
    if (authForm) {
        authForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const response = await fetch('/api/users/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(Object.fromEntries(formData))
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(data.message, 'success');
                    setTimeout(() => window.location.href = data.redirect || '/', 1500);
                } else {
                    showMessage(data.message, 'error');
                }
            } catch (error) {
                showMessage('Ошибка соединения', 'error');
            }
        });
    }
});