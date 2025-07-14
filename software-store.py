#!/usr/bin/env python3
"""
Linux Software Store - Loja de Aplicativos para Debian/Ubuntu no Termux
Compatível com sistemas arm64 e armhf sem suporte a containers
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio, WebKit2
import subprocess
import json
import requests
import threading
import os
import sys
import urllib.parse
import re
from pathlib import Path

class SoftwareStore:
    def __init__(self):
        self.window = None
        self.webview = None
        self.progress_bar = None
        self.cancel_button = None
        self.current_download = None
        self.featured_apps = []
        self.no_sandbox_apps = []
        self.setup_directories()
        self.load_external_data()
        self.setup_ui()
        self.setup_deeplink_handler()
        
    def setup_directories(self):
        """Configura diretórios necessários"""
        self.app_dir = Path.home() / '.local/share/software-store'
        self.cache_dir = self.app_dir / 'cache'
        self.html_dir = self.app_dir / 'html'
        
        for directory in [self.app_dir, self.cache_dir, self.html_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            
    def load_external_data(self):
        """Carrega dados externos (apps em destaque e lista no-sandbox)"""
        try:
            # Carrega apps em destaque
            featured_url = "https://raw.githubusercontent.com/andistro/app-store/refs/heads/alpha/assets/apps-destaque.json"
            response = requests.get(featured_url, timeout=10)
            if response.status_code == 200:
                self.featured_apps = response.json()
                
            # Carrega lista de apps que precisam --no-sandbox
            no_sandbox_url = "https://raw.githubusercontent.com/andistro/app-store/refs/heads/alpha/assets/no-sandbox.json"
            response = requests.get(no_sandbox_url, timeout=10)
            if response.status_code == 200:
                self.no_sandbox_apps = response.json()
        except Exception as e:
            print(f"Erro ao carregar dados externos: {e}")
            
    def setup_ui(self):
        """Configura a interface principal"""
        self.window = Gtk.Window()
        self.window.set_title("Loja de Aplicativos")
        self.window.set_default_size(900, 600)
        self.window.set_resizable(True)
        self.window.connect("destroy", Gtk.main_quit)
        
        # Aplica tema GTK do sistema
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", False)
        
        # CSS para estilização
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .rounded-button {
                border-radius: 8px;
                min-height: 36px;
                padding: 8px 16px;
            }
            .rounded-entry {
                border-radius: 8px;
                min-height: 36px;
                padding: 8px 12px;
            }
            .card {
                border-radius: 12px;
                border: 1px solid #ddd;
                margin: 8px;
                padding: 16px;
                background: #fafafa;
            }
            .card:hover {
                background: #f0f0f0;
            }
            .progress-bar {
                border-radius: 4px;
                min-height: 6px;
            }
        """)
        
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # Layout principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window.add(main_box)
        
        # Barra de ferramentas
        toolbar = self.create_toolbar()
        main_box.pack_start(toolbar, False, False, 0)
        
        # WebView para conteúdo HTML
        self.webview = WebKit2.WebView()
        self.webview.connect("decide-policy", self.on_navigation_policy)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.webview)
        main_box.pack_start(scrolled, True, True, 0)
        
        # Barra de progresso (inicialmente oculta)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.get_style_context().add_class("progress-bar")
        self.progress_bar.set_no_show_all(True)
        main_box.pack_start(self.progress_bar, False, False, 0)
        
        # Carrega página inicial
        self.load_home_page()
        
    def create_toolbar(self):
        """Cria barra de ferramentas com busca"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_left(12)
        toolbar.set_margin_right(12)
        
        # Botão Home
        home_button = Gtk.Button.new_with_label("Início")
        home_button.get_style_context().add_class("rounded-button")
        home_button.connect("clicked", lambda x: self.load_home_page())
        toolbar.pack_start(home_button, False, False, 0)
        
        # Campo de busca
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Pesquisar aplicativos...")
        self.search_entry.get_style_context().add_class("rounded-entry")
        self.search_entry.connect("activate", self.on_search)
        self.search_entry.connect("search-changed", self.on_search_changed)
        toolbar.pack_start(self.search_entry, True, True, 0)
        
        # Botão de busca
        search_button = Gtk.Button.new_with_label("Buscar")
        search_button.get_style_context().add_class("rounded-button")
        search_button.connect("clicked", self.on_search)
        toolbar.pack_start(search_button, False, False, 0)
        
        return toolbar
        
    def on_search_changed(self, entry):
        """Auto-pesquisa ao digitar (com delay)"""
        query = entry.get_text().strip()
        if len(query) > 2:
            GLib.timeout_add(500, lambda: self.perform_search(query))
            
    def on_search(self, widget):
        """Executa busca"""
        query = self.search_entry.get_text().strip()
        if query:
            self.perform_search(query)
            
    def perform_search(self, query):
        """Realiza busca de pacotes"""
        threading.Thread(target=self._search_packages, args=(query,), daemon=True).start()
        
    def _search_packages(self, query):
        """Busca pacotes no sistema (thread separada)"""
        try:
            # Busca usando apt-cache search
            result = subprocess.run(
                ['apt-cache', 'search', '--names-only', query],
                capture_output=True, text=True, timeout=10
            )
            
            packages = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        description = parts[1].strip()
                        
                        # Obtém versão
                        version = self.get_package_version(name)
                        
                        packages.append({
                            'name': name,
                            'description': description,
                            'version': version,
                            'installed': self.is_package_installed(name)
                        })
            
            # Atualiza UI na thread principal
            GLib.idle_add(self.show_search_results, query, packages)
            
        except Exception as e:
            print(f"Erro na busca: {e}")
            
    def get_package_version(self, package_name):
        """Obtém versão do pacote"""
        try:
            result = subprocess.run(
                ['apt-cache', 'show', package_name],
                capture_output=True, text=True, timeout=5
            )
            
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':', 1)[1].strip()
                    
        except Exception:
            pass
        return "unknown"
        
    def is_package_installed(self, package_name):
        """Verifica se pacote está instalado"""
        try:
            result = subprocess.run(
                ['dpkg', '-l', package_name],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
            
    def show_search_results(self, query, packages):
        """Mostra resultados da busca"""
        html_content = self.generate_search_html(query, packages)
        self.save_and_load_html(html_content, 'search_results.html')
        
    def generate_search_html(self, query, packages):
        """Gera HTML dos resultados de busca"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Resultados da Busca</title>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <div class="container">
                <h1>Resultados para "{query}"</h1>
                <div class="search-results">
        """
        
        for pkg in packages:
            status = "Instalado" if pkg['installed'] else "Instalar"
            button_class = "installed" if pkg['installed'] else "install"
            
            html += f"""
                <div class="package-card">
                    <div class="package-info">
                        <h3>{pkg['name']}</h3>
                        <p class="version">Versão: {pkg['version']}</p>
                        <p class="description">{pkg['description']}</p>
                    </div>
                    <button class="btn {button_class}" onclick="handlePackageAction('{pkg['name']}', '{status}')">
                        {status}
                    </button>
                </div>
            """
            
        html += """
                </div>
            </div>
            <script src="script.js"></script>
        </body>
        </html>
        """
        
        return html
        
    def load_home_page(self):
        """Carrega página inicial"""
        html_content = self.generate_home_html()
        self.save_and_load_html(html_content, 'home.html')
        
    def generate_home_html(self):
        """Gera HTML da página inicial"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Loja de Aplicativos</title>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <div class="container">
                <h1>Bem-vindo à Loja de Aplicativos</h1>
                <div class="featured-section">
                    <h2>Aplicativos em Destaque</h2>
                    <div class="carousel">
        """
        
        for app in self.featured_apps:
            html += f"""
                <div class="featured-card">
                    <img src="{app.get('image', 'default-icon.png')}" alt="{app['name']}" class="app-cover">
                    <div class="app-info">
                        <img src="{app.get('icon', 'default-icon.png')}" alt="Ícone" class="app-icon">
                        <h3>{app['name']}</h3>
                        <button class="btn install" onclick="handlePackageAction('{app['package']}', 'install')">
                            Instalar
                        </button>
                    </div>
                </div>
            """
            
        html += """
                    </div>
                </div>
            </div>
            <script src="script.js"></script>
        </body>
        </html>
        """
        
        return html
        
    def save_and_load_html(self, content, filename):
        """Salva HTML e carrega no WebView"""
        # Salva HTML
        html_file = self.html_dir / filename
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # Cria CSS se não existir
        self.create_css_file()
        
        # Cria JavaScript se não existir
        self.create_js_file()
        
        # Carrega no WebView
        self.webview.load_uri(f"file://{html_file}")
        
    def create_css_file(self):
        """Cria arquivo CSS"""
        css_content = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1, h2 {
            color: #333;
        }
        
        .carousel {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .featured-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            min-width: 280px;
            flex: 1;
        }
        
        .app-cover {
            width: 100%;
            height: 150px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        
        .app-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .app-icon {
            width: 48px;
            height: 48px;
            border-radius: 8px;
        }
        
        .package-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .package-info h3 {
            margin: 0 0 8px 0;
            color: #333;
        }
        
        .version {
            color: #666;
            font-size: 0.9em;
            margin: 0 0 8px 0;
        }
        
        .description {
            color: #777;
            margin: 0;
        }
        
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        
        .btn:hover {
            background: #0056b3;
        }
        
        .btn.installed {
            background: #28a745;
        }
        
        .btn.installed:hover {
            background: #1e7e34;
        }
        
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .progress-wrapper {
            margin-top: 10px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: #007bff;
            transition: width 0.3s ease;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .carousel {
                flex-direction: column;
            }
            
            .featured-card {
                min-width: auto;
            }
            
            .package-card {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }
        }
        
        @media (max-width: 400px) {
            .package-card {
                padding: 15px;
            }
            
            .app-info {
                flex-direction: column;
                text-align: center;
            }
        }
        """
        
        css_file = self.html_dir / 'style.css'
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content)
            
    def create_js_file(self):
        """Cria arquivo JavaScript"""
        js_content = """
        function handlePackageAction(packageName, action) {
            console.log(`Action: ${action} for package: ${packageName}`);
            
            // Comunica com o aplicativo Python
            if (action === 'install' || action === 'Instalar') {
                installPackage(packageName);
            } else if (action === 'remove' || action === 'Remover') {
                removePackage(packageName);
            }
        }
        
        function installPackage(packageName) {
            // Desabilita botão e mostra progresso
            const button = event.target;
            button.disabled = true;
            button.textContent = 'Instalando...';
            
            // Cria barra de progresso
            const progressWrapper = document.createElement('div');
            progressWrapper.className = 'progress-wrapper';
            progressWrapper.innerHTML = `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <button class="btn" onclick="cancelInstallation('${packageName}')">Cancelar</button>
            `;
            
            button.parentNode.appendChild(progressWrapper);
            
            // Simula progresso (será substituído pela implementação real)
            simulateProgress(progressWrapper.querySelector('.progress-fill'));
            
            // Chama função Python via WebKit
            window.webkit.messageHandlers.install.postMessage({
                package: packageName,
                action: 'install'
            });
        }
        
        function removePackage(packageName) {
            if (confirm(`Deseja remover o pacote ${packageName}?`)) {
                window.webkit.messageHandlers.install.postMessage({
                    package: packageName,
                    action: 'remove'
                });
            }
        }
        
        function cancelInstallation(packageName) {
            window.webkit.messageHandlers.install.postMessage({
                package: packageName,
                action: 'cancel'
            });
        }
        
        function simulateProgress(progressElement) {
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 100) progress = 100;
                
                progressElement.style.width = progress + '%';
                
                if (progress >= 100) {
                    clearInterval(interval);
                }
            }, 200);
        }
        
        // Função para deeplinks
        function handleDeeplink(url) {
            const urlObj = new URL(url);
            const searchParams = new URLSearchParams(urlObj.search);
            const search = searchParams.get('search');
            
            if (search) {
                // Simula busca pelo pacote
                handlePackageAction(search, 'install');
            }
        }
        """
        
        js_file = self.html_dir / 'script.js'
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write(js_content)
            
    def on_navigation_policy(self, webview, decision, decision_type):
        """Manipula navegação e intercepta deeplinks"""
        if decision_type == WebKit2.NavigationPolicyDecisionType.NAVIGATION_ACTION:
            request = decision.get_request()
            uri = request.get_uri()
            
            if uri.startswith('software-store://'):
                self.handle_deeplink(uri)
                decision.ignore()
                return True
                
        return False
        
    def handle_deeplink(self, uri):
        """Processa deeplinks"""
        try:
            parsed = urllib.parse.urlparse(uri)
            params = urllib.parse.parse_qs(parsed.query)
            
            if 'search' in params:
                package_name = params['search'][0]
                self.show_package_details(package_name)
                
        except Exception as e:
            print(f"Erro ao processar deeplink: {e}")
            
    def show_package_details(self, package_name):
        """Mostra detalhes do pacote em janela pequena"""
        dialog = Gtk.Dialog(
            title=f"Instalar {package_name}",
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL
        )
        
        dialog.set_default_size(400, 300)
        dialog.set_resizable(False)
        
        content_area = dialog.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_left(20)
        content_area.set_margin_right(20)
        content_area.set_margin_top(20)
        content_area.set_margin_bottom(20)
        
        # Informações do pacote
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        # Ícone (placeholder)
        icon = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
        info_box.pack_start(icon, False, False, 0)
        
        # Detalhes
        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{package_name}</b>")
        name_label.set_halign(Gtk.Align.START)
        details_box.pack_start(name_label, False, False, 0)
        
        version_label = Gtk.Label()
        version_label.set_text(f"Versão: {self.get_package_version(package_name)}")
        version_label.set_halign(Gtk.Align.START)
        details_box.pack_start(version_label, False, False, 0)
        
        info_box.pack_start(details_box, True, True, 0)
        content_area.pack_start(info_box, False, False, 0)
        
        # Botões
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        
        if self.is_package_installed(package_name):
            remove_button = Gtk.Button.new_with_label("Remover")
            remove_button.get_style_context().add_class("rounded-button")
            remove_button.connect("clicked", lambda x: self.remove_package(package_name, dialog))
            button_box.pack_start(remove_button, False, False, 0)
        else:
            install_button = Gtk.Button.new_with_label("Instalar")
            install_button.get_style_context().add_class("rounded-button")
            install_button.connect("clicked", lambda x: self.install_package(package_name, dialog))
            button_box.pack_start(install_button, False, False, 0)
            
        cancel_button = Gtk.Button.new_with_label("Cancelar")
        cancel_button.get_style_context().add_class("rounded-button")
        cancel_button.connect("clicked", lambda x: dialog.destroy())
        button_box.pack_start(cancel_button, False, False, 0)
        
        content_area.pack_start(button_box, False, False, 0)
        
        # Barra de progresso (oculta inicialmente)
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_hexpand(True)
        progress_box.pack_start(progress_bar, True, True, 0)
        
        cancel_dl_button = Gtk.Button.new_with_label("Cancelar")
        cancel_dl_button.connect("clicked", lambda x: self.cancel_download())
        progress_box.pack_start(cancel_dl_button, False, False, 0)
        
        progress_box.set_no_show_all(True)
        content_area.pack_start(progress_box, False, False, 0)
        
        dialog.show_all()
        
    def install_package(self, package_name, dialog=None):
        """Instala pacote"""
        threading.Thread(target=self._install_package, args=(package_name, dialog), daemon=True).start()
        
    def _install_package(self, package_name, dialog):
        """Instala pacote (thread separada)"""
        try:
            # Comando de instalação
            cmd = ['apt-get', 'install', '-y', package_name]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.current_download = process
            
            # Monitora progresso
            GLib.idle_add(self.show_progress, True)
            
            # Aguarda conclusão
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # Verifica se precisa adicionar --no-sandbox
                if package_name in self.no_sandbox_apps:
                    self.modify_desktop_file(package_name)
                    
                GLib.idle_add(self.show_success, f"Pacote {package_name} instalado com sucesso!")
            else:
                GLib.idle_add(self.show_error, f"Erro ao instalar {package_name}: {stderr}")
                
        except Exception as e:
            GLib.idle_add(self.show_error, f"Erro na instalação: {e}")
        finally:
            GLib.idle_add(self.show_progress, False)
            if dialog:
                GLib.idle_add(dialog.destroy)
                
    def modify_desktop_file(self, package_name):
        """Modifica arquivo .desktop para adicionar --no-sandbox"""
        try:
            desktop_dirs = [
                Path('/usr/share/applications'),
                Path(f'{os.environ.get("HOME", "/root")}/.local/share/applications')
            ]
            
            for desktop_dir in desktop_dirs:
                desktop_file = desktop_dir / f'{package_name}.desktop'
                if desktop_file.exists():
                    with open(desktop_file, 'r') as f:
                        content = f.read()
                        
                    # Adiciona --no-sandbox ao Exec
                    modified_content = re.sub(
                        r'^Exec=(.+)$',
                        r'Exec=\1 --no-sandbox',
                        content,
                        flags=re.MULTILINE
                    )
                    
                    # Salva no diretório do usuário
                    user_desktop_dir = Path(f'{os.environ.get("HOME", "/root")}/.local/share/applications')
                    user_desktop_dir.mkdir(parents=True, exist_ok=True)
                    
                    user_desktop_file = user_desktop_dir / f'{package_name}.desktop'
                    with open(user_desktop_file, 'w') as f:
                        f.write(modified_content)
                        
                    break
                    
        except Exception as e:
            print(f"Erro ao modificar arquivo .desktop: {e}")
            
    def remove_package(self, package_name, dialog=None):
        """Remove pacote"""
        threading.Thread(target=self._remove_package, args=(package_name, dialog), daemon=True).start()
        
    def _remove_package(self, package_name, dialog):
        """Remove pacote (thread separada)"""
        try:
            process = subprocess.Popen(
                ['apt-get', 'remove', '-y', package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                GLib.idle_add(self.show_success, f"Pacote {package_name} removido com sucesso!")
            else:
                GLib.idle_add(self.show_error, f"Erro ao remover {package_name}: {stderr}")
                
        except Exception as e:
            GLib.idle_add(self.show_error, f"Erro na remoção: {e}")
        finally:
            if dialog:
                GLib.idle_add(dialog.destroy)
                
    def cancel_download(self):
        """Cancela download atual"""
        if self.current_download:
            self.current_download.terminate()
            self.current_download = None
            self.show_progress(False)
            
    def show_progress(self, show):
        """Mostra/oculta barra de progresso"""
        if show:
            self.progress_bar.show()
            self.progress_bar.pulse()
            GLib.timeout_add(100, self.update_progress)
        else:
            self.progress_bar.hide()
            
    def update_progress(self):
        """Atualiza barra de progresso"""
        if self.progress_bar.get_visible():
            self.progress_bar.pulse()
            return True
        return False
        
    def show_success(self, message):
        """Mostra mensagem de sucesso"""
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            message_format=message
        )
        dialog.run()
        dialog.destroy()
        
    def show_error(self, message):
        """Mostra mensagem de erro"""
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=message
        )
        dialog.run()
        dialog.destroy()
        
    def setup_deeplink_handler(self):
        """Configura manipulador de deeplinks"""
        try:
            # Registra esquema de URI personalizado
            desktop_content = f"""[Desktop Entry]
Name=Software Store
Comment=Loja de Aplicativos Linux
Exec={sys.executable} {os.path.abspath(__file__)} %u
Icon=applications-accessories
Terminal=false
Type=Application
MimeType=x-scheme-handler/software-store;
Categories=System;PackageManager;
"""
            
            desktop_dir = Path.home() / '.local/share/applications'
            desktop_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_file = desktop_dir / 'software-store.desktop'
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
                
            # Torna executável
            os.chmod(desktop_file, 0o755)
            
            # Registra esquema
            subprocess.run([
                'xdg-mime', 'default', 'software-store.desktop', 'x-scheme-handler/software-store'
            ], check=False)
            
        except Exception as e:
            print(f"Erro ao configurar deeplink: {e}")
            
    def run(self):
        """Inicia aplicativo"""
        self.window.show_all()
        self.progress_bar.hide()
        
        # Processa argumentos de linha de comando (deeplinks)
        if len(sys.argv) > 1:
            uri = sys.argv[1]
            if uri.startswith('software-store://'):
                self.handle_deeplink(uri)
                
        Gtk.main()


def main():
    """Função principal"""
    # Verifica dependências
    try:
        subprocess.run(['apt-cache', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Erro: apt-cache não encontrado. Este programa requer Debian/Ubuntu.")
        sys.exit(1)
        
    # Cria e executa aplicativo
    app = SoftwareStore()
    app.run()


if __name__ == "__main__":
    main()