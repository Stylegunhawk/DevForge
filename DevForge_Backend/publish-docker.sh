#!/bin/bash
# =============================================================================
# Docker Hub Publishing Script
# =============================================================================
# This script builds, tags, and pushes your DevForge backend to Docker Hub
# Usage: ./publish-docker.sh [version]
# Example: ./publish-docker.sh 0.8.0
# =============================================================================

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
DOCKER_USERNAME="${DOCKER_USERNAME:-stylegunhawk}"  # Change to your Docker Hub username
IMAGE_NAME="devforge-backend"
VERSION="${1:-latest}"

# Functions
print_header() {
    echo -e "${BLUE}=================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Main script
print_header "DevForge Backend - Docker Hub Publisher"

echo "Configuration:"
echo "  Docker Hub Username: $DOCKER_USERNAME"
echo "  Image Name: $IMAGE_NAME"
echo "  Version: $VERSION"
echo ""

# Confirm
read -p "Continue with these settings? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Step 1: Check Docker login
print_header "Step 1: Checking Docker Login"
if docker info | grep -q "Username: $DOCKER_USERNAME"; then
    print_success "Already logged in as $DOCKER_USERNAME"
else
    print_warning "Not logged in. Please login to Docker Hub..."
    docker login
fi

# Step 2: Build the image
print_header "Step 2: Building Docker Image"

echo "Which Dockerfile to use?"
echo "  1) Dockerfile (development - default)"
echo "  2) Dockerfile.prod (production - recommended)"
read -p "Enter choice (1 or 2): " -n 1 -r DOCKERFILE_CHOICE
echo

if [[ $DOCKERFILE_CHOICE == "2" ]]; then
    DOCKERFILE="Dockerfile.prod"
    print_success "Using production Dockerfile"
else
    DOCKERFILE="Dockerfile"
    print_success "Using development Dockerfile"
fi

echo "Building image..."
docker build -f $DOCKERFILE -t ${IMAGE_NAME}:${VERSION} .

print_success "Image built: ${IMAGE_NAME}:${VERSION}"

# Step 3: Test the image
print_header "Step 3: Testing Image"

echo "Starting test container..."
docker run -d \
    --name devforge-test \
    -p 8002:8001 \
    -e PORT=8001 \
    ${IMAGE_NAME}:${VERSION}

echo "Waiting for container to start..."
sleep 5

# Health check
if curl -sf http://localhost:8002/health > /dev/null; then
    print_success "Health check passed!"
else
    print_error "Health check failed!"
    docker logs devforge-test
    docker stop devforge-test >/dev/null 2>&1
    docker rm devforge-test >/dev/null 2>&1
    exit 1
fi

# Cleanup test container
docker stop devforge-test >/dev/null 2>&1
docker rm devforge-test >/dev/null 2>&1
print_success "Test completed and cleaned up"

# Step 4: Tag for Docker Hub
print_header "Step 4: Tagging Images"

# Tag with version
docker tag ${IMAGE_NAME}:${VERSION} ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}
print_success "Tagged: ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

# Tag as latest if version is not 'latest'
if [[ "$VERSION" != "latest" ]]; then
    docker tag ${IMAGE_NAME}:${VERSION} ${DOCKER_USERNAME}/${IMAGE_NAME}:latest
    print_success "Tagged: ${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
fi

# Step 5: Push to Docker Hub
print_header "Step 5: Pushing to Docker Hub"

echo "This will push the following images:"
echo "  - ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
if [[ "$VERSION" != "latest" ]]; then
    echo "  - ${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
fi
echo ""

read -p "Push to Docker Hub? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Skipped pushing to Docker Hub."
    exit 0
fi

# Push version tag
echo "Pushing ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}..."
docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}
print_success "Pushed version tag"

# Push latest tag
if [[ "$VERSION" != "latest" ]]; then
    echo "Pushing ${DOCKER_USERNAME}/${IMAGE_NAME}:latest..."
    docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:latest
    print_success "Pushed latest tag"
fi

# Success!
print_header "✅ Publishing Complete!"

echo ""
echo "Your image is now available at:"
echo "  https://hub.docker.com/r/${DOCKER_USERNAME}/${IMAGE_NAME}"
echo ""
echo "Pull with:"
echo "  docker pull ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""
echo "Run with:"
echo "  docker run -d -p 8001:8001 \\"
echo "    -e OLLAMA_HOST=http://host.docker.internal:11434 \\"
echo "    ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""
print_success "Done! 🎉"
