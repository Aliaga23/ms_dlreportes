"""
Servicio principal para el procesamiento completo de encuestas
Orquesta: QR detection -> API calls -> OCR -> Response mapping
"""

import cv2
import numpy as np
from app.services.qr_service import qr_service
from app.services.encuestas_client import encuestas_client
from app.services.ocr_service import gemini_ocr

class SurveyProcessingService:
    def __init__(self):
        """
        Inicializar servicio de procesamiento de encuestas
        """
        self.qr_service = qr_service
        self.api_client = encuestas_client
        self.ocr_service = gemini_ocr
    
    def process_survey_image(self, image):
     
        try:
            # 1. Escanear QR para obtener entrega_id
            qr_result = self.qr_service.detect_qr_codes(image)
            
            if not qr_result['success'] or not qr_result['entrega_qrs']:
                return {
                    'success': False,
                    'error': 'No se encontró código QR con entrega ID',
                    'step': 'qr_scan'
                }
            
            entrega_id = qr_result['entrega_qrs'][0]['entrega_id']
            
            # 2. Obtener plantilla de encuesta
            template_result = self.api_client.get_entrega_preguntas(entrega_id)
            
            if not template_result['success']:
                return {
                    'success': False,
                    'error': f'Error obteniendo encuesta: {template_result["error"]}',
                    'entrega_id': entrega_id,
                    'step': 'api_get'
                }
            
            # 3. Procesar plantilla
            survey_template = self.api_client.process_survey_template(template_result)
            
            # 4. Llamar a Gemini para llenar respuestas
            ocr_result = self.ocr_service.process_survey(image, survey_template)
            
            if not ocr_result.get('success'):
                return {
                    'success': False,
                    'error': f'Error en Gemini: {ocr_result.get("error")}',
                    'entrega_id': entrega_id,
                    'step': 'gemini_ocr'
                }
            
            # 5. Mapear respuestas para POST
            formatted_responses = self.api_client.format_responses_for_api(
                ocr_result.get('survey_completed', {}), 
                survey_template
            )
            
            # 6. Hacer POST a la API
            save_result = self.api_client.save_entrega_respuestas(entrega_id, formatted_responses)
            
            return {
                'success': True,
                'entrega_id': entrega_id,
                'encuesta': survey_template['encuesta'],
                'responses_sent': len(formatted_responses),
                'save_result': save_result,
                'post_success': save_result.get('success', False)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'step': 'exception'
            }
    
    def process_survey_with_known_id(self, image, entrega_id):
        """
        Procesar encuesta cuando ya conocemos el ID (sin detección QR)
        """
        try:
            # Obtener plantilla de encuesta desde API
            template_result = self.api_client.get_entrega_preguntas(entrega_id)
            
            if not template_result['success']:
                return {
                    'success': False,
                    'error': f'Error obteniendo plantilla: {template_result["error"]}',
                    'entrega_id': entrega_id
                }
            
            # Procesar plantilla para OCR
            survey_template = self.api_client.process_survey_template(template_result)
            
            # Procesar encuesta con OCR
            ocr_result = self.ocr_service.process_survey(image, survey_template)
            
            if not ocr_result.get('success'):
                return {
                    'success': False,
                    'error': f'Error en OCR: {ocr_result.get("error")}',
                    'entrega_id': entrega_id
                }
            
            # Formatear respuestas para API
            survey_completed = ocr_result.get('survey_completed', {})
            formatted_responses = self.api_client.format_responses_for_api(
                survey_completed.get('preguntas', []), 
                survey_template
            )
            
            return {
                'success': True,
                'entrega_id': entrega_id,
                'encuesta': survey_template['encuesta'],
                'ocr_result': survey_completed,
                'api_responses': formatted_responses,
                'total_responses': len(formatted_responses)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error procesando encuesta: {str(e)}',
                'entrega_id': entrega_id
            }
    
    def validate_and_save_responses(self, entrega_id, responses):
        """
        Validar y guardar respuestas manualmente
        """
        try:
            save_result = self.api_client.save_entrega_respuestas(entrega_id, responses)
            return save_result
        except Exception as e:
            return {
                'success': False,
                'error': f'Error guardando respuestas: {str(e)}',
                'entrega_id': entrega_id
            }
    
    def get_survey_preview(self, entrega_id):
        """
        Obtener vista previa de encuesta sin procesar imagen
        """
        try:
            template_result = self.api_client.get_entrega_preguntas(entrega_id)
            
            if not template_result['success']:
                return template_result
            
            survey_template = self.api_client.process_survey_template(template_result)
            
            return {
                'success': True,
                'entrega_id': entrega_id,
                'encuesta': survey_template['encuesta'],
                'preguntas': survey_template['preguntas'],
                'total_preguntas': len(survey_template['preguntas'])
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error obteniendo vista previa: {str(e)}',
                'entrega_id': entrega_id
            }

# Instancia global del servicio
survey_processor = SurveyProcessingService()