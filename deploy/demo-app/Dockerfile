FROM python:3.12-alpine

RUN adduser -D -H -u 10001 appuser
WORKDIR /app
COPY app/main.py /app/main.py
USER appuser

EXPOSE 8080
ENTRYPOINT ["python", "/app/main.py"]
