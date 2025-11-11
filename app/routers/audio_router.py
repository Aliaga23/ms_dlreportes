"""
Router para endpoints de Audio y procesamiento de encuestas
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks, Request
from fastapi.responses import JSONResponse
import json
import json
import asyncio
import logging

from app.services.audio_service import audio_service
from app.services.survey_processor import survey_processor
from app.services.encuestas_client import encuestas_client
from app.services.firebase_service import firebase_service
from app.services.database_service import database_service
from app.services.s3_service import s3_service

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio"])

@router.post("/process")
async def procesar_encuesta_audio_con_notificaciones(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    entrega_id: str = Form(...),
    fcm_token: str = Form(...),
    user_id: str = Form(...)
):
    """
    Endpoint para Flutter App - Procesamiento de audio asíncrono con notificaciones push
    
    Args:
        audio_file: Archivo de audio (.mp3, .wav, .m4a, etc.)
        entrega_id: ID de la entrega para obtener las preguntas
        fcm_token: Token FCM para notificaciones push
        user_id: ID del usuario que envía el audio
    """
    
    logger.info(f"Nueva request de procesamiento de audio para user_id: {user_id}, entrega_id: {entrega_id}")
    
    try:
        # Validar formato de audio
        if not audio_service.validate_audio_format(audio_file.filename):
            logger.error(f"Formato de audio inválido: {audio_file.filename}")
            raise HTTPException(
                status_code=400,
                detail=f"Formato de audio no soportado: {audio_file.filename}. Formatos válidos: mp3, wav, m4a, etc."
            )
        
        # Leer archivo de audio
        audio_bytes = await audio_file.read()
        
        # Validar tamaño (máximo 25MB para Whisper)
        max_size = 25 * 1024 * 1024  # 25MB
        if len(audio_bytes) > max_size:
            logger.error(f"Archivo muy grande: {len(audio_bytes)} bytes")
            raise HTTPException(
                status_code=400,
                detail=f"El archivo es muy grande. Máximo 25MB. Tamaño: {len(audio_bytes)/1024/1024:.1f}MB"
            )
        
        # Obtener información del archivo
        audio_info = audio_service.get_audio_info(audio_bytes, audio_file.filename)
        logger.info(f"Audio recibido: {audio_info}")
        
        # Programar procesamiento en background
        background_tasks.add_task(
            process_audio_survey_background,
            audio_bytes,
            audio_file.filename,
            entrega_id,
            user_id,
            fcm_token
        )
        
        # Respuesta inmediata
        return JSONResponse({
            "success": True,
            "message": "Audio recibido y en procesamiento",
            "entrega_id": entrega_id,
            "user_id": user_id,
            "audio_info": audio_info,
            "status": "processing"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/process-sync")
async def procesar_encuesta_audio_sincrono(
    audio_file: UploadFile = File(...),
    entrega_id: str = Form(...),
    user_id: str = Form(...)
):
    """
    Endpoint síncrono para procesamiento de audio (para testing)
    """
    
    logger.info(f"Procesamiento síncrono de audio para user_id: {user_id}, entrega_id: {entrega_id}")
    
    try:
        # Validaciones similares
        if not audio_service.validate_audio_format(audio_file.filename):
            raise HTTPException(status_code=400, detail="Formato de audio no soportado")
        
        audio_bytes = await audio_file.read()
        
        # Procesar audio inmediatamente
        result = await process_audio_survey_complete(
            audio_bytes, 
            audio_file.filename, 
            entrega_id, 
            user_id
        )
        
        return JSONResponse(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en procesamiento síncrono: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_audio_survey_background(
    audio_bytes: bytes,
    filename: str, 
    entrega_id: str,
    user_id: str,
    fcm_token: str
):
    """
    Procesamiento completo de audio en background
    """
    try:
        logger.info(f"Iniciando procesamiento background para entrega {entrega_id}")
        
        # Enviar notificación de inicio
        await send_notification(
            fcm_token, 
            "Audio en procesamiento", 
            "Tu audio está siendo transcrito y analizado...",
            {"type": "audio_processing_start", "entrega_id": entrega_id, "user_id": user_id}
        )
        
        # Procesar audio completo
        result = await process_audio_survey_complete(audio_bytes, filename, entrega_id, user_id)
        
        if result["success"]:
            # Notificación de éxito
            await send_notification(
                fcm_token,
                "Audio procesado exitosamente",
                f"Tu encuesta ha sido completada. {len(result.get('respuestas', []))} respuestas procesadas.",
                {"type": "audio_processing_complete", "entrega_id": entrega_id, "success": True, "user_id": user_id}
            )
            logger.info(f"Audio procesado exitosamente para entrega {entrega_id}")
        else:
            # Notificación de error
            await send_notification(
                fcm_token,
                "Error procesando audio",
                f"Hubo un problema al procesar tu audio: {result.get('error', 'Error desconocido')}",
                {"type": "audio_processing_error", "entrega_id": entrega_id, "success": False, "user_id": user_id}
            )
            logger.error(f"Error procesando audio para entrega {entrega_id}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error en background task: {e}")
        # Notificación de error crítico
        await send_notification(
            fcm_token,
            "Error crítico",
            "Hubo un error inesperado procesando tu audio. Intenta nuevamente.",
            {"type": "audio_processing_critical_error", "entrega_id": entrega_id}
        )

async def process_audio_survey_complete(
    audio_bytes: bytes,
    filename: str,
    entrega_id: str,
    user_id: str
) -> dict:
    """
    Procesamiento completo: transcripción, análisis y envío de respuestas
    """
    try:
        # 1. Subir audio a S3
        logger.info(f"Subiendo audio a S3...")
        s3_url = await upload_audio_to_s3(audio_bytes, "", user_id, filename)
        
        # 2. Obtener preguntas de la entrega
        logger.info(f"Obteniendo preguntas para entrega {entrega_id}")
        entrega_data = encuestas_client.get_entrega_preguntas(entrega_id)
        
        # 2. Obtener preguntas de la entrega
        logger.info(f"Obteniendo preguntas para entrega {entrega_id}")
        entrega_data = encuestas_client.get_entrega_preguntas(entrega_id)
        
        if not entrega_data or not entrega_data.get("success"):
            return {
                "success": False,
                "error": "No se pudo obtener información de la entrega",
                "s3_url": s3_url
            }
        
        # 3. Procesar template de la encuesta
        survey_template = encuestas_client.process_survey_template(entrega_data)
        
        # 4. Transcribir audio con Whisper
        logger.info(f"Transcribiendo audio con Whisper...")
        transcribed_text = audio_service.transcribe_audio(audio_bytes, filename)
        
        if not transcribed_text:
            return {
                "success": False,
                "error": "No se pudo transcribir el audio",
                "s3_url": s3_url
            }
        
        # 5. Procesar texto transcrito con el template usando Gemini
        logger.info(f"Analizando texto transcrito contra template de encuesta...")
        audio_result = audio_service.process_survey_response(transcribed_text, survey_template)
        
        if not audio_result or not audio_result.get("respuestas"):
            return {
                "success": False,
                "error": "No se pudieron extraer respuestas del audio",
                "transcripcion": transcribed_text,
                "s3_url": s3_url
            }
        
        # 6. Formatear respuestas para API (igual que OCR)
        logger.info(f"RESULTADO MAPEO:")
        logger.info(f"  Respuestas de Gemini: {audio_result['respuestas']}")
        logger.info(f"  Template preguntas IDs: {[p.get('id', 'sin_id') for p in survey_template.get('preguntas', [])]}")
        
        formatted_responses = encuestas_client.format_responses_for_api(
            audio_result["respuestas"], 
            survey_template
        )
        
        logger.info(f"  Total respuestas mapeadas: {len(formatted_responses)}")
        logger.info(f"  Respuestas formateadas: {formatted_responses}")
        logger.info(f"--- FIN MAPEO ---")
        
        # 7. Enviar respuestas a la API
        logger.info(f"Enviando {len(formatted_responses)} respuestas a la API...")
        post_result = encuestas_client.save_entrega_respuestas(entrega_id, formatted_responses)
        
        post_success = post_result.get('success', False)
        responses_sent = len(formatted_responses)
        
        # 8. El resto es igual que OCR
        if post_success:
            logger.info(f"Audio procesado exitosamente - Respuestas: {responses_sent}, POST: {post_success}")
            
            # Guardar registro simple en base de datos
            try:
                db_result = database_service.insert_audio_record(
                    user_id=user_id,
                    entrega_id=entrega_id,
                    s3_url=s3_url
                )
                if db_result['success']:
                    logger.info(f"Registro de audio guardado: {db_result['record_id']}")
                else:
                    logger.warning(f"No se pudo guardar registro de audio: {db_result['error']}")
            except Exception as db_error:
                logger.warning(f"Error guardando audio en BD (continuando): {db_error}")
            
            return {
                "success": True,
                "entrega_id": entrega_id,
                "user_id": user_id,
                "responses_sent": responses_sent,
                "post_success": post_success,
                "s3_url": s3_url
            }
        else:
            # Error en el POST - NO guardar nada en BD
            logger.error(f"Error en POST de respuestas: {post_result.get('error', 'Error desconocido')}")
            
            return {
                "success": False,
                "error": f"Error enviando respuestas: {post_result.get('error')}",
                "s3_url": s3_url
            }
        
    except Exception as e:
        logger.error(f"Error en procesamiento completo: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def upload_audio_to_s3(audio_bytes: bytes, key: str, user_id: str, filename: str) -> str:
    """
    Subir archivo de audio a S3
    """
    try:
        s3_url = s3_service.upload_file_from_bytes(
            audio_bytes,
            user_id,
            filename,
            content_type="audio/mpeg",
            prefix="audios"
        )
        logger.info(f"Audio subido a S3: {s3_url}")
        return s3_url
    except Exception as e:
        logger.error(f"Error subiendo audio a S3: {e}")
        return ""

async def send_notification(fcm_token: str, title: str, body: str, data: dict = None):
    """
    Enviar notificación push
    """
    try:
        if data is None:
            data = {}
        
        # Usar los métodos existentes del firebase_service
        if "processing_start" in data.get("type", ""):
            firebase_service.send_processing_notification(fcm_token, data.get("user_id", ""))
        elif "processing_complete" in data.get("type", ""):
            firebase_service.send_ocr_success_notification(fcm_token, data.get("user_id", ""), body, data.get("entrega_id", ""))
        elif "error" in data.get("type", ""):
            firebase_service.send_ocr_error_notification(fcm_token, data.get("user_id", ""), body)
        
        logger.info(f"Notificación enviada: {title}")
    except Exception as e:
        logger.error(f"Error enviando notificación: {e}")

@router.get("/health")
async def health_check():
    """
    Verificar estado del servicio de audio
    """
    try:
        # Verificar servicios
        services_status = {
            "audio_service": audio_service.gemini_model is not None and audio_service.openai_client is not None,
            "s3_service": True,  # Asumir que está disponible
            "firebase_service": True,  # Asumir que está disponible
            "encuestas_api": True  # Se verificaría con un ping real
        }
        
        all_healthy = all(services_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": services_status,
            "supported_formats": ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm'],
            "max_file_size": "25MB"
        }
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/formats")
async def get_supported_formats():
    """
    Obtener formatos de audio soportados
    """
    return {
        "supported_formats": [
            {
                "extension": ".mp3",
                "description": "MP3 Audio"
            },
            {
                "extension": ".wav", 
                "description": "WAV Audio"
            },
            {
                "extension": ".m4a",
                "description": "M4A Audio" 
            },
            {
                "extension": ".flac",
                "description": "FLAC Audio"
            },
            {
                "extension": ".ogg",
                "description": "OGG Audio"
            },
            {
                "extension": ".webm",
                "description": "WebM Audio"
            }
        ],
        "max_file_size": "25MB",
        "recommended_format": "mp3 o wav para mejor compatibilidad"
    }