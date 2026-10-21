"""Manage only this user's isolated Condor process; never stop a port's owner.

Linux /proc and pidfds identify the exact process before delivering a signal.
This file is copied into ~/.ctf-condor/bin by install-user.sh.
"""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener


def process_identity(pid, proc_root=Path("/proc")):
    """Return UID, argv, start ticks and state without trusting a PID file."""
    try:
        directory = proc_root / str(int(pid))
        raw_stat = (directory / "stat").read_text()
        fields = raw_stat[raw_stat.rfind(")") + 2:].split()
        return {
            "pid": int(pid), "uid": directory.stat().st_uid,
            "argv": [part.decode("utf-8", errors="replace") for part in (directory / "cmdline").read_bytes().split(b"\0") if part],
            "start_ticks": fields[19], "state": fields[0],
        }
    except (OSError, ValueError, IndexError):
        return None


def manager_argv(base):
    return [str(base / "venv/bin/python"), str(base / "bin/user_service.py"), "serve", "--base", str(base)]


def matches_process(record, expected_argv, proc_root=Path("/proc")):
    if not isinstance(record, dict) or record.get("uid") != os.getuid():
        return False
    actual = process_identity(record.get("pid", -1), proc_root)
    return bool(
        actual and actual["state"] != "Z" and actual["uid"] == os.getuid()
        and actual["start_ticks"] == record.get("start_ticks")
        and actual["argv"] == expected_argv
    )


def read_record(base):
    try:
        return json.loads((base / "run/manager.json").read_text())
    except (OSError, ValueError):
        return None


def write_record(base, record):
    path = base / "run/manager.json"
    temporary = path.with_name(f"manager.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(record, output)
    os.replace(temporary, path)


def private_environment(base):
    path = base / "condor.env"
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError("condor.env debe ser un archivo propio, sin enlace simbólico y con permisos 600")
    # The operator supplied and owns this private POSIX shell file. Pass its name
    # as an argument, never interpolate its contents into a command string.
    result = subprocess.run(
        ["/bin/sh", "-c", 'set -a; . "$1"; exec env -0', "condor-env", str(path)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    environment = {}
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            name, value = entry.split(b"=", 1)
            environment[os.fsdecode(name)] = os.fsdecode(value)
    return environment


def runtime(base):
    settings = json.loads((base / "runtime.json").read_text())
    address = ipaddress.IPv4Address(settings["host"])
    private_blocks = [ipaddress.IPv4Network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    if not any(address in block for block in private_blocks):
        raise RuntimeError("La dirección del laboratorio debe ser IPv4 privada")
    port = settings["port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise RuntimeError("El puerto debe estar entre 1024 y 65535")
    return str(address), port


def gunicorn_argv(base, release, host, port):
    return [
        str(base / "venv/bin/python"), "-m", "gunicorn", "--chdir", str(release),
        "--bind", f"{host}:{port}", "--workers", "2", "--timeout", "30",
        "--graceful-timeout", "8",
        "--access-logfile", "-", "--error-logfile", "-", "condor_app:create_app()",
    ]


def owns_listener(child, host, port):
    """Confirm Gunicorn owns the listening socket before accepting healthz."""
    try:
        inodes = {
            os.readlink(path)[8:-1]
            for path in (Path("/proc") / str(child["pid"]) / "fd").iterdir()
            if os.readlink(path).startswith("socket:[")
        }
        expected_ip = socket.inet_aton(host)[::-1].hex().upper()
        expected_address = f"{expected_ip}:{port:04X}"
        for line in Path("/proc/net/tcp").read_text().splitlines()[1:]:
            fields = line.split()
            if fields[1] == expected_address and fields[3] == "0A" and fields[9] in inodes:
                return True
    except (OSError, KeyError, IndexError):
        pass
    return False


def ready(base, record):
    if not matches_process(record, manager_argv(base)):
        return False
    host, port = runtime(base)
    child = record.get("child")
    expected = gunicorn_argv(base, Path(record["release"]), host, port)
    if not matches_process(child, expected) or not owns_listener(child, host, port):
        return False
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://{host}:{port}/healthz", timeout=1) as response:
            body = json.loads(response.read(4096))
        return body == {"status": "ok", "service": "operacion-condor"}
    except (OSError, ValueError):
        return False


def signal_owned_manager(base, record, sig):
    """pidfd pins process identity, preventing a reused PID from being signalled."""
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("Se requiere Linux con pidfd (Ubuntu Server 26.04 es compatible)")
    try:
        descriptor = os.pidfd_open(record["pid"])
    except ProcessLookupError:
        return
    try:
        if not matches_process(record, manager_argv(base)):
            raise RuntimeError("El PID no pertenece a este laboratorio; no se envió ninguna señal")
        signal.pidfd_send_signal(descriptor, sig)
    finally:
        os.close(descriptor)


def stop(base):
    record = read_record(base)
    if not record:
        print("Laboratorio detenido.")
        return
    if not matches_process(record, manager_argv(base)):
        # A stale record is safe to leave alone; never signal its current owner.
        print("No hay proceso propio activo; no se modificó ningún otro proceso.")
        return
    signal_owned_manager(base, record, signal.SIGTERM)
    deadline = time.monotonic() + 18
    while time.monotonic() < deadline:
        if not matches_process(record, manager_argv(base)):
            print("Laboratorio detenido.")
            return
        time.sleep(0.2)
    raise RuntimeError("El proceso propio no terminó; revisa run/service.log. No se detuvo ningún proceso ajeno")


def start(base):
    old_record = read_record(base)
    if ready(base, old_record):
        host, port = runtime(base)
        print(f"Laboratorio ya disponible en http://{host}:{port}/")
        return
    if matches_process(old_record, manager_argv(base)):
        raise RuntimeError("Existe un proceso propio sin readiness; revisa run/service.log o usa stop.sh")
    host, port = runtime(base)
    # A busy port causes a clean failure. Its owner is never inspected or killed.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as error:
            raise RuntimeError("La dirección/puerto no está disponible; no se detuvo ningún servicio existente") from error
    environment = private_environment(base)
    with (base / "run/service.log").open("ab") as output:
        launcher = subprocess.Popen(
            ["nohup", "flock", "-n", str(base / "run/service.lock"), *manager_argv(base)],
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            env=environment, start_new_session=True,
        )
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        record = read_record(base)
        if ready(base, record):
            print(f"Laboratorio disponible en http://{host}:{port}/")
            return
        if launcher.poll() is not None:
            break
        time.sleep(0.25)
    # Leave diagnostic logs; stop only the instance this launch actually created.
    record = read_record(base)
    if record != old_record and matches_process(record, manager_argv(base)):
        stop(base)
    raise RuntimeError("El laboratorio no superó /healthz; revisa run/service.log")


def serve(base):
    host, port = runtime(base)
    release = (base / "current").resolve(strict=True)
    expected_releases = (base / "releases").resolve(strict=True)
    if release.parent != expected_releases:
        raise RuntimeError("current debe apuntar a una release propia")
    stop_requested = False

    def request_stop(_signal, _frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    child = subprocess.Popen(gunicorn_argv(base, release, host, port))
    child_fd = None
    record = None
    try:
        child_fd = os.pidfd_open(child.pid)
        record = process_identity(os.getpid())
        child_identity = process_identity(child.pid)
        if not record or not child_identity:
            raise RuntimeError("El proceso propio terminó antes de registrarse")
        record.update(child=child_identity, release=str(release))
        write_record(base, record)
        while child.poll() is None and not stop_requested:
            time.sleep(0.2)
        if stop_requested and child.poll() is None:
            # This pidfd was captured immediately after spawning our child.
            signal.pidfd_send_signal(child_fd, signal.SIGTERM)
            try:
                child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                child.wait(timeout=3)
        return child.wait()
    finally:
        # Initialization failures also clean up the child we just spawned.
        if child.poll() is None:
            if child_fd is not None:
                signal.pidfd_send_signal(child_fd, signal.SIGTERM)
            else:
                child.terminate()
            try:
                child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                if child_fd is not None:
                    signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                else:
                    child.kill()
                child.wait(timeout=3)
        if child_fd is not None:
            os.close(child_fd)
        current_record = read_record(base)
        if record and current_record and current_record.get("pid") == os.getpid() and current_record.get("start_ticks") == record["start_ticks"]:
            (base / "run/manager.json").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "status", "serve", "init"))
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    base = args.base.resolve()
    try:
        if args.command == "start":
            start(base)
        elif args.command == "stop":
            stop(base)
        elif args.command == "status":
            if not ready(base, read_record(base)):
                raise RuntimeError("Laboratorio sin readiness")
            print("Laboratorio activo y verificado.")
        elif args.command == "init":
            if not args.release:
                raise RuntimeError("init requiere --release")
            subprocess.run(
                [str(base / "venv/bin/python"), "-m", "flask", "--app", "condor_app", "init-lab"],
                cwd=args.release, env=private_environment(base), check=True,
            )
        else:
            return serve(base)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        # Never print environment contents, password or flag.
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
