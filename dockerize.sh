#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="print-site"
RUN_CONTAINER=false
HOST_PORT=5000

usage() {
  cat <<USAGE
Usage: $0 [-t image_name] [--run] [--port host_port]

Options:
  -t, --tag IMAGE_NAME   Name to tag the built Docker image (default: print-site)
      --run              Start a container after building the image
      --port PORT        Host port to bind when running the container (default: 5000)
  -h, --help             Show this help message and exit

The container maps the local webroot directory into /webroot so that
content changes persist on the host.
USAGE
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--tag)
      IMAGE_NAME="$2"
      shift 2
      ;;
    --run)
      RUN_CONTAINER=true
      shift
      ;;
    --port)
      HOST_PORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not found in PATH. Please install Docker and try again." >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building Docker image '$IMAGE_NAME' from $PROJECT_ROOT..."
docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"

echo
if [[ "$RUN_CONTAINER" == true ]]; then
  echo "Starting container from image '$IMAGE_NAME'..."
  docker run --rm \
    -p "${HOST_PORT}:5000" \
    -v "${PROJECT_ROOT}/webroot:/webroot" \
    "$IMAGE_NAME"
else
  cat <<INFO
Docker image '$IMAGE_NAME' built successfully.

To run the container manually execute:
  docker run --rm \\
    -p ${HOST_PORT}:5000 \\
    -v "${PROJECT_ROOT}/webroot:/webroot" \\
    ${IMAGE_NAME}

Reset the admin password by appending "--clear-admin-password" to the run command, e.g.:
  docker run --rm \\
    -p ${HOST_PORT}:5000 \\
    -v "${PROJECT_ROOT}/webroot:/webroot" \\
    ${IMAGE_NAME} --clear-admin-password
INFO
fi
