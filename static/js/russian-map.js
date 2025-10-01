/**
 * 🇷🇺 РОССИЙСКАЯ КАРТОГРАФИЧЕСКАЯ СИСТЕМА БЕЗ БРЕНДИНГА
 * На основе OpenLayers 8.2 с поддержкой российских источников карт
 * Автор: Система управления благоустройством
 * Лицензия: MIT
 */

class RussianMap {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.map = null;
        this.currentLayer = null;
        this.vectorSource = null;
        this.vectorLayer = null;
        
        // Настройки по умолчанию
        this.options = {
            center: options.center || [37.6176, 55.7558], // Москва
            zoom: options.zoom || 10,
            minZoom: options.minZoom || 1,
            maxZoom: options.maxZoom || 20,
            showAttribution: options.showAttribution || false,
            showZoomControls: options.showZoomControls !== false,
            defaultProvider: options.defaultProvider || 'osm',
            debug: options.debug || false,
            ...options
        };
        
        // Российские провайдеры карт без брендинга
        this.mapProviders = {
            osm: {
                name: 'Стандартная карта',
                url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            },
            satellite: {
                name: 'Спутниковые снимки',
                url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                maxZoom: 18,
                attribution: '© Esri'
            }
        };
        
        this.log('🚀 Инициализация российской картографической системы');
        this.init();
    }
    
    log(message, type = 'info') {
        if (!this.options.debug) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const prefix = `[RussianMap ${timestamp}]`;
        
        switch (type) {
            case 'error':
                console.error(`${prefix} ❌ ${message}`);
                break;
            case 'warn':
                console.warn(`${prefix} ⚠️ ${message}`);
                break;
            case 'success':
                console.log(`${prefix} ✅ ${message}`);
                break;
            default:
                console.log(`${prefix} 💡 ${message}`);
        }
    }
    
    init() {
        try {
            this.log('Проверка доступности OpenLayers...');
            
            if (typeof ol === 'undefined') {
                throw new Error('OpenLayers не загружен! Подключите библиотеку OpenLayers.');
            }
            
            this.log('✅ OpenLayers доступен', 'success');
            this.createMap();
            
        } catch (error) {
            this.log(`Критическая ошибка инициализации: ${error.message}`, 'error');
            this.showError(error.message);
        }
    }
    
    createMap() {
        this.log('Создание карты...');
        
        const container = document.getElementById(this.containerId);
        if (!container) {
            throw new Error(`Контейнер с ID "${this.containerId}" не найден`);
        }
        
        // Создаем vector source и layer для маркеров
        this.vectorSource = new ol.source.Vector();
        this.vectorLayer = new ol.layer.Vector({
            source: this.vectorSource,
            zIndex: 1000
        });
        
        // Создаем карту
        const controls = [];
        
        if (this.options.showZoomControls) {
            controls.push(new ol.control.Zoom());
        }
        
        // НЕ добавляем Attribution контрол для скрытия брендинга
        
        // Создаем простую карту без сложной конфигурации
        this.map = new ol.Map({
            target: this.containerId,
            view: new ol.View({
                center: ol.proj.fromLonLat(this.options.center),
                zoom: this.options.zoom,
                minZoom: this.options.minZoom,
                maxZoom: this.options.maxZoom
            })
        });
        
        // Добавляем контролы вручную
        if (this.options.showZoomControls) {
            this.map.addControl(new ol.control.Zoom());
        }
        
        // Добавляем слой для маркеров
        this.map.addLayer(this.vectorLayer);
        
        // Загружаем провайдер по умолчанию
        this.loadProvider(this.options.defaultProvider);
        
        this.log('✅ Карта создана успешно', 'success');
        
        // Немедленно скрываем загрузку и показываем карту
        setTimeout(() => {
            const mapLoading = document.getElementById('map-loading');
            const mapContainer = document.getElementById('map');
            
            if (mapLoading) mapLoading.style.display = 'none';
            if (mapContainer) mapContainer.style.display = 'block';
            
            this.log('✅ Карта отображена', 'success');
            
            // Уведомляем о готовности
            if (typeof window.onMapReady === 'function') {
                window.onMapReady(this);
            }
            
            container.dispatchEvent(new CustomEvent('mapReady', {
                detail: { map: this.map, mapInstance: this }
            }));
        }, 500);
    }
    
    loadProvider(providerKey) {
        const provider = this.mapProviders[providerKey];
        if (!provider) {
            this.log(`Провайдер "${providerKey}" не найден`, 'error');
            return false;
        }
        
        this.log(`Загрузка провайдера: ${provider.name}`);
        
        // Удаляем текущий слой
        if (this.currentLayer) {
            this.map.removeLayer(this.currentLayer);
        }
        
        // Создаем новый слой
        this.currentLayer = new ol.layer.Tile({
            source: new ol.source.XYZ({
                url: provider.url,
                maxZoom: provider.maxZoom,
                crossOrigin: 'anonymous'
            }),
            zIndex: 0
        });
        
        this.map.addLayer(this.currentLayer);
        this.log(`✅ Провайдер "${provider.name}" загружен`, 'success');
        
        return true;
    }
    
    // Добавление маркера
    addMarker(coordinates, options = {}) {
        this.log(`Добавление маркера: [${coordinates[0]}, ${coordinates[1]}]`);
        
        const lonLat = coordinates;
        const point = new ol.geom.Point(ol.proj.fromLonLat(lonLat));
        
        const feature = new ol.Feature({
            geometry: point,
            name: options.title || 'Маркер',
            data: options.data || {}
        });
        
        // Стиль маркера
        const style = new ol.style.Style({
            image: new ol.style.Circle({
                radius: options.radius || 8,
                fill: new ol.style.Fill({
                    color: options.color || '#2942F9'
                }),
                stroke: new ol.style.Stroke({
                    color: options.strokeColor || 'white',
                    width: options.strokeWidth || 2
                })
            })
        });
        
        feature.setStyle(style);
        this.vectorSource.addFeature(feature);
        
        // Popup если указан
        if (options.popup) {
            feature.set('popup', options.popup);
            
            // Добавляем обработчик клика
            this.map.on('click', (event) => {
                this.map.forEachFeatureAtPixel(event.pixel, (clickedFeature) => {
                    if (clickedFeature === feature) {
                        const popup = clickedFeature.get('popup');
                        if (popup) {
                            this.showPopup(event.coordinate, popup);
                        }
                    }
                });
            });
        }
        
        this.log('✅ Маркер добавлен', 'success');
        return feature;
    }
    
    // Добавление полигона
    addPolygon(coordinates, options = {}) {
        this.log('Добавление полигона...');
        
        // Конвертируем координаты
        const polygonCoords = coordinates.map(coord => ol.proj.fromLonLat([coord[0], coord[1]]));
        const polygon = new ol.geom.Polygon([polygonCoords]);
        
        const feature = new ol.Feature({
            geometry: polygon,
            name: options.title || 'Полигон',
            data: options.data || {}
        });
        
        const style = new ol.style.Style({
            stroke: new ol.style.Stroke({
                color: options.strokeColor || '#2942F9',
                width: options.strokeWidth || 2
            }),
            fill: new ol.style.Fill({
                color: options.fillColor || 'rgba(41, 66, 249, 0.2)'
            })
        });
        
        feature.setStyle(style);
        this.vectorSource.addFeature(feature);
        
        this.log('✅ Полигон добавлен', 'success');
        return feature;
    }
    
    // Центрирование карты
    setCenter(coordinates, zoom = null) {
        const lonLat = ol.proj.fromLonLat(coordinates);
        const view = this.map.getView();
        
        view.setCenter(lonLat);
        if (zoom !== null) {
            view.setZoom(zoom);
        }
        
        this.log(`Карта центрирована: [${coordinates[0]}, ${coordinates[1]}]`);
    }
    
    // Подгонка по объектам
    fitToExtent(coordinates, padding = 50) {
        if (!coordinates || coordinates.length === 0) return;
        
        const extent = ol.extent.createEmpty();
        
        coordinates.forEach(coord => {
            const point = ol.proj.fromLonLat([coord[0], coord[1]]);
            ol.extent.extend(extent, point);
        });
        
        this.map.getView().fit(extent, {
            padding: [padding, padding, padding, padding]
        });
        
        this.log('Карта подогнана под объекты');
    }
    
    // Очистка всех объектов
    clearAll() {
        this.vectorSource.clear();
        this.log('Все объекты удалены с карты');
    }
    
    // Смена провайдера
    changeProvider(providerKey) {
        return this.loadProvider(providerKey);
    }
    
    // Получение списка доступных провайдеров
    getProviders() {
        return Object.keys(this.mapProviders).map(key => ({
            key: key,
            name: this.mapProviders[key].name
        }));
    }
    
    // Показ ошибки
    showError(message) {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        container.innerHTML = `
            <div class="flex items-center justify-center h-full bg-gray-50 rounded-lg">
                <div class="text-center p-8">
                    <div class="text-6xl mb-4">❌</div>
                    <h3 class="text-xl font-bold text-gray-900 mb-2">Ошибка карты</h3>
                    <p class="text-sm text-gray-600 mb-4">${message}</p>
                    <button onclick="location.reload()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                        🔄 Перезагрузить
                    </button>
                </div>
            </div>
        `;
    }
    
    // Простой popup (можно заменить на более сложный)
    showPopup(coordinate, content) {
        // Удаляем предыдущие popups
        const existingPopups = document.querySelectorAll('.ol-popup');
        existingPopups.forEach(popup => popup.remove());
        
        // Создаем простой popup
        const popup = document.createElement('div');
        popup.className = 'ol-popup bg-white p-3 rounded-lg shadow-lg border max-w-sm';
        popup.innerHTML = content;
        popup.style.position = 'absolute';
        popup.style.zIndex = '1001';
        popup.style.pointerEvents = 'auto';
        
        // Позиционируем popup
        const pixel = this.map.getPixelFromCoordinate(coordinate);
        popup.style.left = (pixel[0] + 10) + 'px';
        popup.style.top = (pixel[1] - 10) + 'px';
        
        // Добавляем кнопку закрытия
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.className = 'absolute top-1 right-2 text-gray-500 hover:text-gray-700 text-xl';
        closeBtn.onclick = () => popup.remove();
        popup.appendChild(closeBtn);
        
        this.map.getTargetElement().appendChild(popup);
        
        // Автоматически закрываем через 10 секунд
        setTimeout(() => {
            if (popup.parentElement) {
                popup.remove();
            }
        }, 10000);
    }
    
    // Уничтожение карты
    destroy() {
        if (this.map) {
            this.map.setTarget(null);
            this.map = null;
        }
        this.log('Карта уничтожена');
    }
}

// Глобальная функция для создания карты
window.createRussianMap = function(containerId, options = {}) {
    return new RussianMap(containerId, options);
};

// Экспорт для использования в модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RussianMap;
}

console.log('🇷🇺 Russian Map System загружена');