FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/service.db
WORKDIR /workspace
COPY app ./app
COPY data ./data
RUN mkdir /data && chown -R 10001:10001 /workspace /data
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=2)"
CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]
