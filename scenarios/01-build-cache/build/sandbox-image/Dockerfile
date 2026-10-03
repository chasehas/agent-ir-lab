# Kestrel's agent sandbox image: Python plus pytest.
FROM python:3.12-slim
# Extra pip options, e.g. --trusted-host flags behind a TLS-intercepting proxy.
ARG PIP_INSTALL_OPTS=""
RUN pip install --no-cache-dir $PIP_INSTALL_OPTS "pytest==8.3.*"
WORKDIR /repo
