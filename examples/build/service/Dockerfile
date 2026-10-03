FROM python:3.12-slim
ARG PIP_INSTALL_OPTS=""
RUN pip install --no-cache-dir $PIP_INSTALL_OPTS tzdata
COPY server.py /app/server.py
ENV TZ=America/New_York
EXPOSE 8080
CMD ["python", "/app/server.py"]
