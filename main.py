"""
API principal con estructura modular
Servicio de Audio y Reportes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.ocr_router import router as ocr_router
from app.routers.reports_router import router as reports_router
from app.routers.audio_router import router as audio_router

# Crear aplicación FastAPI
app = FastAPI(
    title="API de Audio, OCR y Reportes con IA",
    description="API para procesamiento de audio con Whisper, OCR con Gemini y reportes",
    version="2.0.0"
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
        "message": "API de Audio y Reportes v2.0",
        "description": "API para procesamiento de audio con Whisper y generación de reportes"
    }

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "API funcionando correctamente"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  