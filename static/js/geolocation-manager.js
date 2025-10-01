/**
 * Менеджер геолокации для всех форм системы
 * Автоматически фиксирует геопозицию при внесении данных
 */

class GeolocationManager {
    constructor() {
        this.currentLocation = null;
        this.isTracking = false;
        this.accuracy = null;
        this.lastLocationTime = null;
        this.init();
    }

    init() {
        // Автоматически запускаем отслеживание при загрузке
        this.startLocationTracking();
        
        // Добавляем обработчики для всех форм
        this.attachFormHandlers();
        
        // Добавляем кнопки геолокации
        this.addGeolocationButtons();
    }

    // Запуск отслеживания геолокации
    async startLocationTracking() {
        if (!navigator.geolocation) {
            console.warn('Геолокация не поддерживается в этом браузере');
            return;
        }

        this.isTracking = true;
        
        const options = {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 300000 // 5 минут
        };

        // Получаем текущую позицию
        navigator.geolocation.getCurrentPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            options
        );

        // Запускаем отслеживание позиции
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            options
        );
    }

    // Успешное получение геолокации
    onLocationSuccess(position) {
        const { latitude, longitude, accuracy } = position.coords;
        
        this.currentLocation = {
            latitude: latitude,
            longitude: longitude,
            accuracy: accuracy,
            timestamp: new Date().toISOString()
        };

        this.accuracy = accuracy;
        this.lastLocationTime = new Date();

        // Обновляем UI индикаторы
        this.updateLocationIndicators();
        
        // Автоматически заполняем поля геолокации в формах
        this.autoFillLocationFields();

        console.log('Геолокация обновлена:', this.currentLocation);
    }

    // Ошибка получения геолокации
    onLocationError(error) {
        let message = 'Ошибка определения местоположения';
        
        switch(error.code) {
            case error.PERMISSION_DENIED:
                message = 'Доступ к геолокации запрещен. Разрешите доступ в настройках браузера.';
                break;
            case error.POSITION_UNAVAILABLE:
                message = 'Информация о местоположении недоступна';
                break;
            case error.TIMEOUT:
                message = 'Время ожидания определения местоположения истекло';
                break;
        }

        console.error('Ошибка геолокации:', message);
        this.showLocationError(message);
    }

    // Обновление индикаторов местоположения в UI
    updateLocationIndicators() {
        const indicators = document.querySelectorAll('.location-indicator');
        
        indicators.forEach(indicator => {
            if (this.currentLocation) {
                indicator.className = 'location-indicator inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800';
                indicator.innerHTML = `
                    <i class="fas fa-map-marker-alt mr-1"></i>
                    Местоположение определено
                    <span class="ml-1 text-gray-600">(±${Math.round(this.accuracy)}м)</span>
                `;
            } else {
                indicator.className = 'location-indicator inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800';
                indicator.innerHTML = `
                    <i class="fas fa-location-arrow mr-1 animate-spin"></i>
                    Определение местоположения...
                `;
            }
        });
    }

    // Автоматическое заполнение полей геолокации
    autoFillLocationFields() {
        if (!this.currentLocation) return;

        // Заполняем скрытые поля геолокации
        const latFields = document.querySelectorAll('input[name="latitude"], input[name="lat"], input[data-geo="latitude"]');
        const lngFields = document.querySelectorAll('input[name="longitude"], input[name="lng"], input[data-geo="longitude"]');
        const accuracyFields = document.querySelectorAll('input[name="accuracy"], input[data-geo="accuracy"]');

        latFields.forEach(field => {
            if (!field.value || field.dataset.autoFill !== 'false') {
                field.value = this.currentLocation.latitude.toFixed(6);
            }
        });

        lngFields.forEach(field => {
            if (!field.value || field.dataset.autoFill !== 'false') {
                field.value = this.currentLocation.longitude.toFixed(6);
            }
        });

        accuracyFields.forEach(field => {
            field.value = Math.round(this.accuracy);
        });
    }

    // Добавление кнопок геолокации к формам
    addGeolocationButtons() {
        const forms = document.querySelectorAll('form[data-geolocation="true"]');
        
        forms.forEach(form => {
            this.addGeolocationUI(form);
        });

        // Также добавляем к формам с координатными полями
        const geoForms = document.querySelectorAll('form:has(input[name="latitude"]), form:has(input[name="longitude"])');
        geoForms.forEach(form => {
            if (!form.dataset.geolocation) {
                this.addGeolocationUI(form);
            }
        });
    }

    // Добавление UI геолокации к форме
    addGeolocationUI(form) {
        const latField = form.querySelector('input[name="latitude"]');
        const lngField = form.querySelector('input[name="longitude"]');
        
        if (!latField || !lngField) return;

        // Создаем контейнер для геолокации
        const geoContainer = document.createElement('div');
        geoContainer.className = 'geolocation-container bg-gray-50 rounded-lg p-4 mt-4';
        
        geoContainer.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-medium text-gray-900 flex items-center">
                    <i class="fas fa-crosshairs text-blue-500 mr-2"></i>
                    Геолокация
                </h3>
                <div class="location-indicator"></div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">Широта</label>
                    <div class="relative">
                        <input type="number" step="any" name="latitude" 
                               class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                               placeholder="Автоматическое определение...">
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">Долгота</label>
                    <div class="relative">
                        <input type="number" step="any" name="longitude" 
                               class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                               placeholder="Автоматическое определение...">
                    </div>
                </div>
            </div>
            
            <div class="flex items-center justify-between">
                <button type="button" class="refresh-location-btn text-sm text-blue-600 hover:text-blue-800 font-medium">
                    <i class="fas fa-sync-alt mr-1"></i>
                    Обновить местоположение
                </button>
                <div class="location-timestamp text-xs text-gray-500"></div>
            </div>
            
            <input type="hidden" name="accuracy" class="accuracy-field">
            <input type="hidden" name="location_timestamp" class="timestamp-field">
        `;

        // Вставляем контейнер геолокации перед кнопками отправки
        const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitButton && submitButton.parentNode) {
            submitButton.parentNode.insertBefore(geoContainer, submitButton);
        } else {
            form.appendChild(geoContainer);
        }

        // Заменяем существующие поля на новые
        if (latField && latField.parentNode) {
            const newLatField = geoContainer.querySelector('input[name="latitude"]');
            if (latField.value) newLatField.value = latField.value;
            latField.parentNode.replaceChild(newLatField, latField);
        }
        
        if (lngField && lngField.parentNode) {
            const newLngField = geoContainer.querySelector('input[name="longitude"]');
            if (lngField.value) newLngField.value = lngField.value;
            lngField.parentNode.replaceChild(newLngField, lngField);
        }

        // Добавляем обработчик для кнопки обновления
        const refreshBtn = geoContainer.querySelector('.refresh-location-btn');
        refreshBtn.addEventListener('click', () => this.refreshLocation());

        // Обновляем поля если геолокация уже доступна
        if (this.currentLocation) {
            this.updateFormLocation(form);
        }
    }

    // Обновление геолокации в конкретной форме
    updateFormLocation(form) {
        const latField = form.querySelector('input[name="latitude"]');
        const lngField = form.querySelector('input[name="longitude"]');
        const accuracyField = form.querySelector('input[name="accuracy"]');
        const timestampField = form.querySelector('input[name="location_timestamp"]');
        const timestampDisplay = form.querySelector('.location-timestamp');

        if (this.currentLocation && latField && lngField) {
            latField.value = this.currentLocation.latitude.toFixed(6);
            lngField.value = this.currentLocation.longitude.toFixed(6);
            
            if (accuracyField) {
                accuracyField.value = Math.round(this.accuracy);
            }
            
            if (timestampField) {
                timestampField.value = this.currentLocation.timestamp;
            }
            
            if (timestampDisplay) {
                timestampDisplay.textContent = `Обновлено: ${new Date().toLocaleTimeString()}`;
            }
        }
    }

    // Принудительное обновление местоположения
    async refreshLocation() {
        this.showLocationSpinner();
        
        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0 // Принудительное обновление
        };

        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.onLocationSuccess(position);
                this.hideLocationSpinner();
                this.showLocationSuccess('Местоположение обновлено');
            },
            (error) => {
                this.onLocationError(error);
                this.hideLocationSpinner();
            },
            options
        );
    }

    // Показать спиннер загрузки
    showLocationSpinner() {
        const refreshBtns = document.querySelectorAll('.refresh-location-btn');
        refreshBtns.forEach(btn => {
            const icon = btn.querySelector('i');
            icon.className = 'fas fa-sync-alt animate-spin mr-1';
            btn.disabled = true;
        });
    }

    // Скрыть спиннер загрузки
    hideLocationSpinner() {
        const refreshBtns = document.querySelectorAll('.refresh-location-btn');
        refreshBtns.forEach(btn => {
            const icon = btn.querySelector('i');
            icon.className = 'fas fa-sync-alt mr-1';
            btn.disabled = false;
        });
    }

    // Показать сообщение об успехе
    showLocationSuccess(message) {
        this.showLocationMessage(message, 'success');
    }

    // Показать сообщение об ошибке
    showLocationError(message) {
        this.showLocationMessage(message, 'error');
    }

    // Показать сообщение
    showLocationMessage(message, type) {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 left-4 px-4 py-2 rounded-lg text-white text-sm font-medium z-50 transform translate-x-full transition-transform duration-300 ${
            type === 'success' ? 'bg-green-500' : 'bg-red-500'
        }`;
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 100);

        setTimeout(() => {
            toast.style.transform = 'translateX(-100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Добавление обработчиков форм для автоматической фиксации геолокации
    attachFormHandlers() {
        document.addEventListener('submit', (event) => {
            const form = event.target;
            
            // Проверяем, нужна ли геолокация для этой формы
            if (this.shouldCaptureLocation(form)) {
                // Добавляем данные геолокации в форму
                this.addLocationToForm(form);
            }
        });
    }

    // Определяет, нужно ли фиксировать геолокацию для формы
    shouldCaptureLocation(form) {
        // Формы с явным указанием
        if (form.dataset.geolocation === 'true') return true;
        
        // Формы с полями геолокации
        const hasGeoFields = form.querySelector('input[name="latitude"], input[name="longitude"]');
        if (hasGeoFields) return true;
        
        // Формы нарушений, материалов, отчетов
        const geoForms = [
            'violation-form',
            'material-form', 
            'report-form',
            'delivery-form',
            'inspection-form'
        ];
        
        return geoForms.some(className => 
            form.classList.contains(className) || form.id.includes(className)
        );
    }

    // Добавление данных геолокации в форму
    addLocationToForm(form) {
        if (!this.currentLocation) return;

        // Добавляем скрытые поля, если их нет
        const hiddenFields = [
            { name: 'form_latitude', value: this.currentLocation.latitude },
            { name: 'form_longitude', value: this.currentLocation.longitude },
            { name: 'form_location_accuracy', value: Math.round(this.accuracy) },
            { name: 'form_location_timestamp', value: this.currentLocation.timestamp }
        ];

        hiddenFields.forEach(field => {
            if (!form.querySelector(`input[name="${field.name}"]`)) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = field.name;
                input.value = field.value;
                form.appendChild(input);
            }
        });
    }

    // Получение текущей геолокации
    getCurrentLocation() {
        return this.currentLocation;
    }

    // Остановка отслеживания геолокации
    stopTracking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.isTracking = false;
        }
    }
}

// Глобальный экземпляр менеджера геолокации
window.geoManager = new GeolocationManager();