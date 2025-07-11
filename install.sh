#!/bin/bash

# Script de instalação da Loja de Aplicativos para Debian/Ubuntu
# Compatível com Termux/proot e sistemas ARM64/ARMhf

echo "=== Instalação da Loja de Aplicativos ==="
echo "Verificando dependências..."

# Verificar se está rodando como root
if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

# Função para verificar se um comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificar e instalar dependências
echo "Instalando dependências..."

# Atualizar repositórios
echo "Atualizando repositórios..."
$SUDO apt update

# Instalar Python3 e tkinter
if ! command_exists python3; then
    echo "Instalando Python3..."
    $SUDO apt install -y python3
fi

# Instalar tkinter
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Instalando python3-tkinter..."
    $SUDO apt install -y python3-tk
fi

# Instalar PIL (opcional, para ícones)
if ! python3 -c "import PIL" 2>/dev/null; then
    echo "Instalando PIL (opcional)..."
    $SUDO apt install -y python3-pil python3-pil.imagetk 2>/dev/null || echo "PIL não disponível, continuando sem ícones"
fi

# Verificar se o diretório de destino existe
if [ ! -d "/usr/local/bin" ]; then
    echo "Criando diretório /usr/local/bin..."
    $SUDO mkdir -p /usr/local/bin
fi

# Copiar o script principal
echo "Instalando aplicação..."
$SUDO cp app_store.py /usr/local/bin/
$SUDO chmod +x /usr/local/bin/app_store.py

# Criar diretório para arquivos .desktop
DESKTOP_DIR="$HOME/.local/share/applications"
if [ ! -d "$DESKTOP_DIR" ]; then
    mkdir -p "$DESKTOP_DIR"
fi

# Instalar arquivo .desktop
echo "Criando entrada no menu..."
cat > "$DESKTOP_DIR/app-store.desktop" << 'EOF'
[Desktop Entry]
Name=Loja de Aplicativos
Name[en]=App Store
Comment=Loja de aplicativos para Debian/Ubuntu
Comment[en]=App store for Debian/Ubuntu
Exec=python3 /usr/local/bin/app_store.py
Icon=software-store
Type=Application
Categories=System;PackageManager;
StartupNotify=true
Keywords=software;package;install;apt;store;loja;aplicativo
EOF

# Tornar o arquivo .desktop executável
chmod +x "$DESKTOP_DIR/app-store.desktop"

# Criar link simbólico para facilitar execução via terminal
echo "Criando comando 'app-store'..."
$SUDO ln -sf /usr/local/bin/app_store.py /usr/local/bin/app-store

# Verificar se a instalação foi bem-sucedida
echo ""
echo "=== Verificação da Instalação ==="
if [ -f "/usr/local/bin/app_store.py" ]; then
    echo "✓ Aplicação instalada em /usr/local/bin/app_store.py"
else
    echo "✗ Erro: Aplicação não foi instalada"
    exit 1
fi

if [ -f "$DESKTOP_DIR/app-store.desktop" ]; then
    echo "✓ Entrada do menu criada em $DESKTOP_DIR/app-store.desktop"
else
    echo "✗ Erro: Entrada do menu não foi criada"
fi

if command_exists python3; then
    echo "✓ Python3 está instalado"
else
    echo "✗ Erro: Python3 não está disponível"
    exit 1
fi

if python3 -c "import tkinter" 2>/dev/null; then
    echo "✓ Tkinter está disponível"
else
    echo "✗ Erro: Tkinter não está disponível"
    exit 1
fi

# Testar importação PIL
if python3 -c "import PIL" 2>/dev/null; then
    echo "✓ PIL está disponível (ícones funcionarão)"
else
    echo "! PIL não está disponível (ícones não funcionarão, mas a aplicação funciona)"
fi

echo ""
echo "=== Instalação Concluída ==="
echo "Para executar a Loja de Aplicativos:"
echo "1. Via menu: Procure por 'Loja de Aplicativos' no menu de aplicações"
echo "2. Via terminal: Digite 'app-store' ou 'python3 /usr/local/bin/app_store.py'"
echo ""
echo "Notas importantes:"
echo "- A aplicação funciona em GNOME, XFCE, LXDE, LXQt e outros ambientes"
echo "- Para instalar/remover pacotes, você pode precisar inserir a senha sudo"
echo "- Aplicativos como Chromium, Brave, Code são automaticamente configurados com --no-sandbox"
echo "- O cache de pacotes é salvo em ~/.app_store_cache.json"
echo ""
echo "Deseja executar a aplicação agora? (s/n)"
read -r response
if [[ "$response" =~ ^[Ss]$ ]]; then
    echo "Iniciando Loja de Aplicativos..."
    python3 /usr/local/bin/app_store.py &
    echo "Aplicação iniciada em segundo plano"
fi

echo "Instalação finalizada!"