"""
Servicio TrOCR para reconocimiento de texto
Microsoft TrOCR (Text Recognition with OCR)
"""

from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch
import numpy as np
import cv2

class TrOCRService:
    def __init__(self):
        """
        Inicializar TrOCR - Transformer para OCR
        """
        try:
            # Cargar modelo TrOCR pre-entrenado
            self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
            self.model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
            
            # Configurar dispositivo
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
            self.model.eval()
            
            print(f"TrOCR cargado en: {self.device}")
            
        except Exception as e:
            print(f"Error cargando TrOCR: {e}")
            self.model = None
            self.processor = None
    
    def extract_text_from_image(self, image):
        """
        Extraer texto de imagen usando TrOCR
        
        Args:
            image: numpy array (imagen OpenCV) o PIL Image
            
        Returns:
            str: Texto extraído
        """
        if self.model is None or self.processor is None:
            return "TrOCR no disponible"
        
        try:
            # Convertir imagen si es necesario
            if isinstance(image, np.ndarray):
                if len(image.shape) == 3:
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                else:
                    image_rgb = image
                pil_image = Image.fromarray(image_rgb)
            else:
                pil_image = image
            
            # Procesar imagen
            pixel_values = self.processor(pil_image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Generar texto
            with torch.no_grad():
                generated_ids = self.model.generate(pixel_values)
            
            # Decodificar texto
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return generated_text.strip()
            
        except Exception as e:
            print(f"Error en TrOCR: {e}")
            return f"Error procesando imagen: {str(e)}"
    
    def extract_text_from_regions(self, image, regions):
        """
        Extraer texto de múltiples regiones de la imagen
        
        Args:
            image: numpy array (imagen OpenCV)
            regions: list de tuplas (x, y, w, h)
            
        Returns:
            list: Lista de textos extraídos
        """
        results = []
        
        for i, (x, y, w, h) in enumerate(regions):
            try:
                # Extraer región
                roi = image[y:y+h, x:x+w]
                
                # Extraer texto de la región
                text = self.extract_text_from_image(roi)
                
                results.append({
                    'region_id': i + 1,
                    'bbox': (x, y, w, h),
                    'text': text,
                    'confidence': 0.95  # TrOCR no da confianza directa
                })
                
            except Exception as e:
                results.append({
                    'region_id': i + 1,
                    'bbox': (x, y, w, h),
                    'text': f"Error: {str(e)}",
                    'confidence': 0.0
                })
        
        return results
    
    def preprocess_image_for_ocr(self, image):
        """
        Preprocesar imagen para mejor OCR
        """
        # Convertir a escala de grises
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Mejorar contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Reducir ruido
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Binarización adaptativa
        binary = cv2.adaptiveThreshold(
            denoised, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary

# Instancia global del servicio TrOCR
trocr_service = TrOCRService()