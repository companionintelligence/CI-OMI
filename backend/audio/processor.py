"""
Audio Processor for Omi Companion App
Handles Opus decoding, audio streaming, and Whisper transcription
"""
import asyncio
import logging
import numpy as np
import wave
import io
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import tempfile
import os

import whisper
import soundfile as sf
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class AudioConfig:
    """Audio processing configuration"""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    buffer_duration: float = 1.0  # seconds
    overlap_duration: float = 0.2  # seconds

class AudioProcessor:
    """Handles audio processing, decoding, and transcription"""
    
    def __init__(self, sample_rate: int = 16000):
        self.config = AudioConfig(sample_rate=sample_rate)
        self.whisper_model = None
        self.audio_queue = deque(maxlen=100)
        self.processing_queue = asyncio.Queue(maxsize=50)
        
        # Audio buffers
        self.audio_buffer = np.array([], dtype=np.float32)
        self.processed_chunks = deque(maxlen=10)
        
        # Statistics
        self.stats = {
            "chunks_processed": 0,
            "transcriptions_completed": 0,
            "errors": 0,
            "last_activity": None
        }
        
    async def initialize(self):
        """Initialize the audio processor"""
        try:
            logger.info("🎵 Initializing Audio Processor...")
            
            # Load Whisper model
            logger.info("📥 Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")
            logger.info("✅ Whisper model loaded successfully")
            
            # Start processing task
            asyncio.create_task(self._audio_processing_task())
            
            logger.info("✅ Audio processor initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing audio processor: {e}")
            raise
    
    async def process_opus_stream(self, opus_data: bytes) -> Optional[np.ndarray]:
        """Process incoming Opus audio stream"""
        try:
            if not opus_data:
                return None
            
            # For now, assume raw PCM data (Opus decoding would need opuslib)
            # This is a placeholder - real implementation would decode Opus
            audio_array = self._decode_audio_data(opus_data)
            
            if audio_array is not None:
                # Add to buffer
                self.audio_buffer = np.concatenate([self.audio_buffer, audio_array])
                
                # Check if we have enough data for processing
                samples_needed = int(self.config.sample_rate * self.config.buffer_duration)
                
                if len(self.audio_buffer) >= samples_needed:
                    # Extract chunk for processing
                    chunk = self.audio_buffer[:samples_needed]
                    
                    # Keep overlap for continuity
                    overlap_samples = int(self.config.sample_rate * self.config.overlap_duration)
                    self.audio_buffer = self.audio_buffer[samples_needed - overlap_samples:]
                    
                    # Save audio sample automatically
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"audio_chunk_{timestamp}.wav"
                    await self.save_audio_sample(chunk, filename)
                    
                    # Add to processing queue
                    try:
                        await self.processing_queue.put(chunk)
                        self.stats["chunks_processed"] += 1
                        self.stats["last_activity"] = datetime.now().isoformat()
                    except asyncio.QueueFull:
                        logger.warning("⚠️  Audio processing queue is full")
                
                return audio_array
            
        except Exception as e:
            logger.error(f"❌ Error processing Opus stream: {e}")
            self.stats["errors"] += 1
            return None
    
    def _decode_audio_data(self, data: bytes) -> Optional[np.ndarray]:
        """Decode audio data (placeholder for Opus decoding)"""
        try:
            # For now, assume data is raw 16-bit PCM
            # Real implementation would use opuslib to decode Opus
            if len(data) % 2 != 0:
                # Pad if odd number of bytes
                data = data + b'\x00'
            
            # Convert bytes to numpy array (16-bit signed integers)
            audio_int16 = np.frombuffer(data, dtype=np.int16)
            
            # Convert to float32 normalized to [-1, 1]
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            return audio_float32
            
        except Exception as e:
            logger.error(f"❌ Error decoding audio data: {e}")
            return None
    
    async def _audio_processing_task(self):
        """Background task for processing audio chunks"""
        logger.info("🎵 Audio processing task started")
        
        while True:
            try:
                # Wait for audio chunk
                chunk = await self.processing_queue.get()
                
                # Process the chunk
                await self._process_audio_chunk(chunk)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Error in audio processing task: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_audio_chunk(self, audio_chunk: np.ndarray):
        """Process a single audio chunk"""
        try:
            # Apply audio preprocessing
            processed_chunk = self._preprocess_audio(audio_chunk)
            
            # Store processed chunk
            self.processed_chunks.append({
                "data": processed_chunk,
                "timestamp": datetime.now().isoformat(),
                "length": len(processed_chunk)
            })
            
        except Exception as e:
            logger.error(f"❌ Error processing audio chunk: {e}")
    
    def _preprocess_audio(self, audio: np.ndarray) -> np.ndarray:
        """Apply audio preprocessing"""
        try:
            # Normalize audio
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))
            
            # Apply basic noise reduction (simple high-pass filter)
            # This is a placeholder - real implementation would use more sophisticated methods
            if len(audio) > 1:
                audio = np.diff(audio, prepend=audio[0])
            
            return audio
            
        except Exception as e:
            logger.error(f"❌ Error preprocessing audio: {e}")
            return audio
    
    async def transcribe_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """Transcribe audio using Whisper"""
        try:
            if self.whisper_model is None:
                await self.initialize()
            
            if self.whisper_model is None:
                logger.error("❌ Whisper model not available")
                return None
            
            # Ensure audio is the right format for Whisper
            if len(audio_data) < self.config.sample_rate * 0.1:  # Less than 100ms
                return None
            
            # Whisper expects audio at 16kHz
            if len(audio_data) > self.config.sample_rate * 30:  # Limit to 30 seconds
                audio_data = audio_data[:self.config.sample_rate * 30]
            
            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._transcribe_sync, 
                audio_data
            )
            
            if result and result.strip():
                self.stats["transcriptions_completed"] += 1
                logger.info(f"🎤 Transcription: {result[:100]}...")
                return result.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error transcribing audio: {e}")
            self.stats["errors"] += 1
            return None
    
    def _transcribe_sync(self, audio_data: np.ndarray) -> str:
        """Synchronous transcription function"""
        try:
            # Create temporary file for Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write audio to temporary WAV file
                sf.write(temp_file.name, audio_data, self.config.sample_rate)
                
                # Transcribe with Whisper
                result = self.whisper_model.transcribe(
                    temp_file.name,
                    language="en",  # Can be auto-detected
                    fp16=False,
                    verbose=False
                )
                
                # Clean up temporary file
                os.unlink(temp_file.name)
                
                return result["text"]
                
        except Exception as e:
            logger.error(f"❌ Error in sync transcription: {e}")
            return ""
    
    async def process_queue(self):
        """Process any queued audio data"""
        # This method is called by the main loop to process any pending audio
        pass
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        return {
            **self.stats,
            "queue_size": self.processing_queue.qsize(),
            "buffer_length": len(self.audio_buffer),
            "processed_chunks": len(self.processed_chunks)
        }
    
    async def save_audio_sample(self, audio_data: np.ndarray, filename: str = None) -> str:
        """Save audio sample for debugging"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"audio_sample_{timestamp}.wav"
            
            # Create data directory if it doesn't exist
            os.makedirs("data/audio_samples", exist_ok=True)
            filepath = f"data/audio_samples/{filename}"
            
            # Save audio file
            sf.write(filepath, audio_data, self.config.sample_rate)
            
            logger.info(f"💾 Audio sample saved: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error saving audio sample: {e}")
            return ""
    
    def clear_buffers(self):
        """Clear all audio buffers"""
        self.audio_buffer = np.array([], dtype=np.float32)
        self.processed_chunks.clear()
        
        # Clear queue
        while not self.processing_queue.empty():
            try:
                self.processing_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        logger.info("🧹 Audio buffers cleared")
    
    async def test_transcription(self, test_text: str = "Hello, this is a test") -> bool:
        """Test transcription with synthetic audio"""
        try:
            # Generate simple test audio (sine wave)
            duration = 2.0  # seconds
            frequency = 440  # Hz (A4 note)
            t = np.linspace(0, duration, int(self.config.sample_rate * duration))
            test_audio = 0.1 * np.sin(2 * np.pi * frequency * t)
            
            # Save test audio
            test_file = await self.save_audio_sample(test_audio, "test_audio.wav")
            
            logger.info(f"🧪 Test audio created: {test_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in transcription test: {e}")
            return False
