document.addEventListener('DOMContentLoaded', function() {
    checkUserStatus();
});

async function checkUserStatus() {
    const username = localStorage.getItem('currentUsername');

    if (username) {
        try {
            const response = await fetch(`/check/${username}`);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const data = await response.json();

            if (data.exists) {
                showUserInfo();
            } else {
                showRegistrationForm();
                localStorage.removeItem('currentUsername');
            }
        } catch (error) {
            console.error('Error checking user:', error);
            showRegistrationForm();
            showMessage('Ошибка подключения к серверу', 'error');
        }
    } else {
        showRegistrationForm();
    }
}

function showRegistrationForm() {
    document.getElementById('user-form').style.display = 'block';
    document.getElementById('user-info').style.display = 'none';
    clearMessage();
}

function showUserInfo() {
    document.getElementById('user-form').style.display = 'none';
    document.getElementById('user-info').style.display = 'block';
    clearMessage();
}

async function registerUser() {
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!username || !email) {
        showMessage('Пожалуйста, заполните все поля', 'error');
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email })
        });

        if (response.ok) {
            localStorage.setItem('currentUsername', username);
            showUserInfo();
            showMessage('Пользователь успешно зарегистрирован!', 'success');
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Ошибка регистрации', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('Ошибка соединения с сервером', 'error');
    }
}

async function deleteUser() {
    const username = localStorage.getItem('currentUsername');

    if (!username) {
        showMessage('Пользователь не найден', 'error');
        return;
    }

    try {
        const response = await fetch(`/delete/${username}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            localStorage.removeItem('currentUsername');
            showRegistrationForm();
            document.getElementById('username').value = '';
            document.getElementById('email').value = '';
            showMessage('Данные пользователя удалены', 'success');
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Ошибка удаления', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('Ошибка соединения с сервером', 'error');
    }
}

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.style.display = 'block';

    if (type === 'success') {
        setTimeout(clearMessage, 5000);
    }
}

function clearMessage() {
    const messageDiv = document.getElementById('message');
    messageDiv.style.display = 'none';
    messageDiv.textContent = '';
}