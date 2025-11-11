"""
Router para endpoints de OCR y procesamiento de encuestas
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks, Request
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import json
import asyncio
import logging

from app.services.ocr_service import gemini_ocr
from app.services.survey_processor import survey_processor
from app.services.qr_service import qr_service
from app.services.encuestas_client import encuestas_client
from app.services.firebase_service import firebase_service
from app.services.database_service import database_service
from app.services.s3_service import s3_service

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.post("/process")
async def procesar_encuesta_con_notificaciones(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    fcm_token: str = Form(...),
    user_id: str = Form(...)
):
    """
    Endpoint para Flutter App - Procesamiento asíncrono con notificaciones push
    """
    
    logger.info(f"Nueva request de procesamiento para user_id: {user_id}")
    
    try:
        # Validar archivo
        if not file.content_type.startswith("image/"):
            logger.error(f"Archivo inválido: content_type = {file.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"El archivo debe ser una imagen. Recibido: {file.content_type}"
            )
        
        # Leer imagen
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            logger.error("Error: No se pudo decodificar la imagen")
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar la imagen"
            )
        
        logger.info(f"Imagen válida recibida: {image.shape}, iniciando procesamiento")
        
        # Enviar notificación de procesamiento iniciado
        if firebase_service.is_firebase_available():
            firebase_service.send_processing_notification(fcm_token, user_id)
        
        # Iniciar procesamiento en segundo plano
        background_tasks.add_task(
            process_survey_background,
            image.copy(),
            fcm_token,
            user_id,
            file.filename
        )
        
        logger.info("Procesamiento en background iniciado, enviando respuesta")
        
        # Respuesta inmediata
        return JSONResponse(
            status_code=200,
            content={
                "message": "Imagen recibida. Procesando en segundo plano.",
                "status": "processing",
                "user_id": user_id,
                "filename": file.filename,
                "push_notifications": firebase_service.is_firebase_available()
            }
        )
        
    except HTTPException as he:
        logger.error(f"HTTP EXCEPTION: {he.detail}")
        # Enviar notificación de error inmediato
        if firebase_service.is_firebase_available():
            firebase_service.send_ocr_error_notification(
                fcm_token, user_id, he.detail, "request_validation"
            )
        raise he
        
    except Exception as e:
        logger.error(f"ERROR GENERAL: {str(e)}")
        logger.error(f"TIPO DE ERROR: {type(e)}")
        
        # Enviar notificación de error inmediato
        if firebase_service.is_firebase_available():
            firebase_service.send_ocr_error_notification(
                fcm_token, user_id, str(e), "request_validation"
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando request: {str(e)}"
        )

async def process_survey_background(image, fcm_token, user_id, filename):
    """
    Función para procesamiento en segundo plano
    """
    logger.info(f"Iniciando procesamiento background para user: {user_id}")
    
    # Variables para tracking
    s3_url = None
    db_record_id = None
    
    try:
        # 1. Subir imagen a S3
        logger.info("Subiendo imagen a S3...")
        s3_result = s3_service.upload_image_from_array(image, user_id, "ocr")
        
        if s3_result['success']:
            s3_url = s3_result['url']
            logger.info(f"Imagen subida a S3: {s3_url}")
        else:
            logger.warning(f"Error subiendo a S3: {s3_result['error']}")
        
        # 2. Procesar imagen completa: QR -> GET -> Gemini -> POST
        resultado = survey_processor.process_survey_image(image)
        
        # 3. Preparar contenido para base de datos
        if resultado['success']:
            contenido = {
                "entrega_id": resultado['entrega_id'],
                "encuesta": resultado['encuesta']['nombre'],
                "responses_sent": resultado['responses_sent'],
                "post_success": resultado.get('post_success', False),
                "filename": filename
            }
        else:
            contenido = {
                "error": resultado.get('error', 'Error desconocido'),
                "step_failed": resultado.get('step', 'unknown'),
                "filename": filename
            }
        
        # 4. Guardar registro en base de datos
        logger.info("Guardando registro en base de datos...")
        db_result = database_service.insert_ocr_record(
            user_id=user_id,
            contenido=str(contenido),  # Convertir dict a string JSON-like
            url=s3_url
        )
        
        if db_result['success']:
            db_record_id = db_result['record_id']
            logger.info(f"Registro guardado en BD: {db_record_id}")
        else:
            logger.error(f"Error guardando en BD: {db_result['error']}")
        
        # 5. Procesar resultado y enviar notificaciones
        if resultado['success']:
            # Extraer información para la notificación
            entrega_id = resultado['entrega_id']
            encuesta_nombre = resultado['encuesta']['nombre']
            responses_count = resultado['responses_sent']
            post_success = resultado.get('post_success', False)
            
            logger.info(f"Procesamiento exitoso - Entrega: {entrega_id}, Respuestas: {responses_count}, POST: {post_success}")
            
            # Crear texto resumen incluyendo info de S3 y BD
            summary_text = f"Encuesta: {encuesta_nombre}\nRespuestas enviadas: {responses_count}\nEntrega ID: {entrega_id}\nPOST exitoso: {post_success}"
            if s3_url:
                summary_text += f"\nArchivo guardado: {s3_url}"
            if db_record_id:
                summary_text += f"\nRegistro BD: {db_record_id}"
            
            # Enviar notificación de éxito
            if firebase_service.is_firebase_available():
                firebase_service.send_ocr_success_notification(
                    fcm_token, user_id, summary_text, entrega_id
                )
            
        else:
            # Enviar notificación de error
            error_msg = resultado.get('error', 'Error desconocido')
            step_failed = resultado.get('step', 'unknown')
            
            logger.error(f"Error en procesamiento - Usuario: {user_id}, Paso: {step_failed}, Error: {error_msg}")
            
            if firebase_service.is_firebase_available():
                firebase_service.send_ocr_error_notification(
                    fcm_token, user_id, error_msg, step_failed
                )
            
    except Exception as e:
        # Error inesperado en segundo plano
        logger.error(f"Error inesperado en background - Usuario: {user_id}, Error: {str(e)}")
        
        # Intentar guardar el error en base de datos
        try:
            error_content = {
                "error": str(e),
                "step_failed": "background_processing",
                "filename": filename
            }
            database_service.insert_ocr_record(
                user_id=user_id,
                contenido=str(error_content),
                url=s3_url
            )
        except Exception as db_error:
            logger.error(f"Error guardando error en BD: {db_error}")
        
        if firebase_service.is_firebase_available():
            firebase_service.send_ocr_error_notification(
                fcm_token, user_id, str(e), "background_processing"
            )

@router.get("/history/{user_id}")
async def get_user_ocr_history(user_id: str, limit: int = 10):
    """
    Obtener historial de procesamiento OCR de un usuario
    """
    try:
        logger.info(f"Consultando historial OCR para usuario: {user_id}")
        
        result = database_service.get_ocr_records_by_user(user_id, limit)
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "user_id": user_id,
                    "records": result['records'],
                    "count": len(result['records'])
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": result['error']
                }
            )
            
    except Exception as e:
        logger.error(f"Error consultando historial: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@router.post("/encuesta")
async def procesar_encuesta_ocr(
    file: UploadFile = File(...)
):
    """
    Procesamiento completo automático: QR -> API -> OCR -> Guardar respuestas
    """
    try:
        # Validar archivo
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="El archivo debe ser una imagen"
            )
        
        # Leer imagen
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar la imagen"
            )
        
        # Procesar imagen completa automáticamente
        resultado = survey_processor.process_survey_image(image)
        
        if not resultado.get("success", False):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "filename": file.filename,
                    "error": resultado.get("error", "Error desconocido"),
                    "step_failed": resultado.get("step", "unknown"),
                    "details": resultado.get("details", ""),
                    "message": "No se pudo procesar la encuesta completamente"
                }
            )
        
        # Verificar si se guardaron las respuestas
        save_result = resultado.get("save_result")
        responses_saved = save_result and save_result.get("success", False)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "filename": file.filename,
                "entrega_id": resultado["entrega_id"],
                "encuesta": resultado["encuesta"],
                "total_preguntas": resultado["total_preguntas"],
                "responses_detected": resultado["responses_detected"],
                "responses_saved": responses_saved,
                "save_message": save_result.get("message") if save_result else "No se intentó guardar",
                "qr_detected": True,
                "processing_summary": resultado["processing_steps"],
                "ocr_responses": resultado["ocr_result"]["survey_completed"],
                "api_responses": resultado["api_responses"],
                "message": f"Encuesta procesada exitosamente. {'Respuestas guardadas.' if responses_saved else 'Respuestas detectadas pero no guardadas.'}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando encuesta: {str(e)}"
        )

@router.post("/texto")
async def extraer_texto(file: UploadFile = File(...)):
    """
    Extraer texto simple de una imagen
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="El archivo debe ser una imagen"
            )
        
        # Leer imagen
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar la imagen"
            )
        
        # Extraer texto con OCR
        resultado = gemini_ocr.extract_text(image)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": resultado.get("success", False),
                "filename": file.filename,
                "texto_extraido": resultado.get("text", ""),
                "error": resultado.get("error", None),
                "message": "Texto extraído con OCR"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extrayendo texto: {str(e)}"
        )

@router.post("/estructura")
async def analizar_estructura(file: UploadFile = File(...)):
    """
    Analizar estructura de formulario
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="El archivo debe ser una imagen"
            )
        
        # Leer imagen
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar la imagen"
            )
        
        # Analizar estructura con OCR
        resultado = gemini_ocr.analyze_form_structure(image)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": resultado.get("success", False),
                "filename": file.filename,
                "estructura": resultado.get("structure", None),
                "respuesta_raw": resultado.get("raw_response", ""),
                "error": resultado.get("error", None),
                "message": "Estructura analizada con OCR"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analizando estructura: {str(e)}"
        )

@router.post("/manuscrito")
async def extraer_manuscrito(file: UploadFile = File(...)):
    """
    Extraer solo texto manuscrito
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="El archivo debe ser una imagen"
            )
        
        # Leer imagen
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar la imagen"
            )
        
        # Extraer texto manuscrito con OCR
        resultado = gemini_ocr.extract_handwritten_text(image)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": resultado.get("success", False),
                "filename": file.filename,
                "texto_manuscrito": resultado.get("handwritten_text", ""),
                "error": resultado.get("error", None),
                "message": "Texto manuscrito extraído con OCR"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extrayendo texto manuscrito: {str(e)}"
        )