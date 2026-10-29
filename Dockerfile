FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 --create-home phantom
COPY --chown=phantom:phantom . .
RUN mkdir -p /app/data && chown -R phantom:phantom /app
USER phantom
EXPOSE 8000
CMD ["python", "app.py"]
