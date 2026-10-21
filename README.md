# Operación Cóndor · Cociber CTF

Un portal militar ficticio para resolver el reto **Fuerza bruta de credenciales web**. Desde la terminal SSH de Kali, el estudiante descubre el servicio y los respaldos expuestos, correlaciona cuentas con su bitácora y prueba un diccionario pequeño contra el login HTTP. Publicar un comunicado después de autenticarse confirma el logro y muestra la flag. La portada refleja el cambio.

**Simulación académica:** la unidad, las personas, el escudo, las noticias y los datos son inventados. No representa un sistema real del Ejército ecuatoriano. El único objetivo permitido del ejercicio es la VM del laboratorio indicada por el instructor.

## Empezar

Para la VM **LAB-SRVWEB `10.10.30.20/24`**, con Kali en **VLAN 20 `10.10.20.0/24`**, utiliza la [guía específica de LAB-SRVWEB](GUIA_LAB_SRVWEB.md). Las dos redes requieren el enrutamiento y las reglas de acceso indicados allí. La existencia de esa guía no confirma que la página ya esté instalada en esa VM.

El siguiente ejemplo genérico utiliza dos VMs de la misma subred privada y una instalación con permisos administrativos:

1. Prepara una VM **Ubuntu Server 26.04** y Kali en la misma red privada del laboratorio.
2. Obtén este repositorio en Ubuntu, con Git instalado:

```bash
git clone --depth 1 https://github.com/lavillamarin3-hash/operacion-condor.git
cd operacion-condor
```

3. Ejecuta, reemplazando ambas direcciones por las de tu laboratorio:

```bash
sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24
```

4. Abre `http://192.168.146.150:8080/` desde Kali o desde un equipo de esa subred.

La [guía de Ubuntu paso a paso](GUIA_UBUNTU_26_04.md) incluye la instalación desde este repositorio, la transferencia alternativa del paquete desde Windows, el diagnóstico y la resolución desde Kali. Este repositorio instala únicamente Operación Cóndor.

También existe [una instalación opcional sin sudo](GUIA_UBUNTU_26_04.md#3b-instalación-opcional-con-usuario-normal): `deploy/install-user.sh` usa `~/.ctf-condor`, un archivo privado preparado previamente y Gunicorn directo en una IP privada, por defecto en el puerto `18083`. No instala Nginx ni un servicio systemd, no configura el firewall y no se inicia automáticamente después de reiniciar.

## Qué incluye

- Portada, noticias, acceso de personal y panel de administrador.
- Una cuenta de práctica configurable mediante `CONDOR_ADMIN_USERNAME`; se descubre correlacionando artefactos HTTP, no leyendo las noticias. Su contraseña pertenece al pequeño diccionario de la instalación.
- Reconocimiento por comandos: `robots.txt` → manifiesto → cuentas CSV y bitácora JSON → identificación del único editor activo → diccionario → fuerza bruta HTTP. Los registros históricos y otras cuentas funcionan como señuelos.
- Portada, noticias y formulario de acceso sin credenciales, enlace al diccionario ni respuesta directa del reto. Los respaldos son una exposición deliberada del laboratorio; `robots.txt` no constituye una protección de acceso.
- Login deliberadamente sin límite de intentos, CAPTCHA ni token CSRF, para practicar con un cliente HTTP y el diccionario pequeño del ejercicio. La contraseña débil y estas excepciones están limitadas al laboratorio; no se usan para SSH ni para las cuentas del sistema operativo.
- El resto del ejercicio usa contraseñas con hash, consultas SQL parametrizadas, sesiones firmadas, validación del rol, escape HTML y protección CSRF en las acciones del administrador.
- Flag y clave de sesión aleatorias, fuera del código; los secretos no se imprimen durante la instalación.
- Dos formas de despliegue: instalación administrativa con Gunicorn, Nginx y systemd; o instalación con usuario normal y procesos propios. Ambas conservan SQLite al actualizar.

## Organización MVC

```text
operacion-condor/
├── condor_app/
│   ├── __init__.py           # Factoría Flask y registro de controladores
│   ├── config.py            # Configuración desde el entorno
│   ├── db.py                # Conexiones SQLite
│   ├── models/              # Usuarios, comunicados y estado del reto
│   ├── controllers/         # Rutas públicas, autenticación y administración
│   ├── services/            # Autenticación, reconocimiento, seguridad e inicialización
│   └── views/
│       ├── templates/       # Páginas Jinja
│       └── static/          # CSS, escudo e ilustración local
├── resources/candidatas.txt # Diccionario educativo de 12 palabras
├── deploy/install.sh        # Instalador nativo Ubuntu 26.04
├── deploy/install-user.sh   # Instalador opcional sin sudo
├── deploy/user_service.py   # Inicio/parada/readiness de procesos propios
├── deploy/validate_config.py
├── tests/                   # Pruebas del comportamiento y controles
├── requirements.txt        # Dependencias con versión fijada
└── GUIA_UBUNTU_26_04.md
```

Con el instalador administrativo, `/opt/condor-lab` contiene el código propiedad de root, `/var/lib/condor-lab` la base de datos y `/etc/condor-lab/condor.env` los secretos con permisos `600`. El navegador accede a la IP privada en el puerto `8080`; Gunicorn escucha únicamente en `127.0.0.1:18080`.

Con el instalador de usuario, los secretos están en `~/.ctf-condor/condor.env`, los datos en la ruta privada configurada, y el código en releases bajo `~/.ctf-condor/releases`. Se controla exclusivamente con `start.sh`, `stop.sh` y `status.sh` de ese directorio. No mezcles los archivos de datos o secretos de ambas modalidades.

## Alcance

Este repositorio es un laboratorio independiente. Su uso con la [plataforma Cociber CTF](https://github.com/lavillamarin3-hash/ctf-platform) es opcional. Abrirlo desde Cociber CTF puede hacerse mediante un enlace al portal; **no crea VMs ni asigna puntos automáticamente** en la plataforma. Para puntuar, el instructor puede crear un reto en Cociber CTF y registrar la flag de esta instalación, manteniéndola fuera de las instrucciones del estudiante.

Usa una instancia por grupo: sus integrantes comparten la misma cuenta, el comunicado y la flag. Las sesiones y objetivos separados por estudiante requieren una integración adicional.

Consulta las [comprobaciones realizadas y sus límites](VALIDACION.md) y el [origen de la imagen y del escudo](ASSETS.md).

El entorno está pensado para una red privada NAT o solo anfitrión, sin redirección de puertos hacia Internet. Si la VM está en la misma subred privada que otros equipos, esos equipos también pueden acceder de acuerdo con el CIDR configurado.

## Fuentes de instalación

El entorno Python sigue la recomendación de [Ubuntu de usar `venv`](https://documentation.ubuntu.com/ubuntu-for-developers/tutorials/python-use/). El servicio usa [Gunicorn para desplegar Flask](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) y las reglas [`allow` / `deny` de Nginx](https://nginx.org/en/docs/http/ngx_http_access_module.html) para limitar el acceso por red.
