"""
Router para endpoints de reportes y KPIs
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from app.services.reports_service import reports_service

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reportes", tags=["Reportes"])

@router.get("/kpi")
async def get_kpi_report():
    """
    Obtener reporte completo de KPIs con análisis de AI
    
    Returns:
        JSON con métricas de usuarios, respuestas, uso promedio, 
        tipos de pregunta, top usuarios y conclusiones generadas por AI
    """
    try:
        logger.info("Solicitando reporte de KPIs")
        
        # Generar reporte completo
        result = reports_service.get_kpi_report()
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Reporte de KPIs generado exitosamente",
                    "timestamp": result['data']['generado_en'],
                    "data": result['data']
                }
            )
        else:
            logger.error(f"Error en reporte KPIs: {result['error']}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Error generando reporte de KPIs",
                    "error": result['error']
                }
            )
            
    except Exception as e:
        logger.error(f"Error inesperado en endpoint KPIs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/usuarios")
async def get_usuarios_stats():
    """
    Obtener solo estadísticas de usuarios
    """
    try:
        usuarios_stats = reports_service.get_usuarios_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": usuarios_stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo stats usuarios: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/respuestas")
async def get_respuestas_stats():
    """
    Obtener solo estadísticas de respuestas
    """
    try:
        respuestas_stats = reports_service.get_respuestas_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": respuestas_stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo stats respuestas: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/top-usuarios")
async def get_top_usuarios():
    """
    Obtener top 5 usuarios más activos
    """
    try:
        top_usuarios = reports_service.get_top_usuarios_activos()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "top_usuarios_activos": top_usuarios,
                    "total": len(top_usuarios)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo top usuarios: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/health")
async def health_check():
    """
    Verificar estado del servicio de reportes
    """
    try:
        # Probar conexión básica
        reports_service._ensure_connection()
        
        if reports_service.connection and not reports_service.connection.closed:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Servicio de reportes operativo",
                    "database_connected": True,
                    "ai_available": bool(reports_service.openai_api_key)
                }
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Base de datos no disponible",
                    "database_connected": False,
                    "ai_available": bool(reports_service.openai_api_key)
                }
            )
            
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Error en health check",
                "error": str(e)
            }
        )