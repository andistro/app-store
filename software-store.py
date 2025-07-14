#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, GLib, Pango, WebKit2
import subprocess
import threading
import json
import urllib.request
import urllib.parse
import os
import sys
import re
import tempfile
import shutil

class SoftwareStore:
    def __init__(self):
        self.window = None
        self.search_entry = None
        self.search_results = None
        self.carousel_box = None
        self.main_stack = None
        self.progress_bar = None
        self.install_button = None
        self.current_package = None
        self.installing = False
        self.no_sandbox_apps = []
        self.featured_apps = []
        
        # Carregar dados remotos
        self.load_remote_data()
        
        self.setup_ui()
        self.setup_deeplink_handler()
        
    def load_remote_data(self):
        """Carrega dados remotos de aplicativos em destaque e lista no-sandbox"""
        try:
            # Carregar lista de apps que precisam do --no-sandbox
            with urllib.request.urlopen('https://raw.githubusercontent.com/andistro/app-store/refs/heads/alpha/assets/no-sandbox.json') as response:
                self.no_sandbox_apps = json.loads(response.read().decode())
        except Exception as e:
            print(f"Erro ao carregar no-sandbox.json: {e}")
            self.no_sandbox_apps = []
            
        try:
            # Carregar apps em destaque
            with urllib.request.urlopen('https://raw.githubusercontent.com/andistro/app-store/refs/heads/alpha/assets/apps-destaque.json') as response:
                self.featured_apps = json.loads(response.read().decode())
        except Exception as e:
            print(f"Erro ao carregar apps-destaque.json: {e}")
            self.featured_apps = []
    
    def setup_ui(self):
        """Configura a interface principal"""
        self.window = Gtk.Window()
        self.window.set_title("Software Store")
        self.window.set_default_size(800, 600)
        self.window.set_resizable(True)
        
        # Aplicar tema GTK3 do sistema
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .rounded-button {
                border-radius: 8px;
                min-height: 36px;
            }
            .rounded-entry {
                border-radius: 8px;
                min-height: 36px;
            }
            .card {
                border-radius: 12px;
                margin: 8px;
                padding: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .carousel-card {
                border-radius: 12px;
                margin: 8px;
                padding: 16px;
                min-width: 280px;
            }
        """)
        
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        self.window.connect("destroy", Gtk.main_quit)
        self.window.connect("size-allocate", self.on_window_resize)
        
        # Layout principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_left(16)
        main_box.set_margin_right(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        
        # Barra de busca
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Pesquisar aplicativos...")
        self.search_entry.get_style_context().add_class("rounded-entry")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search)
        self.search_entry.connect("changed", self.on_search_changed)
        
        search_button = Gtk.Button.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON)
        search_button.get_style_context().add_class("rounded-button")
        search_button.connect("clicked", self.on_search)
        
        search_box.pack_start(self.search_entry, True, True, 0)
        search_box.pack_start(search_button, False, False, 0)
        
        # Stack principal para alternar entre páginas
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        # Página principal
        main_page = self.create_main_page()
        self.main_stack.add_named(main_page, "main")
        
        # Página de resultados de busca
        search_page = self.create_search_page()
        self.main_stack.add_named(search_page, "search")
        
        # Página de detalhes do app
        details_page = self.create_details_page()
        self.main_stack.add_named(details_page, "details")
        
        main_box.pack_start(search_box, False, False, 0)
        main_box.pack_start(self.main_stack, True, True, 0)
        
        self.window.add(main_box)
        self.window.show_all()
        
        # Carregar carrossel de apps em destaque
        self.load_featured_apps()
        
    def create_main_page(self):
        """Cria a página principal com carrossel de apps em destaque"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        
        # Título dos apps em destaque
        title_label = Gtk.Label()
        title_label.set_markup("<b>Aplicativos em Destaque</b>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_bottom(8)
        
        # Carrossel horizontal
        carousel_scrolled = Gtk.ScrolledWindow()
        carousel_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        carousel_scrolled.set_min_content_height(200)
        
        self.carousel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        carousel_scrolled.add(self.carousel_box)
        
        box.pack_start(title_label, False, False, 0)
        box.pack_start(carousel_scrolled, False, False, 0)
        
        scrolled.add(box)
        return scrolled
        
    def create_search_page(self):
        """Cria a página de resultados de busca"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.search_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.add(self.search_results)
        
        return scrolled
        
    def create_details_page(self):
        """Cria a página de detalhes do aplicativo"""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_left(32)
        box.set_margin_right(32)
        box.set_margin_top(32)
        box.set_margin_bottom(32)
        
        # Informações do app
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        
        # Ícone do app
        self.app_icon = Gtk.Image()
        self.app_icon.set_pixel_size(64)
        
        # Informações textuais
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        self.app_name_label = Gtk.Label()
        self.app_name_label.set_halign(Gtk.Align.START)
        self.app_name_label.set_markup("<b>Nome do Aplicativo</b>")
        
        self.app_version_label = Gtk.Label()
        self.app_version_label.set_halign(Gtk.Align.START)
        self.app_version_label.set_text("Versão: 1.0")
        
        self.app_description_label = Gtk.Label()
        self.app_description_label.set_halign(Gtk.Align.START)
        self.app_description_label.set_line_wrap(True)
        self.app_description_label.set_text("Descrição do aplicativo...")
        
        text_box.pack_start(self.app_name_label, False, False, 0)
        text_box.pack_start(self.app_version_label, False, False, 0)
        text_box.pack_start(self.app_description_label, True, True, 0)
        
        info_box.pack_start(self.app_icon, False, False, 0)
        info_box.pack_start(text_box, True, True, 0)
        
        # Botão de instalação e barra de progresso
        action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        self.install_button = Gtk.Button()
        self.install_button.set_label("Instalar")
        self.install_button.get_style_context().add_class("rounded-button")
        self.install_button.get_style_context().add_class("suggested-action")
        self.install_button.connect("clicked", self.on_install_clicked)
        
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_no_show_all(True)
        
        action_box.pack_start(self.install_button, False, False, 0)
        action_box.pack_start(self.progress_bar, False, False, 0)
        
        # Botão voltar
        back_button = Gtk.Button()
        back_button.set_label("← Voltar")
        back_button.get_style_context().add_class("rounded-button")
        back_button.connect("clicked", self.on_back_clicked)
        
        box.pack_start(back_button, False, False, 0)
        box.pack_start(info_box, False, False, 0)
        box.pack_start(action_box, False, False, 0)
        
        scrolled.add(box)
        return scrolled
        
    def load_featured_apps(self):
        """Carrega apps em destaque no carrossel"""
        if not self.featured_apps:
            return
            
        for child in self.carousel_box.get_children():
            self.carousel_box.remove(child)
            
        for app in self.featured_apps:
            card = self.create_featured_card(app)
            self.carousel_box.pack_start(card, False, False, 0)
            
        self.carousel_box.show_all()
        
    def create_featured_card(self, app):
        """Cria um card para app em destaque"""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("carousel-card")
        card.get_style_context().add_class("card")
        
        # Imagem de capa (placeholder)
        cover_image = Gtk.Image()
        cover_image.set_from_icon_name("application-x-executable", Gtk.IconSize.LARGE_TOOLBAR)
        cover_image.set_pixel_size(120)
        
        # Informações do app
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Ícone do app
        app_icon = Gtk.Image()
        icon_name = self.get_app_icon(app.get('package', ''))
        app_icon.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        app_icon.set_pixel_size(32)
        
        # Nome do app
        name_label = Gtk.Label()
        name_label.set_text(app.get('name', app.get('package', '')))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        info_box.pack_start(app_icon, False, False, 0)
        info_box.pack_start(name_label, True, True, 0)
        
        # Botão instalar
        install_btn = Gtk.Button()
        install_btn.set_label("Instalar")
        install_btn.get_style_context().add_class("rounded-button")
        install_btn.get_style_context().add_class("suggested-action")
        install_btn.connect("clicked", self.on_featured_install, app.get('package', ''))
        
        card.pack_start(cover_image, False, False, 0)
        card.pack_start(info_box, False, False, 0)
        card.pack_start(install_btn, False, False, 0)
        
        return card
        
    def on_search(self, widget):
        """Realiza busca de pacotes"""
        query = self.search_entry.get_text().strip()
        if not query:
            return
            
        self.main_stack.set_visible_child_name("search")
        
        # Limpar resultados anteriores
        for child in self.search_results.get_children():
            self.search_results.remove(child)
            
        # Buscar pacotes
        threading.Thread(target=self.search_packages, args=(query,), daemon=True).start()
        
    def on_search_changed(self, widget):
        """Auto-busca enquanto digita"""
        query = self.search_entry.get_text().strip()
        if len(query) >= 3:
            GLib.timeout_add(500, self.delayed_search, query)
            
    def delayed_search(self, query):
        """Busca com delay para evitar muitas chamadas"""
        current_query = self.search_entry.get_text().strip()
        if current_query == query:
            self.on_search(None)
        return False
        
    def search_packages(self, query):
        """Busca pacotes no repositório"""
        try:
            # Buscar usando apt-cache search
            result = subprocess.run(['apt-cache', 'search', '--names-only', query], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                packages = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split(' - ', 1)
                        if len(parts) >= 2:
                            package_name = parts[0]
                            description = parts[1]
                            
                            # Filtrar pacotes python3-xyz
                            if package_name.startswith('python3-') and package_name != 'python3':
                                continue
                                
                            packages.append({
                                'name': package_name,
                                'description': description
                            })
                
                GLib.idle_add(self.display_search_results, packages)
                
        except Exception as e:
            print(f"Erro na busca: {e}")
            
    def display_search_results(self, packages):
        """Exibe resultados da busca"""
        if not packages:
            no_results = Gtk.Label()
            no_results.set_text("Nenhum pacote encontrado")
            no_results.set_halign(Gtk.Align.CENTER)
            no_results.set_margin_top(50)
            self.search_results.pack_start(no_results, False, False, 0)
            self.search_results.show_all()
            return
            
        for package in packages[:20]:  # Limitar a 20 resultados
            card = self.create_search_result_card(package)
            self.search_results.pack_start(card, False, False, 0)
            
        self.search_results.show_all()
        
    def create_search_result_card(self, package):
        """Cria card para resultado de busca"""
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card.get_style_context().add_class("card")
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        
        # Ícone do app
        icon = Gtk.Image()
        icon_name = self.get_app_icon(package['name'])
        icon.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        icon.set_pixel_size(32)
        
        # Informações
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        # Nome e versão
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{package['name']}</b>")
        name_label.set_halign(Gtk.Align.START)
        
        version_label = Gtk.Label()
        version_label.set_text(self.get_package_version(package['name']))
        version_label.set_halign(Gtk.Align.START)
        version_label.get_style_context().add_class("dim-label")
        
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(version_label, False, False, 0)
        
        # Descrição
        desc_label = Gtk.Label()
        desc_label.set_text(package['description'][:100] + "..." if len(package['description']) > 100 else package['description'])
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_line_wrap(True)
        desc_label.set_max_width_chars(60)
        desc_label.get_style_context().add_class("dim-label")
        
        info_box.pack_start(name_box, False, False, 0)
        info_box.pack_start(desc_label, False, False, 0)
        
        # Botão instalar
        install_btn = Gtk.Button()
        if self.is_package_installed(package['name']):
            install_btn.set_label("Instalado")
            install_btn.set_sensitive(False)
        else:
            install_btn.set_label("Instalar")
            install_btn.connect("clicked", self.on_package_install, package['name'])
            
        install_btn.get_style_context().add_class("rounded-button")
        install_btn.get_style_context().add_class("suggested-action")
        install_btn.set_valign(Gtk.Align.CENTER)
        
        card.pack_start(icon, False, False, 0)
        card.pack_start(info_box, True, True, 0)
        card.pack_start(install_btn, False, False, 0)
        
        return card
        
    def get_app_icon(self, package_name):
        """Obtém ícone do aplicativo"""
        icon_theme = Gtk.IconTheme.get_default()
        
        # Tentar alguns nomes de ícone comuns
        possible_icons = [
            package_name,
            package_name.replace('-', '_'),
            package_name.split('-')[0],
            'application-x-executable'
        ]
        
        for icon_name in possible_icons:
            if icon_theme.has_icon(icon_name):
                return icon_name
                
        return 'application-x-executable'
        
    def get_package_version(self, package_name):
        """Obtém versão do pacote"""
        try:
            result = subprocess.run(['apt-cache', 'show', package_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        return line.split(':', 1)[1].strip()
        except:
            pass
        return "Desconhecida"
        
    def is_package_installed(self, package_name):
        """Verifica se o pacote está instalado"""
        try:
            result = subprocess.run(['dpkg', '-l', package_name], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
            
    def on_package_install(self, widget, package_name):
        """Instala um pacote"""
        self.show_package_details(package_name)
        
    def on_featured_install(self, widget, package_name):
        """Instala app em destaque"""
        self.show_package_details(package_name)
        
    def show_package_details(self, package_name):
        """Mostra detalhes do pacote"""
        self.current_package = package_name
        
        # Configurar informações
        self.app_name_label.set_markup(f"<b>{package_name}</b>")
        self.app_version_label.set_text(f"Versão: {self.get_package_version(package_name)}")
        
        # Obter descrição
        description = self.get_package_description(package_name)
        self.app_description_label.set_text(description)
        
        # Configurar ícone
        icon_name = self.get_app_icon(package_name)
        self.app_icon.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        
        # Configurar botão
        if self.is_package_installed(package_name):
            self.install_button.set_label("Remover")
            self.install_button.get_style_context().remove_class("suggested-action")
            self.install_button.get_style_context().add_class("destructive-action")
        else:
            self.install_button.set_label("Instalar")
            self.install_button.get_style_context().remove_class("destructive-action")
            self.install_button.get_style_context().add_class("suggested-action")
            
        self.main_stack.set_visible_child_name("details")
        
    def get_package_description(self, package_name):
        """Obtém descrição do pacote"""
        try:
            result = subprocess.run(['apt-cache', 'show', package_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                description = ""
                in_description = False
                for line in result.stdout.split('\n'):
                    if line.startswith('Description:'):
                        description = line.split(':', 1)[1].strip()
                        in_description = True
                    elif in_description and line.startswith(' '):
                        description += "\n" + line.strip()
                    elif in_description and not line.startswith(' '):
                        break
                return description
        except:
            pass
        return "Descrição não disponível"
        
    def on_install_clicked(self, widget):
        """Instala ou remove o pacote atual"""
        if self.installing or not self.current_package:
            return
            
        self.installing = True
        self.install_button.set_sensitive(False)
        self.progress_bar.set_fraction(0)
        self.progress_bar.show()
        
        if self.is_package_installed(self.current_package):
            # Remover
            threading.Thread(target=self.remove_package, daemon=True).start()
        else:
            # Instalar
            threading.Thread(target=self.install_package, daemon=True).start()
            
    def install_package(self):
        """Instala o pacote"""
        try:
            # Simular progresso
            for i in range(10):
                GLib.idle_add(self.update_progress, i/10, f"Instalando {self.current_package}... {i*10}%")
                
            # Instalar usando apt-get
            result = subprocess.run(['sudo', 'apt-get', 'install', '-y', self.current_package], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Verificar se precisa adicionar --no-sandbox
                if self.current_package in self.no_sandbox_apps:
                    self.add_no_sandbox_flag(self.current_package)
                    
                GLib.idle_add(self.installation_complete, True)
            else:
                GLib.idle_add(self.installation_complete, False)
                
        except Exception as e:
            print(f"Erro na instalação: {e}")
            GLib.idle_add(self.installation_complete, False)
            
    def remove_package(self):
        """Remove o pacote"""
        try:
            for i in range(10):
                GLib.idle_add(self.update_progress, i/10, f"Removendo {self.current_package}... {i*10}%")
                
            result = subprocess.run(['sudo', 'apt-get', 'remove', '-y', self.current_package], 
                                  capture_output=True, text=True)
            
            GLib.idle_add(self.installation_complete, result.returncode == 0)
            
        except Exception as e:
            print(f"Erro na remoção: {e}")
            GLib.idle_add(self.installation_complete, False)
            
    def add_no_sandbox_flag(self, package_name):
        """Adiciona flag --no-sandbox ao .desktop file"""
        try:
            desktop_dirs = ['/usr/share/applications', '/usr/local/share/applications']
            
            for desktop_dir in desktop_dirs:
                desktop_file = os.path.join(desktop_dir, f"{package_name}.desktop")
                
                if os.path.exists(desktop_file):
                    with open(desktop_file, 'r') as f:
                        content = f.read()
                        
                    # Adicionar --no-sandbox ao Exec
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('Exec=') and '--no-sandbox' not in line:
                            lines[i] = line.replace('Exec=', 'Exec=').replace(' %', ' --no-sandbox %')
                            if ' %' not in lines[i]:
                                lines[i] += ' --no-sandbox'
                                
                    with open(desktop_file, 'w') as f:
                        f.write('\n'.join(lines))
                        
        except Exception as e:
            print(f"Erro ao adicionar --no-sandbox: {e}")
            
    def update_progress(self, fraction, text):
        """Atualiza barra de progresso"""
        self.progress_bar.set_fraction(fraction)
        self.progress_bar.set_text(text)
        
    def installation_complete(self, success):
        """Finaliza instalação"""
        self.installing = False
        self.install_button.set_sensitive(True)
        self.progress_bar.hide()
        
        if success:
            # Atualizar botão
            if self.is_package_installed(self.current_package):
                self.install_button.set_label("Remover")
                self.install_button.get_style_context().remove_class("suggested-action")
                self.install_button.get_style_context().add_class("destructive-action")
            else:
                self.install_button.set_label("Instalar")
                self.install_button.get_style_context().remove_class("destructive-action")
                self.install_button.get_style_context().add_class("suggested-action")
        else:
            # Mostrar erro
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,
                                     Gtk.ButtonsType.OK, "Erro na operação")
            dialog.format_secondary_text("Não foi possível completar a operação.")
            dialog.run()
            dialog.destroy()
            
    def on_back_clicked(self, widget):
        """Volta para a página anterior"""
        self.main_stack.set_visible_child_name("main")
        
    def on_window_resize(self, widget, allocation):
        """Redimensiona interface para telas menores"""
        if allocation.width < 400:
            # Modo compacto
            self.window.set_size_request(300, 400)
        else:
            self.window.set_size_request(600, 500)
            
    def setup_deeplink_handler(self):
        """Configura handler para deeplinks"""
        # Registrar handler para software-store://
        if len(sys.argv) > 1 and sys.argv[1].startswith('software-store://'):
            self.handle_deeplink(sys.argv[1])
            
    def handle_deeplink(self, url):
        """Processa deeplink"""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.path == '/pkg':
                params = urllib.parse.parse_qs(parsed.query)
                if 'search' in params:
                    package_name = params['search'][0]
                    self.show_deeplink_install(package_name)
        except Exception as e:
            print(f"Erro ao processar deeplink: {e}")
            
    def show_deeplink_install(self, package_name):
        """Mostra janela de instalação para deeplink"""
        # Criar janela pequena para deeplink
        deeplink_window = Gtk.Window()
        deeplink_window.set_title("Instalar Aplicativo")
        deeplink_window.set_default_size(400, 300)
        deeplink_window.set_resizable(False)
        deeplink_window.set_modal(True)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_left(24)
        box.set_margin_right(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        
        # Ícone do app
        icon = Gtk.Image()
        icon_name = self.get_app_icon(package_name)
        icon.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        icon.set_halign(Gtk.Align.CENTER)
        
        # Nome do app
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{package_name}</b>")
        name_label.set_halign(Gtk.Align.CENTER)
        
        # Versão
        version_label = Gtk.Label()
        version_label.set_text(f"Versão: {self.get_package_version(package_name)}")
        version_label.set_halign(Gtk.Align.CENTER)
        version_label.get_style_context().add_class("dim-label")
        
        # Botões
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        
        cancel_btn = Gtk.Button()
        cancel_btn.set_label("Cancelar")
        cancel_btn.get_style_context().add_class("rounded-button")
        cancel_btn.connect("clicked", lambda w: deeplink_window.destroy())
        
        install_btn = Gtk.Button()
        if self.is_package_installed(package_name):
            install_btn.set_label("Remover")
            install_btn.get_style_context().add_class("destructive-action")
        else:
            install_btn.set_label("Instalar")
            install_btn.get_style_context().add_class("suggested-action")
            
        install_btn.get_style_context().add_class("rounded-button")
        install_btn.connect("clicked", self.on_deeplink_install, package_name, deeplink_window)
        
        button_box.pack_start(cancel_btn, False, False, 0)
        button_box.pack_start(install_btn, False, False, 0)
        
        # Barra de progresso
        progress = Gtk.ProgressBar()
        progress.set_no_show_all(True)
        
        box.pack_start(icon, False, False, 0)
        box.pack_start(name_label, False, False, 0)
        box.pack_start(version_label, False, False, 0)
        box.pack_start(button_box, False, False, 0)
        box.pack_start(progress, False, False, 0)
        
        deeplink_window.add(box)
        deeplink_window.show_all()
        
        # Fechar janela principal se aberta via deeplink
        if len(sys.argv) > 1 and sys.argv[1].startswith('software-store://'):
            self.window.hide()
            
    def on_deeplink_install(self, widget, package_name, window):
        """Instala via deeplink"""
        widget.set_sensitive(False)
        progress = window.get_children()[0].get_children()[-1]
        progress.show()
        
        def install_thread():
            try:
                if self.is_package_installed(package_name):
                    # Remover
                    for i in range(10):
                        GLib.idle_add(progress.set_fraction, i/10)
                        GLib.idle_add(progress.set_text, f"Removendo... {i*10}%")
                        
                    result = subprocess.run(['sudo', 'apt-get', 'remove', '-y', package_name], 
                                          capture_output=True, text=True)
                else:
                    # Instalar
                    for i in range(10):
                        GLib.idle_add(progress.set_fraction, i/10)
                        GLib.idle_add(progress.set_text, f"Instalando... {i*10}%")
                        
                    result = subprocess.run(['sudo', 'apt-get', 'install', '-y', package_name], 
                                          capture_output=True, text=True)
                    
                    if result.returncode == 0 and package_name in self.no_sandbox_apps:
                        self.add_no_sandbox_flag(package_name)
                        
                GLib.idle_add(window.destroy)
                
            except Exception as e:
                print(f"Erro na instalação via deeplink: {e}")
                GLib.idle_add(window.destroy)
                
        threading.Thread(target=install_thread, daemon=True).start()


def create_desktop_file():
    """Cria arquivo .desktop para a loja"""
    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=Software Store
Comment=Loja de aplicativos Linux
Exec=python3 /usr/local/bin/software-store.py %U
Icon=software-store
Terminal=false
NoDisplay=false
Categories=System;PackageManager;
MimeType=x-scheme-handler/software-store;
"""
    
    desktop_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dir, exist_ok=True)
    
    desktop_file = os.path.join(desktop_dir, "software-store.desktop")
    with open(desktop_file, 'w') as f:
        f.write(desktop_content)
        
    # Tornar executável
    os.chmod(desktop_file, 0o755)
    
    # Registrar handler de deeplink
    try:
        subprocess.run(['xdg-mime', 'default', 'software-store.desktop', 'x-scheme-handler/software-store'])
    except:
        pass


def install_system_files():
    """Instala arquivos do sistema"""
    script_path = os.path.abspath(__file__)
    
    # Copiar script para /usr/local/bin
    try:
        shutil.copy2(script_path, '/usr/local/bin/software-store.py')
        os.chmod('/usr/local/bin/software-store.py', 0o755)
    except PermissionError:
        print("Execute com sudo para instalar no sistema")
        return False
        
    # Criar arquivo .desktop
    create_desktop_file()
    
    # Atualizar cache de aplicativos
    try:
        subprocess.run(['update-desktop-database', os.path.expanduser("~/.local/share/applications")])
    except:
        pass
        
    return True


def main():
    """Função principal"""
    # Verificar se é primeira execução
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        if install_system_files():
            print("Software Store instalado com sucesso!")
            print("Você pode encontrá-lo no menu de aplicativos ou executar 'software-store.py'")
        else:
            print("Erro na instalação")
        return
        
    # Verificar dependências
    try:
        gi.require_version('Gtk', '3.0')
        gi.require_version('WebKit2', '4.0')
    except ValueError as e:
        print(f"Erro: {e}")
        print("Instale as dependências: sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0")
        return
        
    # Criar e executar aplicação
    app = SoftwareStore()
    
    try:
        Gtk.main()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        Gtk.main_quit()


if __name__ == "__main__":
    main()