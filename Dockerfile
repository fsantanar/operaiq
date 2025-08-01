FROM python:3.12-slim

WORKDIR /app

COPY . /app

# Instalar dependencias del sistema necesarias para WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    libjpeg-dev \
    zlib1g-dev \
    && apt-get clean

RUN pip install --upgrade pip wheel

RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "--worker-class=gthread", "--threads=4", "-w", "1", "-b", "0.0.0.0:8000", "--timeout", "120", "app:app"]
