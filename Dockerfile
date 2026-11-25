# syntax=docker/dockerfile:1
# Pin the exact image digest through PYTHON_IMAGE in release build infrastructure.
# Tag + complete Python package versions here; no production/image publication.
ARG PYTHON_IMAGE=python:3.12.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS wheels
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 SOURCE_DATE_EPOCH=1795478400
WORKDIR /source
COPY deploy/container-requirements.txt /tmp/requirements.txt
RUN python -m pip wheel --wheel-dir /wheels -r /tmp/requirements.txt && python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --no-build-isolation --no-deps --wheel-dir /wheels .
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=wheels /wheels /wheels
COPY deploy/container-requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.txt knowledge-sdk==1.2.0 && rm -rf /wheels /tmp/requirements.txt && mkdir /data && chown 65532:65532 /data
USER 65532:65532
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/v1/ready',timeout=3).close()"]
ENTRYPOINT ["python","-m","knowledge_sdk.server.container"]
