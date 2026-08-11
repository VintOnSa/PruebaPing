from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

import subprocess
import platform
import ipaddress
import re

from concurrent.futures import ThreadPoolExecutor



# Create your views here.

def cDash(request):
    return render(request, 'index.html')


# ============================================================
# LISTA FIJA DE DISPOSITIVOS
# ============================================================

IPS_FIJAS = [
    "192.168.0.1",
    "192.168.1.1",
    "192.168.2.1",
    "192.168.3.1",
    "192.168.4.1",
    "192.168.5.1",
    "192.168.0.25",
    "192.168.0.50",
    "192.168.0.75",
    "192.168.0.233",
    "192.168.0.183",
    "192.168.1.233",
]


# ============================================================
# ESCANEAR
# ============================================================

@require_GET
def Escaner(request):

    dispositivos = [
        {
            "ip": ip
        }
        for ip in IPS_FIJAS
    ]

    return JsonResponse(
        dispositivos,
        safe=False
    )


# ============================================================
# PING A UNA IP
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
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )

        output = resultado.stdout

        if resultado.returncode == 0:
            latency = obtener_latencia(output, sistema)

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
        print(f"Error haciendo ping a {ip}: {error}")
        return { 
            "online": False, 
            "latency": None
        }


# ============================================================
# OBTENER LATENCIA DEL RESULTADO DE PING
# ============================================================

def obtener_latencia(output, sistema):
    
    try:
        if sistema == "windows":
            match = re.search(r"tiempo[=<]\s*(\d+)\s*ms", output, re.IGNORECASE)

        else:
            match = re.search(r"time[=]\s*([\d.]+)\s*ms", output, re.IGNORECASE)

        if match:
            return float(match.group(1))

    except Exception:
        pass
    return None


# ============================================================
# PING DE TODOS LOS DISPOSITIVOS
# ============================================================

@require_GET
def Ping(request):
    resultados = []
    def comprobar_dispositivo(ip):

        intentos = 2

        latencia = None


        for intento in range(intentos):

            resultado = hacer_ping(ip)

            if resultado["online"]:
                latencia = resultado["latency"]
                return {
                    "ip": ip,
                    "online": True,
                    "latency": latencia,
                    "attempts": intento + 1
                }

        return {
            "ip": ip,
            "online": False,
            "latency": None,
            "attempts": intentos
        }
    # --------------------------------------------------------
    # Ejecuta pings en paralelo
    # --------------------------------------------------------
    with ThreadPoolExecutor(
        max_workers=min(
            20,
            len(IPS_FIJAS)
        )
    ) as executor:
        resultados = list(
            executor.map(
                comprobar_dispositivo,
                IPS_FIJAS
            )
        )
    return JsonResponse(
        {
            "devices": resultados
        }
    )

@require_GET
def PingIndividual(request):

    ip = request.GET.get("ip")

    if not ip:
        return JsonResponse(
            {"error": "No se especificó una IP"},
            status=400
        )

    if ip not in IPS_FIJAS:
        return JsonResponse(
            {"error": "IP no autorizada"},
            status=403
        )

    intentos = 2

    for intento in range(intentos):

        resultado = hacer_ping(ip)

        if resultado["online"]:

            return JsonResponse({
                "ip": ip,
                "online": True,
                "latency": resultado["latency"],
                "attempts": intento + 1
            })

    return JsonResponse({
        "ip": ip,
        "online": False,
        "latency": None,
        "attempts": intentos
    })




@require_GET
def Diagnostico(request):

    ip = request.GET.get("ip")

    if not ip:
        return JsonResponse(
            {"error": "No se especificó una IP"},
            status=400
        )

    # Solo permitir dispositivos conocidos
    if ip not in IPS_FIJAS:
        return JsonResponse(
            {"error": "IP no autorizada"},
            status=403
        )

    # Ping
    resultado_ping = hacer_ping(ip)

    # Traceroute
    saltos = hacer_traceroute(ip)

    return JsonResponse({
        "ip": ip,
        "online": resultado_ping["online"],
        "latency": resultado_ping["latency"],
        "hops": saltos
    })


def hacer_traceroute(ip):
    sistema = platform.system().lower()

    if sistema == "windows":
        comando = [
            "tracert",
            "-d",          # No resolver nombres DNS
            "-w", "1000",  # Timeout por salto: 1 segundo
            "-h", "20",    # Máximo 20 saltos
            ip
        ]
    else:
        comando = [
            "traceroute",
            "-n",          # No resolver nombres DNS
            "-w", "1",     # Timeout por salto
            "-q", "1",     # Una consulta por salto
            "-m", "20",    # Máximo 20 saltos
            ip
        ]

    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )

        output = resultado.stdout

        saltos = []

        for linea in output.splitlines():

            linea = linea.strip()

            if not linea:
                continue

            # Buscar número de salto al principio
            match_hop = re.match(r"^(\d+)\s+(.*)", linea)

            if not match_hop:
                continue

            numero = int(match_hop.group(1))
            contenido = match_hop.group(2)

            # Buscar una dirección IPv4
            match_ip = re.search(
                r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                contenido
            )

            ip_salto = match_ip.group(0) if match_ip else None

            # Buscar latencias en ms
            latencias = re.findall(
                r"(<\s*\d+|\d+(?:\.\d+)?)\s*ms",
                contenido,
                re.IGNORECASE
            )

            latencia = None

            if latencias:
                valores = []

                for valor in latencias:
                    valor = valor.replace("<", "").strip()

                    try:
                        valores.append(float(valor))
                    except ValueError:
                        pass

                if valores:
                    latencia = min(valores)

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
            "error": "traceroute/tracert no está instalado"
        }]

    except Exception as error:
        print(f"Error haciendo traceroute a {ip}: {error}")

        return []