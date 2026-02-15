"""RAG Pipeline - Orchestrates the three-agent system."""

from typing import Dict, Any, Optional
import time
import uuid

from .query_router import get_query_router
from .retriever import get_retriever_agent
from .answer_generator import get_answer_generator
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """
    Orchestrates the complete RAG pipeline.

    Pipeline stages:
    1. Query Router: Classify query intent and determine strategy
    2. Retriever: Execute hybrid search and assemble context
    3. Answer Generator: Generate citation-backed answer using LLM
    """

    def __init__(self):
        """Initialize RAG pipeline."""
        self.router = get_query_router()
        self.retriever = get_retriever_agent()
        self.generator = get_answer_generator()

        logger.info("RAGPipeline initialized with 3 agents")

    def process(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        model: str = "deepseek-reasoner",
    ) -> Dict[str, Any]:
        """
        Process a query through the complete RAG pipeline.

        Args:
            query: User's question
            top_k: Number of chunks to retrieve (uses router suggestion if None)
            min_score: Minimum similarity score (uses router suggestion if None)
            model: LLM model for answer generation

        Returns:
            Dict with:
            - query_id: Unique query identifier
            - query: Original query
            - answer: Generated answer text
            - citations: List of citation details
            - confidence: Overall confidence score
            - metadata: Pipeline execution metadata
        """
        query_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"[{query_id}] Starting RAG pipeline for: '{query[:100]}...'")

        try:
            # Stage 1: Route query
            logger.info(f"[{query_id}] Stage 1/3: Routing query...")
            routing = self.router.route(query)

            query_type = routing['query_type']
            strategy = routing['retrieval_strategy']
            search_params = routing['search_params']

            # Override with user-provided params if specified
            if top_k is not None:
                search_params['top_k'] = top_k
            if min_score is not None:
                search_params['min_score'] = min_score

            logger.info(
                f"[{query_id}] → Classified as '{query_type}', "
                f"strategy='{strategy}', top_k={search_params['top_k']}"
            )

            # Stage 2: Retrieve context
            logger.info(f"[{query_id}] Stage 2/3: Retrieving context...")
            retrieval = self.retriever.retrieve(
                query=query,
                strategy=strategy,
                **search_params
            )

            context = retrieval['context']
            results = retrieval['results']

            logger.info(
                f"[{query_id}] → Retrieved {len(results)} chunks, "
                f"top_score={retrieval['metadata']['top_score']:.3f}"
            )

            # Stage 3: Generate answer
            logger.info(f"[{query_id}] Stage 3/3: Generating answer...")
            generation = self.generator.generate(
                query=query,
                context=context,
                results=results,
                query_type=query_type,
                model=model
            )

            answer = generation['answer']
            citations = generation['citations']
            confidence = generation['confidence']

            logger.info(
                f"[{query_id}] → Generated answer with "
                f"{len(citations)} citations, confidence={confidence:.1%}"
            )

            # Assemble complete response
            elapsed = time.time() - start_time

            response = {
                'query_id': query_id,
                'query': query,
                'answer': answer,
                'citations': citations,
                'confidence': confidence,
                'metadata': {
                    'query_type': query_type,
                    'retrieval_strategy': strategy,
                    'num_chunks_retrieved': len(results),
                    'num_citations_used': len(citations),
                    'top_retrieval_score': results[0]['score'] if results else 0.0,
                    'model': generation['metadata']['model'],
                    'total_latency': elapsed,
                    'routing_latency': routing.get('usage', {}).get('latency', 0),
                    'retrieval_latency': retrieval['metadata']['latency'],
                    'generation_latency': generation['metadata']['latency'],
                    'token_usage': generation['metadata']['usage'],
                }
            }

            logger.info(
                f"[{query_id}] Pipeline complete in {elapsed:.2f}s "
                f"(routing + retrieval + generation)"
            )

            return response

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{query_id}] Pipeline failed after {elapsed:.2f}s: {e}")

            # Return error response
            return {
                'query_id': query_id,
                'query': query,
                'answer': f"I encountered an error while processing your question: {str(e)}",
                'citations': [],
                'confidence': 0.0,
                'metadata': {
                    'error': str(e),
                    'total_latency': elapsed,
                }
            }

    def process_batch(
        self,
        queries: list[str],
        **kwargs
    ) -> list[Dict[str, Any]]:
        """
        Process multiple queries in batch.

        Args:
            queries: List of query strings
            **kwargs: Additional arguments passed to process()

        Returns:
            List of response dicts
        """
        logger.info(f"Processing batch of {len(queries)} queries")

        responses = []
        for query in queries:
            response = self.process(query, **kwargs)
            responses.append(response)

        return responses

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.

        Returns:
            Dict with pipeline stats (queries processed, avg latency, etc.)
        """
        # TODO: Implement statistics tracking
        return {
            'queries_processed': 0,
            'avg_latency': 0.0,
            'avg_confidence': 0.0,
            'model_usage': {},
        }


# Singleton instance
_rag_pipeline = None

def get_rag_pipeline() -> RAGPipeline:
    """Get or create singleton RAGPipeline instance."""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
