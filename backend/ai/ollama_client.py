"""
Ollama Client for AI Processing
Handles communication with local Ollama server for LLM and vision tasks
"""
import asyncio
import logging
import json
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for communicating with Ollama server"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.available_models: List[str] = []
        self.default_chat_model = "llama3.2:3b"
        self.default_vision_model = "moondream:1.8b-v2-fp16"
        
        # Statistics
        self.stats = {
            "requests_made": 0,
            "successful_requests": 0,
            "errors": 0,
            "last_request": None,
            "average_response_time": 0.0
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def initialize(self):
        """Initialize the Ollama client"""
        try:
            if self.session is None:
                timeout = aiohttp.ClientTimeout(total=30)
                self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Check if server is available and get models
            await self.refresh_models()
            
            logger.info("✅ Ollama client initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing Ollama client: {e}")
    
    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> bool:
        """Check if Ollama server is available"""
        try:
            if self.session is None:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    return True
                else:
                    logger.warning(f"⚠️  Ollama health check failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Ollama health check error: {e}")
            return False
    
    async def refresh_models(self) -> List[str]:
        """Refresh list of available models"""
        try:
            if self.session is None:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    self.available_models = [model["name"] for model in data.get("models", [])]
                    logger.info(f"📋 Available models: {self.available_models}")
                    return self.available_models
                else:
                    logger.error(f"❌ Failed to get models: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Error refreshing models: {e}")
            return []
    
    async def chat(self, prompt: str, model: str = None, context: str = None) -> Optional[str]:
        """Send chat request to Ollama"""
        try:
            if self.session is None:
                await self.initialize()
            
            if not model:
                model = self.default_chat_model
            
            # Check if model is available
            if model not in self.available_models:
                logger.warning(f"⚠️  Model {model} not available, trying default")
                model = self.default_chat_model
                if model not in self.available_models:
                    logger.error("❌ No suitable model available")
                    return None
            
            # Prepare request
            request_data = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            
            if context:
                request_data["context"] = context
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            # Make request
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=request_data
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    result = data.get("response", "")
                    
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info(f"🤖 Chat response ({response_time:.2f}s): {result[:100]}...")
                    return result
                else:
                    logger.error(f"❌ Chat request failed: {response.status}")
                    self._update_stats(0, False)
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error in chat request: {e}")
            self._update_stats(0, False)
            return None
    
    async def analyze_speech(self, transcription: str) -> Optional[Dict[str, Any]]:
        """Analyze speech transcription for context and intent"""
        try:
            prompt = f"""
            Analyze this speech transcription and provide context:
            
            Transcription: "{transcription}"
            
            Please provide:
            1. Main topic or subject
            2. Emotional tone (positive, negative, neutral)
            3. Intent or purpose (question, statement, command, etc.)
            4. Key entities mentioned (people, places, objects)
            5. Urgency level (low, medium, high)
            
            Respond in JSON format:
            {{
                "topic": "main topic",
                "tone": "emotional tone",
                "intent": "intent type",
                "entities": ["entity1", "entity2"],
                "urgency": "urgency level",
                "summary": "brief summary"
            }}
            """
            
            response = await self.chat(prompt)
            if response:
                try:
                    # Try to extract JSON from response
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response[json_start:json_end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.warning("⚠️  Could not parse JSON from speech analysis")
                
                # Return basic analysis if JSON parsing fails
                return {
                    "topic": "conversation",
                    "tone": "neutral",
                    "intent": "statement",
                    "entities": [],
                    "urgency": "low",
                    "summary": response[:200]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing speech: {e}")
            return None
    
    async def analyze_scene(self, objects: List[str], faces: List[str], text: List[str]) -> Optional[str]:
        """Analyze scene based on detected objects, faces, and text"""
        try:
            prompt = f"""
            Analyze this scene based on the following detections:
            
            Objects detected: {objects}
            People/faces detected: {faces}
            Text detected: {text}
            
            Provide a brief, natural description of what's happening in this scene.
            Focus on:
            - The setting or location type
            - Activities that might be taking place
            - Relationships between people and objects
            - Overall context or situation
            
            Keep the description under 100 words and make it sound natural.
            """
            
            response = await self.chat(prompt)
            return response
            
        except Exception as e:
            logger.error(f"❌ Error analyzing scene: {e}")
            return None
    
    async def translate_text(self, text: str, target_language: str = "English") -> Optional[str]:
        """Translate text to target language"""
        try:
            prompt = f"""
            Translate the following text to {target_language}:
            
            "{text}"
            
            Provide only the translation, nothing else.
            """
            
            response = await self.chat(prompt)
            return response
            
        except Exception as e:
            logger.error(f"❌ Error translating text: {e}")
            return None
    
    async def classify_emotion(self, context: str) -> Optional[str]:
        """Classify emotional context"""
        try:
            prompt = f"""
            Based on this context, classify the overall emotional state:
            
            Context: "{context}"
            
            Choose one of: happy, sad, angry, surprised, fearful, disgusted, neutral
            
            Respond with only the emotion word.
            """
            
            response = await self.chat(prompt)
            if response:
                emotion = response.strip().lower()
                valid_emotions = ["happy", "sad", "angry", "surprised", "fearful", "disgusted", "neutral"]
                if emotion in valid_emotions:
                    return emotion
            
            return "neutral"
            
        except Exception as e:
            logger.error(f"❌ Error classifying emotion: {e}")
            return "neutral"
    
    async def generate_summary(self, events: List[Dict[str, Any]]) -> Optional[str]:
        """Generate summary of recent events"""
        try:
            if not events:
                return None
            
            # Prepare events summary
            events_text = []
            for event in events[-10:]:  # Last 10 events
                event_type = event.get("event_type", "unknown")
                timestamp = event.get("timestamp", "")
                data = event.get("data", {})
                
                if event_type == "speech_transcribed":
                    events_text.append(f"Speech: {data.get('transcription', '')}")
                elif event_type == "object_detected":
                    events_text.append(f"Saw: {data.get('object', '')}")
                elif event_type == "face_recognized":
                    events_text.append(f"Person: {data.get('name', 'unknown')}")
                elif event_type == "text_detected":
                    events_text.append(f"Text: {data.get('text', '')}")
            
            prompt = f"""
            Summarize these recent events into a natural narrative:
            
            {chr(10).join(events_text)}
            
            Create a brief, coherent summary of what happened. 
            Keep it under 150 words and make it sound like a natural description.
            """
            
            response = await self.chat(prompt)
            return response
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {e}")
            return None
    
    def _update_stats(self, response_time: float, success: bool):
        """Update client statistics"""
        if success:
            self.stats["successful_requests"] += 1
            
            # Update average response time
            current_avg = self.stats["average_response_time"]
            total_successful = self.stats["successful_requests"]
            self.stats["average_response_time"] = (
                (current_avg * (total_successful - 1) + response_time) / total_successful
            )
        else:
            self.stats["errors"] += 1
        
        self.stats["last_request"] = datetime.now().isoformat()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self.stats,
            "available_models": self.available_models,
            "base_url": self.base_url
        }
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry"""
        try:
            if self.session is None:
                await self.initialize()
            
            logger.info(f"📥 Pulling model: {model_name}")
            
            async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            ) as response:
                
                if response.status == 200:
                    logger.info(f"✅ Model {model_name} pulled successfully")
                    await self.refresh_models()
                    return True
                else:
                    logger.error(f"❌ Failed to pull model {model_name}: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error pulling model {model_name}: {e}")
            return False
