FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    git \
    libglib2.0-0 \
    libgomp1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip dan setuptools — pkg_resources dibutuhkan face_recognition_models
RUN pip install --no-cache-dir --upgrade pip setuptools==69.5.1

# Heavy dependencies — dlib, face-recognition, opencv (jarang berubah)
COPY requirements-base.txt .
RUN MAKEFLAGS="-j2" pip install --no-cache-dir --default-timeout=300 -r requirements-base.txt

# Light dependencies — flask, gunicorn, dll (sering berubah)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

RUN mkdir -p uploads/faces uploads/kegiatan

EXPOSE 5001

ENTRYPOINT ["./entrypoint.sh"]
