import os
from pathlib import Path
from typing import Dict, List, Any
import config


class MemoryManager:
    """Manages short-term conversation buffer and persistent memory storage."""

    def __init__(self, memory_file_path: Path = config.MEMORY_FILE):
        self.memory_file_path = Path(memory_file_path)
        self.short_term_messages: List[Dict[str, Any]] = []

    def add_message(
        self, user_id: int | str, username: str, content: str, role: str = "user"
    ) -> bool:
        """
        Appends a message to the short-term buffer.
        Returns True if the buffer reaches 50 messages (triggering consolidation), else False.
        """
        # Normalize content whitespace defensively
        clean_content = " ".join(content.split())
        message = {
            "user_id": str(user_id),
            "username": username.lstrip("@"),
            "content": clean_content,
            "role": role,
        }
        self.short_term_messages.append(message)

        return len(self.short_term_messages) >= 50

    def get_short_term_context(self) -> List[Dict[str, Any]]:
        """
        Returns the short-term conversational context (up to the 49 most recent messages).
        """
        return self.short_term_messages[-49:]

    def get_full_batch(self) -> List[Dict[str, Any]]:
        """
        Returns all messages in the current batch (up to 50).
        """
        return list(self.short_term_messages)

    def get_short_term_count(self) -> int:
        """
        Returns the number of messages currently in short-term buffer.
        """
        return len(self.short_term_messages)

    def get_persistent_memory(self) -> str:
        """
        Reads persistent memory from data/memory.txt.
        """
        if self.memory_file_path.exists():
            return self.memory_file_path.read_text(encoding="utf-8").strip()
        return ""

    def get_persistent_memory_size(self) -> int:
        """
        Returns the character size of persistent memory.
        """
        return len(self.get_persistent_memory())

    def save_persistent_memory(self, new_memory_text: str) -> bool:
        """
        Atomically saves new memory text into memory.txt.
        Verifies the write succeeded before returning True.
        """
        clean_text = new_memory_text.strip()
        temp_file = self.memory_file_path.with_suffix(".tmp")

        try:
            temp_file.write_text(clean_text, encoding="utf-8")
            # Verify write succeeded
            written_content = temp_file.read_text(encoding="utf-8")
            if written_content != clean_text:
                raise ValueError("Verification failed: written content does not match.")

            # Atomic replace
            os.replace(temp_file, self.memory_file_path)
            return True
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise IOError(f"Failed to save persistent memory safely: {e}") from e

    def reset_short_term_batch(self):
        """
        Resets the short-term message buffer after a successful memory update.
        """
        self.short_term_messages.clear()
