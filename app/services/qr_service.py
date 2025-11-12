"""
Servicio para detección y procesamiento de códigos QR
"""

import cv2
import numpy as np
from PIL import Image
import re

class QRCodeService:
    def __init__(self):
        """
        Inicializar servicio de QR
        """
        self.qr_detector = cv2.QRCodeDetector()
        self.qr_patterns = {
            'entrega_id': r'entregaId[=:]([a-f0-9\-]+)',
            'url_entrega': r'entrega[/\?]([a-f0-9\-]+)',
            'uuid': r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
            'simple_id': r'([a-zA-Z0-9\-_]{10,50})'
        }
    
    def detect_qr_codes(self, image):
        """
        Detectar todos los códigos QR en la imagen
        """
        try:
            # Convertir a escala de grises si es necesario
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Detectar y decodificar códigos QR usando OpenCV
            data, bbox, _ = self.qr_detector.detectAndDecode(gray)
            
            results = []
            if data:
                # Extraer posible entrega ID
                entrega_id = self.extract_entrega_id(data)
                
                qr_info = {
                    'data': data,
                    'type': 'QRCODE',
                    'bbox': self._format_bbox(bbox) if bbox is not None else None,
                    'entrega_id': entrega_id,
                    'is_entrega': entrega_id is not None
                }
                
                results.append(qr_info)
            
            return {
                'success': True,
                'qr_codes': results,
                'total_found': len(results),
                'entrega_qrs': [qr for qr in results if qr['is_entrega']],
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'qr_codes': [],
                'total_found': 0,
                'entrega_qrs': [],
                'error': str(e)
            }
    
    def _format_bbox(self, bbox):
        """
        Formatear bbox de OpenCV al formato esperado
        """
        if bbox is None or len(bbox) == 0:
            return None
        
        # OpenCV devuelve puntos como [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        points = bbox[0]
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        x = int(min(x_coords))
        y = int(min(y_coords))
        x2 = int(max(x_coords))
        y2 = int(max(y_coords))
        w = x2 - x
        h = y2 - y
        
        return {
            'x': x, 'y': y,
            'width': w, 'height': h,
            'x2': x2, 'y2': y2
        }
    
    def extract_entrega_id(self, qr_data):
        """
        Extraer ID de entrega del contenido del QR
        """
        try:
            # Probar diferentes patrones para encontrar el ID de entrega
            for pattern_name, pattern in self.qr_patterns.items():
                matches = re.findall(pattern, qr_data, re.IGNORECASE)
                if matches:
                    # Validar que parece un UUID válido
                    potential_id = matches[0]
                    if self.is_valid_entrega_id(potential_id):
                        return potential_id
            
            # Si no encuentra patrón, verificar si toda la cadena es un ID
            if self.is_valid_entrega_id(qr_data):
                return qr_data
                
            return None
            
        except Exception as e:
            return None
    
    def is_valid_entrega_id(self, text):
        """
        Verificar si el texto parece un ID de entrega válido
        """
        # UUID estándar
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        if re.match(uuid_pattern, text, re.IGNORECASE):
            return True
        
        # ID personalizado (letras, números, guiones, 10-50 caracteres)
        custom_pattern = r'^[a-zA-Z0-9\-_]{10,50}$'
        if re.match(custom_pattern, text):
            return True
        
        return False
    
    def remove_qr_from_image(self, image, qr_results):
        """
        Eliminar códigos QR de la imagen para limpio procesamiento OCR
        """
        if not qr_results.get('success') or not qr_results.get('qr_codes'):
            return image
        
        output = image.copy()
        
        for qr in qr_results['qr_codes']:
            bbox = qr.get('bbox')
            if bbox is None:
                continue
                
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            
            # Expandir un poco el área para asegurar eliminación completa
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            x2 = min(image.shape[1], bbox['x2'] + padding)
            y2 = min(image.shape[0], bbox['y2'] + padding)
            
            # Rellenar con color promedio del área circundante
            surrounding_area = self._get_surrounding_color(image, x, y, x2, y2)
            cv2.rectangle(output, (x, y), (x2, y2), surrounding_area, -1)
        
        return output
    
    def _get_surrounding_color(self, image, x1, y1, x2, y2):
        """
        Obtener color promedio del área circundante para rellenar QR
        """
        h, w = image.shape[:2]
        
        # Definir área de muestreo alrededor del QR
        sample_size = 20
        left = max(0, x1 - sample_size)
        right = min(w, x2 + sample_size)
        top = max(0, y1 - sample_size)
        bottom = min(h, y2 + sample_size)
        
        # Extraer área de muestreo excluyendo el QR
        mask = np.ones((bottom - top, right - left), dtype=np.uint8) * 255
        
        # Excluir área del QR del promedio
        qr_rel_x1 = max(0, x1 - left)
        qr_rel_y1 = max(0, y1 - top)
        qr_rel_x2 = min(right - left, x2 - left)
        qr_rel_y2 = min(bottom - top, y2 - top)
        
        cv2.rectangle(mask, (qr_rel_x1, qr_rel_y1), (qr_rel_x2, qr_rel_y2), 0, -1)
        
        # Calcular color promedio
        sample_area = image[top:bottom, left:right]
        if len(image.shape) == 3:
            mean_color = cv2.mean(sample_area, mask)[:3]
            return tuple(int(c) for c in mean_color)
        else:
            mean_color = cv2.mean(sample_area, mask)[0]
            return int(mean_color)
    
    def find_best_entrega_qr(self, qr_results):
        """
        Encontrar el mejor código QR que contenga una entrega ID
        """
        entrega_qrs = qr_results.get('entrega_qrs', [])
        
        if not entrega_qrs:
            return None
        
        # Si hay múltiples, elegir el primero (o el más grande si tienen bbox)
        best_qr = entrega_qrs[0]
        if best_qr.get('bbox'):
            best_qr = max(entrega_qrs, key=lambda x: x['bbox']['width'] * x['bbox']['height'] if x.get('bbox') else 0)
        
        return {
            'entrega_id': best_qr['entrega_id'],
            'qr_data': best_qr['data'],
            'confidence': 'high' if len(entrega_qrs) == 1 else 'medium',
            'bbox': best_qr.get('bbox')
        }

# Instancia global del servicio
qr_service = QRCodeService()