#!/usr/bin/env bash
# Operación Cóndor: instalación exclusiva para una red privada de laboratorio.
set -Eeuo pipefail
umask 022

usage() {
    cat <<'HELP'
Uso:
  sudo bash deploy/install.sh --server-ip IP_PRIVADA --lab-cidr SUBRED_PRIVADA/CIDR
  bash deploy/install.sh --server-ip IP_PRIVADA --lab-cidr SUBRED_PRIVADA/CIDR --validate-only

Ejemplo:
  sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24

Instala Flask + Gunicorn en un venv y un sitio Nginx en IP_PRIVADA:8080.
La IP debe existir en esta VM. --validate-only solo valida los parámetros.
--lab-cidr indica la subred cliente autorizada; puede estar en otra VLAN.
Conserva la base de datos, la contraseña y la flag al reinstalar.
No modifica UFW, SSH, sitios Nginx ajenos ni el sitio predeterminado.
HELP
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
trap 'printf "Instalación detenida en la línea %s. Revisa el error anterior; no se han impreso secretos.\n" "$LINENO" >&2' ERR

SERVER_IP=''
LAB_CIDR=''
VALIDATE_ONLY=false
while (($#)); do
    case "$1" in
        --server-ip|--lab-cidr)
            (($# >= 2)) || die "Falta el valor de $1."
            [[ -n "$2" && "$2" != --* ]] || die "Falta el valor de $1."
            if [[ "$1" == --server-ip ]]; then SERVER_IP="$2"; else LAB_CIDR="$2"; fi
            shift 2 ;;
        --validate-only) VALIDATE_ONLY=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Opción desconocida: $1. Usa --help." ;;
    esac
done
[[ -n "$SERVER_IP" && -n "$LAB_CIDR" ]] || { usage >&2; exit 2; }
command -v python3 >/dev/null || die 'Se necesita python3 (incluido normalmente en Ubuntu Server).'
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
VALIDATED="$(python3 "$SOURCE_DIR/deploy/validate_config.py" --server-ip "$SERVER_IP" --lab-cidr "$LAB_CIDR")"
mapfile -t NETWORK_VALUES <<< "$VALIDATED"
SERVER_IP="${NETWORK_VALUES[0]}"
LAB_CIDR="${NETWORK_VALUES[1]}"
if "$VALIDATE_ONLY"; then
    printf 'Parámetros válidos: servidor %s; subred %s. No se modificó el sistema.\n' "$SERVER_IP" "$LAB_CIDR"
    exit 0
fi
[[ "$EUID" == 0 ]] || die 'Ejecuta la instalación con sudo.'
[[ -f /etc/os-release ]] || die 'Este instalador requiere Ubuntu Server 26.04.'
# Archivo del sistema suministrado por Ubuntu, no un archivo de la aplicación.
. /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 26.04 ]] || die 'Se requiere Ubuntu Server 26.04.'
command -v ip >/dev/null || die 'Falta iproute2. Instálalo con sudo apt install iproute2.'
command -v ss >/dev/null || die 'Falta ss (paquete iproute2).'
ip -j -4 address show | python3 -c 'import json,sys; expected=sys.argv[1]; found={i["local"] for x in json.load(sys.stdin) for i in x.get("addr_info", [])}; sys.exit(0 if expected in found else 1)' "$SERVER_IP" || die 'La IP indicada no está asignada a una interfaz de esta VM. Comprueba ip -4 address.'
[[ -f "$SOURCE_DIR/condor_app/__init__.py" && -f "$SOURCE_DIR/requirements.txt" && -f "$SOURCE_DIR/resources/candidatas.txt" ]] || die 'El paquete está incompleto. Extrae el archivo completo antes de instalar.'
[[ -z "$(find "$SOURCE_DIR/condor_app" "$SOURCE_DIR/deploy" "$SOURCE_DIR/resources" -type l -print -quit)" ]] || die 'El paquete contiene enlaces simbólicos inesperados.'

APP_ROOT=/opt/condor-lab
DATA_ROOT=/var/lib/condor-lab
CONFIG_ROOT=/etc/condor-lab
ENV_FILE="$CONFIG_ROOT/condor.env"
SITE=/etc/nginx/sites-available/condor-lab.conf
SITE_LINK=/etc/nginx/sites-enabled/condor-lab.conf
UNIT=/etc/systemd/system/condor-lab.service
MARKER='COCIBER_CONDOR_MANAGED_V1'

for directory in "$APP_ROOT" "$DATA_ROOT" "$CONFIG_ROOT"; do
    [[ ! -L "$directory" ]] || die "Ruta insegura: $directory es un enlace simbólico."
    if [[ -e "$directory" ]]; then
        [[ -d "$directory" && -f "$directory/.condor-lab-managed" && ! -L "$directory/.condor-lab-managed" ]] || die "La ruta $directory ya existe y no pertenece a este instalador."
        [[ "$(cat "$directory/.condor-lab-managed")" == "$MARKER" ]] || die "Marcador desconocido en $directory."
        [[ "$(stat -c %u "$directory")" == 0 || "$directory" == "$DATA_ROOT" ]] || die "Propietario inesperado en $directory."
    fi
done
for path in "$SITE" "$UNIT"; do
    [[ ! -L "$path" ]] || die "Ruta insegura: $path es un enlace simbólico."
    if [[ -e "$path" ]]; then
        [[ -f "$path" ]] && grep -qxF "# $MARKER" "$path" || die "No se sobrescribirá el archivo ajeno $path."
        [[ "$(stat -c %u "$path")" == 0 ]] || die "Propietario inesperado en $path."
    fi
done
if [[ -e "$SITE_LINK" || -L "$SITE_LINK" ]]; then
    [[ -L "$SITE_LINK" && "$(readlink "$SITE_LINK")" == "$SITE" ]] || die "No se modificará el sitio ajeno $SITE_LINK."
fi
[[ ! -L "$ENV_FILE" ]] || die 'El archivo de secretos no puede ser un enlace simbólico.'
if [[ -e "$ENV_FILE" ]]; then
    [[ -f "$ENV_FILE" && "$(stat -c %u:%g "$ENV_FILE")" == 0:0 && "$(stat -c %a "$ENV_FILE")" == 600 ]] || die 'El archivo de secretos debe ser regular, root:root y modo 600.'
fi
if [[ -e "$APP_ROOT/releases" || -L "$APP_ROOT/releases" ]]; then
    [[ -d "$APP_ROOT/releases" && ! -L "$APP_ROOT/releases" && "$(stat -c %u "$APP_ROOT/releases")" == 0 ]] || die 'Directorio de versiones inseguro.'
fi
if [[ -e "$APP_ROOT/current" || -L "$APP_ROOT/current" ]]; then
    [[ -L "$APP_ROOT/current" ]] || die 'current debe ser el enlace administrado por este instalador.'
    case "$(readlink -f "$APP_ROOT/current")" in "$APP_ROOT"/releases/*) ;; *) die 'El enlace current apunta fuera de las versiones administradas.' ;; esac
fi
if getent passwd condor-lab >/dev/null; then
    [[ -f "$APP_ROOT/.condor-lab-managed" ]] || die 'El usuario condor-lab ya existe y no pertenece a una instalación reconocida.'
    [[ "$(getent passwd condor-lab | cut -d: -f7)" == /usr/sbin/nologin ]] || die 'El usuario condor-lab tiene un shell inesperado.'
fi

# Evita apropiarse de puertos usados por otras aplicaciones. En una actualización
# solo se aceptan Nginx del sitio administrado y procesos de nuestra unidad.
python3 - "$SERVER_IP" "$SITE" "$UNIT" <<'PY'
import pathlib
import re
import subprocess
import sys
address, site, unit = sys.argv[1:]
for line in subprocess.check_output(["ss", "-H", "-ltnp"], text=True).splitlines():
    fields = line.split()
    if len(fields) < 4:
        continue
    local = fields[3]
    port = local.rsplit(":", 1)[-1]
    if port not in {"8080", "18080"}:
        continue
    if port == "8080" and local == f"{address}:8080" and pathlib.Path(site).is_file() and '"nginx"' in line:
        continue
    if port == "18080" and local == "127.0.0.1:18080" and pathlib.Path(unit).is_file():
        pids = re.findall(r"pid=(\d+)", line)
        if pids and all("/condor-lab.service" in pathlib.Path(f"/proc/{pid}/cgroup").read_text() for pid in pids):
            continue
    sys.exit(f"ERROR: puerto {port} ocupado por un servicio ajeno o por otra dirección. No se modificará ese servicio.")
PY

printf 'Instalando dependencias del sistema y creando el entorno aislado…\n'
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv nginx curl
if ! getent passwd condor-lab >/dev/null; then
    useradd --system --user-group --home-dir "$DATA_ROOT" --no-create-home --shell /usr/sbin/nologin condor-lab
fi
install -d -o root -g root -m 0755 "$APP_ROOT" "$APP_ROOT/releases"
install -d -o root -g root -m 0700 "$CONFIG_ROOT"
install -d -o condor-lab -g condor-lab -m 0700 "$DATA_ROOT"
for directory in "$APP_ROOT" "$CONFIG_ROOT" "$DATA_ROOT"; do
    printf '%s\n' "$MARKER" > "$directory/.condor-lab-managed"
    chown root:root "$directory/.condor-lab-managed"
    chmod 0600 "$directory/.condor-lab-managed"
done
RELEASE="$APP_ROOT/releases/$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -o root -g root -m 0755 "$RELEASE"
cp -R -- "$SOURCE_DIR/condor_app" "$SOURCE_DIR/resources" "$SOURCE_DIR/deploy" "$RELEASE/"
install -o root -g root -m 0644 "$SOURCE_DIR/requirements.txt" "$RELEASE/"
find "$RELEASE" -type d -exec chmod 0755 {} +
find "$RELEASE" -type f -exec chmod 0644 {} +
chown -R root:root "$RELEASE"
python3 -m venv "$RELEASE/venv"
"$RELEASE/venv/bin/python" -m pip --disable-pip-version-check install -r "$RELEASE/requirements.txt"

# Escribe valores controlados una sola vez; nunca ejecuta ni imprime el archivo.
python3 - "$ENV_FILE" "$SOURCE_DIR/resources/candidatas.txt" "$SERVER_IP" <<'PY'
import os
import pathlib
import re
import secrets
import sys
path, words, address = sys.argv[1:]
expected = {"CONDOR_INSTANCE_PATH", "CONDOR_DATABASE", "CONDOR_TRUSTED_HOSTS", "CONDOR_SECRET_KEY", "CONDOR_FLAG", "CONDOR_ADMIN_PASSWORD", "CONDOR_COOKIE_SECURE"}
if pathlib.Path(path).exists():
    entries = {}
    for line in pathlib.Path(path).read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in entries or key not in expected or not re.fullmatch(r"[A-Za-z0-9_./,{}!@+-]+", value):
            sys.exit("ERROR: archivo de configuración no válido; se conserva sin ejecutar su contenido.")
        entries[key] = value
    if set(entries) != expected or entries["CONDOR_DATABASE"] != "/var/lib/condor-lab/condor.sqlite3" or entries["CONDOR_INSTANCE_PATH"] != "/var/lib/condor-lab" or entries["CONDOR_TRUSTED_HOSTS"] != f"{address},condor.lab,localhost,127.0.0.1":
        sys.exit("ERROR: configuración previa incompatible con esta IP o estructura; no se cambió ningún secreto.")
else:
    candidates = pathlib.Path(words).read_text(encoding="ascii").splitlines()
    if len(candidates) != 12 or len(set(candidates)) != 12 or not all(re.fullmatch(r"[A-Za-z0-9!@+_-]{6,64}", word) for word in candidates):
        sys.exit("ERROR: el diccionario debe contener exactamente 12 contraseñas ASCII de laboratorio.")
    entries = {
        "CONDOR_INSTANCE_PATH": "/var/lib/condor-lab",
        "CONDOR_DATABASE": "/var/lib/condor-lab/condor.sqlite3",
        "CONDOR_TRUSTED_HOSTS": f"{address},condor.lab,localhost,127.0.0.1",
        "CONDOR_SECRET_KEY": secrets.token_hex(32),
        "CONDOR_FLAG": "COCIBER{CONDOR_" + secrets.token_hex(16) + "}",
        "CONDOR_ADMIN_PASSWORD": secrets.choice(candidates),
        "CONDOR_COOKIE_SECURE": "false",
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("# COCIBER_CONDOR_MANAGED_V1\n")
        stream.write("".join(f"{key}={value}\n" for key, value in entries.items()))
PY

# Carga literal en un proceso hijo; no utiliza source ni eval para los secretos.
python3 - "$ENV_FILE" "$RELEASE" <<'PY'
import os
import pathlib
import subprocess
import sys
environment = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        environment[key] = value
environment["PYTHONDONTWRITEBYTECODE"] = "1"
subprocess.run(["runuser", "-u", "condor-lab", "--", sys.argv[2] + "/venv/bin/flask", "--app", "condor_app", "init-lab"], cwd=sys.argv[2], env=environment, check=True)
PY

cat > "$UNIT" <<'UNIT'
# COCIBER_CONDOR_MANAGED_V1
[Unit]
Description=Cociber CTF - Operación Cóndor (laboratorio privado)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=condor-lab
Group=condor-lab
WorkingDirectory=/opt/condor-lab/current
EnvironmentFile=/etc/condor-lab/condor.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/condor-lab/current/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:18080 --access-logfile - --error-logfile - --timeout 30 "condor_app:create_app()"
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/condor-lab
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$UNIT"
cat > "$SITE" <<NGINX
# $MARKER
server {
    listen $SERVER_IP:8080;
    server_name $SERVER_IP condor.lab;
    server_tokens off;
    client_max_body_size 16k;
    allow $LAB_CIDR;
    deny all;

    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 35s;
    }
}
NGINX
chmod 0644 "$SITE"
[[ -L "$SITE_LINK" ]] || ln -s "$SITE" "$SITE_LINK"
nginx -t
ln -s "$RELEASE" "$APP_ROOT/.current-new-$$"
mv -Tf "$APP_ROOT/.current-new-$$" "$APP_ROOT/current"
systemctl daemon-reload
systemctl enable condor-lab.service
systemctl restart condor-lab.service
systemctl enable --now nginx.service
systemctl reload nginx.service

READY=false
for attempt in {1..15}; do
    # The server can be outside the allowed client VLAN. Check Gunicorn locally;
    # the end-to-end Nginx/routing check must be run from the allowed Kali VLAN.
    if curl --silent --show-error --fail --max-time 3 "http://127.0.0.1:18080/healthz" >/dev/null 2>&1; then READY=true; break; fi
    sleep 1
done
"$READY" || die 'El servicio no respondió. Revisa sudo journalctl -u condor-lab -n 50 --no-pager.'
printf '\nListo. Portal: http://%s:8080/\n' "$SERVER_IP"
printf 'Acceso permitido únicamente desde %s. La contraseña y la flag se conservan en un archivo root:root 600.\n' "$LAB_CIDR"
printf 'No se modificaron las reglas de UFW ni el servicio SSH.\n'
printf 'Comprueba desde Kali el portal y /healthz; la comprobación local verificó Gunicorn.\n'
