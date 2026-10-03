# Kestrel's internal exchange-rates service (a stand-in for the lab).
FROM python:3.12-slim
# Extra pip options, e.g. --trusted-host flags behind a TLS-intercepting proxy.
ARG PIP_INSTALL_OPTS=""
RUN pip install --no-cache-dir $PIP_INSTALL_OPTS tzdata
COPY server.py /app/server.py
ENV TZ=America/New_York
EXPOSE 8080
CMD ["python", "/app/server.py"]
