"""
Servicio de reportes y KPIs para la plataforma de encuestas
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import requests
from pymongo import MongoClient
from bson import ObjectId

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class ReportsService:
    def __init__(self):
        """
        Inicializar servicio de reportes
        """
        self.database_url = os.getenv('RAILWAY_DATABASE_URL')
        if not self.database_url:
            raise ValueError("RAILWAY_DATABASE_URL no está configurada en el archivo .env")
        
        self.connection = None
        
        # Configurar MongoDB para usuarios
        self.mongo_url = os.getenv('MONGODB_URL')
        if not self.mongo_url:
            raise ValueError("MONGODB_URL no está configurada en el archivo .env")
        
        self.mongo_client = None
        self.mongo_db = None
        
        # Configurar OpenAI
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = None
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        self._connect()
        self._connect_mongo()
    
    def _connect(self):
        """Establecer conexión con la base de datos"""
        try:
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            logger.info("Conexión exitosa a PostgreSQL para reportes")
        except Exception as e:
            logger.error(f"Error conectando a PostgreSQL: {e}")
            self.connection = None
    
    def _connect_mongo(self):
        """Establecer conexión con MongoDB"""
        try:
            self.mongo_client = MongoClient(self.mongo_url)
            self.mongo_db = self.mongo_client['sw2p2go_db']
            # Probar la conexión
            self.mongo_client.admin.command('ismaster')
            logger.info("Conexión exitosa a MongoDB para usuarios")
        except Exception as e:
            logger.error(f"Error conectando a MongoDB: {e}")
            self.mongo_client = None
            self.mongo_db = None
    
    def _ensure_connection(self):
        """Asegurar que la conexión esté activa"""
        if not self.connection or self.connection.closed:
            self._connect()
    
    def execute_query(self, query, description=""):
        """
        Ejecutar consulta SQL
        
        Args:
            query: Consulta SQL
            description: Descripción de la consulta
            
        Returns:
            list: Resultados de la consulta
        """
        try:
            self._ensure_connection()
            
            if not self.connection:
                logger.error("No se pudo establecer conexión con la base de datos")
                return []
            
            cursor = self.connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            logger.error(f"Error en consulta '{description}': {e}")
            return []
    
    def get_usuarios_names(self, user_ids):
        """
        Obtener nombres de usuarios desde MongoDB
        
        Args:
            user_ids: Lista de IDs de usuarios
            
        Returns:
            dict: Mapeo de user_id -> nombre
        """
        try:
            if self.mongo_db is None:
                logger.warning("No hay conexión a MongoDB")
                return {}
            
            # Buscar usuarios en MongoDB por sus IDs
            usuarios_collection = self.mongo_db['usuarios']
            
            logger.info(f"Buscando usuarios con IDs: {user_ids}")
            
            # Primero intentar con ObjectId
            object_ids = []
            string_ids = []
            
            for user_id in user_ids:
                try:
                    # Intentar convertir a ObjectId
                    obj_id = ObjectId(user_id)
                    object_ids.append(obj_id)
                    logger.info(f"ID {user_id} convertido a ObjectId: {obj_id}")
                except Exception as e:
                    # Si falla, usar como string
                    string_ids.append(user_id)
                    logger.info(f"ID {user_id} usado como string: {e}")
            
            # Crear query dinámico
            query_parts = []
            if object_ids:
                query_parts.append({"_id": {"$in": object_ids}})
            if string_ids:
                query_parts.append({"_id": {"$in": string_ids}})
            
            if not query_parts:
                logger.warning("No se pudieron procesar los user_ids")
                return {}
            
            query = {"$or": query_parts} if len(query_parts) > 1 else query_parts[0]
            logger.info(f"Query MongoDB: {query}")
            
            usuarios_cursor = usuarios_collection.find(query, {"_id": 1, "nombre": 1})
            
            usuarios_map = {}
            for usuario in usuarios_cursor:
                usuarios_map[str(usuario['_id'])] = usuario.get('nombre', f"Usuario {usuario['_id']}")
            
            logger.info(f"Obtenidos {len(usuarios_map)} nombres de usuarios desde MongoDB")
            return usuarios_map
                
        except Exception as e:
            logger.error(f"Error obteniendo nombres de usuarios desde MongoDB: {e}")
            return {}
    
    def get_usuarios_stats(self):
        """Obtener estadísticas de usuarios"""
        query_usuarios = """
        SELECT 
          COUNT(DISTINCT user_id) as usuarios_activos,
          COUNT(DISTINCT CASE WHEN creado_en >= NOW() - INTERVAL '30 days' THEN user_id END) as usuarios_mes_actual
        FROM (
          SELECT user_id, creado_en FROM encuesta
          UNION
          SELECT user_id, creado_en FROM destinatario
          UNION
          SELECT user_id, creado_en FROM campaña
        ) usuarios;
        """
        
        usuarios_result = self.execute_query(query_usuarios, "Estadísticas de usuarios")
        
        if usuarios_result:
            row = usuarios_result[0]
            return {
                "total_activos": row['usuarios_activos'] or 0,
                "nuevos_este_mes": row['usuarios_mes_actual'] or 0
            }
        
        return {"total_activos": 0, "nuevos_este_mes": 0}
    
    def get_respuestas_stats(self):
        """Obtener estadísticas de respuestas"""
        query_respuestas = """
        SELECT 
          COUNT(*) as total_respuestas,
          COUNT(CASE WHEN recibido_en >= NOW() - INTERVAL '7 days' THEN 1 END) as respuestas_ultima_semana,
          COUNT(CASE WHEN recibido_en >= NOW() - INTERVAL '30 days' THEN 1 END) as respuestas_ultimo_mes,
          COUNT(DISTINCT "entregaId") as entregas_con_respuestas
        FROM respuesta
        WHERE recibido_en IS NOT NULL;
        """
        
        respuestas_result = self.execute_query(query_respuestas, "Estadísticas de respuestas")
        
        if respuestas_result:
            row = respuestas_result[0]
            return {
                "total": row['total_respuestas'] or 0,
                "ultima_semana": row['respuestas_ultima_semana'] or 0,
                "ultimo_mes": row['respuestas_ultimo_mes'] or 0,
                "entregas_con_respuestas": row['entregas_con_respuestas'] or 0
            }
        
        return {"total": 0, "ultima_semana": 0, "ultimo_mes": 0, "entregas_con_respuestas": 0}
    
    def get_uso_promedio_stats(self):
        """Obtener estadísticas de uso promedio"""
        query_promedios = """
        WITH user_stats AS (
          SELECT 
            e.user_id,
            COUNT(DISTINCT e.id) as num_encuestas,
            COALESCE(COUNT(DISTINCT d.id), 0) as num_destinatarios,
            COALESCE(COUNT(DISTINCT en.id), 0) as num_entregas
          FROM encuesta e
          LEFT JOIN destinatario d ON d.user_id = e.user_id
          LEFT JOIN entrega en ON en."encuestaId" = e.id
          GROUP BY e.user_id
        )
        SELECT 
          COALESCE(AVG(NULLIF(num_encuestas, 0)), 0) as promedio_encuestas_por_usuario,
          COALESCE(AVG(NULLIF(num_destinatarios, 0)), 0) as promedio_destinatarios_por_usuario,
          COALESCE(AVG(NULLIF(num_entregas, 0)), 0) as promedio_entregas_por_usuario
        FROM user_stats
        WHERE num_encuestas > 0;
        """
        
        promedio_result = self.execute_query(query_promedios, "Estadísticas de uso promedio")
        
        if promedio_result:
            row = promedio_result[0]
            return {
                "encuestas_por_usuario": round(float(row['promedio_encuestas_por_usuario'] or 0), 1),
                "destinatarios_por_usuario": round(float(row['promedio_destinatarios_por_usuario'] or 0), 1),
                "entregas_por_usuario": round(float(row['promedio_entregas_por_usuario'] or 0), 1)
            }
        
        return {"encuestas_por_usuario": 0, "destinatarios_por_usuario": 0, "entregas_por_usuario": 0}
    
    def get_tipos_pregunta_stats(self):
        """Obtener estadísticas de tipos de pregunta"""
        query_tipos = """
        SELECT 
          tp.nombre as tipo_pregunta,
          COUNT(*) as total_preguntas,
          ROUND(
            COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0), 
            1
          ) as porcentaje,
          COUNT(DISTINCT p."encuestaId") as encuestas_usando_tipo
        FROM preguntas p
        JOIN tipo_pregunta tp ON tp.id = p."tipo_preguntaId"
        GROUP BY tp.id, tp.nombre
        ORDER BY total_preguntas DESC;
        """
        
        tipos_result = self.execute_query(query_tipos, "Estadísticas de tipos de pregunta")
        
        tipos_populares = []
        for row in tipos_result:
            tipos_populares.append({
                "tipo": row['tipo_pregunta'],
                "total": row['total_preguntas'] or 0,
                "porcentaje": round(float(row['porcentaje'] or 0), 1),
                "encuestas_usando": row['encuestas_usando_tipo'] or 0
            })
        
        return tipos_populares
    
    def get_top_usuarios_activos(self):
        """Obtener top 5 usuarios más activos con sus nombres"""
        query_top_usuarios = """
        SELECT 
          e.user_id,
          COUNT(DISTINCT e.id) as total_encuestas,
          COUNT(DISTINCT en.id) as total_entregas,
          COUNT(DISTINCT r.id) as total_respuestas
        FROM encuesta e
        LEFT JOIN entrega en ON en."encuestaId" = e.id
        LEFT JOIN respuesta r ON r."entregaId" = en.id
        GROUP BY e.user_id
        ORDER BY total_respuestas DESC, total_encuestas DESC
        LIMIT 5;
        """
        
        usuarios_result = self.execute_query(query_top_usuarios, "Top 5 usuarios más activos")
        
        if not usuarios_result:
            return []
        
        # Extraer los user_ids para buscar nombres
        user_ids = [str(row['user_id']) for row in usuarios_result]
        usuarios_names = self.get_usuarios_names(user_ids)
        
        usuarios_activos = []
        for row in usuarios_result:
            user_id = str(row['user_id'])
            usuarios_activos.append({
                "user_id": user_id,
                "nombre": usuarios_names.get(user_id, f"Usuario {user_id}"),
                "total_encuestas": row['total_encuestas'] or 0,
                "total_entregas": row['total_entregas'] or 0,
                "total_respuestas": row['total_respuestas'] or 0
            })
        
        return usuarios_activos
    
    def generate_ai_insights(self, kpi_data):
        """
        Generar conclusiones usando GPT-4 mini
        
        Args:
            kpi_data: Diccionario con todos los KPIs
            
        Returns:
            dict: Conclusiones generadas por AI
        """
        if not self.openai_api_key or not self.openai_client:
            return {
                "resumen_ejecutivo": "Análisis AI no disponible - Configurar OPENAI_API_KEY",
                "tendencias": [],
                "recomendaciones": [],
                "alertas": []
            }
        
        try:
            # Preparar prompt con los datos
            prompt = f"""
            Analiza los siguientes KPIs de una plataforma de encuestas y proporciona conclusiones breves:

            DATOS:
            - Usuarios totales activos: {kpi_data['usuarios']['total_activos']}
            - Nuevos usuarios este mes: {kpi_data['usuarios']['nuevos_este_mes']}
            - Total respuestas: {kpi_data['respuestas']['total']}
            - Respuestas última semana: {kpi_data['respuestas']['ultima_semana']}
            - Respuestas último mes: {kpi_data['respuestas']['ultimo_mes']}
            - Promedio encuestas por usuario: {kpi_data['uso_promedio']['encuestas_por_usuario']}
            - Top usuarios activos: {len(kpi_data['top_usuarios_activos'])} usuarios con actividad significativa

            Proporciona un análisis en formato JSON con:
            - resumen_ejecutivo (1-2 frases)
            - tendencias (lista de 2-3 observaciones clave)
            - recomendaciones (lista de 2-3 acciones)
            - alertas (lista de 0-2 puntos de atención)
            
            Responde SOLO con el JSON válido:
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista de datos especializado en métricas de plataformas digitales. Responde solo con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            import json
            ai_response = response.choices[0].message.content.strip()
            
            # Limpiar respuesta si tiene markdown
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.replace("```", "").strip()
            
            insights = json.loads(ai_response)
            logger.info("Conclusiones AI generadas exitosamente")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generando conclusiones AI: {e}")
            return {
                "resumen_ejecutivo": f"Error generando análisis: {str(e)}",
                "tendencias": ["Análisis no disponible temporalmente"],
                "recomendaciones": ["Revisar configuración de AI"],
                "alertas": ["Sistema de análisis en mantenimiento"]
            }
    
    def get_kpi_report(self):
        """
        Generar reporte completo de KPIs con conclusiones AI
        
        Returns:
            dict: Reporte completo con datos y conclusiones
        """
        logger.info("Generando reporte de KPIs completo...")
        
        try:
            # Obtener todas las métricas
            usuarios_stats = self.get_usuarios_stats()
            respuestas_stats = self.get_respuestas_stats()
            uso_promedio_stats = self.get_uso_promedio_stats()
            tipos_pregunta_stats = self.get_tipos_pregunta_stats()
            top_usuarios_stats = self.get_top_usuarios_activos()
            
            # Agregar promedio de encuestas a usuarios
            usuarios_stats["promedio_encuestas"] = uso_promedio_stats["encuestas_por_usuario"]
            
            # Estructurar datos para AI
            kpi_data = {
                "usuarios": usuarios_stats,
                "respuestas": respuestas_stats,
                "uso_promedio": uso_promedio_stats,
                "tipos_pregunta_populares": tipos_pregunta_stats,
                "top_usuarios_activos": top_usuarios_stats
            }
            
            # Generar conclusiones AI
            ai_insights = self.generate_ai_insights(kpi_data)
            
            # Reporte final
            reporte = {
                "generado_en": datetime.now().isoformat(),
                "usuarios": usuarios_stats,
                "respuestas": respuestas_stats,
                "uso_promedio": uso_promedio_stats,
                "tipos_pregunta_populares": tipos_pregunta_stats,
                "top_usuarios_activos": top_usuarios_stats,
                "conclusiones_ai": ai_insights
            }
            
            logger.info("Reporte de KPIs generado exitosamente")
            return {
                "success": True,
                "data": reporte,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error generando reporte KPIs: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
    
    def close(self):
        """Cerrar conexiones"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Conexión PostgreSQL cerrada")
        
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("Conexión MongoDB cerrada")

# Instancia global del servicio
reports_service = ReportsService()