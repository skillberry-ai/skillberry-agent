# syntax=docker/dockerfile:1.3
FROM python:3.11

# Define build arguments
ARG BUILD_VERSION=latest
ARG BUILD_DATE
ENV BUILD_VERSION=$BUILD_VERSION
ENV BUILD_DATE=$BUILD_DATE

# Set the working directory
WORKDIR /app

# Copy the application
COPY . .
RUN --mount=type=ssh \
    mkdir -p /root/.ssh && \
    ssh-keyscan github.ibm.com >> /root/.ssh/known_hosts && \
    pip install --no-cache-dir -e .

# Expose a port
EXPOSE 7000 7001

# Set the entrypoint command
CMD sh -c 'echo "Starting skillberry tools-agent (version $BUILD_VERSION built on $BUILD_DATE)" && echo "" && python main.py'


