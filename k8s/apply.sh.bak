#!/bin/bash

set -e

echo "──────────────────────────────────────────"
echo "  Aplicant TOTS els fitxers .yml del directori"
echo "──────────────────────────────────────────"

for f in *.yml; do
    if [ -f "$f" ]; then
        echo "[+] Aplicant: $f"
        kubectl apply -f "$f"
    fi
done

echo "──────────────────────────────────────────"
echo "  ✅ Tot aplicat correctament!"
echo "──────────────────────────────────────────"
