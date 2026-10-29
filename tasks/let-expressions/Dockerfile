# Environment for this task: CPython 3.13 and a pinned pytest, nothing else.
# The library under test has no dependencies of its own. The base image is
# pinned by digest, so a rebuild gets the same interpreter.
FROM python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir \
    pytest==8.4.1 iniconfig==2.1.0 pluggy==1.6.0 packaging==25.0 pygments==2.19.2

# Tests run as an unprivileged user. The harness mounts the tree read-only
# at /work and starts the container with --network none.
RUN useradd --create-home --uid 10001 runner
USER runner
WORKDIR /work
