#!/bin/sh
# Install the isolated Condor lab for the current user. No sudo or system changes.
set -eu
umask 077

SOURCE=""
HOST="192.168.146.137"
PORT="18083"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --source) SOURCE=${2:?Falta directorio --source}; shift 2 ;;
        --host) HOST=${2:?Falta IPv4 --host}; shift 2 ;;
        --port) PORT=${2:?Falta puerto --port}; shift 2 ;;
        *) printf '%s\n' 'Uso: sh deploy/install-user.sh --source DIR [--host IP] [--port 18083]' >&2; exit 2 ;;
    esac
done
[ -n "$SOURCE" ] || { printf '%s\n' 'Se requiere --source DIR.' >&2; exit 2; }
[ "$(id -u)" -ne 0 ] || { printf '%s\n' 'Ejecuta este instalador con tu usuario normal, sin sudo.' >&2; exit 2; }
command -v python3 >/dev/null
command -v flock >/dev/null
command -v nohup >/dev/null

CONDOR_USER_BASE="$HOME/.ctf-condor"
mkdir -p "$CONDOR_USER_BASE/run" "$CONDOR_USER_BASE/bin" "$CONDOR_USER_BASE/releases"
chmod 700 "$CONDOR_USER_BASE" "$CONDOR_USER_BASE/run" "$CONDOR_USER_BASE/bin" "$CONDOR_USER_BASE/releases"
exec 9>"$CONDOR_USER_BASE/run/install.lock"
flock -n 9 || { printf '%s\n' 'Ya hay una instalación propia en curso.' >&2; exit 1; }

# Validate the operator-provided private file before running its contents.
python3 - "$CONDOR_USER_BASE" "$SOURCE" "$HOST" "$PORT" <<'PY'
import ipaddress, os, pathlib, stat, sys
base, source = map(pathlib.Path, sys.argv[1:3])
host, port = sys.argv[3:5]
secret = base / 'condor.env'
try:
    info = secret.lstat()
except OSError:
    raise SystemExit('Falta ~/.ctf-condor/condor.env privado; el instalador no lo genera ni sobrescribe.')
if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
    raise SystemExit('condor.env debe ser un archivo propio, sin enlace simbólico y con permisos 600.')
address = ipaddress.IPv4Address(host)
blocks = [ipaddress.IPv4Network(value) for value in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
if not any(address in block for block in blocks):
    raise SystemExit('El host debe ser una IPv4 privada.')
if not port.isdecimal() or not 1024 <= int(port) <= 65535:
    raise SystemExit('El puerto debe estar entre 1024 y 65535.')
for required in ('condor_app/__init__.py','resources/candidatas.txt','requirements.txt','deploy/user_service.py'):
    if not (source / required).is_file():
        raise SystemExit('El directorio --source no contiene el paquete completo.')
PY

# Dependencies are pinned in requirements.txt. Never apt, sudo or global pip.
if [ ! -x "$CONDOR_USER_BASE/venv/bin/python" ]; then
    if ! python3 -m venv "$CONDOR_USER_BASE/venv"; then
        # Ubuntu may omit ensurepip. Existing user pip can manage a pip-less venv
        # without installing an OS package or modifying the global environment.
        python3 -m venv --without-pip "$CONDOR_USER_BASE/venv"
    fi
fi
if "$CONDOR_USER_BASE/venv/bin/python" -m pip --version >/dev/null 2>&1; then
    "$CONDOR_USER_BASE/venv/bin/python" -m pip install --disable-pip-version-check -r "$SOURCE/requirements.txt"
else
    python3 -m pip --python "$CONDOR_USER_BASE/venv/bin/python" install --disable-pip-version-check -r "$SOURCE/requirements.txt"
fi

CONDOR_USER_RELEASE=$(python3 - "$CONDOR_USER_BASE" "$SOURCE" <<'PY'
import hashlib, os, pathlib, shutil, sys, tempfile
base, source = (pathlib.Path(value).resolve() for value in sys.argv[1:3])
files = [source / 'requirements.txt']
for folder in ('condor_app','resources'):
    files.extend(path for path in (source / folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
digest = hashlib.sha256()
for path in sorted(files):
    if path.is_symlink():
        raise SystemExit('El paquete de la aplicación no debe contener enlaces simbólicos.')
    digest.update(path.relative_to(source).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
release = base / 'releases' / digest.hexdigest()[:24]
if not release.exists():
    temporary = pathlib.Path(tempfile.mkdtemp(prefix='release-', dir=base / 'releases'))
    try:
        for path in files:
            target = temporary / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        os.rename(temporary, release)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
print(release)
PY
)

# Stop only the previously managed process before replacing its controller.
if [ -f "$CONDOR_USER_BASE/bin/user_service.py" ]; then
    "$CONDOR_USER_BASE/venv/bin/python" "$CONDOR_USER_BASE/bin/user_service.py" stop --base "$CONDOR_USER_BASE"
fi
cp "$SOURCE/deploy/user_service.py" "$CONDOR_USER_BASE/bin/user_service.py"
chmod 600 "$CONDOR_USER_BASE/bin/user_service.py"
"$CONDOR_USER_BASE/venv/bin/python" "$CONDOR_USER_BASE/bin/user_service.py" init --base "$CONDOR_USER_BASE" --release "$CONDOR_USER_RELEASE"

python3 - "$CONDOR_USER_BASE" "$CONDOR_USER_RELEASE" "$HOST" "$PORT" <<'PY'
import json, os, pathlib, shlex, sys
base, release = map(pathlib.Path, sys.argv[1:3])
(base / 'runtime.json').write_text(json.dumps({'host':sys.argv[3], 'port':int(sys.argv[4])}) + '\n')
temporary = base / 'current.new'
temporary.unlink(missing_ok=True)
temporary.symlink_to(release, target_is_directory=True)
os.replace(temporary, base / 'current')
for command in ('start','stop','status'):
    wrapper = base / (command + '.sh')
    argv = [str(base / 'venv/bin/python'), str(base / 'bin/user_service.py'), command, '--base', str(base)]
    wrapper.write_text('#!/bin/sh\nset -eu\numask 077\nexec ' + shlex.join(argv) + '\n')
    wrapper.chmod(0o700)
PY

"$CONDOR_USER_BASE/start.sh"
printf '%s\n' 'Instalación propia terminada. Usa ~/.ctf-condor/start.sh, stop.sh o status.sh.'
