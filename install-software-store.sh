#!/bin/bash

set -e

INSTALL_DIR="/opt/software-store"
BIN_PATH="/usr/local/bin/software-store"
DESKTOP_PATH="/usr/share/applications/software-store.desktop"

echo "Instalando dependências Python (é necessário python3, python3-gi, gir1.2-webkit2-4.0, gir1.2-gtk-3.0)..."
sudo apt-get update
sudo apt-get install -y python3 python3-gi gir1.2-webkit2-4.0 gir1.2-gtk-3.0

echo "Copiando arquivos da loja para $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r ./* "$INSTALL_DIR"

echo "Criando lançador em $BIN_PATH..."
sudo tee "$BIN_PATH" > /dev/null << EOF
#!/bin/bash
python3 $INSTALL_DIR/main.py
EOF
sudo chmod +x "$BIN_PATH"

echo "Criando atalho de menu em $DESKTOP_PATH..."
sudo tee "$DESKTOP_PATH" > /dev/null << EOF
[Desktop Entry]
Name=Software Store
Exec=software-store
Icon=applications
Type=Application
Terminal=false
Categories=System;
Comment=Loja de Aplicativos estilo GNOME Software para Debian/Ubuntu
EOF

echo "Instalação concluída! Execute 'software-store' para iniciar a interface gráfica."