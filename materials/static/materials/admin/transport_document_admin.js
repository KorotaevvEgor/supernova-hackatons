(function($) {
    $(document).ready(function() {
        // Функция для заполнения полей получателя при выборе проекта
        function updateReceiverFields(projectId) {
            if (!projectId) return;
            
            $.ajax({
                url: '/api/projects/' + projectId + '/',
                method: 'GET',
                success: function(data) {
                    if (data.name && data.address) {
                        // Заполняем поля получателя данными из проекта
                        $('#id_receiver_name').val(data.contractor || data.name);
                        $('#id_receiver_address').val(data.address);
                        
                        // Можно также заполнить описание груза
                        if (!$('#id_cargo_description').val()) {
                            $('#id_cargo_description').val('Материалы для проекта: ' + data.name);
                        }
                    }
                },
                error: function() {
                    console.log('Ошибка при получении данных проекта');
                }
            });
        }
        
        // Отслеживаем изменение поля проекта
        $('#id_project').on('change', function() {
            const projectId = $(this).val();
            updateReceiverFields(projectId);
        });
        
        // Если проект уже выбран при загрузке страницы, заполняем поля
        const initialProjectId = $('#id_project').val();
        if (initialProjectId) {
            updateReceiverFields(initialProjectId);
        }
    });
})(django.jQuery);