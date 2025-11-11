# Guía de Despliegue en DigitalOcean Kubernetes (DOKS)

## Prerequisitos
- Docker instalado y configurado
- doctl instalado y autenticado
- kubectl instalado
- Cluster de Kubernetes en DigitalOcean creado

## Pasos de Despliegue

### 1. Conectar kubectl a tu cluster DOKS
```powershell
# Listar tus clusters
doctl kubernetes cluster list

# Conectar kubectl al cluster
doctl kubernetes cluster kubeconfig save <tu-cluster-id>

# Verificar conexión
kubectl cluster-info
```

### 2. Crear los Secrets
Los secrets contienen las variables de entorno (.env) y el archivo de Firebase.

```powershell
# Desde la carpeta k8s/
cd k8s
.\create-secrets.ps1
```

O manualmente:
```powershell
# Crear secret desde .env
kubectl create secret generic sw2p2-env-secrets --from-env-file=.env

# Crear secret desde firebase JSON
kubectl create secret generic firebase-credentials --from-file=firebase-service-account.json=firebase-service-account.json
```

### 3. Aplicar el Deployment
```powershell
kubectl apply -f deployment.yaml
```

### 4. Aplicar el Service (LoadBalancer)
```powershell
kubectl apply -f service.yaml
```

### 5. Ver el estado del deployment
```powershell
# Ver pods
kubectl get pods

# Ver services y obtener IP externa
kubectl get services

# Ver logs
kubectl logs -l app=sw2p2-dlreportes --tail=100 -f
```

### 6. Obtener la IP del LoadBalancer
```powershell
kubectl get service sw2p2-dlreportes-service
```

La columna `EXTERNAL-IP` tendrá la IP pública de tu aplicación.

## Actualizar la Aplicación

### 1. Construir nueva imagen
```powershell
docker build -t sw2p2-dlreportes:latest .
```

### 2. Etiquetar con nueva versión
```powershell
docker tag sw2p2-dlreportes:latest registry.digitalocean.com/sw2p2-registry/sw2p2-dlreportes:v1.1
```

### 3. Push al registry
```powershell
docker push registry.digitalocean.com/sw2p2-registry/sw2p2-dlreportes:v1.1
```

### 4. Actualizar deployment
```powershell
kubectl set image deployment/sw2p2-dlreportes sw2p2-dlreportes=registry.digitalocean.com/sw2p2-registry/sw2p2-dlreportes:v1.1
```

O edita `deployment.yaml` y vuelve a aplicar:
```powershell
kubectl apply -f deployment.yaml
```

## Comandos Útiles

```powershell
# Ver todos los recursos
kubectl get all

# Describir un pod específico
kubectl describe pod <pod-name>

# Ver logs en tiempo real
kubectl logs -l app=sw2p2-dlreportes -f

# Escalar replicas
kubectl scale deployment sw2p2-dlreportes --replicas=3

# Reiniciar deployment
kubectl rollout restart deployment/sw2p2-dlreportes

# Ver historial de despliegues
kubectl rollout history deployment/sw2p2-dlreportes

# Rollback a versión anterior
kubectl rollout undo deployment/sw2p2-dlreportes

# Ejecutar comando en un pod
kubectl exec -it <pod-name> -- /bin/bash
```

## Verificar la Aplicación

Una vez desplegado, tu API estará disponible en:
```
http://<EXTERNAL-IP>/docs
```

## Troubleshooting

### Ver por qué un pod no inicia
```powershell
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Ver eventos del cluster
```powershell
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Verificar secrets
```powershell
kubectl get secrets
kubectl describe secret sw2p2-env-secrets
```

### Acceder al pod para debugging
```powershell
kubectl exec -it <pod-name> -- /bin/bash
```
