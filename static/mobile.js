// Мобильные функции
class MobileApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupTouchGestures();
        this.setupPullToRefresh();
        this.detectDevice();
        this.setupOfflineSupport();
    }

    setupTouchGestures() {
        // Свайп для навигации
        let startX, startY;

        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            if (!startX || !startY) return;

            const endX = e.changedTouches[0].clientX;
            const endY = e.changedTouches[0].clientY;

            const diffX = endX - startX;
            const diffY = endY - startY;

            // Горизонтальный свайп (для навигации между шаблонами)
            if (Math.abs(diffX) > 50 && Math.abs(diffX) > Math.abs(diffY)) {
                if (diffX > 0) {
                    this.handleSwipeRight();
                } else {
                    this.handleSwipeLeft();
                }
            }

            startX = null;
            startY = null;
        });
    }

    handleSwipeRight() {
        // Переход к предыдущему шаблону в галерее
        const prevBtn = document.querySelector('.pagination-prev');
        if (prevBtn) prevBtn.click();
    }

    handleSwipeLeft() {
        // Переход к следующему шаблону в галерее
        const nextBtn = document.querySelector('.pagination-next');
        if (nextBtn) nextBtn.click();
    }

    setupPullToRefresh() {
        // Простая реализация pull-to-refresh
        let startY = 0;
        let pullDistance = 0;

        document.addEventListener('touchstart', (e) => {
            if (window.scrollY === 0) {
                startY = e.touches[0].pageY;
            }
        });

        document.addEventListener('touchmove', (e) => {
            if (!startY) return;

            const currentY = e.touches[0].pageY;
            pullDistance = currentY - startY;

            if (pullDistance > 0) {
                e.preventDefault();
                this.showPullIndicator(pullDistance);
            }
        });

        document.addEventListener('touchend', () => {
            if (pullDistance > 100) {
                this.refreshContent();
            }
            this.hidePullIndicator();
            startY = 0;
            pullDistance = 0;
        });
    }

    showPullIndicator(distance) {
        let indicator = document.getElementById('pull-refresh-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'pull-refresh-indicator';
            indicator.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 60px;
                background: linear-gradient(45deg, #e94560, #ff7b54);
                display: flex;
                align-items: center;
                justify-content: center;
                transform: translateY(-100%);
                transition: transform 0.3s;
                z-index: 10000;
                color: white;
                font-weight: bold;
            `;
            document.body.appendChild(indicator);
        }

        const progress = Math.min(distance / 100, 1);
        indicator.style.transform = `translateY(${progress * 60 - 60}px)`;
        indicator.textContent = progress > 0.7 ? 'Отпустите для обновления' : 'Потяните для обновления';
    }

    hidePullIndicator() {
        const indicator = document.getElementById('pull-refresh-indicator');
        if (indicator) {
            indicator.style.transform = 'translateY(-100%)';
            setTimeout(() => indicator.remove(), 300);
        }
    }

    async refreshContent() {
        // Обновляем контент страницы
        if (window.location.pathname === '/gallery') {
            window.location.reload();
        } else {
            // Для других страниц можно сделать AJAX обновление
            const event = new Event('refreshContent');
            window.dispatchEvent(event);
        }
    }

    detectDevice() {
        const userAgent = navigator.userAgent;
        const isMobile = /Mobile|Android|iPhone|iPad|iPod/i.test(userAgent);

        if (isMobile) {
            document.body.classList.add('mobile-device');

            // Добавляем touch класс для лучшей обработки касаний
            document.documentElement.classList.add('touch-device');

            // Сохраняем информацию об устройстве
            localStorage.setItem('device_type', 'mobile');
        } else {
            document.body.classList.add('desktop-device');
            localStorage.setItem('device_type', 'desktop');
        }
    }

    setupOfflineSupport() {
        // Проверяем статус сети
        window.addEventListener('online', this.handleOnline);
        window.addEventListener('offline', this.handleOffline);

        // Периодическая проверка соединения
        setInterval(() => {
            if (!navigator.onLine) {
                this.showOfflineBanner();
            }
        }, 30000);
    }

    handleOnline() {
        document.body.classList.remove('offline');
        document.body.classList.add('online');

        // Скрываем оффлайн баннер если есть
        const offlineBanner = document.getElementById('offline-banner');
        if (offlineBanner) {
            offlineBanner.remove();
        }

        // Показываем уведомление о восстановлении
        if (window.app) {
            window.app.showMessage('Соединение восстановлено', 'success');
        }
    }

    handleOffline() {
        document.body.classList.remove('online');
        document.body.classList.add('offline');
        this.showOfflineBanner();
    }

    showOfflineBanner() {
        if (document.getElementById('offline-banner')) return;

        const banner = document.createElement('div');
        banner.id = 'offline-banner';
        banner.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        `;

        banner.innerHTML = `
            <span>📶 Нет соединения</span>
            <button onclick="this.parentElement.remove()"
                    style="background:none;border:none;color:white;cursor:pointer">
                ✕
            </button>
        `;

        document.body.appendChild(banner);
    }

    // Оптимизация для мобильных
    optimizeForMobile() {
        // Ленивая загрузка изображений
        this.setupLazyLoading();

        // Предотвращение масштабирования при фокусе на input
        this.preventZoomOnFocus();

        // Улучшение скролла
        this.improveScrolling();
    }

    setupLazyLoading() {
        const images = document.querySelectorAll('img[data-src]');

        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        });

        images.forEach(img => imageObserver.observe(img));
    }

    preventZoomOnFocus() {
        document.addEventListener('focusin', (e) => {
            if (e.target.matches('input, textarea, select')) {
                document.body.style.fontSize = '16px';
            }
        });

        document.addEventListener('focusout', () => {
            document.body.style.fontSize = '';
        });
    }

    improveScrolling() {
        // Добавляем плавный скролл
        document.documentElement.style.scrollBehavior = 'smooth';

        // Предотвращаем скачки при скролле на iOS
        document.addEventListener('touchmove', (e) => {
            if (e.target.matches('input, textarea, select')) return;
            e.preventDefault();
        }, { passive: false });
    }

    // Функция для вибрации (если поддерживается)
    vibrate(pattern = 50) {
        if ('vibrate' in navigator) {
            navigator.vibrate(pattern);
        }
    }

    // Обработка hardware back button на Android
    setupBackButton() {
        if (window.history && window.history.pushState) {
            window.history.pushState(null, null, window.location.href);

            window.addEventListener('popstate', () => {
                window.history.pushState(null, null, window.location.href);
                // Можно добавить подтверждение выхода
                if (confirm('Выйти из приложения?')) {
                    navigator.app && navigator.app.exitApp && navigator.app.exitApp();
                }
            });
        }
    }
}

// Инициализация мобильного приложения
let mobileApp;

document.addEventListener('DOMContentLoaded', () => {
    mobileApp = new MobileApp();
    mobileApp.optimizeForMobile();

    // Добавляем обработчик для аппаратной кнопки "Назад"
    if (/Android/i.test(navigator.userAgent)) {
        mobileApp.setupBackButton();
    }
});

// Экспортируем глобально
window.mobileApp = mobileApp;