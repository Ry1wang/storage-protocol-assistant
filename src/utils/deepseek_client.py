"""DeepSeek API client for LLM integration."""

import time
from typing import List, Dict, Any, Optional
from openai import OpenAI

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)


class DeepSeekClient:
    """
    Client for interacting with DeepSeek API.

    Supports both DeepSeek-Chat (fast routing/classification) and
    DeepSeek-Reasoner (deep reasoning for answer generation).
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key (uses settings.deepseek_api_key if not provided)
        """
        self.api_key = api_key or settings.deepseek_api_key
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable.")

        # Initialize OpenAI-compatible client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

        logger.info("DeepSeek client initialized")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.0,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion using DeepSeek.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (deepseek-chat or deepseek-reasoner)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional API parameters

        Returns:
            Response dict with 'content', 'model', 'usage', etc.
        """
        start_time = time.time()

        try:
            logger.debug(f"Calling DeepSeek API with model={model}, messages={len(messages)}")

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )

            elapsed = time.time() - start_time

            if stream:
                return response

            # Extract response content
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            # Extract usage info
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens,
            }

            result = {
                'content': content,
                'model': response.model,
                'finish_reason': finish_reason,
                'usage': usage,
                'latency': elapsed,
            }

            logger.info(
                f"DeepSeek API call completed: model={model}, "
                f"tokens={usage['total_tokens']}, latency={elapsed:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            raise

    def classify_query(
        self,
        query: str,
        categories: List[str],
        examples: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Classify a query into predefined categories using DeepSeek-Chat.

        Args:
            query: User query to classify
            categories: List of possible categories
            examples: Optional dict mapping categories to example queries

        Returns:
            Dict with 'category', 'confidence', and 'reasoning'
        """
        # Build classification prompt
        prompt_parts = [
            "You are a query classification expert for a storage protocol Q&A system.",
            f"\nClassify the following query into one of these categories: {', '.join(categories)}",
        ]

        if examples:
            prompt_parts.append("\n\nExamples:")
            for cat, example_list in examples.items():
                for ex in example_list:
                    prompt_parts.append(f"- '{ex}' → {cat}")

        prompt_parts.append(f"\n\nQuery to classify: '{query}'")
        prompt_parts.append("\nRespond with ONLY the category name (no explanation).")

        prompt = "\n".join(prompt_parts)

        messages = [
            {"role": "system", "content": "You are a precise query classifier."},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(
            messages=messages,
            model="deepseek-chat",
            temperature=0.0,
            max_tokens=50
        )

        category = response['content'].strip()

        # Validate category
        if category not in categories:
            logger.warning(f"Invalid category '{category}', defaulting to first category")
            category = categories[0]

        return {
            'category': category,
            'confidence': 1.0,  # DeepSeek doesn't provide confidence scores
            'reasoning': f"Classified as '{category}' based on query content",
            'usage': response['usage'],
        }

    def generate_answer(
        self,
        query: str,
        context: str,
        instructions: Optional[str] = None,
        model: str = "deepseek-reasoner",
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Generate an answer to a query using retrieved context.

        Args:
            query: User's question
            context: Retrieved context from vector search
            instructions: Optional additional instructions
            model: Model to use (deepseek-reasoner recommended)
            temperature: Sampling temperature

        Returns:
            Dict with 'answer', 'citations', 'confidence', 'usage'
        """
        # Build answer generation prompt
        system_prompt = """You are an expert assistant for storage protocol specifications (eMMC, UFS, SD Card).

Your task is to answer questions based ONLY on the provided context from the specifications.

CRITICAL RULES:
1. ONLY use information from the provided context
2. EVERY claim must include a citation [1], [2], etc.
3. If the context doesn't contain the answer, say "I cannot answer this based on the provided context"
4. Do NOT hallucinate or make up information
5. Be precise and technical - this is for engineers

Format:
- Use clear paragraphs
- Include citations after each claim: [1], [2], etc.
- End with a "Sources:" section listing all citations"""

        if instructions:
            system_prompt += f"\n\nAdditional instructions:\n{instructions}"

        user_prompt = f"""Context from specifications:

{context}

---

Question: {query}

Please provide a detailed, citation-backed answer."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=4000
        )

        return {
            'answer': response['content'],
            'model': response['model'],
            'usage': response['usage'],
            'latency': response['latency'],
        }

    def extract_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from text using DeepSeek-Chat.

        Args:
            prompt: Extraction prompt
            schema: Optional JSON schema for validation

        Returns:
            Extracted JSON object
        """
        messages = [
            {"role": "system", "content": "You extract structured JSON from text. Respond with ONLY valid JSON, no markdown or explanation."},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(
            messages=messages,
            model="deepseek-chat",
            temperature=0.0,
            max_tokens=2000
        )

        import json
        try:
            result = json.loads(response['content'])
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from DeepSeek response: {e}")
            # Try to extract JSON from markdown code blocks
            content = response['content']
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
                return json.loads(json_str)
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
                return json.loads(json_str)
            raise


# Singleton instance for easy access
_deepseek_client = None

def get_deepseek_client() -> DeepSeekClient:
    """Get or create singleton DeepSeek client."""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    return _deepseek_client
