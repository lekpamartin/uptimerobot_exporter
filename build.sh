#!/usr/bin/env bash
#
# Build the image and push it to Docker Hub:
#   docker login
#   ./build.sh 1.2.3 push
#
# Without "push", the image is only built for the local platform and loaded
# into the local docker images.

usage() {
  cat <<EOF
Usage: $0 [TAG] [push]

  TAG    image tag (default: latest)
  push   build for all platforms and push ${IMAGE_NAME}:TAG to Docker Hub

Environment variables:
  IMAGE_NAME  image name (default: lekpamartin/uptimerobot_exporter)
  PLATFORMS   platforms to push (default: linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64)
  DOCKERFILE  Dockerfile to use (default: Dockerfile)
EOF
}

set -euo pipefail

cd "$(readlink -f "$(dirname "$0")")"

IMAGE_NAME="${IMAGE_NAME:-lekpamartin/uptimerobot_exporter}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"

case "${1:-}" in
  help | h | --help | -h)
    usage
    exit 0
    ;;
esac

TAG="${1:-latest}"
PUSH="${2:-}"

BUILD_ARGS=(
  --file "$DOCKERFILE"
  --tag "${IMAGE_NAME}:${TAG}"
  --label "org.opencontainers.image.version=${TAG}"
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
)

case "$PUSH" in
  push | p | --push | -p)
    # Multi-platform images cannot be loaded locally then pushed with
    # `docker push`, buildx builds and pushes the multi-platform manifest at once
    BUILD_ARGS+=(--platform "$PLATFORMS" --push)
    ;;
  "")
    BUILD_ARGS+=(--load)
    ;;
  *)
    usage
    exit 1
    ;;
esac

set -x
docker buildx build "${BUILD_ARGS[@]}" .
