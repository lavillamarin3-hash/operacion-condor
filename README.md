# Operación Cóndor · Cociber CTF

Un portal militar ficticio para resolver el reto **Fuerza bruta de credenciales web**. El estudiante descubre el servicio, encuentra el usuario, prueba un diccionario pequeño e ingresa al centro de mando. Publicar un comunicado confirma el logro y muestra la flag. La portada refleja el cambio.

**Simulación académica:** la unidad, las personas, el escudo, las noticias y los datos son inventados. No representa un sistema real del Ejército ecuatoriano. El único objetivo permitido del ejercicio es la VM del laboratorio indicada por el instructor.

## Empezar

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

## Qué incluye

- Portada, noticias, acceso de personal y panel de administrador.
- Una cuenta de práctica `admin.condor`; su contraseña se elige aleatoriamente entre las 12 candidatas del ejercicio durante la primera instalación.
- Login deliberadamente sin límite de intentos, CAPTCHA ni token CSRF, para practicar con un cliente HTTP y el diccionario pequeño del ejercicio. La contraseña débil y estas excepciones están limitadas al laboratorio; no se usan para SSH ni para las cuentas del sistema operativo.
- El resto del ejercicio usa contraseñas con hash, consultas SQL parametrizadas, sesiones firmadas, validación del rol, escape HTML y protección CSRF en las acciones del administrador.
- Flag y clave de sesión aleatorias, fuera del código; los secretos no se imprimen durante la instalación.
- Gunicorn como usuario sin privilegios, Nginx con acceso limitado a la subred elegida y datos SQLite conservados al actualizar.

## Organización MVC

```text
operacion-condor/
├── condor_app/
│   ├── __init__.py           # Factoría Flask y registro de controladores
│   ├── config.py            # Configuración desde el entorno
│   ├── db.py                # Conexiones SQLite
│   ├── models/              # Usuarios, comunicados y estado del reto
│   ├── controllers/         # Rutas públicas, autenticación y administración
│   ├── services/            # Reglas de autenticación, seguridad e inicialización
│   └── views/
│       ├── templates/       # Páginas Jinja
│       └── static/          # CSS, escudo e ilustración local
├── resources/candidatas.txt # Diccionario educativo de 12 palabras
├── deploy/install.sh        # Instalador nativo Ubuntu 26.04
├── deploy/validate_config.py
├── tests/                   # Pruebas del comportamiento y controles
├── requirements.txt        # Dependencias con versión fijada
└── GUIA_UBUNTU_26_04.md
```

En el servidor, `/opt/condor-lab` contiene el código propiedad de root, `/var/lib/condor-lab` la base de datos y `/etc/condor-lab/condor.env` los secretos con permisos `600`. El navegador accede a la IP privada en el puerto `8080`; Gunicorn escucha únicamente en `127.0.0.1:18080`.

## Alcance

Este repositorio es un laboratorio independiente. Su uso con la [plataforma Cociber CTF](https://github.com/lavillamarin3-hash/ctf-platform) es opcional. Abrirlo desde Cociber CTF puede hacerse mediante un enlace al portal; **no crea VMs ni asigna puntos automáticamente** en la plataforma. Para puntuar, el instructor puede crear un reto en Cociber CTF y registrar la flag de esta instalación, manteniéndola fuera de las instrucciones del estudiante.

Usa una instancia por grupo: sus integrantes comparten la misma cuenta, el comunicado y la flag. Las sesiones y objetivos separados por estudiante requieren una integración adicional.

Consulta las [comprobaciones realizadas y sus límites](VALIDACION.md) y el [origen de la imagen y del escudo](ASSETS.md).

El entorno está pensado para una red privada NAT o solo anfitrión, sin redirección de puertos hacia Internet. Si la VM está en la misma subred privada que otros equipos, esos equipos también pueden acceder de acuerdo con el CIDR configurado.

## Fuentes de instalación

El entorno Python sigue la recomendación de [Ubuntu de usar `venv`](https://documentation.ubuntu.com/ubuntu-for-developers/tutorials/python-use/). El servicio usa [Gunicorn para desplegar Flask](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) y las reglas [`allow` / `deny` de Nginx](https://nginx.org/en/docs/http/ngx_http_access_module.html) para limitar el acceso por red.
