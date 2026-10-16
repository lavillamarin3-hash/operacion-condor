# Comprobaciones de entrega

Validado el 16 de octubre de 2026 con Ubuntu 26.04 y Python 3.14 en un contenedor de prueba, separado de las VMs y de los datos de Cociber CTF.

- 11 pruebas de aplicación aprobadas: acceso, sesiones, CSRF, permisos, inicialización idempotente, escape HTML, rechazo de Host y entrega de flag después de publicar.
- 4 pruebas de parámetros de red aprobadas: redes RFC1918, rechazo de direcciones públicas y entradas no válidas.
- `bash -n deploy/install.sh`, `--help` y `--validate-only` aprobados.
- Comprobación HTTP real con Gunicorn sin privilegios: Nmap detectó el puerto; Hydra encontró la cuenta de práctica usando las 12 candidatas; una sesión real publicó un comunicado y recibió la flag; la portada mostró el comunicado y no reveló la flag.
- La plantilla Nginx del instalador pasó `nginx -t`; se verificaron proxy HTTP, respuesta 200 desde la dirección permitida y 403 desde una excluida en una prueba de loopback.
- Portada, noticias, acceso y panel revisados en el navegador.

Para repetir las pruebas de aplicación y parámetros desde el paquete extraído:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s deploy -v
bash -n deploy/install.sh
```

La prueba en contenedor no arranca una VM Ubuntu con systemd como PID 1. La instalación completa del servicio y su arranque después de reiniciar deben verificarse en la VM con los comandos de la guía. Este paquete todavía no se ha instalado en tu VM Ubuntu ni está integrado automáticamente con el inicio de retos o el puntaje de Cociber CTF.
