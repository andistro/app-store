import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, WebKit2, GLib, Gdk
import json
import os
import subprocess
import urllib.request

APPSTREAM_PATH = '/usr/share/app-info/xmls/'
ICON_PATH = '/usr/share/icons/hicolor/48x48/apps/'
APPS_DESTAQUE_URL = 'https://raw.githubusercontent.com/andistro/app-store/alpha/assets/apps-destaque.json'
NO_SANDBOX_URL = 'https://raw.githubusercontent.com/andistro/app-store/alpha/assets/no-sandbox.json'

class SoftwareStore(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Software Store")
        self.set_default_size(700, 520)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_name("SoftwareStore")
        self.set_border_width(0)
        self.connect("delete-event", Gtk.main_quit)

        # WebKit UI
        self.webview = WebKit2.WebView()
        self.webview.connect('decide-policy', self.on_decide_policy)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.webview)
        self.add(scrolled)

        # Load theme
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-theme-name", self.get_gtk_theme())

        # Caches
        self.apps_destaque = []
        self.no_sandbox = set()
        self.deeplink_active = None

        # Load featured apps
        self.load_featured_apps()
        self.load_no_sandbox_list()

        # Load initial page
        GLib.timeout_add(300, self.load_home)

    def get_gtk_theme(self):
        # Try to get system theme
        theme = os.environ.get('GTK_THEME')
        if theme:
            return theme
        # Fallback to Adwaita
        return 'Adwaita'

    def load_featured_apps(self):
        try:
            with urllib.request.urlopen(APPS_DESTAQUE_URL) as response:
                self.apps_destaque = json.loads(response.read().decode())
        except Exception as e:
            print("Erro ao carregar apps-destaque:", e)
            self.apps_destaque = []

    def load_no_sandbox_list(self):
        try:
            with urllib.request.urlopen(NO_SANDBOX_URL) as response:
                self.no_sandbox = set(json.loads(response.read().decode()))
        except Exception as e:
            print("Erro ao carregar no-sandbox.json:", e)
            self.no_sandbox = set()

    def load_home(self, *_):
        # Render index.html with apps_destaque
        context = {
            "apps_destaque": self.apps_destaque,
        }
        self.render_html("ui/index.html", context)
        return False

    def load_search(self, search_term):
        # dpkg-query busca pacotes
        pkgs = self.search_packages(search_term)
        context = {
            "search_term": search_term,
            "results": pkgs,
        }
        self.render_html("ui/search.html", context)

    def load_details(self, pkg_name):
        info = self.get_package_info(pkg_name)
        context = {
            "pkg": info,
        }
        self.render_html("ui/details.html", context)

    def on_decide_policy(self, webview, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            uri = decision.get_request().get_uri()
            if uri.startswith("software-store://pkg?search="):
                pkg_name = uri.split("search=")[-1]
                self.load_details(pkg_name)
                decision.ignore()
                return True
        return False

    def render_html(self, template_path, context):
        # Render HTML + context (simples, substitui {{key}})
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
        for k, v in context.items():
            html = html.replace("{{ " + k + " }}", json.dumps(v))
        self.webview.load_html(html, "file://"+os.path.abspath(template_path))

    def search_packages(self, term):
        # Busca por nome/descrição
        try:
            cmd = ["apt-cache", "search", term]
            output = subprocess.check_output(cmd).decode()
            results = []
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                pkg, desc = line.split(" - ", 1)
                info = self.get_package_info(pkg.strip())
                results.append({
                    "name": info.get("name", pkg.strip()),
                    "package": pkg.strip(),
                    "version": info.get("version", ""),
                    "icon": info.get("icon", ""),
                    "description": desc,
                    "installed": info.get("installed", False)
                })
            return results
        except Exception as e:
            print("Erro na busca:", e)
            return []

    def get_package_info(self, pkg_name):
        # Busca informações do pacote + AppStream
        info = {"package": pkg_name, "name": pkg_name, "icon": "", "version": "", "installed": False, "description": ""}
        try:
            # Verifica se está instalado
            installed = subprocess.call(["dpkg", "-l", pkg_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            info["installed"] = installed
            # Busca versão
            output = subprocess.check_output(["apt-cache", "policy", pkg_name]).decode()
            for line in output.split("\n"):
                if "Installed:" in line:
                    info["version"] = line.split(":")[1].strip()
            # AppStream
            appstream_file = os.path.join(APPSTREAM_PATH, f"{pkg_name}.xml")
            if os.path.exists(appstream_file):
                # Parse XML para nome, descrição, screenshots, icon
                import xml.etree.ElementTree as ET
                root = ET.parse(appstream_file).getroot()
                name = root.findtext(".//name") or pkg_name
                description = root.findtext(".//description") or ""
                info["name"] = name
                info["description"] = description
                # Screenshots
                screenshots = [img.text for img in root.findall(".//screenshot/image")]
                info["screenshots"] = screenshots
                # Icon prioritário appstream
                icon = root.findtext(".//icon[@type='stock']") or ""
                info["icon"] = icon
            # Se não tem icone, tenta buscar em /usr/share/icons ou pasta padrão
            if not info["icon"]:
                icon_path = os.path.join(ICON_PATH, f"{pkg_name}.png")
                if os.path.exists(icon_path):
                    info["icon"] = "file://" + icon_path
            # Se não tem, usa ícone genérico
            if not info["icon"]:
                info["icon"] = "file:///usr/share/pixmaps/applications.png"
        except Exception as e:
            print("Erro ao buscar info:", e)
        return info

    def install_package(self, pkg_name):
        # Instala pacote com barra de progresso
        cmd = ["apt-get", "install", "-y", pkg_name]
        if pkg_name in self.no_sandbox:
            # Adiciona --no-sandbox ao exec post-instalação
            self.patch_exec_no_sandbox(pkg_name)
        # Executa em subprocesso com progresso
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def progress():
            while proc.poll() is None:
                # Calcula progresso
                # Opcional: pode estimar pelo tamanho baixado ou passos do apt
                yield 0.5  # Exemplo: progresso estático
            yield 1.0
        for p in progress():
            self.update_progress_bar(p)
        return proc.returncode == 0

    def patch_exec_no_sandbox(self, pkg_name):
        # Modifica exec para adicionar --no-sandbox se necessário (sem criar arquivo novo)
        # Exemplo: modifica .desktop temporariamente
        pass  # Implementação depende do ambiente, pode ser manual

    def update_progress_bar(self, progress):
        # Atualiza barra de progresso na interface (via JS)
        self.webview.run_javascript(f"updateProgress({progress});", None, None, None)

def main():
    app = SoftwareStore()
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()