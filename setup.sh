#!/bin/bash

# Docker Update Orchestrator - Quick Setup Script
# This script helps you get started quickly

set -e

echo "====================================="
echo "Docker Update Orchestrator Setup"
echo "====================================="
echo ""

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your API keys:"
    echo "   - ANTHROPIC_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY"
    echo "   - Or install Ollama for local LLM (free)"
    echo ""
    read -p "Press enter to continue after editing .env..."
else
    echo "✅ .env file already exists"
fi

echo ""

# Check SSH keys
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "⚠️  No SSH key found at ~/.ssh/id_rsa"
    echo "   You'll need SSH access to your Docker servers."
    echo ""
    read -p "Do you want to generate an SSH key? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
        echo "✅ SSH key generated"
        echo ""
        echo "📋 Copy this public key to your Docker servers:"
        echo ""
        cat ~/.ssh/id_rsa.pub
        echo ""
        read -p "Press enter to continue after copying the key..."
    fi
else
    echo "✅ SSH key found"
fi

echo ""

# Create directories
echo "📁 Creating necessary directories..."
mkdir -p backend/app/api
mkdir -p backend/app/core
mkdir -p backend/app/models
mkdir -p backend/app/services
mkdir -p backend/app/tasks
mkdir -p frontend/src/components
mkdir -p frontend/src/pages
mkdir -p frontend/public
mkdir -p docs
mkdir -p logs

echo "✅ Directories created"
echo ""

# Build and start containers
echo "🐳 Building Docker containers..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services are running!"
else
    echo "❌ Some services failed to start. Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "====================================="
echo "Setup Complete! 🎉"
echo "====================================="
echo ""
echo "📊 Access points:"
echo "   - Dashboard:    http://localhost:3000"
echo "   - API:          http://localhost:8000"
echo "   - API Docs:     http://localhost:8000/docs"
echo "   - Flower:       http://localhost:5555"
echo ""
echo "📝 Next steps:"
echo "   1. Open http://localhost:3000"
echo "   2. Go to 'Servers' page"
echo "   3. Add your Docker servers"
echo "   4. Click 'Scan All Servers' to discover containers"
echo "   5. Click 'Check for Updates' to find available updates"
echo ""
echo "📚 Documentation:"
echo "   - README.md for full documentation"
echo "   - .env for configuration options"
echo ""
echo "🔍 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "Happy updating! 🐳"
