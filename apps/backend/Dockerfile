FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /repo/requirements.txt
RUN pip install --no-cache-dir -r /repo/requirements.txt

COPY . /repo
WORKDIR /repo
CMD ["python", "-m", "uvicorn", "apps.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
