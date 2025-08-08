# Running the Omi Companion Capture App

This guide will help you set up and run the Omi Companion Capture App, a multi-modal AI system for omiGlass & DevKit 2.

## Prerequisites

### System Requirements
- **OS**: macOS, Linux, or Windows (Linux recommended)
- **Python**: 3.8 or higher
- **RAM**: 8GB+ (16GB recommended)
- **Storage**: 10GB+ free space
- **Network**: Local network access for device connectivity

### Hardware Requirements
- **Omi DevKit 2**: For audio capture and BLE communication
- **omiGlass DevKit**: For camera/video capture (optional)
- **Companion PC**: For running the backend server

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd ci-capture-omi

# Run the setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2. Install Ollama (Required for AI features)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve

# In a new terminal, pull required models
ollama pull llama3.2:3b
ollama pull moondream:1.8b-v2-fp16
```

### 3. Run the Application

```bash
# Activate virtual environment and run
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
cd backend
python main.py
```

Or use the provided run script:
```bash
./run.sh
```

## Detailed Setup Instructions

### Step 1: Environment Setup

1. **Check Python Version**
   ```bash
   python3 --version  # Should be 3.8+
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   cd ..
   ```

### Step 2: Configuration

1. **Environment Variables**
   The setup script creates a `.env` file with default settings. You can modify it:

   ```bash
   # Edit .env file
   nano .env
   ```

   Key settings:
   ```env
   # Ollama Configuration
   OLLAMA_URL=http://localhost:11434
   OLLAMA_VISION_MODEL=moondream:1.8b-v2-fp16
   OLLAMA_CHAT_MODEL=llama3.2:3b
   
   # BLE Configuration
   BLE_DEVICE_NAME=Omi
   BLE_SCAN_TIMEOUT=10
   
   # Audio Configuration
   AUDIO_SAMPLE_RATE=16000
   AUDIO_CHANNELS=1
   
   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8000
   ```

2. **Create Data Directories**
   ```bash
   mkdir -p data/{events,audio_samples,face_embeddings,logs}
   ```

### Step 3: Ollama Setup

1. **Install Ollama**
   - **macOS**: `curl -fsSL https://ollama.ai/install.sh | sh`
   - **Linux**: `curl -fsSL https://ollama.ai/install.sh | sh`
   - **Windows**: Download from https://ollama.ai

2. **Start Ollama Server**
   ```bash
   ollama serve
   ```

3. **Pull AI Models**
   ```bash
   # General purpose LLM
   ollama pull llama3.2:3b
   
   # Vision-language model
   ollama pull moondream:1.8b-v2-fp16
   ```

### Step 4: Hardware Preparation

1. **Omi DevKit 2 Setup**
   - Power on the DevKit 2
   - Ensure it's advertising as "Omi" via BLE
   - Verify audio recording functionality

2. **omiGlass DevKit Setup** (Optional)
   - Flash latest firmware
   - Connect to WiFi network
   - Verify camera functionality

### Step 5: Running the Application

1. **Start the Backend Server**
   ```bash
   # Activate virtual environment
   source venv/bin/activate
   
   # Set Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
   
   # Run the application
   cd backend
   python main.py
   ```

2. **Verify the Application**
   - Open browser to `http://localhost:8000/docs` for API documentation
   - Check `http://localhost:8000/api/status` for system status

## Usage

### Starting the System

1. **Via API**
   ```bash
   curl -X POST http://localhost:8000/api/start
   ```

2. **Via Web Interface**
   - Navigate to `http://localhost:8000`
   - Click "Start System" button

### Monitoring

1. **System Status**
   ```bash
   curl http://localhost:8000/api/status
   ```

2. **Connected Devices**
   ```bash
   curl http://localhost:8000/api/devices
   ```

3. **Event Log**
   ```bash
   curl http://localhost:8000/api/events
   ```

### WebSocket Connection

For real-time updates, connect to the WebSocket endpoint:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/live');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Start Ollama if not running
   ollama serve
   ```

2. **BLE Device Not Found**
   - Ensure DevKit 2 is powered on and advertising
   - Check if BLE is enabled on your system
   - Verify device name is "Omi"

3. **Audio Processing Issues**
   - Check PyAudio installation
   - Verify audio permissions
   - Test with `python -c "import pyaudio; print('PyAudio OK')"`

4. **Vision Processing Errors**
   - Ensure OpenCV and MediaPipe are installed
   - Check camera permissions
   - Verify CUDA/GPU drivers if using GPU acceleration

5. **Port Already in Use**
   ```bash
   # Check what's using port 8000
   lsof -i :8000
   
   # Kill the process or change port in .env
   ```

### Logs and Debugging

1. **View Application Logs**
   ```bash
   tail -f data/logs/omi_companion.log
   ```

2. **Enable Debug Logging**
   ```bash
   # Edit .env file
   LOG_LEVEL=DEBUG
   ```

3. **Check System Resources**
   ```bash
   # Monitor CPU and memory usage
   htop
   
   # Check disk space
   df -h
   ```

## Development

### Project Structure
```
ci-capture-omi/
├── backend/                 # Python backend
│   ├── main.py             # Main application
│   ├── requirements.txt    # Python dependencies
│   ├── ai/                 # AI/ML components
│   ├── audio/              # Audio processing
│   ├── ble/                # BLE communication
│   ├── vision/             # Computer vision
│   └── utils/              # Utilities
├── scripts/                # Setup and utility scripts
├── data/                   # Data storage
└── README.md              # Project documentation
```

### Adding New Features

1. **New AI Model**
   - Add model to `ai/` directory
   - Update `requirements.txt`
   - Configure in `.env`

2. **New Device Support**
   - Add device handler in `ble/` directory
   - Update device discovery logic
   - Add device-specific processing

3. **New Vision Features**
   - Extend `vision/processor.py`
   - Add new MediaPipe solutions
   - Update configuration options

## API Reference

### Core Endpoints

- `GET /api/status` - System status
- `POST /api/start` - Start capture system
- `POST /api/stop` - Stop capture system
- `GET /api/devices` - Connected devices
- `GET /api/events` - Event history
- `POST /api/events` - Submit event
- `PUT /api/config` - Update configuration
- `WS /ws/live` - Real-time updates

### Event Types

- `speech_transcribed` - Speech-to-text results
- `object_detected` - Object detection results
- `face_recognized` - Face recognition results
- `gesture_detected` - Hand gesture results
- `text_detected` - OCR results

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the logs in `data/logs/`
3. Check the API documentation at `http://localhost:8000/docs`
4. Consult the main README.md for architecture details

## License

This project is part of the Omi Companion Capture App. See the main README for license information.
