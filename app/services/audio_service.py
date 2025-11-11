"""
Servicio de Audio para transcripción y procesamiento de encuestas
"""

import google.generativeai as genai
from openai import OpenAI
import json
import io
import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self, gemini_api_key=None, openai_api_key=None):
        """
        Inicializar servicio de Audio
        """
        try:
            # Configurar Gemini para análisis
            self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
            if not self.gemini_api_key:
                raise ValueError("API key de Gemini no encontrada. Configurar GEMINI_API_KEY en .env")
            
            genai.configure(api_key=self.gemini_api_key)
            
            # Configuración optimizada para análisis de texto
            self.generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2000,
            )
            
            self.gemini_model = genai.GenerativeModel(
                'gemini-2.5-flash', 
                generation_config=self.generation_config
            )
            
            # Configurar OpenAI Whisper para transcripción
            self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
            if not self.openai_api_key:
                raise ValueError("API key de OpenAI no encontrada. Configurar OPENAI_API_KEY en .env")
            
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            
            logger.info("Audio Service inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando Audio Service: {e}")
            self.gemini_model = None
            self.openai_client = None
    
    def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        Transcribir audio a texto usando Whisper
        
        Args:
            audio_bytes: Bytes del archivo de audio
            filename: Nombre del archivo (para el tipo)
            
        Returns:
            str: Texto transcrito
        """
        try:
            if not self.openai_client:
                raise ValueError("Cliente OpenAI no inicializado")
            
            # Crear archivo temporal en memoria
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename
            
            # Transcribir con Whisper
            response = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es"  # Español por defecto
            )
            
            transcribed_text = response.text
            logger.info(f"Audio transcrito exitosamente. Longitud: {len(transcribed_text)} caracteres")
            
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return ""
    
    def process_survey_response(self, transcribed_text: str, survey_template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar texto transcrito contra template de encuesta usando Gemini
        
        Args:
            transcribed_text: Texto transcrito del audio
            survey_template: Template de la encuesta
            
        Returns:
            dict: Respuestas estructuradas
        """
        try:
            if not self.gemini_model:
                raise ValueError("Modelo Gemini no inicializado")
            
            # Crear prompt para análisis con Gemini
            prompt = f"""
            Analiza el siguiente texto transcrito de audio y mapéalo contra las preguntas de la encuesta.
            
            TEXTO TRANSCRITO:
            "{transcribed_text}"
            
            TEMPLATE DE ENCUESTA:
            {json.dumps(survey_template, ensure_ascii=False, indent=2)}
            
            INSTRUCCIONES:
            1. Identifica las respuestas en el texto transcrito que corresponden a cada pregunta
            2. Para preguntas de selección múltiple, encuentra la opción que mejor coincida
            3. Para preguntas abiertas, extrae la respuesta textual relevante
            4. Para preguntas numéricas, extrae el número mencionado
            5. Si no encuentras respuesta para una pregunta, marca como null
            
            FORMATO DE RESPUESTA (JSON):
            {{
                "respuestas": [
                    {{
                        "pregunta_id": "id_de_la_pregunta",
                        "tipo_pregunta": "tipo",
                        "respuesta": "valor_de_la_respuesta",
                        "confianza": 0.95
                    }}
                ],
                "resumen": "Breve resumen del procesamiento"
            }}
            
            IMPORTANTE: Usa "pregunta_id" (el ID exacto de la pregunta del template) para el mapeo correcto.
            También puedes usar el texto de la pregunta para guiarte y encontrar la respuesta correcta.
            
            Responde SOLO con el JSON válido:
            """
            
            # Enviar a Gemini
            response = self.gemini_model.generate_content(prompt)
            response_text = response.text
            
            # Limpiar respuesta si tiene markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.replace("```", "").strip()
            
            # Parsear JSON
            result = json.loads(response_text)
            logger.info(f"Encuesta procesada exitosamente. {len(result.get('respuestas', []))} respuestas encontradas")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON: {e}")
            return {
                "respuestas": [],
                "resumen": f"Error parseando respuesta: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error procesando encuesta: {e}")
            return {
                "respuestas": [],
                "resumen": f"Error en procesamiento: {str(e)}"
            }
    
    def process_audio_survey(self, audio_bytes: bytes, survey_template: Dict[str, Any], filename: str = "audio.wav") -> Dict[str, Any]:
        """
        Procesar audio completo: transcripción + análisis de encuesta
        
        Args:
            audio_bytes: Bytes del archivo de audio
            survey_template: Template de la encuesta
            filename: Nombre del archivo
            
        Returns:
            dict: Resultado completo con transcripción y respuestas
        """
        try:
            # Paso 1: Transcribir audio
            logger.info("Iniciando transcripción de audio...")
            transcribed_text = self.transcribe_audio(audio_bytes, filename)
            
            if not transcribed_text:
                return {
                    "success": False,
                    "error": "No se pudo transcribir el audio",
                    "transcripcion": "",
                    "respuestas": []
                }
            
            # Paso 2: Analizar respuestas
            logger.info("Analizando respuestas de encuesta...")
            survey_result = self.process_survey_response(transcribed_text, survey_template)
            
            # Resultado final
            result = {
                "success": True,
                "transcripcion": transcribed_text,
                "respuestas": survey_result.get("respuestas", []),
                "resumen": survey_result.get("resumen", ""),
                "estadisticas": {
                    "longitud_transcripcion": len(transcribed_text),
                    "respuestas_encontradas": len(survey_result.get("respuestas", [])),
                    "filename": filename
                }
            }
            
            logger.info("Audio procesado exitosamente")
            return result
            
        except Exception as e:
            logger.error(f"Error en proceso completo de audio: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcripcion": "",
                "respuestas": []
            }
    
    def validate_audio_format(self, filename: str) -> bool:
        """
        Validar formato de audio soportado
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            bool: True si el formato es válido
        """
        supported_formats = [
            '.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', 
            '.wav', '.webm', '.flac', '.ogg'
        ]
        
        file_extension = os.path.splitext(filename.lower())[1]
        is_valid = file_extension in supported_formats
        
        if not is_valid:
            logger.warning(f"Formato de audio no soportado: {file_extension}")
        
        return is_valid
    
    def get_audio_info(self, audio_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Obtener información básica del archivo de audio
        
        Args:
            audio_bytes: Bytes del archivo
            filename: Nombre del archivo
            
        Returns:
            dict: Información del archivo
        """
        try:
            return {
                "filename": filename,
                "size_bytes": len(audio_bytes),
                "size_mb": round(len(audio_bytes) / (1024 * 1024), 2),
                "format": os.path.splitext(filename.lower())[1],
                "is_valid_format": self.validate_audio_format(filename)
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de audio: {e}")
            return {
                "filename": filename,
                "error": str(e)
            }

# Instancia global del servicio
audio_service = AudioService()