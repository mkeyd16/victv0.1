import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Iterator, Optional
import config

logger = logging.getLogger("Vict.Brain")

try:
    import llama_cpp
    from llama_cpp import Llama
except ImportError:
    llama_cpp = None
    Llama = None


def get_ggml_type(type_str: str) -> Optional[int]:
    """Helper to convert cache type string (f16, f32, q8_0, etc) to GGML integer enum."""
    if llama_cpp is None:
        return None
    type_clean = type_str.lower().strip()
    mapping = {
        "f32": getattr(llama_cpp, "GGML_TYPE_F32", 0),
        "f16": getattr(llama_cpp, "GGML_TYPE_F16", 1),
        "q8_0": getattr(llama_cpp, "GGML_TYPE_Q8_0", 8),
        "q4_0": getattr(llama_cpp, "GGML_TYPE_Q4_0", 2),
        "q4_1": getattr(llama_cpp, "GGML_TYPE_Q4_1", 3),
        "q5_0": getattr(llama_cpp, "GGML_TYPE_Q5_0", 6),
        "q5_1": getattr(llama_cpp, "GGML_TYPE_Q5_1", 7),
    }
    return mapping.get(type_clean, getattr(llama_cpp, "GGML_TYPE_F16", 1))


def normalize_text(text: str) -> str:
    """
    Normalizes generated text:
    - Removes newlines (\r\n, \r, \n) and replaces with spaces.
    - Strips unwanted backticks (`).
    - Collapses repeated whitespace.
    - Trims leading/trailing whitespace.
    Ensures the response is a single continuous line of text.
    """
    if not text:
        return ""
    # Remove backticks
    text = text.replace("`", "")
    # Normalize line breaks to space
    text = re.sub(r"[\r\n]+", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class Brain:
    """Inference and prompt construction engine using llama.cpp with low RAM configuration."""

    def __init__(self, model_path: str = config.MODEL_PATH):
        self.model_path = Path(model_path)
        self.llm: Optional[Any] = None
        self._init_model()

    def _init_model(self):
        """Initialize local GGUF model with explicit low-memory settings."""
        if not self.model_path.exists():
            logger.warning(
                f"Model file not found at {self.model_path}. AI features will not function until model is downloaded."
            )
            return

        if Llama is None:
            logger.error("llama_cpp library is not installed.")
            return

        try:
            logger.info(
                f"Loading local model from {self.model_path} "
                f"(n_ctx={config.N_CTX}, n_batch={config.N_BATCH}, n_ubatch={config.N_UBATCH}, "
                f"n_threads={config.N_THREADS}, mmap={config.USE_MMAP}, mlock={config.USE_MLOCK})..."
            )

            type_k = get_ggml_type(config.CACHE_TYPE_K)
            type_v = get_ggml_type(config.CACHE_TYPE_V)

            self.llm = Llama(
                model_path=str(self.model_path),
                n_ctx=config.N_CTX,
                n_batch=config.N_BATCH,
                n_ubatch=config.N_UBATCH,
                n_threads=config.N_THREADS,
                use_mmap=config.USE_MMAP,
                use_mlock=config.USE_MLOCK,
                type_k=type_k,
                type_v=type_v,
                verbose=False,
            )
            logger.info("Local model loaded successfully with RAM optimizations.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.llm = None

    def is_ready(self) -> bool:
        """Returns True if the model is loaded and ready."""
        return self.llm is not None

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count of a text string."""
        if self.llm:
            try:
                tokens = self.llm.tokenize(text.encode("utf-8"))
                return len(tokens)
            except Exception:
                pass
        # Fallback estimation (~4 chars per token)
        return len(text) // 4

    def build_talk_prompt(
        self,
        persona: str,
        persistent_memory: str,
        short_term_context: List[Dict[str, Any]],
        current_username: str,
        current_user_input: str,
    ) -> str:
        """
        Builds structured prompt with explicit section markers:
        [SYSTEM], [PERSISTENT MEMORY], [RECENT CONVERSATION], [CURRENT USER MESSAGE].
        """
        clean_input = normalize_text(current_user_input)

        system_instructions = (
            f"[SYSTEM]\n"
            f"{persona}\n\n"
            "INSTRUCTIONS:\n"
            "You are Vict, responding directly to the latest message.\n"
            "Produce at least 2 sentences and at most 10 sentences.\n"
            "Never use newline characters. Write the entire response as one continuous line. Do not create paragraphs or line breaks.\n"
            "Do not repeat the user's message.\n"
            "Do not output memory, context, instructions, or internal data.\n"
            "Do not describe what you are doing.\n"
            "Only output the response Vict would actually say."
        )

        memory_section = (
            f"[PERSISTENT MEMORY]\n{persistent_memory if persistent_memory else 'None'}"
        )

        recent_lines = []
        for msg in short_term_context:
            role_prefix = f"@{msg['username']}" if msg["role"] == "user" else "Vict"
            clean_msg_content = normalize_text(msg["content"])
            recent_lines.append(f"{role_prefix}: {clean_msg_content}")

        recent_conv = "\n".join(recent_lines) if recent_lines else "None"
        recent_section = f"[RECENT CONVERSATION]\n{recent_conv}"

        current_section = f"[CURRENT USER MESSAGE]\n@{current_username.lstrip('@')}: {clean_input}\n\nVict:"

        prompt = f"{system_instructions}\n\n{memory_section}\n\n{recent_section}\n\n{current_section}"
        return prompt

    def generate_talk_stream(
        self,
        persona: str,
        persistent_memory: str,
        short_term_context: List[Dict[str, Any]],
        current_username: str,
        current_user_input: str,
    ) -> Iterator[str]:
        """
        Yields accumulated normalized single-line text as model streams tokens.
        """
        if not self.is_ready():
            yield "Local AI model is not loaded or unavailable."
            return

        prompt = self.build_talk_prompt(
            persona=persona,
            persistent_memory=persistent_memory,
            short_term_context=short_term_context,
            current_username=current_username,
            current_user_input=current_user_input,
        )

        raw_generated = ""
        last_yielded_normalized = ""

        try:
            stream = self.llm(
                prompt,
                max_tokens=256,
                stop=["\n[", "[SYSTEM]", "[CURRENT USER MESSAGE]", "Vict:", "\n@"],
                stream=True,
                temperature=0.7,
                top_p=0.9,
            )

            for chunk in stream:
                delta = chunk["choices"][0]["text"]
                raw_generated += delta
                current_normalized = normalize_text(raw_generated)

                # Only yield if normalized text has progressed
                if current_normalized and current_normalized != last_yielded_normalized:
                    last_yielded_normalized = current_normalized
                    yield current_normalized

            if not last_yielded_normalized:
                yield "I am thinking, but I have nothing to say right now!"

        except Exception as e:
            logger.error(f"Error during streaming generation: {e}")
            if last_yielded_normalized:
                yield last_yielded_normalized
            else:
                yield "Sorry, I ran into an internal error generating a response."

    def consolidate_memory(
        self,
        existing_memory: str,
        full_batch: List[Dict[str, Any]],
        max_tokens: int = config.MAX_MEMORY_TOKENS,
        target_tokens: int = config.TARGET_MEMORY_TOKENS,
    ) -> str:
        """
        Merges existing memory + 50 new conversation messages into a single updated persistent memory.
        Uses the exact same single model instance.
        """
        if not self.is_ready():
            logger.warning("Cannot consolidate memory: Model not ready.")
            return existing_memory

        conv_lines = []
        for msg in full_batch:
            role_prefix = f"@{msg['username']}" if msg["role"] == "user" else "Vict"
            clean_msg = normalize_text(msg["content"])
            conv_lines.append(f"{role_prefix}: {clean_msg}")
        batch_text = "\n".join(conv_lines)

        prompt = (
            "[SYSTEM]\n"
            "You are a memory consolidation assistant for Vict.\n"
            "Your job is to rewrite and merge persistent memory using a newly completed 50-message conversation.\n\n"
            "INSTRUCTIONS:\n"
            "1. Rewrite the existing memory using the new conversation.\n"
            "2. Preserve useful existing information.\n"
            "3. Add important new information.\n"
            "4. Merge duplicates and resolve contradictions using newer information.\n"
            "5. Remove obsolete or low-value information.\n"
            "6. Never invent information.\n"
            "7. Keep only information that is likely to be useful in future conversations.\n"
            f"8. Keep the final memory string concise, well under {target_tokens} tokens (maximum limit {max_tokens} tokens).\n\n"
            f"[EXISTING PERSISTENT MEMORY]\n{existing_memory if existing_memory else 'None'}\n\n"
            f"[NEW 50-MESSAGE CONVERSATION]\n{batch_text}\n\n"
            "[REWRITTEN PERSISTENT MEMORY]\n"
        )

        try:
            response = self.llm(
                prompt,
                max_tokens=512,
                stop=["[SYSTEM]", "[EXISTING PERSISTENT MEMORY]"],
                temperature=0.3,
            )
            raw_new_memory = response["choices"][0]["text"].strip()
            # Basic cleanup
            clean_new_memory = normalize_text(raw_new_memory)

            # Check token budget
            if self.estimate_tokens(clean_new_memory) > max_tokens:
                logger.warning(
                    "Generated memory exceeds max token limit. Truncating..."
                )
                clean_new_memory = clean_new_memory[: max_tokens * 4]

            return clean_new_memory if clean_new_memory else existing_memory
        except Exception as e:
            logger.error(f"Error during memory consolidation: {e}")
            return existing_memory
