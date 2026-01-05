"""Text chunking strategies for CHIMERA.

Chunks content into semantic units for embedding.
Target: 500-1000 tokens with 50 token overlap.
"""

import re
from dataclasses import dataclass

from chimera.utils.logging import get_logger

logger = get_logger(__name__)

# Approximate tokens per word (for English)
TOKENS_PER_WORD = 1.3


@dataclass
class Chunk:
    """A content chunk."""
    index: int
    content: str
    chunk_type: str  # paragraph, section, code_block, etc.
    start_char: int
    end_char: int
    token_count: int


class TextChunker:
    """Chunk text content for embedding."""
    
    def __init__(
        self,
        target_tokens: int = 500,
        max_tokens: int = 1000,
        overlap_tokens: int = 50,
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        
        # Convert to approximate word counts
        self.target_words = int(target_tokens / TOKENS_PER_WORD)
        self.max_words = int(max_tokens / TOKENS_PER_WORD)
        self.overlap_words = int(overlap_tokens / TOKENS_PER_WORD)
    
    def chunk(self, text: str, chunk_type: str = "paragraph") -> list[Chunk]:
        """Chunk text into semantic units."""
        if not text.strip():
            return []
        
        # Try semantic chunking first (by paragraphs/sections)
        chunks = self._chunk_by_paragraphs(text)
        
        # If any chunk is too large, split further
        final_chunks = []
        for chunk in chunks:
            if self._word_count(chunk.content) > self.max_words:
                # Split large chunk by sentences
                sub_chunks = self._split_by_sentences(chunk)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        # Merge small chunks if needed
        final_chunks = self._merge_small_chunks(final_chunks)
        
        # Re-index
        for i, chunk in enumerate(final_chunks):
            chunk.index = i
        
        return final_chunks
    
    def _chunk_by_paragraphs(self, text: str) -> list[Chunk]:
        """Split text by paragraphs."""
        # Split on double newlines or markdown headers
        parts = re.split(r'\n\n+|(?=^#{1,6}\s)', text, flags=re.MULTILINE)
        
        chunks = []
        pos = 0
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                pos += len(part) + 2  # Account for newlines
                continue
            
            # Detect chunk type
            chunk_type = "paragraph"
            if part.startswith("#"):
                chunk_type = "header"
            elif part.startswith("```") or part.startswith("    "):
                chunk_type = "code_block"
            elif part.startswith("- ") or part.startswith("* ") or re.match(r'^\d+\.', part):
                chunk_type = "list"
            
            chunks.append(Chunk(
                index=len(chunks),
                content=part,
                chunk_type=chunk_type,
                start_char=pos,
                end_char=pos + len(part),
                token_count=int(self._word_count(part) * TOKENS_PER_WORD),
            ))
            
            pos += len(part) + 2
        
        return chunks
    
    def _split_by_sentences(self, chunk: Chunk) -> list[Chunk]:
        """Split a large chunk by sentences."""
        # Simple sentence splitting (could use nltk for better results)
        sentences = re.split(r'(?<=[.!?])\s+', chunk.content)
        
        current_chunk = []
        current_words = 0
        chunks = []
        start_char = chunk.start_char
        
        for sentence in sentences:
            sentence_words = self._word_count(sentence)
            
            if current_words + sentence_words > self.target_words and current_chunk:
                # Create chunk from accumulated sentences
                content = " ".join(current_chunk)
                chunks.append(Chunk(
                    index=len(chunks),
                    content=content,
                    chunk_type=chunk.chunk_type,
                    start_char=start_char,
                    end_char=start_char + len(content),
                    token_count=int(current_words * TOKENS_PER_WORD),
                ))
                
                # Start new chunk with overlap
                overlap_sentences = current_chunk[-2:] if len(current_chunk) > 2 else []
                start_char += len(content) - sum(len(s) for s in overlap_sentences)
                current_chunk = overlap_sentences + [sentence]
                current_words = sum(self._word_count(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_words += sentence_words
        
        # Add remaining content
        if current_chunk:
            content = " ".join(current_chunk)
            chunks.append(Chunk(
                index=len(chunks),
                content=content,
                chunk_type=chunk.chunk_type,
                start_char=start_char,
                end_char=start_char + len(content),
                token_count=int(current_words * TOKENS_PER_WORD),
            ))
        
        return chunks
    
    def _merge_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Merge chunks that are too small."""
        if not chunks:
            return []
        
        min_words = self.target_words // 4  # Minimum chunk size
        merged = []
        current = chunks[0]
        
        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            current_words = self._word_count(current.content)
            
            if current_words < min_words:
                # Merge with next chunk
                current = Chunk(
                    index=current.index,
                    content=current.content + "\n\n" + next_chunk.content,
                    chunk_type=current.chunk_type,
                    start_char=current.start_char,
                    end_char=next_chunk.end_char,
                    token_count=current.token_count + next_chunk.token_count,
                )
            else:
                merged.append(current)
                current = next_chunk
        
        merged.append(current)
        return merged
    
    def _word_count(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())


class CodeChunker:
    """Chunk code files by semantic units."""
    
    def __init__(self, max_lines: int = 100) -> None:
        self.max_lines = max_lines
    
    def chunk(self, content: str, code_elements: list[dict]) -> list[Chunk]:
        """Chunk code by functions and classes."""
        if not code_elements:
            # Fall back to line-based chunking
            return self._chunk_by_lines(content)
        
        lines = content.splitlines()
        chunks = []
        
        for element in code_elements:
            start = element.get("line_start", 1) - 1
            end = element.get("line_end", len(lines))
            
            element_content = "\n".join(lines[start:end])
            element_type = element.get("element_type", "code")
            
            chunks.append(Chunk(
                index=len(chunks),
                content=element_content,
                chunk_type=f"code_{element_type}",
                start_char=sum(len(l) + 1 for l in lines[:start]),
                end_char=sum(len(l) + 1 for l in lines[:end]),
                token_count=int(len(element_content.split()) * TOKENS_PER_WORD),
            ))
        
        return chunks
    
    def _chunk_by_lines(self, content: str) -> list[Chunk]:
        """Chunk code by lines when no structure available."""
        lines = content.splitlines()
        chunks = []
        
        for i in range(0, len(lines), self.max_lines):
            chunk_lines = lines[i:i + self.max_lines]
            chunk_content = "\n".join(chunk_lines)
            
            chunks.append(Chunk(
                index=len(chunks),
                content=chunk_content,
                chunk_type="code_block",
                start_char=sum(len(l) + 1 for l in lines[:i]),
                end_char=sum(len(l) + 1 for l in lines[:i + len(chunk_lines)]),
                token_count=int(len(chunk_content.split()) * TOKENS_PER_WORD),
            ))
        
        return chunks
