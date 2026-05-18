#!/bin/bash

echo "=============================="
echo " Limpieza segura del sistema "
echo "=============================="
echo

# 1. Mostrar uso inicial
echo "[INFO] Uso de disco antes:"
df -h /
echo

# 2. Limpiar APT
echo "[INFO] Limpiando cache de APT..."
sudo apt clean
sudo apt autoclean
echo

# 3. Limpiar logs de systemd-journald
echo "[INFO] Limpiando logs antiguos (journald)..."
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=100M
echo

# 4. Detectar kernel actual
KERNEL_ACTUAL="$(uname -r)"
echo "[INFO] Kernel actual en uso: $KERNEL_ACTUAL"
echo

# 5. Listar kernels instalados y borrar los antiguos
echo "[INFO] Buscando kernels antiguos para eliminar..."

dpkg -l | awk '/linux-(image|modules|headers|tools)/ && /generic/ {print $2}' | while read paquete; do
  if [[ "$paquete" != *"$KERNEL_ACTUAL"* ]]; then
    echo "  -> Eliminando $paquete"
    sudo apt -y purge "$paquete"
  fi
done

echo

# 6. Autoremove final
echo "[INFO] Ejecutando autoremove..."
sudo apt -y autoremove --purge
echo

# 7. Intentar reparar paquetes rotos
echo "[INFO] Reparando dependencias rotas (si existen)..."
sudo apt --fix-broken install -y
echo

# 8. Reintentar actualización
echo "[INFO] Reintentando actualización completa..."
sudo apt update
sudo apt -y full-upgrade
echo

# 9. Mostrar uso final
echo "[INFO] Uso de disco después:"
df -h /
echo

echo "=============================="
echo " Limpieza finalizada"
echo "=============================="
