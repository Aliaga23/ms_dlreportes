"""
API principal con estructura modular
Integra el router OCR con los endpoints existentes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.ocr_router import router as ocr_router
from app.routers.reports_router import router as reports_router
from app.routers.audio_router import router as audio_router

# Crear aplicación FastAPI
app = FastAPI(
    title="API de Reconocimiento de Texto y Audio con IA",
    description="API modular para OCR, Audio, checkboxes y procesamiento de encuestas",
    version="2.1.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Incluir routers
app.include_router(ocr_router)
app.include_router(audio_router)
app.include_router(reports_router)

# Endpoint principal
@app.get("/")
async def root():
    return {
        "message": "API de Reconocimiento de Texto con IA v2.0",
        "description": "API que procesa automáticamente encuestas desde imágenes usando QR y OCR"
    }

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "API funcionando correctamente"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  