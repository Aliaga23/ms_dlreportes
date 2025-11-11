"""
Servicio para manejo de base de datos PostgreSQL
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import os
import json
from dotenv import load_dotenv
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class DatabaseService:
    def __init__(self):
        """
        Inicializar servicio de base de datos
        """
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL no encontrada en variables de entorno")
        
        self.connection = None
        self._connect()
    
    def _connect(self):
        """
        Establecer conexión con la base de datos
        """
        try:
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            logger.info("Conexión exitosa a PostgreSQL")
        except Exception as e:
            logger.error(f"Error conectando a PostgreSQL: {e}")
            self.connection = None
    
    def _ensure_connection(self):
        """
        Asegurar que la conexión esté activa
        """
        if not self.connection or self.connection.closed:
            self._connect()
    
    def insert_ocr_record(self, user_id, contenido, url=None):
        """
        Insertar registro en tabla OCR
        
        Args:
            user_id: ID del usuario (str o UUID)
            contenido: Contenido extraído del OCR (str)
            url: URL del archivo en S3 (opcional)
            
        Returns:
            dict: {"success": bool, "record_id": str, "error": str}
        """
        try:
            self._ensure_connection()
            
            if not self.connection:
                return {
                    "success": False,
                    "record_id": None,
                    "error": "No se pudo establecer conexión con la base de datos"
                }
            
            # Extraer URL del diccionario si es necesario
            actual_url = url
            if isinstance(url, dict):
                actual_url = url.get('url', str(url))
            
            cursor = self.connection.cursor()
            
            insert_query = """
                INSERT INTO ocr (user_id, contenido, url, created_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id, created_at
            """
            
            cursor.execute(insert_query, (str(user_id), contenido, actual_url))
            result = cursor.fetchone()
            
            self.connection.commit()
            cursor.close()
            
            logger.info(f"Registro OCR insertado exitosamente")
            
            return {
                "success": True,
                "record_id": str(result['id']) if result else "unknown",
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error insertando registro OCR: {e}")
            
            if self.connection:
                self.connection.rollback()
            
            return {
                "success": False,
                "record_id": None,
                "error": str(e)
            }
    
    def insert_audio_record(self, user_id, entrega_id, s3_url):
        """
        Insertar registro específico para AUDIO (simplificado)
        
        Args:
            user_id: ID del usuario (str)
            entrega_id: ID de la entrega
            s3_url: URL del archivo de audio en S3
            
        Returns:
            dict: {"success": bool, "record_id": str, "error": str}
        """
        try:
            self._ensure_connection()
            
            if not self.connection:
                return {
                    "success": False,
                    "record_id": None,
                    "error": "No se pudo establecer conexión con la base de datos"
                }
            
            # Debug: verificar tipos de datos antes del insert
            logger.info(f"DEBUG - user_id type: {type(user_id)}, value: {user_id}")
            logger.info(f"DEBUG - entrega_id type: {type(entrega_id)}, value: {entrega_id}")
            logger.info(f"DEBUG - s3_url type: {type(s3_url)}, value: {s3_url}")
            
            # Extraer URL del diccionario si es necesario
            actual_s3_url = s3_url
            if isinstance(s3_url, dict):
                actual_s3_url = s3_url.get('url', str(s3_url))
                logger.info(f"DEBUG - Extracted URL from dict: {actual_s3_url}")
            
            cursor = self.connection.cursor()
            
            # Usar tabla existente 'audio' sin columna contenido - Supabase genera el ID automáticamente
            insert_query = """
                INSERT INTO audio (user_id, url, created_at)
                VALUES (%s, %s, NOW())
                RETURNING id, created_at
            """
            
            cursor.execute(insert_query, (
                str(user_id), str(actual_s3_url)
            ))
            result = cursor.fetchone()
            
            self.connection.commit()
            cursor.close()
            
            logger.info(f"Registro AUDIO insertado exitosamente")
            
            return {
                "success": True,
                "record_id": str(result['id']) if result else "unknown",
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error insertando registro AUDIO: {e}")
            if self.connection:
                self.connection.rollback()
            
            return {
                "success": False,
                "record_id": None,
                "error": str(e)
            }
    
    def get_ocr_records_by_user(self, user_id, limit=10):
        """
        Obtener registros OCR de un usuario
        
        Args:
            user_id: ID del usuario
            limit: Número máximo de registros a retornar
            
        Returns:
            dict: {"success": bool, "records": list, "error": str}
        """
        try:
            self._ensure_connection()
            
            if not self.connection:
                return {
                    "success": False,
                    "records": [],
                    "error": "No se pudo establecer conexión con la base de datos"
                }
            
            cursor = self.connection.cursor()
            
            select_query = """
                SELECT id, user_id, contenido, url, created_at
                FROM ocr
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            
            cursor.execute(select_query, (user_id, limit))
            records = cursor.fetchall()
            cursor.close()
            
            # Convertir registros a lista de diccionarios
            result_records = []
            for record in records:
                result_records.append({
                    "id": str(record['id']),
                    "user_id": str(record['user_id']),
                    "contenido": record['contenido'],
                    "url": record['url'],
                    "created_at": record['created_at'].isoformat()
                })
            
            return {
                "success": True,
                "records": result_records,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo registros OCR: {e}")
            return {
                "success": False,
                "records": [],
                "error": str(e)
            }
    
    def close(self):
        """
        Cerrar conexión con la base de datos
        """
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Conexión a PostgreSQL cerrada")

# Instancia global del servicio
database_service = DatabaseService()