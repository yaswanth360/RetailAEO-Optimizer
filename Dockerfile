FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
EXPOSE 8000
# Mount your product.yaml and .env into /app, e.g.:
#   docker run -p 8000:8000 -v $PWD/product.yaml:/app/product.yaml --env-file .env surfaced
CMD ["surfaced", "serve", "--host", "0.0.0.0"]
