"""
Cliente para la API de encuestas.sw2ficct.lat
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

class EncuestasAPIClient:
    def __init__(self, base_url=None):
        """
        Inicializar cliente de la API de encuestas
        """
        self.base_url = base_url or os.getenv('ENCUESTAS_API_URL', 'https://encuestas.sw2ficct.lat/api')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_entrega_preguntas(self, entrega_id):
        """
        Obtener preguntas de una entrega específica
        GET /api/entrega/:id/preguntas
        """
        try:
            url = f"{self.base_url}/entrega/{entrega_id}/preguntas"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'entrega_id': data.get('entregaId'),
                    'encuesta': data.get('encuesta'),
                    'preguntas': data.get('preguntas', []),
                    'total_preguntas': len(data.get('preguntas', [])),
                    'error': None
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Entrega no encontrada',
                    'entrega_id': entrega_id,
                    'status_code': 404
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'entrega_id': entrega_id,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}',
                'entrega_id': entrega_id,
                'status_code': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'entrega_id': entrega_id,
                'status_code': None
            }
    
    def save_entrega_respuestas(self, entrega_id, respuestas):
        """
        Guardar respuestas de una entrega
        POST /api/entrega/:id/respuestas
        
        Args:
            entrega_id: ID de la entrega
            respuestas: Lista de respuestas en formato:
                [
                    {"preguntaId": "uuid", "opcionId": "uuid"},  # Para preguntas con opciones
                    {"preguntaId": "uuid", "texto": "respuesta"}  # Para preguntas abiertas
                ]
        """
        try:
            url = f"{self.base_url}/entrega/{entrega_id}/respuestas"
            payload = {"respuestas": respuestas}
            
            response = self.session.post(url, json=payload)
            
            if response.status_code == 201:
                data = response.json()
                return {
                    'success': True,
                    'message': data.get('message'),
                    'entrega_id': data.get('entregaId'),
                    'total_respuestas': data.get('totalRespuestas'),
                    'respuestas_guardadas': data.get('respuestas', []),
                    'error': None
                }
            elif response.status_code == 400:
                error_data = response.json()
                return {
                    'success': False,
                    'error': error_data.get('message', 'Error de validación'),
                    'entrega_id': entrega_id,
                    'status_code': 400,
                    'validation_error': True
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Entrega no encontrada',
                    'entrega_id': entrega_id,
                    'status_code': 404
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'entrega_id': entrega_id,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}',
                'entrega_id': entrega_id,
                'status_code': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'entrega_id': entrega_id,
                'status_code': None
            }
    
    def process_survey_template(self, preguntas_data):
        """
        Convertir respuesta de la API a formato de plantilla para OCR
        """
        if not preguntas_data.get('success'):
            return None
        
        preguntas = preguntas_data.get('preguntas', [])
        encuesta_info = preguntas_data.get('encuesta', {})
        
        template = {
            'entrega_id': preguntas_data.get('entrega_id'),
            'encuesta': {
                'id': encuesta_info.get('id'),
                'nombre': encuesta_info.get('nombre'),
                'descripcion': encuesta_info.get('descripcion')
            },
            'preguntas': []
        }
        
        for pregunta in preguntas:
            pregunta_template = {
                'id': pregunta.get('id'),
                'texto': pregunta.get('texto'),
                'orden': pregunta.get('orden'),
                'obligatorio': pregunta.get('obligatorio', False),
                'tipo': pregunta.get('tipo', {}).get('nombre', ''),
                'opciones': []
            }
            
            # Procesar opciones si existen
            for opcion in pregunta.get('opciones', []):
                pregunta_template['opciones'].append({
                    'id': opcion.get('id'),
                    'texto': opcion.get('texto'),
                    'valor': opcion.get('valor')
                })
            
            template['preguntas'].append(pregunta_template)
        
        return template
    
    def format_responses_for_api(self, ocr_responses, template):
        """
        Mapeo directo de respuestas OCR a formato API
        """
        if not ocr_responses or not template:
            return []
        
        api_responses = []
        
        # Si ocr_responses es un dict con la estructura completa
        if isinstance(ocr_responses, dict) and 'preguntas' in ocr_responses:
            preguntas_ocr = ocr_responses['preguntas']
        else:
            preguntas_ocr = ocr_responses
        
        # Mapear por orden de pregunta o por pregunta_id
        for pregunta_ocr in preguntas_ocr:
            if not pregunta_ocr.get('respuesta'):
                continue
                
            # Encontrar pregunta correspondiente en template
            pregunta_template = None
            
            # Primero intentar por pregunta_id (para audio)
            pregunta_id = pregunta_ocr.get('pregunta_id')
            if pregunta_id:
                for p in template.get('preguntas', []):
                    if p.get('id') == pregunta_id:
                        pregunta_template = p
                        break
            
            # Si no encontró por pregunta_id, intentar por orden (para OCR tradicional)
            if not pregunta_template:
                orden_ocr = pregunta_ocr.get('orden')
                for p in template.get('preguntas', []):
                    if p.get('orden') == orden_ocr:
                        pregunta_template = p
                        break
            
            if not pregunta_template:
                continue
            
            respuesta = pregunta_ocr['respuesta']
            
            # Verificar si es pregunta abierta por tipo
            if pregunta_template['tipo'].lower() in ['abierta', 'completar']:
                # Pregunta abierta - usar campo texto
                api_responses.append({
                    'preguntaId': pregunta_template['id'],
                    'texto': str(respuesta)
                })
            else:
                # Pregunta con opciones - manejar múltiples respuestas
                respuestas_list = respuesta if isinstance(respuesta, list) else [respuesta]
                
                for resp_item in respuestas_list:
                    # Si la respuesta es un UUID (opcionId directo), buscar por ID
                    encontrada = False
                    for opcion in pregunta_template['opciones']:
                        if str(opcion['id']).lower() == str(resp_item).lower():
                            api_responses.append({
                                'preguntaId': pregunta_template['id'],
                                'opcionId': opcion['id']
                            })
                            encontrada = True
                            break
                    
                    if not encontrada:
                        # Si no es UUID válido, intentar por número (1, 2, 3...)
                        if str(resp_item).isdigit():
                            option_index = int(resp_item) - 1  # Convertir a índice 0-based
                            if 0 <= option_index < len(pregunta_template['opciones']):
                                api_responses.append({
                                    'preguntaId': pregunta_template['id'],
                                    'opcionId': pregunta_template['opciones'][option_index]['id']
                                })
                                encontrada = True
                    
                    if not encontrada:
                        # Si no es número ni UUID, buscar por texto como antes
                        for opcion in pregunta_template['opciones']:
                            if opcion['texto'].lower() in str(resp_item).lower():
                                api_responses.append({
                                    'preguntaId': pregunta_template['id'],
                                    'opcionId': opcion['id']
                                })
                                break
        
        print(f"\nRESULTADO MAPEO:")
        print(f"  Total respuestas mapeadas: {len(api_responses)}")
        for i, resp in enumerate(api_responses):
            print(f"  Respuesta {i+1}: {resp}")
        print("--- FIN MAPEO ---\n")
        
        return api_responses
    
    def validate_entrega_id(self, entrega_id):
        """
        Validar que una entrega ID existe haciendo una consulta rápida
        """
        result = self.get_entrega_preguntas(entrega_id)
        return {
            'valid': result.get('success', False),
            'exists': result.get('status_code') != 404,
            'error': result.get('error') if not result.get('success') else None
        }

# Instancia global del cliente
encuestas_client = EncuestasAPIClient()