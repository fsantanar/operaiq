# OperaIQ - Tu Asistente Virtual de Operaciones

Esta herramienta es una demo funcional de una plataforma online que maneja el funcionamiento real de tu empresa. Usando una base de datos bien estructurada y calculos que aseguran consistencia, OperaIQ te permite fácilmente no solo registrar sino administrar de manera simple y centralizada las operaciones principales de tu empresa, optimizando tus recursos a través de un portal de uso intuitivo e interfaz amigable.


Diseñada para ser:
- ✅ Fácil de adaptar y entender.
- ✅ Reproducible en distintos entornos (Docker o sin Docker).
- ✅ Profesional desde el backend hasta la interfaz.
- ✅ Capaz de mostrar claramente habilidades de desarrollo, diseño y despliegue.

---

## 🚀 ¿Qué puede hacer esta herramienta?

- Planificar y registrar servicios o trabajos con múltiples componentes.
- Asignar trabajadores y materiales requeridos de forma automática o manual.
- Hacer seguimiento de avance, consumo de insumos y ejecución de HH.
- Consultar reportes operacionales, cargas de trabajo y balances financieros.
- Subir archivos, generar cotizaciones y revisar historiales.
- Visualizar la estructura de datos y analizar el rendimiento de operaciones.

---

## 📦 Instalación con Docker (recomendada)

### 1. Clona el repositorio:

```bash
git clone https://github.com/fsantanar/operaiq.git
cd operaiq
```

### 2. Instala Docker si no lo tienes

Primero actualiza el sistema con 

```bash
sudo apt update && sudo apt upgrade -y
```

Luego instala Docker con

```bash
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
```

Agrega tu usario al grupo docker

```bash
sudo usermod -aG docker $USER
```

Cierra sesión e inicia de nuevo para que se reflejen los cambios.

Y finalmente instala docker-compose con 

```bash
sudo apt install -y docker-compose
```

Para otros sistemas operativos sigue las instrucciones oficiales en:

- Docker: https://docs.docker.com/get-docker/

- Docker Compose: https://docs.docker.com/compose/install/

### 3. Crea el archivo .env.docker

Primero haz

```bash
cp .env.example .env.docker
```

Luego cambia los valores de parametros como DB_PASSWORD, DB_USER, DB_NAME de los valores genericos a los que quieras
usar para tu base de datos.

Luego asegurate que el valor de DB_HOST sea igual al del servicio en el archivo docker-compose.yml, como lo es actualmante
donde ambos son "db"

Cambia las claves a usar para clientes internos y externos por las que desees usar.

Descomenta las últimas líneas (bajo "Para el contenedor db") y asegurate que los valores de
nombre, usuario y clave de la base de datos sean consistentes con los parametros tipo "DB_"

### 4. Levanta la aplicación:

```bash
docker-compose up --build -d
```

### 5. Accede en el navegador

```arduino
http://localhost:8000
```

## 🧪 Uso sin Docker (modo desarrollo)

### 1. Requisitos:

- Python 3.11+

- PostgreSQL

Además asegurate de tener las dependencias necesarias de WEasyPrint

Por ejemplo en Ubuntu/Debian puedes hacer

```bash
sudo apt-get update && sudo apt-get install -y \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libcairo2 \
  libgdk-pixbuf2.0-0 \
  libffi-dev \
  libglib2.0-0 \
  libxml2 \
  libxslt1.1 \
  libjpeg-dev \
  zlib1g-dev
```

### 2. Crea una base de datos vacía, por ejemplo operaiq, y carga el archivo:

```bash
psql -U tu_usuario -d operaiq -f db_backup/operaiq.sql
```

### 3. Crea el archivo .env:

```bash
cp .env.example .env
```

Ajusta DB_HOST=localhost y las credenciales que usaste para PostgreSQL.

Elimina las últimas lineas usadas para docker (desde "Para el contenedor db" hacia abajo)

### 4. Instala dependencias y corre la app:

```bash
pip install -r requirements.txt
python app.py
```

## 🔐 Configuración del archivo .env
Tu aplicación usa variables de entorno para conectarse a la base de datos y definir credenciales de acceso.

El archivo .env.example incluido te muestra todas las claves necesarias. Según el entorno, debes:

✅ Usar .env.docker si corres con Docker (usa DB_HOST=db y los parámetros POSTGRES_).

✅ Usar .env si corres fuera de Docker (usa DB_HOST=localhost).

Nunca subas .env reales con claves productivas.

## 🧰 Tecnologías usadas
Python (Flask)

PostgreSQL

Docker y Docker Compose

Gunicorn

HTML + CSS

ReportLab / WeasyPrint (para PDF)

dotenv

## 📁 Estructura del proyecto
```arduino
.
├── app.py
├── Dockerfile
├── docker-compose.yml
├── routes/
├── templates/
├── static/
├── models/
├── db_backup/operaiq.sql
├── .env.docker
├── .env.example
└── README.md
```

## 🤝 Contribuciones
Este proyecto es parte de un desarrollo continuo. Si te interesa adaptarlo, mejorarlo o dar feedback, puedes abrir un issue o proponer un pull request.

## 📬 Contacto
Para más información, sugerencias o acceso a la demo en línea:

fsantanar@gmail.com

