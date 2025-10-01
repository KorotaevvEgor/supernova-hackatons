/**
 * Менеджер офлайн функциональности
 * Обеспечивает работу приложения без интернета и синхронизацию данных
 */

class OfflineManager {
    constructor() {
        this.dbName = 'UrbanControlOffline';
        this.dbVersion = 1;
        this.db = null;
        this.isOnline = navigator.onLine;
        this.init();
    }

    async init() {
        // Инициализация IndexedDB
        await this.initDB();
        
        // Регистрация Service Worker
        if ('serviceWorker' in navigator) {
            try {
                await navigator.serviceWorker.register('/static/js/sw.js');
                console.log('Service Worker зарегистрирован');
            } catch (error) {
                console.error('Ошибка регистрации Service Worker:', error);
            }
        }

        // Сохраняем начальное состояние сети для отслеживания изменений
        this.previousOnlineStatus = this.isOnline;

        // Подписка на события сети
        window.addEventListener('online', () => {
            const wasOffline = !this.isOnline;
            this.isOnline = true;
            
            // Показываем плашку только при изменении статуса
            if (wasOffline) {
                this.showNetworkStatus('online');
                this.syncOfflineData();
            }
        });

        window.addEventListener('offline', () => {
            const wasOnline = this.isOnline;
            this.isOnline = false;
            
            // Показываем плашку только при изменении статуса
            if (wasOnline) {
                this.showNetworkStatus('offline');
            }
        });

        // Не показываем плашку при загрузке - только при изменениях
        console.log(`Статус сети при загрузке: ${this.isOnline ? 'online' : 'offline'}`);
    }

    async initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Таблица для офлайн данных
                if (!db.objectStoreNames.contains('offlineData')) {
                    const store = db.createObjectStore('offlineData', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    store.createIndex('type', 'type', { unique: false });
                }

                // Таблица для геолокации
                if (!db.objectStoreNames.contains('geolocations')) {
                    const geoStore = db.createObjectStore('geolocations', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    geoStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
            };
        });
    }

    // Сохранение данных для офлайн отправки
    async saveOfflineData(url, method, data, type = 'form') {
        if (!this.db) await this.initDB();

        const transaction = this.db.transaction(['offlineData'], 'readwrite');
        const store = transaction.objectStore('offlineData');

        const offlineEntry = {
            url: url,
            method: method,
            data: data,
            type: type,
            timestamp: new Date().toISOString(),
            synced: false
        };

        return new Promise((resolve, reject) => {
            const request = store.add(offlineEntry);
            request.onsuccess = () => {
                console.log('Данные сохранены для офлайн отправки');
                this.showOfflineNotification('Данные сохранены и будут отправлены при подключении к интернету');
                resolve(request.result);
            };
            request.onerror = () => reject(request.error);
        });
    }

    // Синхронизация офлайн данных
    async syncOfflineData() {
        if (!this.isOnline || !this.db) return;

        const transaction = this.db.transaction(['offlineData'], 'readwrite');
        const store = transaction.objectStore('offlineData');

        const request = store.getAll();
        request.onsuccess = async () => {
            const offlineData = request.result.filter(item => !item.synced);
            
            for (const item of offlineData) {
                try {
                    const formData = new FormData();
                    
                    // Восстанавливаем данные формы
                    if (item.data) {
                        Object.keys(item.data).forEach(key => {
                            if (item.data[key] !== null && item.data[key] !== undefined) {
                                formData.append(key, item.data[key]);
                            }
                        });
                    }

                    const response = await fetch(item.url, {
                        method: item.method,
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        }
                    });

                    if (response.ok) {
                        // Отмечаем как синхронизированное
                        const updateTransaction = this.db.transaction(['offlineData'], 'readwrite');
                        const updateStore = updateTransaction.objectStore('offlineData');
                        
                        item.synced = true;
                        updateStore.put(item);
                        
                        console.log('Данные успешно синхронизированы:', item);
                    }
                } catch (error) {
                    console.error('Ошибка синхронизации данных:', error);
                }
            }

            // Показываем уведомление о завершении синхронизации
            if (offlineData.length > 0) {
                this.showOfflineNotification(`Синхронизировано ${offlineData.length} записей`);
            }
        };
    }

    // Сохранение геолокации
    async saveGeolocation(lat, lng, accuracy, description = '') {
        if (!this.db) await this.initDB();

        const transaction = this.db.transaction(['geolocations'], 'readwrite');
        const store = transaction.objectStore('geolocations');

        const geoEntry = {
            latitude: lat,
            longitude: lng,
            accuracy: accuracy,
            description: description,
            timestamp: new Date().toISOString()
        };

        return new Promise((resolve, reject) => {
            const request = store.add(geoEntry);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // Получение текущей геолокации
    async getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Геолокация не поддерживается'));
                return;
            }

            const options = {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            };

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const { latitude, longitude, accuracy } = position.coords;
                    
                    // Сохраняем геолокацию
                    await this.saveGeolocation(latitude, longitude, accuracy);
                    
                    resolve({
                        latitude: latitude,
                        longitude: longitude,
                        accuracy: accuracy
                    });
                },
                (error) => {
                    console.error('Ошибка получения геолокации:', error);
                    reject(error);
                },
                options
            );
        });
    }

    // Показ статуса сети
    showNetworkStatus(status) {
        let existingStatus = document.getElementById('network-status');
        if (existingStatus) {
            existingStatus.remove();
        }

        const statusBar = document.createElement('div');
        statusBar.id = 'network-status';
        statusBar.className = `fixed top-0 left-0 right-0 z-50 px-4 py-2 text-center text-sm font-medium transition-all duration-300 ${
            status === 'online' 
                ? 'bg-green-500 text-white' 
                : 'bg-red-500 text-white'
        }`;
        
        statusBar.innerHTML = `
            <i class="fas fa-${status === 'online' ? 'wifi' : 'wifi-slash'} mr-2"></i>
            ${status === 'online' ? 'Подключение восстановлено' : 'Работаем в офлайн режиме'}
        `;

        document.body.prepend(statusBar);

        // Скрываем статус "онлайн" через 3 секунды
        if (status === 'online') {
            setTimeout(() => {
                if (statusBar && statusBar.parentNode) {
                    statusBar.style.transform = 'translateY(-100%)';
                    setTimeout(() => statusBar.remove(), 300);
                }
            }, 3000);
        }
    }

    // Показ уведомления об офлайн действии
    showOfflineNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'fixed bottom-4 right-4 bg-blue-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 transform translate-y-full transition-transform duration-300';
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-cloud-upload-alt mr-3"></i>
                <span>${message}</span>
            </div>
        `;

        document.body.appendChild(notification);

        // Анимация появления
        setTimeout(() => {
            notification.style.transform = 'translateY(0)';
        }, 100);

        // Удаление через 4 секунды
        setTimeout(() => {
            notification.style.transform = 'translateY(full)';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    // Проверка, находимся ли мы в офлайн режиме
    isOffline() {
        return !this.isOnline;
    }

    // Обработка отправки форм
    async handleFormSubmit(form, url, method = 'POST') {
        const formData = new FormData(form);
        const data = {};
        
        // Конвертируем FormData в объект
        for (let [key, value] of formData.entries()) {
            data[key] = value;
        }

        if (this.isOffline()) {
            // Сохраняем данные для отложенной отправки
            await this.saveOfflineData(url, method, data, 'form');
            return { success: true, offline: true };
        } else {
            // Отправляем немедленно
            try {
                const response = await fetch(url, {
                    method: method,
                    body: formData
                });
                
                return { success: response.ok, offline: false, response: response };
            } catch (error) {
                // Если ошибка сети, сохраняем офлайн
                await this.saveOfflineData(url, method, data, 'form');
                return { success: true, offline: true, error: error };
            }
        }
    }
}

// Глобальный экземпляр менеджера
window.offlineManager = new OfflineManager();