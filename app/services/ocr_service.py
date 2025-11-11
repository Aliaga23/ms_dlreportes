"""
Servicio OCR para reconocimiento de texto y procesamiento de encuestas
"""

import google.generativeai as genai
from PIL import Image
import json
import cv2
import numpy as np
import io
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class GeminiOCRService:
    def __init__(self, api_key=None):
        """
        Inicializar servicio OCR
        """
        try:
            # Usar API key desde variables de entorno o parámetro
            self.api_key = api_key or os.getenv('GEMINI_API_KEY')
            if not self.api_key:
                raise ValueError("API key no encontrada. Configurar GEMINI_API_KEY en .env")
            
            genai.configure(api_key=self.api_key)
            
            # Configuración optimizada para OCR
            self.generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2000,
            )
            
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash', 
                generation_config=self.generation_config
            )
            
            print(f"OCR Service inicializado correctamente")
            
        except Exception as e:
            print(f"Error inicializando OCR: {e}")
            self.model = None
    
    def extract_text(self, image):
        """
        Extraer texto simple de la imagen
        """
        if self.model is None:
            return {"error": "OCR no disponible"}
        
        try:
            # Optimizar imagen si es muy grande
            pil_image = self._prepare_image(image)
            
            prompt = "Extrae todo el texto visible de esta imagen, IGNORANDO cualquier código QR. Responde solo con el texto extraído, sin explicaciones adicionales."
            
            response = self.model.generate_content([prompt, pil_image])
            
            return {
                "success": True,
                "text": response.text.strip(),
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "text": "",
                "error": str(e)
            }
    
    def process_survey(self, image, survey_template):
        """
        Procesar encuesta completa con plantilla
        """
        if self.model is None:
            return {"error": "OCR no disponible"}
        
        try:
            pil_image = self._prepare_image(image)
            
            prompt = f"""
Extrae el texto de esta imagen y completa esta encuesta. IGNORA cualquier código QR que veas en la imagen.

PLANTILLA DE ENCUESTA:
{json.dumps(survey_template, ensure_ascii=False, indent=2)}

INSTRUCCIONES CRÍTICAS:
1. DEBES responder TODAS las preguntas de la plantilla - no omitas ninguna
2. Para cada pregunta, identifica la respuesta en la imagen
3. Para preguntas con opciones: busca checkboxes marcados (✓), círculos marcados (●), o texto subrayado
4. Para preguntas abiertas: extrae el texto escrito manualmente en campos de texto
5. Si no encuentras respuesta para una pregunta, ponla como "No encontrada" 
6. Mantén EXACTAMENTE la estructura JSON de la plantilla
7. Agrega el campo "respuesta" a cada pregunta con el valor encontrado
8. NO incluyas información de códigos QR
9. IMPORTANTE: Responde las {len(survey_template.get('preguntas', []))} preguntas que están en la plantilla

FORMATO DE RESPUESTA:
Para preguntas con opciones: usar el "texto" de la opción seleccionada
Para preguntas abiertas: usar el texto extraído del campo

Responde SOLO con el JSON completado:
            """
            
            response = self.model.generate_content([prompt, pil_image])
            
            # Limpiar respuesta
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.replace("```", "").strip()
            
            try:
                survey_result = json.loads(response_text)
                
                return {
                    "success": True,
                    "survey_completed": survey_result,
                    "raw_response": response.text,
                    "error": None
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "survey_completed": None,
                    "raw_response": response.text,
                    "error": f"No se pudo parsear el JSON de respuesta: {e}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "survey_completed": None,
                "raw_response": "",
                "error": str(e)
            }
    
    def analyze_form_structure(self, image):
        """
        Analizar estructura del formulario
        """
        if self.model is None:
            return {"error": "OCR no disponible"}
        
        try:
            pil_image = self._prepare_image(image)
            
            prompt = """
Analiza esta imagen de formulario y identifica:
1. Título/encabezado principal
2. Preguntas (enuméralas)
3. Tipos de respuesta (texto libre, opción múltiple, checkbox)
4. Campos de respuesta escritos a mano

Responde en formato JSON:
{
  "titulo": "...",
  "preguntas": [
    {
      "numero": 1,
      "texto": "...",
      "tipo": "texto_abierto|opcion_multiple|checkbox",
      "respuesta_detectada": "..."
    }
  ]
}
            """
            
            response = self.model.generate_content([prompt, pil_image])
            
            # Limpiar respuesta
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.replace("```", "").strip()
            
            try:
                structure = json.loads(response_text)
                return {
                    "success": True,
                    "structure": structure,
                    "raw_response": response.text,
                    "error": None
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "structure": None,
                    "raw_response": response.text,
                    "error": "No se pudo parsear el análisis estructural"
                }
                
        except Exception as e:
            return {
                "success": False,
                "structure": None,
                "raw_response": "",
                "error": str(e)
            }
    
    def extract_handwritten_text(self, image):
        """
        Extraer específicamente texto manuscrito
        """
        if self.model is None:
            return {"error": "OCR no disponible"}
        
        try:
            pil_image = self._prepare_image(image)
            
            prompt = """
Identifica y extrae SOLAMENTE el texto manuscrito/escrito a mano de esta imagen.
Ignora el texto impreso.
Si hay múltiples campos de texto manuscrito, sepáralos claramente.
Responde solo con el texto manuscrito extraído.
            """
            
            response = self.model.generate_content([prompt, pil_image])
            
            return {
                "success": True,
                "handwritten_text": response.text.strip(),
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "handwritten_text": "",
                "error": str(e)
            }
    
    def _prepare_image(self, image):
        """
        Preparar imagen para procesamiento (convertir y optimizar)
        """
        if isinstance(image, np.ndarray):
            # Convertir de OpenCV a PIL
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = image
        
        # Optimizar tamaño si es muy grande
        if pil_image.size[0] > 1024 or pil_image.size[1] > 1024:
            pil_image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        return pil_image
    
    def batch_process_images(self, images, operation="extract_text"):
        """
        Procesar múltiples imágenes en lote
        """
        results = []
        
        for i, image in enumerate(images):
            try:
                if operation == "extract_text":
                    result = self.extract_text(image)
                elif operation == "analyze_structure":
                    result = self.analyze_form_structure(image)
                elif operation == "handwritten":
                    result = self.extract_handwritten_text(image)
                else:
                    result = {"error": f"Operación '{operation}' no soportada"}
                
                result["image_index"] = i
                results.append(result)
                
            except Exception as e:
                results.append({
                    "image_index": i,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "total_processed": len(results),
            "successful": len([r for r in results if r.get("success", False)]),
            "failed": len([r for r in results if not r.get("success", False)]),
            "results": results
        }

# Instancia global del servicio
gemini_ocr = GeminiOCRService()