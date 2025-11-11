"""
Servicio de notificaciones Firebase para el backend OCR
"""

import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FirebaseNotificationService:
    def __init__(self):
        """
        Inicializar Firebase Admin SDK
        """
        try:
            # Inicializar Firebase Admin SDK
            if not firebase_admin._apps:
                # Intentar leer desde variable de entorno primero (para Railway)
                firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
                
                if firebase_creds_json:
                    # Parsear el JSON desde la variable de entorno
                    cred_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(cred_dict)
                    print("Usando credenciales Firebase desde variable de entorno")
                else:
                    # Fallback: leer desde archivo local (desarrollo)
                    firebase_credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-service-account.json')
                    
                    if not os.path.exists(firebase_credentials_path):
                        print(f"Archivo de credenciales Firebase no encontrado en: {firebase_credentials_path}")
                        print("Descarga el archivo desde Firebase Console > Configuración > Cuentas de servicio")
                        self.firebase_app = None
                        return
                    
                    cred = credentials.Certificate(firebase_credentials_path)
                    print("Usando credenciales Firebase desde archivo local")
                
                self.firebase_app = firebase_admin.initialize_app(cred)
                print("Firebase Admin SDK inicializado correctamente")
            else:
                self.firebase_app = firebase_admin.get_app()
                
        except Exception as e:
            print(f"Error inicializando Firebase: {e}")
            self.firebase_app = None
    
    def send_ocr_success_notification(self, fcm_token, user_id, extracted_text, entrega_id):
        """
        Enviar notificación de éxito en el procesamiento OCR
        """
        if not self.firebase_app:
            return {'success': False, 'error': 'Firebase no inicializado'}
        
        try:
            # Truncar texto si es muy largo para la notificación
            preview_text = extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text
            
            # Estructura de la notificación
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Encuesta Procesada",
                    body=f"Respuestas enviadas exitosamente para entrega {entrega_id[:8]}..."
                ),
                data={
                    'type': 'ocr_success',
                    'user_id': str(user_id),
                    'entrega_id': str(entrega_id),
                    'extracted_text': str(extracted_text),
                    'preview': preview_text,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'completed'
                },
                token=fcm_token,
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        channel_id='high_importance_channel',
                        priority='high'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1
                        )
                    )
                )
            )
            
            # Enviar notificación
            response = messaging.send(message)
            
            return {
                'success': True,
                'message_id': response,
                'sent_to': fcm_token,
                'type': 'ocr_success'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error enviando notificación: {str(e)}'
            }
    
    def send_ocr_error_notification(self, fcm_token, user_id, error_message, step_failed=None):
        """
        Enviar notificación de error en el procesamiento
        """
        if not self.firebase_app:
            return {'success': False, 'error': 'Firebase no inicializado'}
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Error en Procesamiento",
                    body=f"No se pudo procesar la encuesta. Error: {error_message[:50]}..."
                ),
                data={
                    'type': 'ocr_error',
                    'user_id': str(user_id),
                    'error_message': str(error_message),
                    'step_failed': str(step_failed or 'unknown'),
                    'timestamp': datetime.now().isoformat(),
                    'status': 'failed'
                },
                token=fcm_token,
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        channel_id='high_importance_channel',
                        priority='high',
                        color='#FF0000'
                    )
                )
            )
            
            response = messaging.send(message)
            
            return {
                'success': True,
                'message_id': response,
                'sent_to': fcm_token,
                'type': 'ocr_error'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error enviando notificación de error: {str(e)}'
            }
    
    def send_processing_notification(self, fcm_token, user_id):
        """
        Enviar notificación de que el procesamiento ha iniciado
        """
        if not self.firebase_app:
            return {'success': False, 'error': 'Firebase no inicializado'}
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Procesando Encuesta",
                    body="Analizando imagen y detectando respuestas..."
                ),
                data={
                    'type': 'ocr_processing',
                    'user_id': str(user_id),
                    'status': 'processing',
                    'timestamp': datetime.now().isoformat()
                },
                token=fcm_token
            )
            
            response = messaging.send(message)
            
            return {
                'success': True,
                'message_id': response,
                'sent_to': fcm_token,
                'type': 'processing'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error enviando notificación de procesamiento: {str(e)}'
            }
    
    def is_firebase_available(self):
        """
        Verificar si Firebase está disponible
        """
        return self.firebase_app is not None

# Instancia global del servicio
firebase_service = FirebaseNotificationService()