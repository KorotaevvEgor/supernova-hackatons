from django import template
import json
import re

register = template.Library()


@register.filter
def coordinates_to_json(project):
    """
    Преобразует координаты проекта в JSON строку для JavaScript
    """
    if not project or not hasattr(project, 'coordinates') or not project.coordinates:
        return 'null'
    
    # Если уже JSON - возвращаем как есть
    if project.coordinates.strip().startswith('{'):
        try:
            # Проверяем валидность JSON
            json.loads(project.coordinates)
            return project.coordinates
        except:
            pass
    
    # Парсим WKT формат
    if project.coordinates.strip().upper().startswith('POLYGON'):
        try:
            match = re.search(r'POLYGON\s*\(\(([^)]+)\)\)', project.coordinates)
            if match:
                coords_str = match.group(1)
                coords = []
                for pair in coords_str.split(','):
                    parts = pair.strip().split()
                    if len(parts) >= 2:
                        lng, lat = float(parts[0]), float(parts[1])
                        coords.append([lng, lat])
                
                # Возвращаем GeoJSON-подобный объект как JSON строку
                geojson = {
                    'type': 'Polygon',
                    'coordinates': [coords]
                }
                return json.dumps(geojson)
        except Exception as e:
            print(f'Ошибка парсинга WKT в фильтре: {e}')
    
    return 'null'


@register.filter
def has_valid_coordinates(project):
    """
    Проверяет, есть ли у проекта валидные координаты
    """
    if not project or not hasattr(project, 'coordinates') or not project.coordinates:
        return False
    
    coords_json = coordinates_to_json(project)
    return coords_json != 'null'