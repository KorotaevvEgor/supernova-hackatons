/**
 * Workflow JavaScript - интерактивные компоненты для роль-специфичных дашбордов
 */

class WorkflowManager {
    constructor() {
        this.currentLocation = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.requestLocation();
        this.loadNotifications();
    }

    setupEventListeners() {
        // Активация проектов
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="activate-project"]')) {
                this.showActivationModal(e.target.dataset.projectId);
            }
            
            if (e.target.matches('[data-action="complete-task"]')) {
                this.completeTask(e.target.dataset.taskId);
            }
            
            if (e.target.matches('[data-action="report-work"]')) {
                this.showWorkReportModal(e.target.dataset.workId);
            }
            
            if (e.target.matches('[data-action="create-inspection"]')) {
                this.showInspectionModal(e.target.dataset.projectId);
            }
            
            if (e.target.matches('[data-action="complete-inspection"]')) {
                this.showInspectionResultModal(e.target.dataset.inspectionId);
            }
            
            if (e.target.matches('[data-action="take-photo"]')) {
                this.takePhoto(e.target.dataset.taskId);
            }

            if (e.target.matches('[data-action="mark-notification-read"]')) {
                this.markNotificationRead(e.target.dataset.notificationId);
            }
        });

        // Обработка форм
        document.addEventListener('submit', (e) => {
            if (e.target.matches('#activationForm')) {
                e.preventDefault();
                this.handleActivationForm(e.target);
            }
            
            if (e.target.matches('#workReportForm')) {
                e.preventDefault();
                this.handleWorkReportForm(e.target);
            }
            
            if (e.target.matches('#inspectionForm')) {
                e.preventDefault();
                this.handleInspectionForm(e.target);
            }
        });
    }

    async requestLocation() {
        if ('geolocation' in navigator) {
            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject);
                });
                
                this.currentLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                
                this.showToast('Геолокация определена', 'success');
            } catch (error) {
                console.warn('Не удалось получить геолокацию:', error);
                this.showToast('Геолокация недоступна', 'warning');
            }
        }
    }

    showActivationModal(projectId) {
        const modalHtml = `
            <div class="modal fade show" id="activationModal" style="display: block;">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-primary text-white">
                            <h5 class="modal-title">
                                <i class="fas fa-play-circle me-2"></i>
                                Активация проекта
                            </h5>
                            <button type="button" class="btn-close btn-close-white" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body">
                            <form id="activationForm" data-project-id="${projectId}">
                                <div class="mb-3">
                                    <label class="form-label">Причина активации</label>
                                    <textarea class="form-control" name="reason" rows="3" 
                                            placeholder="Укажите основание для активации проекта..." required></textarea>
                                </div>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    После активации проект станет доступен для выполнения работ прорабом и проверок инспекторами.
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Отмена</button>
                            <button type="submit" form="activationForm" class="btn btn-primary">
                                <i class="fas fa-play me-2"></i>Активировать
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    async handleActivationForm(form) {
        const projectId = form.dataset.projectId;
        const formData = new FormData(form);
        
        try {
            this.showLoading(true);
            
            const response = await fetch(`/projects/api/projects/${projectId}/activate/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    reason: formData.get('reason')
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Проект успешно активирован!', 'success');
                form.closest('.modal').remove();
                this.refreshProjectStatus(projectId);
                this.loadNotifications(); // Обновляем уведомления
            } else {
                this.showToast(result.error || 'Ошибка при активации', 'error');
            }
        } catch (error) {
            console.error('Ошибка активации:', error);
            this.showToast('Ошибка соединения с сервером', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async completeTask(taskId) {
        if (!this.currentLocation) {
            this.showToast('Для выполнения задачи требуется геолокация', 'warning');
            return;
        }

        try {
            this.showLoading(true);
            
            const response = await fetch(`/projects/api/tasks/${taskId}/complete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    latitude: this.currentLocation.lat,
                    longitude: this.currentLocation.lng
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Задача отмечена как выполненная!', 'success');
                this.updateTaskStatus(taskId, 'completed');
                this.updateProjectReadiness(result.project_readiness);
            } else {
                this.showToast(result.error || 'Ошибка при выполнении задачи', 'error');
            }
        } catch (error) {
            console.error('Ошибка выполнения задачи:', error);
            this.showToast('Ошибка соединения с сервером', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    showWorkReportModal(workId) {
        const modalHtml = `
            <div class="modal fade show" id="workReportModal" style="display: block;">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-success text-white">
                            <h5 class="modal-title">
                                <i class="fas fa-clipboard-check me-2"></i>
                                Отчет о выполнении работ
                            </h5>
                            <button type="button" class="btn-close btn-close-white" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body">
                            <form id="workReportForm" data-work-id="${workId}">
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="workCompleted" name="completed">
                                        <label class="form-check-label" for="workCompleted">
                                            <strong>Работа завершена</strong>
                                        </label>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Комментарии к выполнению</label>
                                    <textarea class="form-control" name="comments" rows="3" 
                                            placeholder="Опишите ход выполнения работ, использованные материалы, особенности..."></textarea>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Отмена</button>
                            <button type="submit" form="workReportForm" class="btn btn-success">
                                <i class="fas fa-save me-2"></i>Сохранить отчет
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    async handleWorkReportForm(form) {
        const workId = form.dataset.workId;
        const formData = new FormData(form);
        
        try {
            this.showLoading(true);
            
            const response = await fetch(`/projects/api/works/${workId}/report/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    completed: formData.has('completed'),
                    comments: formData.get('comments')
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Отчет о работах сохранен!', 'success');
                form.closest('.modal').remove();
                this.updateWorkStatus(workId, result.work_status);
                this.updateProjectCompletion(result.project_completion);
            } else {
                this.showToast(result.error || 'Ошибка при сохранении отчета', 'error');
            }
        } catch (error) {
            console.error('Ошибка отчета:', error);
            this.showToast('Ошибка соединения с сервером', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    showInspectionModal(projectId) {
        const modalHtml = `
            <div class="modal fade show" id="inspectionModal" style="display: block;">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-warning text-dark">
                            <h5 class="modal-title">
                                <i class="fas fa-search me-2"></i>
                                Планирование проверки
                            </h5>
                            <button type="button" class="btn-close" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body">
                            <form id="inspectionForm" data-project-id="${projectId}">
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label class="form-label">Тип проверки</label>
                                            <select class="form-select" name="inspection_type" required>
                                                <option value="">Выберите тип проверки</option>
                                                <option value="quality">Контроль качества</option>
                                                <option value="safety">Контроль безопасности</option>
                                                <option value="compliance">Соответствие нормам</option>
                                                <option value="final">Окончательная приемка</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label class="form-label">Дата и время</label>
                                            <input type="datetime-local" class="form-control" name="scheduled_date" required>
                                        </div>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Области контроля</label>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" name="areas" value="foundation" id="area1">
                                                <label class="form-check-label" for="area1">Фундамент</label>
                                            </div>
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" name="areas" value="structure" id="area2">
                                                <label class="form-check-label" for="area2">Конструкции</label>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" name="areas" value="materials" id="area3">
                                                <label class="form-check-label" for="area3">Материалы</label>
                                            </div>
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" name="areas" value="safety" id="area4">
                                                <label class="form-check-label" for="area4">Безопасность</label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Примечания</label>
                                    <textarea class="form-control" name="notes" rows="3" 
                                            placeholder="Дополнительные требования к проверке..."></textarea>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Отмена</button>
                            <button type="submit" form="inspectionForm" class="btn btn-warning">
                                <i class="fas fa-calendar-plus me-2"></i>Запланировать
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    async handleInspectionForm(form) {
        const projectId = form.dataset.projectId;
        const formData = new FormData(form);
        
        // Собираем области контроля
        const areas = Array.from(form.querySelectorAll('input[name="areas"]:checked'))
                          .map(input => input.value);
        
        try {
            this.showLoading(true);
            
            const response = await fetch('/projects/api/inspections/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    project_id: projectId,
                    inspection_type: formData.get('inspection_type'),
                    scheduled_date: formData.get('scheduled_date'),
                    areas_to_check: areas,
                    notes: formData.get('notes')
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Проверка успешно запланирована!', 'success');
                form.closest('.modal').remove();
                this.loadInspections(); // Обновляем список проверок
            } else {
                this.showToast(result.error || 'Ошибка при планировании проверки', 'error');
            }
        } catch (error) {
            console.error('Ошибка планирования проверки:', error);
            this.showToast('Ошибка соединения с сервером', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async takePhoto(taskId) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showToast('Камера недоступна в вашем браузере', 'error');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: 'environment' }, 
                audio: false 
            });
            
            this.showCameraModal(taskId, stream);
        } catch (error) {
            console.error('Ошибка доступа к камере:', error);
            this.showToast('Не удалось получить доступ к камере', 'error');
        }
    }

    showCameraModal(taskId, stream) {
        const modalHtml = `
            <div class="modal fade show" id="cameraModal" style="display: block;">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-camera me-2"></i>
                                Фотоотчет
                            </h5>
                            <button type="button" class="btn-close" onclick="this.stopCamera(); this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body text-center">
                            <video id="cameraPreview" autoplay muted style="max-width: 100%; max-height: 300px;"></video>
                            <canvas id="photoCanvas" style="display: none;"></canvas>
                            <div id="photoPreview" style="display: none;">
                                <img id="capturedPhoto" style="max-width: 100%; max-height: 300px;">
                            </div>
                            <div class="mt-3">
                                <input type="text" id="photoDescription" class="form-control" 
                                       placeholder="Описание фото (необязательно)" style="display: none;">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="this.stopCamera(); this.closest('.modal').remove()">Отмена</button>
                            <button id="captureBtn" type="button" class="btn btn-primary" onclick="this.capturePhoto('${taskId}')">
                                <i class="fas fa-camera me-2"></i>Сделать фото
                            </button>
                            <button id="uploadBtn" type="button" class="btn btn-success" style="display: none;" onclick="this.uploadPhoto('${taskId}')">
                                <i class="fas fa-upload me-2"></i>Загрузить
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const video = document.getElementById('cameraPreview');
        video.srcObject = stream;
        this.currentStream = stream;
    }

    capturePhoto(taskId) {
        const video = document.getElementById('cameraPreview');
        const canvas = document.getElementById('photoCanvas');
        const preview = document.getElementById('capturedPhoto');
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        
        const dataURL = canvas.toDataURL('image/jpeg', 0.8);
        preview.src = dataURL;
        
        // Скрываем видео, показываем фото
        document.getElementById('cameraPreview').style.display = 'none';
        document.getElementById('photoPreview').style.display = 'block';
        document.getElementById('photoDescription').style.display = 'block';
        
        document.getElementById('captureBtn').style.display = 'none';
        document.getElementById('uploadBtn').style.display = 'inline-block';
        
        this.currentPhotoData = dataURL;
    }

    stopCamera() {
        if (this.currentStream) {
            this.currentStream.getTracks().forEach(track => track.stop());
        }
    }

    // Утилитарные методы
    async loadNotifications() {
        try {
            const response = await fetch('/api/notifications/', {
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            if (response.ok) {
                const notifications = await response.json();
                this.updateNotificationBadge(notifications.unread_count);
            }
        } catch (error) {
            console.error('Ошибка загрузки уведомлений:', error);
        }
    }

    updateNotificationBadge(count) {
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        }
    }

    async markNotificationRead(notificationId) {
        try {
            await fetch(`/api/notifications/${notificationId}/read/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            this.loadNotifications(); // Обновляем счетчик
        } catch (error) {
            console.error('Ошибка отметки уведомления:', error);
        }
    }

    showToast(message, type = 'info') {
        const colors = {
            success: 'bg-success',
            error: 'bg-danger', 
            warning: 'bg-warning',
            info: 'bg-info'
        };
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white ${colors[type]} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        const container = document.getElementById('toast-container') || this.createToastContainer();
        container.appendChild(toast);
        
        // Автоматически показываем и скрываем тост
        setTimeout(() => {
            toast.classList.add('show');
            setTimeout(() => {
                toast.remove();
            }, 5000);
        }, 100);
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }

    showLoading(show) {
        let loader = document.getElementById('global-loader');
        if (!loader && show) {
            loader = document.createElement('div');
            loader.id = 'global-loader';
            loader.innerHTML = `
                <div class="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" 
                     style="background: rgba(0,0,0,0.5); z-index: 10000;">
                    <div class="spinner-border text-light" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                </div>
            `;
            document.body.appendChild(loader);
        } else if (loader && !show) {
            loader.remove();
        }
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    updateTaskStatus(taskId, status) {
        const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskElement) {
            taskElement.classList.add('completed');
            const statusElement = taskElement.querySelector('.task-status');
            if (statusElement) {
                statusElement.textContent = 'Выполнено';
                statusElement.className = 'task-status badge bg-success';
            }
        }
    }

    updateProjectReadiness(readiness) {
        const readinessElements = document.querySelectorAll('.project-readiness');
        readinessElements.forEach(element => {
            element.textContent = `${readiness}%`;
        });
        
        const progressBars = document.querySelectorAll('.readiness-progress');
        progressBars.forEach(bar => {
            bar.style.width = `${readiness}%`;
            bar.setAttribute('aria-valuenow', readiness);
        });
    }

    async refreshProjectStatus(projectId) {
        try {
            const response = await fetch(`/projects/api/projects/${projectId}/status/`);
            if (response.ok) {
                const status = await response.json();
                this.updateProjectReadiness(status.readiness_score);
                // Обновляем другие элементы интерфейса при необходимости
            }
        } catch (error) {
            console.error('Ошибка обновления статуса проекта:', error);
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.workflowManager = new WorkflowManager();
});