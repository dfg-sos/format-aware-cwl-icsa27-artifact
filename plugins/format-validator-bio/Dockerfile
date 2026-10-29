# The file format service with this plugin installed: the service image unchanged, plus one package.
# Mappings are mounted at run time, as for the service image itself (README.md).
#   docker build -t file-format-service-eo-bio:0.2.0 plugins/format-validator-bio
ARG SERVICE_IMAGE=ghcr.io/dfg-sos/file-format-service:0.2.0
FROM ${SERVICE_IMAGE}
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/
COPY pyproject.toml /tmp/format-validator-bio/
COPY src /tmp/format-validator-bio/src
# Installs the dependencies declared in pyproject.toml. format-validator is already in the image and satisfies the
# requirement, so it stays as it is; --no-sources ignores the development source in pyproject.toml.
RUN uv pip install --python /opt/venv/bin/python --no-sources /tmp/format-validator-bio \
    && rm -rf /tmp/format-validator-bio /usr/local/bin/uv
