#!/bin/bash

# Instalador da Loja de Aplicativos Linux
# Para sistemas Debian/Ubuntu no Termux

set -e

echo "=== Instalador da Loja de Aplicativos Linux ==="

# Verifica sistema
if ! command -v apt-get &> /dev/null; then
    echo "Erro: Este instalador requer um sistema Debian/Ubuntu"
    exit 1
fi

# Atualiza repositórios
echo "Atualizando repositórios..."
apt-get update

# Instala dependências
echo "Instalando dependências..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.0 \
    python3-requests \
    xdg-utils \
    desktop-file-utils

# Instala dependências Python
echo "Instalando dependências Python..."
pip3 install --user requests

# Cria diretórios
echo "Criando diretórios..."
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/software-store

# Copia arquivo principal
echo "Instalando aplicativo..."
cp software-store.py ~/.local/bin/software-store
chmod +x ~/.local/bin/software-store

# Cria arquivo .desktop
echo "Criando entrada no menu..."
cat > ~/.local/share/applications/software-store.desktop << EOF
[Desktop Entry]
Name=Loja de Aplicativos
Name[en]=Software Store
Comment=Loja de aplicativos para Debian/Ubuntu
Comment[en]=Software store for Debian/Ubuntu
Exec=python3 ~/.local/bin/software-store
Icon=applications-accessories
Terminal=false
Type=Application
Categories=System;PackageManager;
MimeType=x-scheme-handler/software-store;
StartupNotify=true
EOF

# Torna executável
chmod +x ~/.local/share/applications/software-store.desktop

# Registra esquema URI
echo "Registrando deeplinks..."
xdg-mime default software-store.desktop x-scheme-handler/software-store

# Atualiza cache do desktop
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

# Adiciona ao PATH se necessário
if ! echo $PATH | grep -q ~/.local/bin; then
    echo ""
    echo "IMPORTANTE: Adicione ~/.local/bin ao seu PATH"
    echo "Execute: echo 'export PATH=\$PATH:\$HOME/.local/bin' >> ~/.bashrc"
    echo "E depois: source ~/.bashrc"
fi

echo ""
echo "=== Instalação concluída! ==="
echo ""
echo "Para iniciar a loja de aplicativos:"
echo "1. Execute: python3 ~/.local/bin/software-store"
echo "2. Ou procure por 'Loja de Aplicativos' no menu"
echo ""
echo "Para testar deeplinks, abra no navegador:"
echo "software-store://pkg?search=inkscape"
echo ""
echo "Recursos disponíveis:"
echo "- Busca de pacotes do repositório"
echo "- Instalação e remoção de programas"
echo "- Suporte a deeplinks"
echo "- Interface responsiva"
echo "- Aplicativos em destaque"
echo "- Modificação automática para apps que precisam --no-sandbox"
echo ""