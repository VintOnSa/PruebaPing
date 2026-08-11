import os
import re
import platform
import sqlite3
import subprocess
import ipaddress
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import webview


# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_NAME = "NetworkDashboard"


def obtener_directorio_datos():
    """
    Directorio donde se almacenará la BD.

    Windows:
        C:\\Users\\Usuario\\AppData\\Local\\NetworkDashboard

    Linux:
        ~/.local/share/NetworkDashboard

    macOS:
        ~/Library/Application Support/NetworkDashboard
    """

    sistema = platform.system()

    if sistema == "Windows":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home()
            )
        )

    elif sistema == "Darwin":
        base = (
            Path.home()
            / "Library"
            / "Application Support"
        )

    else:
        base = (
            Path.home()
            / ".local"
            / "share"
        )

    directorio = base / APP_NAME
    directorio.mkdir(
        parents=True,
        exist_ok=True
    )

    return directorio


APP_DIR = obtener_directorio_datos()
DB_PATH = APP_DIR / "network.db"


# ============================================================
# BASE DE DATOS
# ============================================================

def conectar_bd():
    return sqlite3.connect(DB_PATH)


def inicializar_bd():

    with conectar_bd() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL UNIQUE,
                nombre TEXT DEFAULT '',
                descripcion TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


# ============================================================
# VALIDAR IP
# ============================================================

def validar_ip(ip):

    try:
        ipaddress.ip_address(ip)
        return True

    except ValueError:
        return False


# ============================================================
# OBTENER DISPOSITIVOS
# ============================================================

def obtener_dispositivos():

    with conectar_bd() as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT
                id,
                ip,
                nombre,
                descripcion,
                created_at
            FROM devices
            ORDER BY id
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ============================================================
# BUSCAR DISPOSITIVO
# ============================================================

def obtener_dispositivo(device_id):

    with conectar_bd() as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT
                id,
                ip,
                nombre,
                descripcion,
                created_at
            FROM devices
            WHERE id = ?
        """, (
            device_id,
        )).fetchone()

        if row:
            return dict(row)

        return None


# ============================================================
# AGREGAR DISPOSITIVO
# ============================================================

def agregar_dispositivo(
    ip,
    nombre="",
    descripcion=""
):

    ip = str(ip).strip()
    nombre = str(nombre or "").strip().title()
    descripcion = str(descripcion or "").strip().title()

    if not ip:

        return {
            "success": False,
            "error": "La IP es obligatoria."
        }

    if not validar_ip(ip):

        return {
            "success": False,
            "error": "La dirección IP no es válida."
        }

    try:

        with conectar_bd() as conn:

            cursor = conn.execute("""
                INSERT INTO devices (
                    ip,
                    nombre,
                    descripcion
                )
                VALUES (?, ?, ?)
            """, (
                ip,
                nombre,
                descripcion
            ))

            conn.commit()

            device_id = cursor.lastrowid

        return {
            "success": True,
            "device": obtener_dispositivo(
                device_id
            )
        }

    except sqlite3.IntegrityError:

        return {
            "success": False,
            "error": "Esa dirección IP ya existe."
        }

    except Exception as error:

        print(
            f"Error agregando dispositivo: {error}"
        )

        return {
            "success": False,
            "error": "No se pudo agregar el dispositivo."
        }


# ============================================================
# EDITAR DISPOSITIVO
# ============================================================

def editar_dispositivo(
    device_id,
    ip,
    nombre="",
    descripcion=""
):

    ip = str(ip).strip()
    nombre = str(nombre or "").strip().title()
    descripcion = str(descripcion or "").strip().title()

    if not ip:

        return {
            "success": False,
            "error": "La IP es obligatoria."
        }

    if not validar_ip(ip):

        return {
            "success": False,
            "error": "La dirección IP no es válida."
        }

    try:

        with conectar_bd() as conn:

            cursor = conn.execute("""
                UPDATE devices
                SET
                    ip = ?,
                    nombre = ?,
                    descripcion = ?
                WHERE id = ?
            """, (
                ip,
                nombre,
                descripcion,
                int(device_id)
            ))

            conn.commit()

            if cursor.rowcount == 0:

                return {
                    "success": False,
                    "error": "El dispositivo no existe."
                }

        return {
            "success": True,
            "device": obtener_dispositivo(
                int(device_id)
            )
        }

    except sqlite3.IntegrityError:

        return {
            "success": False,
            "error": "Esa dirección IP ya existe."
        }

    except Exception as error:

        print(
            f"Error editando dispositivo: {error}"
        )

        return {
            "success": False,
            "error": "No se pudo editar el dispositivo."
        }


# ============================================================
# ELIMINAR DISPOSITIVO
# ============================================================

def eliminar_dispositivo(device_id):

    try:

        with conectar_bd() as conn:

            cursor = conn.execute("""
                DELETE FROM devices
                WHERE id = ?
            """, (
                int(device_id),
            ))

            conn.commit()

            if cursor.rowcount == 0:

                return {
                    "success": False,
                    "error": "El dispositivo no existe."
                }

        return {
            "success": True
        }

    except Exception as error:

        print(
            f"Error eliminando dispositivo: {error}"
        )

        return {
            "success": False,
            "error": "No se pudo eliminar el dispositivo."
        }


# ============================================================
# PING
# ============================================================

def hacer_ping(ip):

    sistema = platform.system().lower()

    if sistema == "windows":

        comando = [
            "ping",
            "-n",
            "1",
            "-w",
            "1000",
            ip
        ]

    else:

        comando = [
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            ip
        ]

    try:

        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "timeout": 3
        }

        if sistema == "windows":

            kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW
            )

        resultado = subprocess.run(
            comando,
            **kwargs
        )

        output = resultado.stdout

        if resultado.returncode == 0:

            latency = obtener_latencia(
                output,
                sistema
            )

            return {
                "online": True,
                "latency": latency
            }

        return {
            "online": False,
            "latency": None
        }

    except subprocess.TimeoutExpired:

        return {
            "online": False,
            "latency": None
        }

    except Exception as error:

        print(
            f"Error haciendo ping a {ip}: {error}"
        )

        return {
            "online": False,
            "latency": None
        }


# ============================================================
# OBTENER LATENCIA
# ============================================================

def obtener_latencia(
    output,
    sistema
):

    try:

        if sistema == "windows":

            match = re.search(
                r"(?:tiempo|time)[=<]\s*(\d+)\s*ms",
                output,
                re.IGNORECASE
            )

        else:

            match = re.search(
                r"time[=]\s*([\d.]+)\s*ms",
                output,
                re.IGNORECASE
            )

        if match:

            return float(
                match.group(1)
            )

    except Exception:
        pass

    return None


# ============================================================
# PING INDIVIDUAL
# ============================================================

def ping_individual(device_id):

    dispositivo = obtener_dispositivo(
        device_id
    )

    if not dispositivo:

        return {
            "success": False,
            "error": "Dispositivo no encontrado."
        }

    ip = dispositivo["ip"]

    intentos = 2

    for intento in range(intentos):

        resultado = hacer_ping(ip)

        if resultado["online"]:

            return {
                "success": True,
                "id": device_id,
                "ip": ip,
                "online": True,
                "latency": resultado["latency"],
                "attempts": intento + 1
            }

    return {
        "success": True,
        "id": device_id,
        "ip": ip,
        "online": False,
        "latency": None,
        "attempts": intentos
    }


# ============================================================
# PING DE TODOS
# ============================================================

def ping_todos():

    dispositivos = obtener_dispositivos()

    if not dispositivos:

        return {
            "success": True,
            "devices": []
        }

    def comprobar(dispositivo):

        return ping_individual(
            dispositivo["id"]
        )

    max_workers = min(
        20,
        len(dispositivos)
    )

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        resultados = list(
            executor.map(
                comprobar,
                dispositivos
            )
        )

    return {
        "success": True,
        "devices": resultados
    }


# ============================================================
# TRACEROUTE
# ============================================================

def hacer_traceroute(ip):

    sistema = platform.system().lower()

    if sistema == "windows":

        comando = [
            "tracert",
            "-d",
            "-w",
            "1000",
            "-h",
            "20",
            ip
        ]

    else:

        comando = [
            "traceroute",
            "-n",
            "-w",
            "1",
            "-q",
            "1",
            "-m",
            "20",
            ip
        ]

    try:

        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "timeout": 30
        }

        if sistema == "windows":

            kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW
            )

        resultado = subprocess.run(
            comando,
            **kwargs
        )

        output = resultado.stdout

        saltos = []

        for linea in output.splitlines():

            linea = linea.strip()

            if not linea:
                continue

            match_hop = re.match(
                r"^(\d+)\s+(.*)",
                linea
            )

            if not match_hop:
                continue

            numero = int(
                match_hop.group(1)
            )

            contenido = match_hop.group(2)

            match_ip = re.search(
                r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                contenido
            )

            ip_salto = (
                match_ip.group(0)
                if match_ip
                else None
            )

            latencias = re.findall(
                r"(<\s*\d+|\d+(?:\.\d+)?)\s*ms",
                contenido,
                re.IGNORECASE
            )

            latencia = None

            if latencias:

                valores = []

                for valor in latencias:

                    valor = (
                        valor
                        .replace("<", "")
                        .strip()
                    )

                    try:

                        valores.append(
                            float(valor)
                        )

                    except ValueError:
                        pass

                if valores:

                    latencia = min(
                        valores
                    )

            saltos.append({
                "hop": numero,
                "ip": ip_salto,
                "latency": latencia,
                "online": ip_salto is not None
            })

        return saltos

    except subprocess.TimeoutExpired:

        return []

    except FileNotFoundError:

        return [{
            "hop": 0,
            "ip": None,
            "latency": None,
            "online": False,
            "error": (
                "traceroute/tracert "
                "no está instalado"
            )
        }]

    except Exception as error:

        print(
            f"Error haciendo traceroute: {error}"
        )

        return []


# ============================================================
# DIAGNÓSTICO
# ============================================================

def diagnostico(device_id):

    dispositivo = obtener_dispositivo(
        device_id
    )

    if not dispositivo:

        return {
            "success": False,
            "error": "Dispositivo no encontrado."
        }

    ip = dispositivo["ip"]

    resultado_ping = hacer_ping(ip)

    saltos = hacer_traceroute(ip)

    return {
        "success": True,
        "id": device_id,
        "ip": ip,
        "online": resultado_ping["online"],
        "latency": resultado_ping["latency"],
        "hops": saltos
    }



# ============================================================
# DIAGNÓSTICO DE IP NO REGISTRADA
# ============================================================

def diagnostico_ip(ip):

    ip = str(ip).strip()

    if not ip:
        return {
            "success": False,
            "error": "La IP es obligatoria."
        }

    if not validar_ip(ip):
        return {
            "success": False,
            "error": "La dirección IP no es válida."
        }

    # Hacemos los mismos 2 intentos que ping_individual()
    intentos = 2
    resultado_ping = None

    for intento in range(intentos):

        resultado_ping = hacer_ping(ip)

        if resultado_ping["online"]:
            break

    # Traceroute independiente de que el ping responda
    saltos = hacer_traceroute(ip)

    return {
        "success": True,
        "ip": ip,
        "online": resultado_ping["online"],
        "latency": resultado_ping["latency"],
        "attempts": intento + 1,
        "hops": saltos
    }



# ============================================================
# API PARA JAVASCRIPT
# ============================================================

class Api:

    def listar_dispositivos(self):

        return {
            "success": True,
            "devices": obtener_dispositivos()
        }

    def agregar_dispositivo(
        self,
        ip,
        nombre="",
        descripcion=""
    ):

        return agregar_dispositivo(
            ip,
            nombre,
            descripcion
        )

    def editar_dispositivo(
        self,
        device_id,
        ip,
        nombre="",
        descripcion=""
    ):

        return editar_dispositivo(
            int(device_id),
            ip,
            nombre,
            descripcion
        )

    def eliminar_dispositivo(
        self,
        device_id
    ):

        return eliminar_dispositivo(
            int(device_id)
        )

    def ping_individual(
        self,
        device_id
    ):

        return ping_individual(
            int(device_id)
        )

    def ping_todos(self):

        return ping_todos()

    def diagnostico(
        self,
        device_id
    ):

        return diagnostico(
            int(device_id)
        )
    
    def diagnostico_ip(
        self,
        ip
    ):

        return diagnostico_ip(ip)


# ============================================================
# RUTA DEL INDEX.HTML
# ============================================================

def resource_path(relative_path):

    try:

        # PyInstaller --onefile
        base_path = Path(
            os.environ["_MEIPASS"]
        )

    except KeyError:

        # Ejecución normal
        base_path = Path(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

    return base_path / relative_path


# ============================================================
# INICIO
# ============================================================

if __name__ == "__main__":

    # Crear BD y tabla si no existen
    inicializar_bd()

    # Crear API para JavaScript
    api = Api()

    # Obtener index.html
    HTML_FILE = resource_path(
        "index.html"
    )

    # Crear ventana
    window = webview.create_window(
        "Network Dashboard",
        str(HTML_FILE),
        js_api=api,
        width=1400,
        height=900,
        resizable=True
    )

    webview.start(
        debug=False
    )