FROM python:3.12-alpine

RUN pip install --no-cache-dir flask

WORKDIR /app
COPY NN-Manager.py .

VOLUME ["/data"]

# Web UI
EXPOSE 8080
# Syslog UDP (use 5514 if not running as root)
EXPOSE 514/udp

ENV DB_PATH=/data/ninja.db
ENV WEB_PORT=8080
ENV SYSLOG_PORT=514

CMD ["python", "NN-Manager.py"]
