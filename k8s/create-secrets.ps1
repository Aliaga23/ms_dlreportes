# Script para crear secrets desde archivos locales
# Ejecutar este script ANTES de aplicar el deployment

# 1. Crear secret desde .env
Write-Host "Creando secret desde .env..." -ForegroundColor Green
kubectl create secret generic sw2p2-env-secrets --from-env-file=../.env --dry-run=client -o yaml | kubectl apply -f -

# 2. Crear secret desde firebase-service-account.json
Write-Host "Creando secret desde firebase-service-account.json..." -ForegroundColor Green
kubectl create secret generic firebase-credentials --from-file=firebase-service-account.json=../firebase-service-account.json --dry-run=client -o yaml | kubectl apply -f -

Write-Host "`nSecrets creados exitosamente!" -ForegroundColor Green
Write-Host "Ahora puedes aplicar el deployment con: kubectl apply -f deployment.yaml" -ForegroundColor Yellow
