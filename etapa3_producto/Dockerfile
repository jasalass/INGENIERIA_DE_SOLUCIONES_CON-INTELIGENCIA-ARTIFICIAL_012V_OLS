FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY etapa3_producto/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY etapa3_producto /app/etapa3_producto
COPY etapa2_rag /app/etapa2_rag
COPY etapa1_datos/data/processed/chunks.json /app/etapa1_datos/data/processed/chunks.json
COPY docs/Ley-21719_13-DIC-2024.pdf /app/docs/Ley-21719_13-DIC-2024.pdf
RUN mkdir -p /app/docs/evidencia_local && chown appuser:appuser /app/docs/evidencia_local
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "etapa3_producto.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
