#!/usr/bin/env python3
"""
Loja de Aplicativos para Debian/Ubuntu - Compatível com Termux/proot
Criada para funcionar em qualquer ambiente desktop (GNOME, XFCE, LXDE, LXQt)
"""

import sys
import os
import subprocess
import json
import threading
import time
import re
from pathlib import Path
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    from tkinter.font import Font
    import tkinter.font as tkFont
except ImportError:
    print("Erro: tkinter não está instalado. Execute: apt install python3-tk")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Aviso: PIL não disponível. Ícones não serão mostrados.")

class AppStore:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_variables()
        self.setup_styles()
        self.create_widgets()
        self.cache_file = os.path.expanduser("~/.app_store_cache.json")
        self.load_cache()
        
    def setup_window(self):
        self.root.title("Loja de Aplicativos - Debian/Ubuntu")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Ícone da janela (se disponível)
        try:
            self.root.iconbitmap("@/usr/share/pixmaps/synaptic.xpm")
        except:
            pass
            
    def setup_variables(self):
        self.packages = {}
        self.filtered_packages = {}
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        self.loading = False
        self.installing = False
        
        # Aplicativos que precisam do --no-sandbox
        self.no_sandbox_apps = {
            'chromium', 'chromium-browser', 'brave-browser', 'vivaldi-stable',
            'code', 'visual-studio-code', 'firefox', 'google-chrome'
        }
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar cores
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Subtitle.TLabel', font=('Arial', 12))
        style.configure('Package.TLabel', font=('Arial', 10))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Título
        title_label = ttk.Label(main_frame, text="Loja de Aplicativos", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Barra de busca
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text="Buscar:").grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=('Arial', 12))
        self.search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.search_button = ttk.Button(search_frame, text="Buscar", command=self.search_packages)
        self.search_button.grid(row=0, column=2, padx=(0, 5))
        
        self.refresh_button = ttk.Button(search_frame, text="Atualizar Lista", command=self.refresh_packages)
        self.refresh_button.grid(row=0, column=3)
        
        # Frame de conteúdo
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # Lista de pacotes com scrollbar
        self.packages_frame = ttk.Frame(content_frame)
        self.packages_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas para scroll
        self.canvas = tk.Canvas(self.packages_frame, bg='white')
        self.scrollbar = ttk.Scrollbar(self.packages_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Barra de status
        self.status_var = tk.StringVar()
        self.status_var.set("Pronto")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Barra de progresso
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Carregar lista inicial
        self.load_initial_packages()
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def load_cache(self):
        """Carrega cache de pacotes"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    if cache_data.get('timestamp', 0) > time.time() - 3600:  # Cache válido por 1 hora
                        self.packages = cache_data.get('packages', {})
                        return True
        except Exception as e:
            print(f"Erro ao carregar cache: {e}")
        return False
        
    def save_cache(self):
        """Salva cache de pacotes"""
        try:
            cache_data = {
                'timestamp': time.time(),
                'packages': self.packages
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar cache: {e}")
            
    def load_initial_packages(self):
        """Carrega lista inicial de pacotes populares"""
        popular_packages = [
            'firefox', 'chromium', 'libreoffice', 'vlc', 'gimp', 'code',
            'git', 'vim', 'nano', 'htop', 'curl', 'wget', 'python3',
            'nodejs', 'npm', 'docker.io', 'snapd', 'flatpak', 'synaptic',
            'gparted', 'filezilla', 'transmission', 'audacity', 'blender',
            'inkscape', 'thunderbird', 'obs-studio', 'discord', 'telegram-desktop'
        ]
        
        self.status_var.set("Carregando pacotes populares...")
        self.progress.start()
        
        def load_thread():
            try:
                for pkg in popular_packages:
                    if pkg not in self.packages:
                        info = self.get_package_info(pkg)
                        if info:
                            self.packages[pkg] = info
                            
                self.filtered_packages = self.packages.copy()
                self.root.after(0, self.update_package_list)
                self.root.after(0, self.save_cache)
                self.root.after(0, lambda: self.status_var.set("Pronto"))
                self.root.after(0, self.progress.stop)
                
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Erro: {e}"))
                self.root.after(0, self.progress.stop)
                
        threading.Thread(target=load_thread, daemon=True).start()
        
    def get_package_info(self, package_name):
        """Obtém informações do pacote usando apt-cache"""
        try:
            # Informações básicas
            result = subprocess.run(['apt-cache', 'show', package_name], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return None
                
            info = {}
            lines = result.stdout.split('\n')
            
            for line in lines:
                if line.startswith('Package: '):
                    info['name'] = line.split(': ', 1)[1]
                elif line.startswith('Version: '):
                    info['version'] = line.split(': ', 1)[1]
                elif line.startswith('Description: '):
                    info['description'] = line.split(': ', 1)[1]
                elif line.startswith('Size: '):
                    info['size'] = line.split(': ', 1)[1]
                elif line.startswith('Section: '):
                    info['section'] = line.split(': ', 1)[1]
                elif line.startswith('Maintainer: '):
                    info['maintainer'] = line.split(': ', 1)[1]
                elif line.startswith(' ') and 'description' in info:
                    info['description'] += ' ' + line.strip()
                    
            # Verificar se está instalado
            install_check = subprocess.run(['dpkg', '-l', package_name], 
                                         capture_output=True, text=True)
            info['installed'] = install_check.returncode == 0
            
            return info
            
        except Exception as e:
            print(f"Erro ao obter informações do pacote {package_name}: {e}")
            return None
            
    def search_packages(self):
        """Busca pacotes no repositório"""
        if self.loading:
            return
            
        search_term = self.search_var.get().strip()
        if not search_term:
            self.filtered_packages = self.packages.copy()
            self.update_package_list()
            return
            
        self.loading = True
        self.status_var.set(f"Buscando por '{search_term}'...")
        self.progress.start()
        
        def search_thread():
            try:
                # Buscar no cache primeiro
                filtered = {}
                for name, info in self.packages.items():
                    if (search_term.lower() in name.lower() or 
                        search_term.lower() in info.get('description', '').lower()):
                        filtered[name] = info
                
                # Buscar novos pacotes
                result = subprocess.run(['apt-cache', 'search', search_term], 
                                      capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines[:20]:  # Limitar a 20 resultados
                        if ' - ' in line:
                            pkg_name = line.split(' - ')[0]
                            if pkg_name not in self.packages:
                                info = self.get_package_info(pkg_name)
                                if info:
                                    self.packages[pkg_name] = info
                                    filtered[pkg_name] = info
                
                self.filtered_packages = filtered
                self.root.after(0, self.update_package_list)
                self.root.after(0, self.save_cache)
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro na busca: {e}"))
                
            finally:
                self.loading = False
                self.root.after(0, lambda: self.status_var.set("Pronto"))
                self.root.after(0, self.progress.stop)
                
        threading.Thread(target=search_thread, daemon=True).start()
        
    def on_search_change(self, *args):
        """Filtro em tempo real"""
        search_term = self.search_var.get().strip().lower()
        if not search_term:
            self.filtered_packages = self.packages.copy()
        else:
            self.filtered_packages = {
                name: info for name, info in self.packages.items()
                if (search_term in name.lower() or 
                    search_term in info.get('description', '').lower())
            }
        self.update_package_list()
        
    def update_package_list(self):
        """Atualiza a lista de pacotes na interface"""
        # Limpar lista atual
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not self.filtered_packages:
            no_results = ttk.Label(self.scrollable_frame, 
                                  text="Nenhum pacote encontrado", 
                                  style='Subtitle.TLabel')
            no_results.pack(pady=20)
            return
            
        # Criar widgets para cada pacote
        for i, (name, info) in enumerate(self.filtered_packages.items()):
            self.create_package_widget(self.scrollable_frame, name, info, i)
            
    def create_package_widget(self, parent, name, info, index):
        """Cria widget para um pacote"""
        # Frame do pacote
        bg_color = "#f0f0f0" if index % 2 == 0 else "#ffffff"
        package_frame = tk.Frame(parent, bg=bg_color, relief="flat", bd=1)
        package_frame.pack(fill="x", padx=5, pady=2)
        
        # Frame para informações
        info_frame = tk.Frame(package_frame, bg=bg_color)
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        # Nome e versão
        name_version = f"{name} ({info.get('version', 'N/A')})"
        name_label = tk.Label(info_frame, text=name_version, 
                             font=("Arial", 11, "bold"), bg=bg_color)
        name_label.pack(anchor="w")
        
        # Descrição
        description = info.get('description', 'Sem descrição')
        if len(description) > 100:
            description = description[:100] + "..."
        desc_label = tk.Label(info_frame, text=description, 
                             font=("Arial", 9), bg=bg_color, wraplength=600)
        desc_label.pack(anchor="w")
        
        # Informações adicionais
        details = []
        if info.get('size'):
            details.append(f"Tamanho: {info['size']}")
        if info.get('section'):
            details.append(f"Seção: {info['section']}")
            
        if details:
            details_text = " | ".join(details)
            details_label = tk.Label(info_frame, text=details_text, 
                                   font=("Arial", 8), fg="#666666", bg=bg_color)
            details_label.pack(anchor="w")
        
        # Botão de instalação
        button_frame = tk.Frame(package_frame, bg=bg_color)
        button_frame.pack(side="right", padx=10, pady=5)
        
        if info.get('installed'):
            status_label = tk.Label(button_frame, text="Instalado", 
                                   fg="green", font=("Arial", 9, "bold"), bg=bg_color)
            status_label.pack()
            
            remove_button = ttk.Button(button_frame, text="Remover", 
                                     command=lambda: self.remove_package(name))
            remove_button.pack(pady=(2, 0))
        else:
            install_button = ttk.Button(button_frame, text="Instalar", 
                                      command=lambda: self.install_package(name))
            install_button.pack()
            
    def install_package(self, package_name):
        """Instala um pacote"""
        if self.installing:
            messagebox.showwarning("Aviso", "Já existe uma instalação em andamento")
            return
            
        result = messagebox.askyesno("Confirmar Instalação", 
                                   f"Deseja instalar o pacote '{package_name}'?")
        if not result:
            return
            
        self.installing = True
        self.status_var.set(f"Instalando {package_name}...")
        self.progress.start()
        
        def install_thread():
            try:
                # Comando de instalação
                cmd = ['apt', 'install', '-y', package_name]
                
                # Usar sudo se não for root
                if os.getuid() != 0:
                    cmd.insert(0, 'sudo')
                    
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    # Atualizar informações do pacote
                    info = self.get_package_info(package_name)
                    if info:
                        self.packages[package_name] = info
                        
                    # Criar .desktop se necessário
                    self.create_desktop_file(package_name)
                    
                    self.root.after(0, lambda: messagebox.showinfo("Sucesso", 
                                                                  f"Pacote '{package_name}' instalado com sucesso!"))
                    self.root.after(0, self.update_package_list)
                else:
                    error_msg = stderr if stderr else "Erro desconhecido"
                    self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                                   f"Erro ao instalar '{package_name}':\n{error_msg}"))
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                               f"Erro na instalação: {e}"))
            finally:
                self.installing = False
                self.root.after(0, lambda: self.status_var.set("Pronto"))
                self.root.after(0, self.progress.stop)
                
        threading.Thread(target=install_thread, daemon=True).start()
        
    def remove_package(self, package_name):
        """Remove um pacote"""
        if self.installing:
            messagebox.showwarning("Aviso", "Já existe uma operação em andamento")
            return
            
        result = messagebox.askyesno("Confirmar Remoção", 
                                   f"Deseja remover o pacote '{package_name}'?")
        if not result:
            return
            
        self.installing = True
        self.status_var.set(f"Removendo {package_name}...")
        self.progress.start()
        
        def remove_thread():
            try:
                cmd = ['apt', 'remove', '-y', package_name]
                
                if os.getuid() != 0:
                    cmd.insert(0, 'sudo')
                    
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    # Atualizar informações do pacote
                    info = self.get_package_info(package_name)
                    if info:
                        self.packages[package_name] = info
                        
                    self.root.after(0, lambda: messagebox.showinfo("Sucesso", 
                                                                  f"Pacote '{package_name}' removido com sucesso!"))
                    self.root.after(0, self.update_package_list)
                else:
                    error_msg = stderr if stderr else "Erro desconhecido"
                    self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                                   f"Erro ao remover '{package_name}':\n{error_msg}"))
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                               f"Erro na remoção: {e}"))
            finally:
                self.installing = False
                self.root.after(0, lambda: self.status_var.set("Pronto"))
                self.root.after(0, self.progress.stop)
                
        threading.Thread(target=remove_thread, daemon=True).start()
        
    def create_desktop_file(self, package_name):
        """Cria arquivo .desktop para aplicativos que precisam de --no-sandbox"""
        if package_name not in self.no_sandbox_apps:
            return
            
        try:
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)
            
            desktop_file = os.path.join(desktop_dir, f"{package_name}-no-sandbox.desktop")
            
            # Mapear nomes de executáveis
            exec_map = {
                'chromium': 'chromium-browser',
                'code': 'code',
                'brave-browser': 'brave-browser',
                'vivaldi-stable': 'vivaldi'
            }
            
            exec_name = exec_map.get(package_name, package_name)
            
            desktop_content = f"""[Desktop Entry]
Name={package_name.title()} (No Sandbox)
Comment={package_name.title()} com --no-sandbox para Termux
Exec={exec_name} --no-sandbox %U
Icon={package_name}
Type=Application
Categories=Network;WebBrowser;
StartupNotify=true
"""
            
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
                
            os.chmod(desktop_file, 0o755)
            
        except Exception as e:
            print(f"Erro ao criar arquivo .desktop: {e}")
            
    def refresh_packages(self):
        """Atualiza lista de repositórios"""
        if self.loading:
            return
            
        self.loading = True
        self.status_var.set("Atualizando repositórios...")
        self.progress.start()
        
        def refresh_thread():
            try:
                cmd = ['apt', 'update']
                if os.getuid() != 0:
                    cmd.insert(0, 'sudo')
                    
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if process.returncode == 0:
                    # Limpar cache
                    self.packages.clear()
                    if os.path.exists(self.cache_file):
                        os.remove(self.cache_file)
                        
                    self.root.after(0, lambda: messagebox.showinfo("Sucesso", 
                                                                  "Repositórios atualizados com sucesso!"))
                    self.root.after(0, self.load_initial_packages)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                                   "Erro ao atualizar repositórios"))
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro", 
                                                               f"Erro: {e}"))
            finally:
                self.loading = False
                self.root.after(0, lambda: self.status_var.set("Pronto"))
                self.root.after(0, self.progress.stop)
                
        threading.Thread(target=refresh_thread, daemon=True).start()
        
    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()

def main():
    """Função principal"""
    try:
        app = AppStore()
        app.run()
    except KeyboardInterrupt:
        print("\nAplicação interrompida pelo usuário")
    except Exception as e:
        print(f"Erro ao executar aplicação: {e}")

if __name__ == "__main__":
    main()