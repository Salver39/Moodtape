#!/bin/bash

# Moodtape Bot - Production Testing Script
# Usage: ./run_tests.sh

set -e

echo "🎵 Moodtape Bot - Production Testing"
echo "======================================"
echo

# Check if we're in the right directory
if [[ ! -f "bot/main.py" ]]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "❌ Error: Python $required_version+ required, found $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Creating from env.example..."
    
    if [[ -f "env.example" ]]; then
        cp env.example .env
        echo "   Please edit .env with your API keys before running tests"
        echo
    else
        echo "❌ Error: env.example not found"
        exit 1
    fi
fi

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e .

# Install optional testing dependencies
echo "📦 Installing test dependencies..."
pip install --quiet psutil 2>/dev/null || echo "⚠️  psutil not available (optional)"

# Create data directory if it doesn't exist
if [[ ! -d "data" ]]; then
    echo "📁 Creating data directory..."
    mkdir -p data
fi

# Run production tests
echo
echo "🧪 Running production tests..."
echo "=============================="
python tests/test_production.py

test_exit_code=$?

echo
if [[ $test_exit_code -eq 0 ]]; then
    echo "🎉 All tests passed! Bot is ready for production deployment."
    echo
    echo "Next steps:"
    echo "1. Configure your .env file with real API keys"
    echo "2. Deploy using: docker-compose up -d"
    echo "3. Set up webhook: see Docs/deployment.md"
    echo
else
    echo "❌ Some tests failed. Please fix issues before deploying."
    echo "Check the test output above for details."
    echo
fi

exit $test_exit_code 