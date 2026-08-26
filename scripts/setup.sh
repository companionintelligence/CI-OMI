#!/bin/bash

# Omi Companion Setup Script
# Sets up the development environment and installs dependencies

set -e

echo "🚀 Setting up Omi Companion Capture App..."

# Check if Python 3.8+ is available
python_version=$(python3 --version 2>&1 | cut -d" " -f2 | cut -d"." -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📥 Installing Python dependencies..."
cd backend
pip install -r requirements.txt
cd ..

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/{events,audio_samples,face_embeddings,logs}

# Generate an API key if one was not supplied. The backend refuses every
# endpoint except /health until this is set, so a blank value would leave a
# fresh install unusable.
if [ -z "$OMI_COMPANION_API_KEY" ]; then
    OMI_COMPANION_API_KEY=$(openssl rand -hex 32 2>/dev/null \
        || python3 -c "import secrets; print(secrets.token_hex(32))")
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cat > .env << EOF
# API Authentication (REQUIRED)
# Clients must send this as the X-API-Key header. Rotate by editing this file
# and restarting the service.
OMI_COMPANION_API_KEY=$OMI_COMPANION_API_KEY

# Ollama Configuration
OLLAMA_URL=http://localhost:11434
OLLAMA_VISION_MODEL=moondream:1.8b-v2-fp16
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=30

# BLE Configuration
BLE_DEVICE_NAME=Omi
BLE_SCAN_TIMEOUT=10
BLE_CONNECTION_TIMEOUT=10

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
WHISPER_MODEL=base

# Video Configuration
VIDEO_FPS=10
VIDEO_WIDTH=640
VIDEO_HEIGHT=480

# AI Feature Toggles
ENABLE_FACE_RECOGNITION=true
ENABLE_OBJECT_DETECTION=true
ENABLE_OCR=true
ENABLE_GESTURE_DETECTION=true
ENABLE_EMOTION_ANALYSIS=true

# Confidence Thresholds
CONFIDENCE_THRESHOLD=0.7
FACE_RECOGNITION_THRESHOLD=0.8
OBJECT_DETECTION_THRESHOLD=0.6

# Storage Configuration
DATABASE_PATH=data/events.db
JSON_BACKUP_PATH=data/events_backup.json
FACE_DB_PATH=data/face_embeddings.json

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/logs/omi_companion.log
EOF
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# Check if Ollama is installed
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama server is running"
        
        # Pull required models
        echo "📥 Pulling Ollama models..."
        ollama pull llama3.2:3b
        ollama pull moondream:1.8b-v2-fp16
        echo "✅ Ollama models installed"
    else
        echo "⚠️  Ollama server is not running. Start it with 'ollama serve'"
    fi
else
    echo "⚠️  Ollama not found. Please install it from https://ollama.ai"
fi

# Create run script
echo "📝 Creating run script..."
cat > run.sh << 'EOF'
#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Run the application
echo "🚀 Starting Omi Companion Capture App..."
cd backend
python main.py
EOF

chmod +x run.sh

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the application:"
echo "  ./run.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  export PYTHONPATH=\$PYTHONPATH:\$(pwd)/backend"
echo "  cd backend && python main.py"
echo ""
echo "The API will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo ""
echo "Make sure Ollama is running: ollama serve"
echo ""
