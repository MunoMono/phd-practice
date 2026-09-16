import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionLogger:
    """Logs all human-AI collaboration sessions for cybernetic research documentation"""
    
    def __init__(self, log_dir: str = "logs/sessions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def log_session(
        self,
        session_id: str,
        query: str,
        retrieved_chunks: list,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a complete interaction session"""
        
        session_data = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "retrieved_chunks": [
                {
                    "chunk_id": chunk.get("id"),
                    "content": chunk.get("content"),
                    "source": chunk.get("source"),
                    "relevance_score": chunk.get("score")
                }
                for chunk in retrieved_chunks
            ],
            "agent_response": agent_response,
            "metadata": metadata or {}
        }
        
        log_file = self.log_dir / f"{session_id}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            logger.info(f"Session logged: {session_id}")
        except Exception as e:
            logger.error(f"Failed to log session {session_id}: {e}")
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a logged session"""
        log_file = self.log_dir / f"{session_id}.json"
        
        if not log_file.exists():
            return None
        
        try:
            with open(log_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None
    
    def list_sessions(self, limit: int = 50) -> list:
        """List recent sessions"""
        session_files = sorted(
            self.log_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]
        
        sessions = []
        for file in session_files:
            try:
                with open(file, 'r') as f:
                    sessions.append(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load session from {file}: {e}")
        
        return sessions


session_logger = SessionLogger()
