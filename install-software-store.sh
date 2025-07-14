#!/bin/bash

# Script de instalação do Software Store
# Para usar: bash install.sh

echo "=== Instalação do Software Store ==="
echo

# Verificar se está rodando como root
if [[ $EUID -eq 0 ]]; then
   echo "Este script não deve ser executado como root"
   echo "Execute: bash install.sh"
   exit 1
fi

# Verificar dependências
echo "Verificando dependências..."

# Lista de pacotes necessários
DEPS=(
    "python3"
    "python3-gi"
    "python3-gi-cairo"
    "gir1.2-gtk-3.0"
    "gir1.2-webkit2-4.0"
    "apt-utils"
    "sudo"
)

MISSING_DEPS=()

for dep in "${DEPS[@]}"; do
    if ! dpkg -l | grep -q "^ii  $dep "; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Instalando dependências em falta..."
    echo "Pacotes necessários: ${MISSING_DEPS[*]}"
    
    sudo apt-get update
    sudo apt-get install -y "${MISSING_DEPS[@]}"
    
    if [ $? -ne 0 ]; then
        echo "Erro ao instalar dependências"
        exit 1
    fi
fi

echo "✓ Todas as dependências estão instaladas"

# Criar diretórios necessários
echo "Criando diretórios..."
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/bin

# Baixar ou usar o arquivo software-store.py
if [ -f "software-store.py" ]; then
    echo "Usando arquivo software-store.py local..."
    SCRIPT_FILE="software-store.py"
else
    echo "Erro: arquivo software-store.py não encontrado"
    echo "Certifique-se de que o arquivo está no mesmo diretório que este script"
    exit 1
fi

# Copiar arquivo para ~/.local/bin
echo "Instalando aplicativo..."
cp "$SCRIPT_FILE" ~/.local/bin/software-store.py
chmod +x ~/.local/bin/software-store.py

# Criar arquivo .desktop
echo "Criando entrada no menu..."
cat > ~/.local/share/applications/software-store.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Software Store
Comment=Loja de aplicativos Linux para Termux/proot-distro
Exec=$HOME/.local/bin/software-store.py %U
Icon=software-store
Terminal=false
NoDisplay=false
Categories=System;PackageManager;
MimeType=x-scheme-handler/software-store;
StartupNotify=true
EOF

chmod +x ~/.local/share/applications/software-store.desktop

# Registrar handler de deeplink
echo "Registrando handler de deeplink..."
if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default software-store.desktop x-scheme-handler/software-store
fi

# Atualizar cache de aplicativos
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database ~/.local/share/applications
fi

# Adicionar ~/.local/bin ao PATH se necessário
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "Adicionando ~/.local/bin ao PATH..."
    
    # Adicionar ao .bashrc
    if [ -f ~/.bashrc ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi
    
    # Adicionar ao .profile
    if [ -f ~/.profile ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile
    fi
    
    echo "Reinicie o terminal ou execute: source ~/.bashrc"
fi

echo
echo "=== Instalação concluída com sucesso! ==="
echo
echo "Para executar a Software Store:"
echo "  1. Procure por 'Software Store' no menu de aplicativos"
echo "  2. Execute: ~/.local/bin/software-store.py"
echo "  3. Use deeplinks: software-store://pkg?search=inkscape"
echo
echo "Exemplo de uso:"
echo "  software-store://pkg?search=inkscape"
echo "  software-store://pkg?search=gimp"
echo "  software-store://pkg?search=firefox"
echo
echo "Funcionalidades principais:"
echo "  • Interface gráfica moderna com tema GTK3"
echo "  • Busca de pacotes em repositórios Debian/Ubuntu"
echo "  • Carrossel de aplicativos em destaque"
echo "  • Suporte a deeplinks para instalação rápida"
echo "  • Compatível com Termux/proot-distro"
echo "  • Adiciona automaticamente --no-sandbox para apps necessários"
echo "  • Interface responsiva para diferentes tamanhos de tela"
echo