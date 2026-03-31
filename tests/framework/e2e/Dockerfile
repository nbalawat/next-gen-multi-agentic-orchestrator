FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    git curl jq bash \
    && rm -rf /var/lib/apt/lists/*

# Python test dependencies
COPY pyproject.toml /opt/rapids/pyproject.toml
COPY src/ /opt/rapids/src/
RUN pip install -e "/opt/rapids[dev]"

# Copy RAPIDS framework (the plugin being tested)
COPY rapids-core/ /opt/rapids/rapids-core/
COPY tests/ /opt/rapids/tests/

# Copy E2E runner
COPY tests/framework/e2e/run_e2e.sh /usr/local/bin/rapids-e2e
RUN chmod +x /usr/local/bin/rapids-e2e

# Environment
ENV RAPIDS_FRAMEWORK_ROOT="/opt/rapids"
ENV PYTHONPATH="/opt/rapids/src"
ENV RAPIDS_E2E_MODE="true"

WORKDIR /workspace

ENTRYPOINT ["rapids-e2e"]
CMD ["tier2-todo-enhancement"]
