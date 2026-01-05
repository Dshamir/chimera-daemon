"""FAE (Full Archaeology Excavation) extractors for AI conversation exports.

Supports: Claude, ChatGPT, Gemini, Grok
"""

import json
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CanonicalMessage:
    """Canonical message format."""
    id: str
    role: Literal["human", "assistant", "system"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalConversation:
    """Canonical conversation format."""
    id: str
    title: str
    provider: str
    created_at: datetime
    updated_at: datetime
    messages: list[CanonicalMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FAEResult:
    """Result of FAE processing."""
    file_path: Path
    provider: str
    conversations: list[CanonicalConversation] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class BaseFAEParser:
    """Base class for FAE parsers."""
    
    provider: str = "generic"
    
    @abstractmethod
    def detect(self, data: Any) -> bool:
        """Check if data matches this provider's format."""
        pass
    
    @abstractmethod
    def parse(self, data: Any) -> list[CanonicalConversation]:
        """Parse data into canonical conversations."""
        pass


class ClaudeParser(BaseFAEParser):
    """Parser for Claude conversation exports."""
    
    provider = "claude"
    
    def detect(self, data: Any) -> bool:
        """Check for Claude export signature."""
        if not isinstance(data, list):
            return False
        if len(data) == 0:
            return False
        
        sample = data[0]
        if not isinstance(sample, dict):
            return False
        required = {"uuid", "name", "created_at", "chat_messages"}
        return required.issubset(sample.keys())
    
    def parse(self, data: list) -> list[CanonicalConversation]:
        """Parse Claude export."""
        conversations = []
        
        for conv in data:
            messages = []
            for msg in conv.get("chat_messages", []):
                # Handle different content formats
                content = msg.get("text", "")
                if not content and "content" in msg:
                    content_list = msg.get("content", [])
                    if isinstance(content_list, list):
                        content = " ".join(
                            c.get("text", "") for c in content_list 
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                
                messages.append(CanonicalMessage(
                    id=msg.get("uuid", ""),
                    role="human" if msg.get("sender") == "human" else "assistant",
                    content=content,
                    timestamp=self._parse_datetime(msg.get("created_at")),
                    metadata={"attachments": msg.get("attachments", [])},
                ))
            
            conversations.append(CanonicalConversation(
                id=conv.get("uuid", ""),
                title=conv.get("name", "Untitled"),
                provider="claude",
                created_at=self._parse_datetime(conv.get("created_at")),
                updated_at=self._parse_datetime(conv.get("updated_at")),
                messages=messages,
                metadata={"project": conv.get("project")},
            ))
        
        return conversations
    
    def _parse_datetime(self, value: str | None) -> datetime:
        """Parse datetime string."""
        if not value:
            return datetime.now()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now()


class ChatGPTParser(BaseFAEParser):
    """Parser for ChatGPT conversation exports."""
    
    provider = "chatgpt"
    
    def detect(self, data: Any) -> bool:
        """Check for ChatGPT export signature."""
        if not isinstance(data, list):
            return False
        if len(data) == 0:
            return False
        
        sample = data[0]
        if not isinstance(sample, dict):
            return False
        return "mapping" in sample and "title" in sample
    
    def parse(self, data: list) -> list[CanonicalConversation]:
        """Parse ChatGPT export."""
        conversations = []
        
        for conv in data:
            messages = []
            mapping = conv.get("mapping", {})
            
            # Build message tree
            for node_id, node in mapping.items():
                msg_data = node.get("message")
                if not msg_data:
                    continue
                
                role = msg_data.get("author", {}).get("role", "unknown")
                if role not in ("user", "assistant", "system"):
                    continue
                
                content_parts = msg_data.get("content", {}).get("parts", [])
                content = " ".join(str(p) for p in content_parts if p)
                
                if content.strip():
                    messages.append(CanonicalMessage(
                        id=msg_data.get("id", node_id),
                        role="human" if role == "user" else role,
                        content=content,
                        timestamp=self._parse_timestamp(msg_data.get("create_time")),
                    ))
            
            # Sort by timestamp
            messages.sort(key=lambda m: m.timestamp or datetime.min)
            
            conversations.append(CanonicalConversation(
                id=conv.get("id", ""),
                title=conv.get("title", "Untitled"),
                provider="chatgpt",
                created_at=self._parse_timestamp(conv.get("create_time")),
                updated_at=self._parse_timestamp(conv.get("update_time")),
                messages=messages,
            ))
        
        return conversations
    
    def _parse_timestamp(self, ts: float | None) -> datetime:
        """Parse Unix timestamp."""
        if ts:
            try:
                return datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                pass
        return datetime.now()


class GeminiParser(BaseFAEParser):
    """Parser for Gemini conversation exports."""
    
    provider = "gemini"
    
    def detect(self, data: Any) -> bool:
        """Check for Gemini export signature."""
        # Gemini uses Google Takeout format
        if isinstance(data, dict):
            return "conversations" in data or "chats" in data
        return False
    
    def parse(self, data: Any) -> list[CanonicalConversation]:
        """Parse Gemini export."""
        # TODO: Implement based on actual Gemini export format
        logger.warning("Gemini parser not fully implemented")
        return []


class GrokParser(BaseFAEParser):
    """Parser for Grok conversation exports."""
    
    provider = "grok"
    
    def detect(self, data: Any) -> bool:
        """Check for Grok export signature."""
        # TODO: Implement based on actual Grok export format
        return False
    
    def parse(self, data: Any) -> list[CanonicalConversation]:
        """Parse Grok export."""
        # TODO: Implement based on actual Grok export format
        logger.warning("Grok parser not fully implemented")
        return []


class FAEProcessor:
    """Main FAE processor that orchestrates parsing."""
    
    def __init__(self) -> None:
        self.parsers = [
            ClaudeParser(),
            ChatGPTParser(),
            GeminiParser(),
            GrokParser(),
        ]
    
    def detect_provider(self, file_path: Path) -> str | None:
        """Detect which provider the export is from."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return None
        
        for parser in self.parsers:
            if parser.detect(data):
                return parser.provider
        
        return None
    
    def process(self, file_path: Path, provider: str | None = None) -> FAEResult:
        """Process an AI conversation export."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return FAEResult(
                file_path=file_path,
                provider="unknown",
                success=False,
                error=f"Invalid JSON: {e}",
            )
        except OSError as e:
            return FAEResult(
                file_path=file_path,
                provider="unknown",
                success=False,
                error=f"File error: {e}",
            )
        
        # Find appropriate parser
        parser = None
        if provider:
            for p in self.parsers:
                if p.provider == provider:
                    parser = p
                    break
        else:
            for p in self.parsers:
                if p.detect(data):
                    parser = p
                    break
        
        if not parser:
            return FAEResult(
                file_path=file_path,
                provider="unknown",
                success=False,
                error="Could not detect provider format",
            )
        
        # Parse conversations
        try:
            conversations = parser.parse(data)
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return FAEResult(
                file_path=file_path,
                provider=parser.provider,
                success=False,
                error=f"Parse error: {e}",
            )
        
        logger.info(f"Parsed {len(conversations)} conversations from {file_path.name}")
        
        return FAEResult(
            file_path=file_path,
            provider=parser.provider,
            conversations=conversations,
            success=True,
        )
