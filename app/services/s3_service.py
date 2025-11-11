"""
Servicio para manejo de archivos en AWS S3
"""

import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import logging
import uuid
from datetime import datetime
import cv2
import numpy as np

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class S3Service:
    def __init__(self):
        """
        Inicializar servicio de S3
        """
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = os.getenv('AWS_REGION')
        self.bucket_name = os.getenv('AWS_BUCKET_NAME')
        
        if not all([self.access_key, self.secret_key, self.region, self.bucket_name]):
            raise ValueError("Credenciales de AWS S3 incompletas en variables de entorno")
        
        self.s3_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """
        Inicializar cliente de S3
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            logger.info("Cliente S3 inicializado correctamente")
        except Exception as e:
            logger.error(f"Error inicializando cliente S3: {e}")
            self.s3_client = None
    
    def upload_image_from_array(self, image_array, user_id, prefix="ocr"):
        """
        Subir imagen desde array numpy a S3
        
        Args:
            image_array: Array numpy de la imagen (formato OpenCV)
            user_id: ID del usuario
            prefix: Prefijo para organizar archivos (ej: "ocr", "audio")
            
        Returns:
            dict: {"success": bool, "url": str, "key": str, "error": str}
        """
        try:
            if not self.s3_client:
                return {
                    "success": False,
                    "url": None,
                    "key": None,
                    "error": "Cliente S3 no inicializado"
                }
            
            # Generar nombre único para el archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_id = str(uuid.uuid4())[:8]
            file_key = f"{prefix}/{user_id}/{timestamp}_{file_id}.jpg"
            
            # Convertir array numpy a bytes
            success, buffer = cv2.imencode('.jpg', image_array)
            if not success:
                return {
                    "success": False,
                    "url": None,
                    "key": None,
                    "error": "Error codificando imagen"
                }
            
            image_bytes = buffer.tobytes()
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=image_bytes,
                ContentType='image/jpeg'
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_key}"
            
            logger.info(f"Imagen subida exitosamente a S3: {file_key}")
            
            return {
                "success": True,
                "url": file_url,
                "key": file_key,
                "error": None
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Error S3 ClientError: {error_code} - {e}")
            return {
                "success": False,
                "url": None,
                "key": None,
                "error": f"Error S3: {error_code}"
            }
        except Exception as e:
            logger.error(f"Error subiendo imagen a S3: {e}")
            return {
                "success": False,
                "url": None,
                "key": None,
                "error": str(e)
            }
    
    def upload_file_from_bytes(self, file_bytes, user_id, filename, content_type="application/octet-stream", prefix="files"):
        """
        Subir archivo desde bytes a S3
        
        Args:
            file_bytes: Contenido del archivo en bytes
            user_id: ID del usuario
            filename: Nombre del archivo original
            content_type: Tipo MIME del archivo
            prefix: Prefijo para organizar archivos
            
        Returns:
            dict: {"success": bool, "url": str, "key": str, "error": str}
        """
        try:
            if not self.s3_client:
                return {
                    "success": False,
                    "url": None,
                    "key": None,
                    "error": "Cliente S3 no inicializado"
                }
            
            # Generar nombre único manteniendo extensión original
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_id = str(uuid.uuid4())[:8]
            
            # Extraer extensión del archivo original
            if '.' in filename:
                extension = filename.split('.')[-1]
            else:
                extension = 'bin'
            
            file_key = f"{prefix}/{user_id}/{timestamp}_{file_id}.{extension}"
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_bytes,
                ContentType=content_type
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_key}"
            
            logger.info(f"Archivo subido exitosamente a S3: {file_key}")
            
            return {
                "success": True,
                "url": file_url,
                "key": file_key,
                "error": None
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Error S3 ClientError: {error_code} - {e}")
            return {
                "success": False,
                "url": None,
                "key": None,
                "error": f"Error S3: {error_code}"
            }
        except Exception as e:
            logger.error(f"Error subiendo archivo a S3: {e}")
            return {
                "success": False,
                "url": None,
                "key": None,
                "error": str(e)
            }
    
    def delete_file(self, file_key):
        """
        Eliminar archivo de S3
        
        Args:
            file_key: Clave del archivo en S3
            
        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            if not self.s3_client:
                return {
                    "success": False,
                    "error": "Cliente S3 no inicializado"
                }
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"Archivo eliminado exitosamente de S3: {file_key}")
            
            return {
                "success": True,
                "error": None
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Error S3 eliminando archivo: {error_code} - {e}")
            return {
                "success": False,
                "error": f"Error S3: {error_code}"
            }
        except Exception as e:
            logger.error(f"Error eliminando archivo de S3: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Instancia global del servicio
s3_service = S3Service()