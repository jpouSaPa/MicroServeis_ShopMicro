# Kubernetes / k3s — Manteniment i Supervisió

Guia de referència ràpida per gestionar el cluster k3s del projecte **ShopMicro**.

---

## Índex

1. [Estat del cluster](#1-estat-del-cluster)
2. [Gestió de pods](#2-gestió-de-pods)
3. [Gestió de deployments](#3-gestió-de-deployments)
4. [Logs](#4-logs)
5. [Serveis i xarxa](#5-serveis-i-xarxa)
6. [Secrets i configuració](#6-secrets-i-configuració)
7. [Volums persistents](#7-volums-persistents)
8. [Desplegament i actualització](#8-desplegament-i-actualització)
9. [Escalar serveis](#9-escalar-serveis)
10. [Diagnòstic d'errors](#10-diagnòstic-derrors)
11. [Comandes k3s específiques](#11-comandes-k3s-específiques)

---

## 1. Estat del cluster

```bash
# Veure els nodes del cluster i el seu estat
kubectl get nodes

# Veure els nodes amb més detalls (IP, versió, OS)
kubectl get nodes -o wide

# Informació detallada d'un node concret
kubectl describe node joan01
```

---

## 2. Gestió de pods

```bash
# Llistar tots els pods del namespace shopmicro
kubectl get pods -n shopmicro

# Llistar pods amb més detalls (node, IP)
kubectl get pods -n shopmicro -o wide

# Veure l'estat dels pods en temps real
kubectl get pods -n shopmicro -w

# Informació detallada d'un pod (events, volums, variables d'entorn)
kubectl describe pod <nom-del-pod> -n shopmicro

# Eliminar un pod (Kubernetes el recrearà automàticament)
kubectl delete pod <nom-del-pod> -n shopmicro

# Entrar dins d'un pod (shell interactiu)
kubectl exec -it <nom-del-pod> -n shopmicro -- /bin/sh

# Executar una comanda puntual dins d'un pod
kubectl exec -n shopmicro deployment/product-service -- wget -qO- http://localhost:5000/health
```

---

## 3. Gestió de deployments

```bash
# Llistar tots els deployments
kubectl get deployments -n shopmicro

# Informació detallada d'un deployment
kubectl describe deployment user-service -n shopmicro

# Reiniciar un deployment (força la baixada de la nova imatge)
kubectl rollout restart deployment/user-service -n shopmicro

# Veure l'estat d'un rollout en curs
kubectl rollout status deployment/user-service -n shopmicro

# Historial de canvis d'un deployment
kubectl rollout history deployment/user-service -n shopmicro

# Tornar a la versió anterior (rollback)
kubectl rollout undo deployment/user-service -n shopmicro
```

---

## 4. Logs

```bash
# Veure els logs d'un pod
kubectl logs <nom-del-pod> -n shopmicro

# Seguir els logs en temps real
kubectl logs -f <nom-del-pod> -n shopmicro

# Veure els logs del deployment (agafa un pod automàticament)
kubectl logs -f deployment/order-service -n shopmicro

# Veure els logs de totes les rèpliques d'un deployment
kubectl logs -f deployment/product-service -n shopmicro --all-containers

# Veure els logs del pod anterior (útil si ha petat i s'ha recreat)
kubectl logs <nom-del-pod> -n shopmicro --previous

# Veure només les últimes N línies
kubectl logs <nom-del-pod> -n shopmicro --tail=100
```

---

## 5. Serveis i xarxa

```bash
# Llistar tots els serveis
kubectl get services -n shopmicro

# Veure les IPs externes (LoadBalancer)
kubectl get services -n shopmicro | grep LoadBalancer

# Informació detallada d'un servei
kubectl describe service api-gateway -n shopmicro

# Provar connectivitat entre pods
kubectl exec -n shopmicro deployment/frontend -- wget -qO- http://api-gateway/health

# Provar un servei des de fora del cluster
curl http://<IP-del-node>:<NodePort>/health

# Ports del projecte ShopMicro:
#   Frontend:    http://<IP>:30916
#   API Gateway: http://<IP>:31232
```

---

## 6. Secrets i configuració

```bash
# Llistar els secrets
kubectl get secrets -n shopmicro

# Veure el contingut d'un secret (en base64)
kubectl get secret db-root-password-products -n shopmicro -o yaml

# Decodificar un secret
kubectl get secret db-root-password-products -n shopmicro \
  -o jsonpath='{.data.password}' | base64 -d

# Crear o actualitzar secrets (reaplicar el fitxer)
kubectl apply -f k8s/secrets-db.yml
```

---

## 7. Volums persistents

```bash
# Llistar els PersistentVolumeClaims
kubectl get pvc -n shopmicro

# Veure l'estat dels PersistentVolumes
kubectl get pv

# Informació detallada d'un PVC
kubectl describe pvc db-products-pvc -n shopmicro
```

Els PVCs del projecte i la seva mida:

| PVC | Servei | Mida |
|-----|--------|------|
| `db-products-pvc` | MySQL productes | 2Gi |
| `db-orders-pvc` | MySQL comandes | 2Gi |
| `db-users-pvc` | MySQL usuaris | 2Gi |
| `rabbitmq-pvc` | RabbitMQ | 2Gi |

---

## 8. Desplegament i actualització

### Primer desplegament

```bash
# Crear el namespace
kubectl create namespace shopmicro

# Aplicar tots els YAMLs en ordre correcte
cd k8s && bash apply.sh
```

### Actualitzar una imatge

```bash
# 1. Construir la nova imatge
docker build -t jpou/shopmicro-product-service:latest ./product-service

# 2. Pujar al Docker Hub
docker push jpou/shopmicro-product-service:latest

# 3. Forçar que k3s baixi la nova imatge
kubectl rollout restart deployment/product-service -n shopmicro

# 4. Verificar que el rollout ha anat bé
kubectl rollout status deployment/product-service -n shopmicro
```

### Aplicar canvis als YAMLs

```bash
# Aplicar un fitxer concret
kubectl apply -f k8s/product-service.yml

# Aplicar tots els fitxers (script del projecte)
cd k8s && bash apply.sh
```

---

## 9. Escalar serveis

```bash
# Escalar un servei manualment
kubectl scale deployment product-service -n shopmicro --replicas=3

# Tornar a una sola rèplica
kubectl scale deployment product-service -n shopmicro --replicas=1
```

Els serveis **stateless** es poden escalar lliurement:
- `api-gateway`, `frontend`
- `user-service`, `product-service`, `order-service`, `notification-service`

Els serveis **stateful** NO s'han d'escalar amb aquest mètode:
- `db-users`, `db-products`, `db-orders` (MySQL)
- `cache` (Redis)
- `message-queue` (RabbitMQ)

---

## 10. Diagnòstic d'errors

### Pod en `CrashLoopBackOff`

```bash
# Veure els logs del pod que ha petat
kubectl logs <nom-del-pod> -n shopmicro --previous

# Veure els events del pod
kubectl describe pod <nom-del-pod> -n shopmicro
```

### Pod en `Pending`

```bash
# Normalment és falta d'espai o imatge no trobada
kubectl describe pod <nom-del-pod> -n shopmicro
# Mirar la secció "Events" al final
```

### Pod en `ImagePullBackOff`

```bash
# La imatge no s'ha pogut baixar del registry
# Comprovar que el nom de la imatge és correcte al YAML
kubectl describe pod <nom-del-pod> -n shopmicro | grep Image
```

### Comprovar espai al disc

```bash
df -h /
docker system df
```

### Netejar imatges antigues de Docker

```bash
# Eliminar imatges sense tag
docker image prune -f

# Netejar tot el que no s'usa (imatges, contenidors aturats, cache)
docker system prune -f
```

---

## 11. Comandes k3s específiques

```bash
# Estat del servei k3s
sudo systemctl status k3s

# Reiniciar k3s
sudo systemctl restart k3s

# Veure les imatges que té containerd (runtime de k3s)
sudo k3s crictl images

# Importar una imatge local a containerd manualment
docker save jpou/shopmicro-api-gateway:latest | sudo k3s ctr images import -

# Veure els logs del servei k3s
sudo journalctl -u k3s -f

# Veure l'ús de recursos dels nodes
kubectl top nodes

# Veure l'ús de recursos dels pods
kubectl top pods -n shopmicro
```

---

## Referència ràpida de serveis ShopMicro

| Servei | Port intern | Tecnologia | Escala |
|--------|-------------|------------|--------|
| `frontend` | 80 | nginx | ✅ Sí |
| `api-gateway` | 80 | nginx | ✅ Sí |
| `user-service` | 5002 | Flask + gunicorn | ✅ Sí |
| `product-service` | 5000 | Flask + gunicorn | ✅ Sí |
| `order-service` | 5001 | Flask + gunicorn | ✅ Sí |
| `notification-service` | 5003 | Python + pika | ✅ Sí |
| `db-users` | 3306 | MySQL 8.0 | ⚠️ StatefulSet |
| `db-products` | 3306 | MySQL 8.0 | ⚠️ StatefulSet |
| `db-orders` | 3306 | MySQL 8.0 | ⚠️ StatefulSet |
| `cache` | 6379 | Redis 7 | ⚠️ StatefulSet |
| `message-queue` | 5672/15672 | RabbitMQ | ⚠️ StatefulSet |
