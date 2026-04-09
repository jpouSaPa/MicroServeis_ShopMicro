#!/bin/bash

set -e

echo "──────────────────────────────────────────"
echo "  Eliminant recursos definits als .yml"
echo "──────────────────────────────────────────"

# Eliminar deployments, services, secrets, etc.
for f in *.yml; do
    if [ -f "$f" ]; then
        echo "[-] Eliminant: $f"
        kubectl delete -f "$f" --ignore-not-found
    fi
done

echo "──────────────────────────────────────────"
echo "  ✅ Recursos eliminats!"
echo "──────────────────────────────────────────"

# Comprovar si hi ha PVCs al fitxer pvc.yml
if grep -q "PersistentVolumeClaim" pvc.yml 2>/dev/null; then
    echo
    read -p "Vols eliminar també els PVCs i PERDRE les dades? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "[-] Eliminant PVCs"
        kubectl delete -f pvc.yml --ignore-not-found
    else
        echo "[!] PVCs preservats"
    fi
fi

echo "──────────────────────────────────────────"
echo "  ✅ Eliminació finalitzada!"
echo "──────────────────────────────────────────"
