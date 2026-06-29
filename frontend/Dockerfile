FROM python:3.11-slim

WORKDIR /app

COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ ./frontend/

ENV PYTHONPATH=/app
EXPOSE 7860

CMD ["python", "frontend/app.py"]
