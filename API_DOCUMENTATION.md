# Omi Companion API Documentation

## Overview

The Omi Companion API provides real-time audio streaming, conversation events, transcriptions, and webhook endpoints for the Omi Companion Capture App.

**Base URL**: `https://dev.companionintelligence.com`

## Authentication

> **⚠️ BREAKING CHANGE.** Every endpoint except `GET /health` now requires an API
> key. Existing deployments and clients **will break** until the server is given a
> key and every caller is updated to send it.

Set `OMI_COMPANION_API_KEY` in the server's environment (or `.env`) and send the
same value in the `X-API-Key` header on every request:

```bash
curl -H "X-API-Key: $OMI_COMPANION_API_KEY" http://localhost:8000/api/status
```

Generate a key with `openssl rand -hex 32`. `./scripts/setup.sh` and `./run.sh`
generate one automatically when they create a fresh `.env`.

**The default is closed.** If `OMI_COMPANION_API_KEY` is unset or empty, the
service does not fall back to open access - it refuses every guarded request with
`503 Service Unavailable`. There is no environment in which authentication is
skipped: it is enforced identically in development and production.

### What is protected

| Scope | Auth |
|-------|------|
| `GET /health` | **Open.** Liveness only - returns `{"status": "ok"}` and nothing else. |
| Everything else, including `/api/webhooks/*` and `/ws/live` | **API key required.** |

`OMI_API_KEY` is unrelated: that is the upstream credential this service uses to
call `api.omi.me`, not the credential clients use to call this service.

### WebSocket

`/ws/live` accepts the key in the `X-API-Key` header. Browsers cannot set request
headers on a WebSocket handshake, so the `api_key` query parameter is accepted as
well - it lands in proxy access logs, so prefer the header wherever the client can
send one.

```
ws://localhost:8000/ws/live?api_key=<key>
```

A handshake without a valid key is rejected before it is accepted, so the client
sees the upgrade fail with HTTP `403` rather than an open socket that closes.
(The ASGI close code is `1008`, policy violation.)

### Webhook senders

`/api/webhooks/conversation`, `/api/webhooks/audio` and `/api/webhooks/transcript`
are no longer open. Whatever is configured to POST to them must be updated to send
the `X-API-Key` header, or its deliveries will start returning `401`.

## Endpoints

### 🔴 Streaming Endpoints

#### Audio Streaming

##### Get Audio Stream Info
```http
GET /api/stream/audio/{device_id}
```

**Response:**
```json
{
  "device_id": "device_123",
  "status": "streaming",
  "audio_format": "wav",
  "sample_rate": 16000,
  "channels": 1,
  "stream_url": "/api/stream/audio/device_123/live"
}
```

##### Live Audio Stream
```http
GET /api/stream/audio/{device_id}/live
```

**Response:**
```json
{
  "device_id": "device_123",
  "audio_data": [0.1, 0.2, 0.3, ...],
  "timestamp": "2025-08-07T19:30:00.000Z",
  "duration": 1.5
}
```

#### Transcript Streaming

##### Get Transcript Stream Info
```http
GET /api/stream/transcript/{device_id}
```

**Response:**
```json
{
  "device_id": "device_123",
  "status": "streaming",
  "transcripts": [],
  "stream_url": "/api/stream/transcript/device_123/live"
}
```

##### Live Transcript Stream
```http
GET /api/stream/transcript/{device_id}/live
```

**Response:**
```json
{
  "device_id": "device_123",
  "transcript": "Hello, this is a live transcript",
  "timestamp": "2025-08-07T19:30:00.000Z",
  "confidence": 0.95
}
```

### 🔗 Webhook Endpoints

#### Conversation Webhook
```http
POST /api/webhooks/conversation
```

**Request Body:**
```json
{
  "device_id": "device_123",
  "conversation_type": "voice",
  "participants": ["user1", "user2"],
  "duration": 120.5,
  "metadata": {
    "location": "office",
    "topic": "meeting"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "event_id": "uuid-12345",
  "message": "Conversation event logged successfully"
}
```

#### Audio Webhook
```http
POST /api/webhooks/audio
```

**Request Body:**
```json
{
  "device_id": "device_123",
  "audio_bytes": "base64_encoded_audio_data",
  "format": "wav",
  "sample_rate": 16000,
  "channels": 1
}
```

**Response:**
```json
{
  "status": "success",
  "event_id": "uuid-12345",
  "filepath": "data/audio_samples/webhook_audio_device_123_20250807_193000.wav",
  "message": "Audio webhook processed successfully"
}
```

#### Transcript Webhook
```http
POST /api/webhooks/transcript
```

**Request Body:**
```json
{
  "device_id": "device_123",
  "transcript": "Hello, this is a transcript",
  "confidence": 0.95,
  "language": "en",
  "timestamp": "2025-08-07T19:30:00.000Z"
}
```

**Response:**
```json
{
  "status": "success",
  "event_id": "uuid-12345",
  "message": "Transcript webhook processed successfully"
}
```

### 📊 Event Endpoints

#### Get Conversation Events
```http
GET /api/events/conversations?limit=50&offset=0
```

**Response:**
```json
{
  "events": [
    {
      "id": "uuid-12345",
      "timestamp": "2025-08-07T19:30:00.000Z",
      "device_id": "device_123",
      "source": "webhook",
      "event_type": "conversation",
      "data": {
        "event_id": "uuid-12345",
        "conversation_data": {
          "device_id": "device_123",
          "conversation_type": "voice",
          "participants": ["user1", "user2"],
          "duration": 120.5
        },
        "timestamp": "2025-08-07T19:30:00.000Z"
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### Get Audio Events
```http
GET /api/events/audio?limit=50&offset=0
```

#### Get Transcript Events
```http
GET /api/events/transcripts?limit=50&offset=0
```

### 🎵 Audio Capture Endpoints

#### Manual Audio Capture
```http
POST /api/capture/audio
```

**Response:**
```json
{
  "status": "success",
  "message": "Audio captured successfully",
  "filepath": "data/audio_samples/manual_audio_20250807_193000.wav",
  "duration": 1.5
}
```

#### List Audio Files
```http
GET /api/storage/audio?limit=50
```

**Response:**
```json
{
  "files": [
    {
      "filename": "audio_chunk_20250807_193000.wav",
      "filepath": "data/audio_samples/audio_chunk_20250807_193000.wav",
      "size": 25600,
      "created": "2025-08-07T19:30:00.000Z",
      "modified": "2025-08-07T19:30:00.000Z"
    }
  ],
  "total": 1
}
```

### 📸 Image Capture Endpoints

#### Manual Image Capture
```http
POST /api/capture/image
```

#### List Image Files
```http
GET /api/storage/images?limit=50
```

### 🔧 System Endpoints

#### System Status
```http
GET /api/status
```

The `config` object is **redacted**. Any field whose name ends in `_key`,
`_token`, `_secret` or `_password` is omitted and replaced by a
`<field>_configured` boolean, so a caller learns whether a credential is set but
never what it is:

```json
{
  "status": "running",
  "config": {
    "ollama_url": "http://localhost:11434",
    "api_port": 8000,
    "omi_api_key_configured": true
  }
}
```

The same redaction applies to the `config` in a `PUT /api/config` response and to
the `config_updated` message broadcast on `/ws/live`.

#### Start System
```http
POST /api/start
```

#### Stop System
```http
POST /api/stop
```

#### Get Devices
```http
GET /api/devices
```

## WebSocket Endpoints

### Live Updates
```http
WS /ws/live
```

**Message Types:**
- `conversation_event`: New conversation events
- `audio_webhook`: New audio webhook events
- `transcript_webhook`: New transcript webhook events

**Example Message:**
```json
{
  "type": "conversation_event",
  "event_id": "uuid-12345",
  "data": {
    "device_id": "device_123",
    "conversation_type": "voice"
  },
  "timestamp": "2025-08-07T19:30:00.000Z"
}
```

## Error Responses

All endpoints return standard HTTP status codes:

- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized - missing or invalid `X-API-Key`
- `404`: Not Found
- `500`: Internal Server Error
- `503`: Service Unavailable - the server has no `OMI_COMPANION_API_KEY` configured

**Error Response Format:**
```json
{
  "detail": "Error message description"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing rate limiting for production use.

## CORS

CORS is enabled for all origins. Configure appropriately for production.

## SSL/TLS

All endpoints are served over HTTPS with modern SSL/TLS configuration.

## Logging

All API requests are logged to `/var/log/nginx/companion_access.log` and `/var/log/nginx/companion_error.log`.

## Monitoring

### Health Check
```http
GET /health
```

Unauthenticated liveness probe for nginx and process supervisors. Returns
`{"status": "ok"}` and deliberately nothing else - no configuration, device or
event data. For the detailed system status use the authenticated `GET /api/status`.

## Deployment

### Prerequisites
- Ubuntu 20.04+ or similar Linux distribution
- Python 3.8+
- Nginx
- SSL certificate for `dev.companionintelligence.com`

### Installation
1. Clone the repository
2. Run the deployment script:
   ```bash
   sudo ./scripts/deploy.sh
   ```

### Service Management
```bash
# Check service status
sudo systemctl status omi-companion

# Restart service
sudo systemctl restart omi-companion

# View logs
sudo journalctl -u omi-companion -f
```

## Development

### Local Development
```bash
# Start the application locally
./run.sh

# Load the generated key
export OMI_COMPANION_API_KEY=$(grep OMI_COMPANION_API_KEY .env | cut -d= -f2)

# Liveness needs no key
curl http://localhost:8000/health

# Everything else does
curl -H "X-API-Key: $OMI_COMPANION_API_KEY" http://localhost:8000/api/status
```

### Testing Webhooks
```bash
# Test conversation webhook
curl -X POST http://localhost:8000/api/webhooks/conversation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OMI_COMPANION_API_KEY" \
  -d '{"device_id": "test_device", "conversation_type": "voice"}'

# Test audio webhook
curl -X POST http://localhost:8000/api/webhooks/audio \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OMI_COMPANION_API_KEY" \
  -d '{"device_id": "test_device", "audio_bytes": "base64_data"}'

# Test transcript webhook
curl -X POST http://localhost:8000/api/webhooks/transcript \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OMI_COMPANION_API_KEY" \
  -d '{"device_id": "test_device", "transcript": "Hello world"}'
```
