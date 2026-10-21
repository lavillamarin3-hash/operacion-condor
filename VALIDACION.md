# Comprobaciones de entrega

Revisión final del **21 de octubre de 2026**. Las pruebas automatizadas se ejecutan con una base SQLite temporal, separadas de las VMs y de los datos de Cociber CTF.

- **16 pruebas de aplicación aprobadas:** autenticación, sesiones, CSRF, inicialización idempotente, escape HTML, rechazo de Host y flag únicamente después de publicar en la sesión autorizada.
- Incluyen la cadena de reconocimiento `robots.txt` → manifiesto → cuentas/bitácora, la deducción única por perfil y último estado, los señuelos, el diccionario configurado y los intentos HTTP acotados. No requieren que el HTML publique una cuenta o un enlace al diccionario.
- **9 pruebas de despliegue aprobadas:** validación de redes privadas, direcciones no válidas y red cliente en otra VLAN; controles de procesos propios mediante UID, argumentos e identidad de inicio; rechazo de un archivo de secretos con permisos abiertos y de un listener ajeno.
- Las pruebas de proceso son verificaciones de seguridad del controlador; no sustituyen una instalación de Gunicorn en Ubuntu. La prueba de aplicación usa el cliente HTTP de Flask, sin un escaneo Nmap ni una ejecución real de Hydra en esta revisión.

La entrega original del 16 de octubre registró comprobaciones en un contenedor Ubuntu 26.04 con Python 3.14, Gunicorn, Nmap, Hydra y Nginx, además de una revisión visual. Aquellas pruebas preceden la nueva cadena de reconocimiento y no prueban el despliegue actual en una VM.

Para repetir las pruebas de aplicación y despliegue desde el repositorio:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s deploy -v
bash -n deploy/install.sh
sh -n deploy/install-user.sh
```

La comprobación de sintaxis de shell debe ejecutarse en Linux. En esta revisión no se inició systemd, no se instaló el paquete en una víctima y no se efectuó una prueba de red entre VLANs. El inicio real, la conectividad y el arranque después de reiniciar se verifican en la VM con los comandos de la guía correspondiente.

Consulta la [guía genérica de Ubuntu](GUIA_UBUNTU_26_04.md) y la [guía de LAB-SRVWEB](GUIA_LAB_SRVWEB.md). Ninguna de estas comprobaciones acredita por sí misma que el sitio ya esté instalado en LAB-SRVWEB. La integración automática con la creación de VMs y el puntaje de Cociber CTF es un trabajo separado.
