// app/static/js/service-worker.js

const CACHE_NAME = 'dnd-forge-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/css/responsive.css',
  '/static/js/main.js',
  '/static/js/auth.js',
  '/static/js/mobile.js',
  '/static/images/logo.png',
  '/manifest.json'
];

// Установка Service Worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Активация и очистка старых кэшей
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Стратегия кэширования: Network First, Fallback to Cache
self.addEventListener('fetch', event => {
  // Пропускаем non-GET запросы
  if (event.request.method !== 'GET') return;

  // Для API запросов используем network-first
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Клонируем response для кэширования
          const responseClone = response.clone();
          caches.open(CACHE_NAME)
            .then(cache => cache.put(event.request, responseClone));
          return response;
        })
        .catch(() => {
          return caches.match(event.request);
        })
    );
  } else {
    // Для статических ресурсов используем cache-first
    event.respondWith(
      caches.match(event.request)
        .then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }

          return fetch(event.request)
            .then(response => {
              // Проверяем валидность ответа
              if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
              }

              // Клонируем response
              const responseToCache = response.clone();

              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, responseToCache);
                });

              return response;
            });
        })
    );
  }
});

// Push уведомления
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'D&D Forge';
  const options = {
    body: data.body || 'У вас новое сообщение!',
    icon: '/static/images/icon-192.png',
    badge: '/static/images/badge.png',
    tag: 'dnd-forge-notification',
    renotify: true,
    actions: [
      {
        action: 'open',
        title: 'Открыть'
      },
      {
        action: 'close',
        title: 'Закрыть'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Клик по уведомлению
self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// Фоновая синхронизация
self.addEventListener('sync', event => {
  if (event.tag === 'sync-templates') {
    event.waitUntil(syncTemplates());
  }
});

async function syncTemplates() {
  // Здесь будет логика синхронизации
  console.log('Syncing templates...');
}

// Обработка сообщений
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});