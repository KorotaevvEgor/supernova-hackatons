// Основной JavaScript для системы управления благоустройством

// Инициализация приложения
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Инициализация компонентов
    initMobileMenu();
    initNotifications();
    initGeolocation();
    initOfflineSupport();
    
    console.log('Система управления благоустройством загружена');
}

// Мобильное меню
function initMobileMenu() {
    const menuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (menuButton && mobileMenu) {
        menuButton.addEventListener('click', function() {
            mobileMenu.classList.toggle('open');
        });
    }
}

// Система уведомлений
function initNotifications() {
    // Проверка разрешений на уведомления
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// Показать уведомление
function showNotification(title, body, type = 'info') {
    // Web Notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: body,
            icon: '/static/img/moscow-logo.png'
        });
    }
    
    // Toast уведомление
    showToast(title, body, type);
}

// Toast уведомления
function showToast(title, message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 max-w-sm p-4 rounded-lg shadow-lg z-50 transition-all duration-300 transform translate-x-full`;
    
    let bgColor = 'bg-blue-500';
    let icon = 'fa-info-circle';
    
    switch(type) {
        case 'success':
            bgColor = 'bg-green-500';
            icon = 'fa-check-circle';
            break;
        case 'error':
            bgColor = 'bg-red-500';
            icon = 'fa-times-circle';
            break;
        case 'warning':
            bgColor = 'bg-yellow-500';
            icon = 'fa-exclamation-triangle';
            break;
    }
    
    toast.className += ` ${bgColor} text-white`;
    toast.innerHTML = `
        <div class="flex items-start">
            <i class="fas ${icon} text-lg mr-3 mt-0.5"></i>
            <div class="flex-1">
                <h4 class="font-semibold">${title}</h4>
                <p class="text-sm opacity-90">${message}</p>
            </div>
            <button class="ml-3 text-white opacity-70 hover:opacity-100" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Анимация появления
    setTimeout(() => {
        toast.classList.remove('translate-x-full');
    }, 100);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        toast.classList.add('translate-x-full');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Геолокация
let currentPosition = null;

function initGeolocation() {
    if ('geolocation' in navigator) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                currentPosition = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date()
                };
                console.log('Геолокация получена:', currentPosition);
            },
            function(error) {
                console.log('Ошибка геолокации:', error.message);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000 // 5 минут
            }
        );
    }
}

// Получить текущую позицию
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!('geolocation' in navigator)) {
            reject(new Error('Геолокация не поддерживается'));
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            position => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date()
                });
            },
            error => {
                reject(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    });
}

// Offline поддержка
function initOfflineSupport() {
    // Service Worker регистрация (если доступен)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('Service Worker зарегистрирован');
            })
            .catch(error => {
                console.log('Ошибка регистрации Service Worker:', error);
            });
    }
    
    // Обработка онлайн/офлайн событий
    window.addEventListener('online', function() {
        showToast('Соединение восстановлено', 'Синхронизация данных...', 'success');
        syncOfflineData();
    });
    
    window.addEventListener('offline', function() {
        showToast('Нет соединения', 'Работа в автономном режиме', 'warning');
    });
}

// Синхронизация офлайн данных
function syncOfflineData() {
    const offlineData = getOfflineData();
    if (offlineData.length > 0) {
        offlineData.forEach(async (data) => {
            try {
                await sendDataToServer(data);
                removeOfflineData(data.id);
            } catch (error) {
                console.log('Ошибка синхронизации:', error);
            }
        });
    }
}

// Сохранение данных в офлайн режиме
function saveOfflineData(data) {
    const offlineData = getOfflineData();
    data.id = Date.now().toString();
    data.timestamp = new Date().toISOString();
    offlineData.push(data);
    localStorage.setItem('offlineData', JSON.stringify(offlineData));
}

// Получение офлайн данных
function getOfflineData() {
    const data = localStorage.getItem('offlineData');
    return data ? JSON.parse(data) : [];
}

// Удаление синхронизированных данных
function removeOfflineData(id) {
    const offlineData = getOfflineData();
    const filtered = offlineData.filter(item => item.id !== id);
    localStorage.setItem('offlineData', JSON.stringify(filtered));
}

// Отправка данных на сервер
async function sendDataToServer(data) {
    const response = await fetch(data.endpoint, {
        method: data.method || 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data.payload)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
}

// Получение CSRF токена
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    return '';
}

// Утилиты для работы с формами
function submitForm(formElement, options = {}) {
    const formData = new FormData(formElement);
    const data = Object.fromEntries(formData.entries());
    
    // Добавляем геолокацию если требуется
    if (options.includeLocation && currentPosition) {
        data.latitude = currentPosition.latitude;
        data.longitude = currentPosition.longitude;
    }
    
    const requestData = {
        endpoint: formElement.action,
        method: formElement.method || 'POST',
        payload: data
    };
    
    if (navigator.onLine) {
        return sendDataToServer(requestData);
    } else {
        saveOfflineData(requestData);
        showToast('Данные сохранены', 'Будут отправлены при восстановлении связи', 'info');
        return Promise.resolve({ success: true, offline: true });
    }
}

// Загрузка и отображение данных
async function loadData(endpoint) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        showToast('Ошибка загрузки', 'Не удалось загрузить данные', 'error');
        throw error;
    }
}

// Экспорт основных функций для глобального использования
window.UrbanControl = {
    showNotification,
    showToast,
    getCurrentLocation,
    submitForm,
    loadData,
    saveOfflineData,
    syncOfflineData
};
