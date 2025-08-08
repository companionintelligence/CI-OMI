"""
Event Logger for Omi Companion App
Handles event storage, retrieval, and JSON backup
"""
import asyncio
import logging
import json
import sqlite3
import aiosqlite
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class EventSchema:
    """Event data schema"""
    id: str
    timestamp: str
    device_id: str
    source: str
    event_type: str
    data: Dict[str, Any]
    location: Optional[str] = None
    session_id: Optional[str] = None
    confidence: Optional[float] = None

class EventLogger:
    """Manages event logging and storage"""
    
    def __init__(self, db_path: str = "data/events.db", backup_path: str = "data/events_backup.json"):
        self.db_path = db_path
        self.backup_path = backup_path
        self.db: Optional[aiosqlite.Connection] = None
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Statistics
        self.stats = {
            "events_logged": 0,
            "events_retrieved": 0,
            "backup_saves": 0,
            "errors": 0,
            "last_event": None
        }
    
    async def initialize(self):
        """Initialize the event logger and database"""
        try:
            logger.info("📊 Initializing Event Logger...")
            
            # Connect to database
            self.db = await aiosqlite.connect(self.db_path)
            
            # Enable WAL mode for better concurrency
            await self.db.execute("PRAGMA journal_mode=WAL")
            await self.db.execute("PRAGMA synchronous=NORMAL")
            await self.db.execute("PRAGMA cache_size=10000")
            
            # Create tables
            await self._create_tables()
            
            # Load existing events count
            count = await self.get_event_count()
            logger.info(f"📊 Event Logger initialized. Existing events: {count}")
            
        except Exception as e:
            logger.error(f"❌ Error initializing event logger: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables"""
        try:
            # Events table
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    location TEXT,
                    session_id TEXT,
                    confidence REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better query performance
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                ON events(timestamp)
            """)
            
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type 
                ON events(event_type)
            """)
            
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_device 
                ON events(device_id)
            """)
            
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_session 
                ON events(session_id)
            """)
            
            # Event statistics table
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS event_stats (
                    date TEXT PRIMARY KEY,
                    total_events INTEGER DEFAULT 0,
                    by_type TEXT DEFAULT '{}',
                    by_device TEXT DEFAULT '{}',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.db.commit()
            logger.info("✅ Database tables created/verified")
            
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
            raise
    
    async def log_event(self, event: Dict[str, Any]):
        """Log an event to storage"""
        try:
            if self.db is None:
                await self.initialize()
            
            # Validate required fields
            required_fields = ["id", "timestamp", "device_id", "source", "event_type", "data"]
            for field in required_fields:
                if field not in event:
                    raise ValueError(f"Missing required field: {field}")
            
            # Insert event
            await self.db.execute("""
                INSERT INTO events (
                    id, timestamp, device_id, source, event_type, 
                    data, location, session_id, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["id"],
                event["timestamp"],
                event["device_id"],
                event["source"],
                event["event_type"],
                json.dumps(event["data"]),
                event.get("location"),
                event.get("session_id"),
                event.get("confidence")
            ))
            
            await self.db.commit()
            
            # Update statistics
            self.stats["events_logged"] += 1
            self.stats["last_event"] = event["timestamp"]
            
            # Update daily statistics
            await self._update_daily_stats(event)
            
            # Backup to JSON periodically
            if self.stats["events_logged"] % 10 == 0:
                await self._backup_to_json()
            
            logger.debug(f"📝 Event logged: {event['event_type']} from {event['device_id']}")
            
        except Exception as e:
            logger.error(f"❌ Error logging event: {e}")
            self.stats["errors"] += 1
            raise
    
    async def get_events(self, limit: int = 100, offset: int = 0, 
                        event_type: str = None, device_id: str = None,
                        start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """Retrieve events from storage"""
        try:
            if self.db is None:
                await self.initialize()
            
            # Build query
            query = "SELECT * FROM events WHERE 1=1"
            params = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # Execute query
            async with self.db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
            
            # Convert to dictionaries
            events = []
            for row in rows:
                event = {
                    "id": row[0],
                    "timestamp": row[1],
                    "device_id": row[2],
                    "source": row[3],
                    "event_type": row[4],
                    "data": json.loads(row[5]),
                    "location": row[6],
                    "session_id": row[7],
                    "confidence": row[8],
                    "created_at": row[9]
                }
                events.append(event)
            
            self.stats["events_retrieved"] += len(events)
            return events
            
        except Exception as e:
            logger.error(f"❌ Error retrieving events: {e}")
            self.stats["errors"] += 1
            return []
    
    async def get_event_count(self, event_type: str = None, device_id: str = None) -> int:
        """Get total event count"""
        try:
            if self.db is None:
                await self.initialize()
            
            query = "SELECT COUNT(*) FROM events WHERE 1=1"
            params = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)
            
            async with self.db.execute(query, params) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"❌ Error getting event count: {e}")
            return 0
    
    async def get_recent_events(self, minutes: int = 60, limit: int = 50) -> List[Dict[str, Any]]:
        """Get events from the last N minutes"""
        try:
            cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
            return await self.get_events(
                limit=limit,
                start_time=cutoff_time
            )
        except Exception as e:
            logger.error(f"❌ Error getting recent events: {e}")
            return []
    
    async def get_events_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all events for a session"""
        try:
            if self.db is None:
                await self.initialize()
            
            query = "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp DESC"
            
            async with self.db.execute(query, [session_id]) as cursor:
                rows = await cursor.fetchall()
            
            # Convert to dictionaries
            events = []
            for row in rows:
                event = {
                    "id": row[0],
                    "timestamp": row[1],
                    "device_id": row[2],
                    "source": row[3],
                    "event_type": row[4],
                    "data": json.loads(row[5]),
                    "location": row[6],
                    "session_id": row[7],
                    "confidence": row[8],
                    "created_at": row[9]
                }
                events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"❌ Error getting events by session: {e}")
            return []
    
    async def get_events_by_type(self, event_type: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get events by specific type"""
        try:
            return await self.get_events(limit=limit, offset=offset, event_type=event_type)
        except Exception as e:
            logger.error(f"❌ Error getting events by type: {e}")
            return []
    
    async def _update_daily_stats(self, event: Dict[str, Any]):
        """Update daily statistics"""
        try:
            date = event["timestamp"][:10]  # YYYY-MM-DD
            
            # Get existing stats
            async with self.db.execute(
                "SELECT total_events, by_type, by_device FROM event_stats WHERE date = ?",
                (date,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                total_events = result[0] + 1
                by_type = json.loads(result[1])
                by_device = json.loads(result[2])
            else:
                total_events = 1
                by_type = {}
                by_device = {}
            
            # Update counters
            event_type = event["event_type"]
            device_id = event["device_id"]
            
            by_type[event_type] = by_type.get(event_type, 0) + 1
            by_device[device_id] = by_device.get(device_id, 0) + 1
            
            # Save updated stats
            await self.db.execute("""
                INSERT OR REPLACE INTO event_stats 
                (date, total_events, by_type, by_device, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                date,
                total_events,
                json.dumps(by_type),
                json.dumps(by_device)
            ))
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ Error updating daily stats: {e}")
    
    async def get_daily_stats(self, date: str = None) -> Dict[str, Any]:
        """Get daily statistics"""
        try:
            if self.db is None:
                await self.initialize()
            
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")
            
            async with self.db.execute(
                "SELECT * FROM event_stats WHERE date = ?",
                (date,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result:
                return {
                    "date": result[0],
                    "total_events": result[1],
                    "by_type": json.loads(result[2]),
                    "by_device": json.loads(result[3]),
                    "updated_at": result[4]
                }
            else:
                return {
                    "date": date,
                    "total_events": 0,
                    "by_type": {},
                    "by_device": {},
                    "updated_at": None
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting daily stats: {e}")
            return {}
    
    async def _backup_to_json(self):
        """Backup recent events to JSON file"""
        try:
            # Get recent events
            recent_events = await self.get_recent_events(minutes=1440)  # Last 24 hours
            
            # Save to JSON file
            backup_data = {
                "backup_timestamp": datetime.now().isoformat(),
                "event_count": len(recent_events),
                "events": recent_events
            }
            
            with open(self.backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            self.stats["backup_saves"] += 1
            logger.debug(f"💾 Backup saved: {len(recent_events)} events")
            
        except Exception as e:
            logger.error(f"❌ Error backing up to JSON: {e}")
    
    async def cleanup_old_events(self, days: int = 30):
        """Clean up events older than specified days"""
        try:
            if self.db is None:
                await self.initialize()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Count events to be deleted
            async with self.db.execute(
                "SELECT COUNT(*) FROM events WHERE timestamp < ?",
                (cutoff_date,)
            ) as cursor:
                count_result = await cursor.fetchone()
                count_to_delete = count_result[0] if count_result else 0
            
            if count_to_delete > 0:
                # Delete old events
                await self.db.execute(
                    "DELETE FROM events WHERE timestamp < ?",
                    (cutoff_date,)
                )
                
                await self.db.commit()
                logger.info(f"🧹 Cleaned up {count_to_delete} old events (older than {days} days)")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old events: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get logger statistics"""
        return self.stats.copy()
    
    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
            self.db = None
