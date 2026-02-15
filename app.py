"""Main Streamlit application for Storage Protocol Assistant."""

import streamlit as st
import uuid
from datetime import datetime
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="Storage Protocol Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import after streamlit config
from src.utils.config import settings
from src.utils.logger import setup_logging, get_logger
from src.database.qdrant_client import QdrantVectorStore
from src.database.sqlite_client import SQLiteClient
from src.agents.rag_pipeline import get_rag_pipeline

# Initialize logging
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_id" not in st.session_state:
    st.session_state.query_id = None


def initialize_components():
    """Initialize database clients and agents."""
    if "qdrant_client" not in st.session_state:
        try:
            st.session_state.qdrant_client = QdrantVectorStore()
            st.session_state.sqlite_client = SQLiteClient()
            logger.info("Components initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            st.error(f"Failed to connect to services: {e}")
            st.stop()


def render_sidebar():
    """Render sidebar with filters and settings."""
    with st.sidebar:
        st.title("📚 Protocol Assistant")

        st.divider()

        # Document selection
        st.subheader("Document Filters")

        try:
            documents = st.session_state.sqlite_client.list_documents()

            if documents:
                protocols = list(set([doc.protocol for doc in documents]))
                selected_protocols = st.multiselect(
                    "Select Protocols",
                    options=protocols,
                    default=protocols,
                )

                versions = list(set([doc.version for doc in documents]))
                selected_versions = st.multiselect(
                    "Select Versions",
                    options=versions,
                    default=versions,
                )

                st.session_state.filter_protocols = selected_protocols
                st.session_state.filter_versions = selected_versions
            else:
                st.info("No documents uploaded yet")
                st.session_state.filter_protocols = []
                st.session_state.filter_versions = []

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            st.error("Error loading document list")

        st.divider()

        # Settings
        st.subheader("Settings")

        retrieval_top_k = st.slider(
            "Top-K Results",
            min_value=5,
            max_value=20,
            value=settings.top_k,
            help="Number of chunks to retrieve",
        )
        st.session_state.top_k = retrieval_top_k

        min_confidence = st.slider(
            "Minimum Confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            help="Minimum similarity score threshold (0.0 = no threshold)",
        )
        st.session_state.min_score = min_confidence if min_confidence > 0 else None

        retrieval_strategy = st.selectbox(
            "Retrieval Strategy",
            options=["auto", "vector", "hybrid"],
            index=0,
            help="'auto' lets the router decide. 'vector' uses semantic search. 'hybrid' combines vector + BM25 keyword search.",
        )
        st.session_state.retrieval_strategy = retrieval_strategy

        use_llm = st.toggle(
            "🤖 Use LLM (DeepSeek)",
            value=True,
            help="Enable AI-powered answer generation with citations. Requires DeepSeek API key."
        )
        st.session_state.use_llm = use_llm

        if use_llm:
            st.info("✨ LLM mode: Generates comprehensive answers with citations")
        else:
            st.warning("⚠️ Simple mode: Shows raw retrieval results only")

        st.divider()

        # System info
        st.subheader("System Info")
        if documents:
            st.metric("Documents", len(documents))
            total_chunks = sum([doc.total_chunks for doc in documents])
            st.metric("Total Chunks", total_chunks)

        st.caption(f"Version: 0.1.0 (MVP)")


def _resolve_doc_source(doc_id: str) -> str:
    """Resolve doc_id to a human-readable source name via SQLite."""
    try:
        db = st.session_state.get("sqlite_client")
        if db:
            doc = db.get_document(doc_id)
            if doc:
                return f"{doc.protocol} {doc.version}"
    except Exception:
        pass
    return doc_id


def _render_reasoning_steps(metadata: dict):
    """Render pipeline reasoning steps in an expander."""
    with st.expander("🔍 Agent Reasoning", expanded=False):
        cols = st.columns(3)
        with cols[0]:
            query_type = metadata.get("query_type", "N/A")
            st.markdown(f"**Query Type:** `{query_type}`")
        with cols[1]:
            strategy = metadata.get("retrieval_strategy", "N/A")
            st.markdown(f"**Strategy:** `{strategy}`")
        with cols[2]:
            chunks = metadata.get("num_chunks_retrieved", "N/A")
            st.markdown(f"**Chunks Retrieved:** `{chunks}`")

        # Latency breakdown
        total = metadata.get("total_latency")
        if total is not None:
            st.markdown("**Latency Breakdown:**")
            routing_ms = metadata.get("routing_latency", 0) * 1000
            retrieval_ms = metadata.get("retrieval_latency", 0) * 1000
            generation_ms = metadata.get("generation_latency", 0) * 1000
            st.markdown(
                f"- Routing: `{routing_ms:.0f}ms` · "
                f"Retrieval: `{retrieval_ms:.0f}ms` · "
                f"Generation: `{generation_ms:.0f}ms` · "
                f"**Total: `{total * 1000:.0f}ms`**"
            )

        # Token usage
        usage = metadata.get("token_usage", {})
        if usage:
            prompt_tok = usage.get("prompt_tokens", 0)
            completion_tok = usage.get("completion_tokens", 0)
            st.markdown(
                f"**Tokens:** prompt={prompt_tok}, completion={completion_tok}"
            )


def render_chat_interface():
    """Render main chat interface."""
    st.title("💬 Ask About Storage Protocols")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Display citations if available
            if "citations" in message and message["citations"]:
                with st.expander("📖 Citations", expanded=False):
                    for i, citation in enumerate(message["citations"], 1):
                        st.markdown(f"""
                        **{i}. {citation.get('source', 'Unknown')}** - Page {citation.get('page', 'N/A')}

                        Section: *{citation.get('section', 'N/A')}*

                        > {citation.get('text', '')}

                        Confidence: {citation.get('confidence', 0):.2%}
                        """)
                        st.divider()

            # Display reasoning steps if available
            if "metadata" in message and message["metadata"]:
                _render_reasoning_steps(message["metadata"])

    # Chat input
    if prompt := st.chat_input("Ask a question about storage protocols..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    response = process_query(prompt)

                    # Display response
                    st.markdown(response["answer"])

                    metadata = response.get("metadata", {})

                    # Add assistant message
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "citations": response.get("citations", []),
                        "metadata": metadata,
                    })

                    # Display citations
                    if response.get("citations"):
                        with st.expander("📖 Citations", expanded=True):
                            for i, citation in enumerate(response["citations"], 1):
                                st.markdown(f"""
                                **{i}. {citation.get('source', 'Unknown')}** - Page {citation.get('page', 'N/A')}

                                Section: *{citation.get('section', 'N/A')}*

                                > {citation.get('text', '')}

                                Confidence: {citation.get('confidence', 0):.2%}
                                """)
                                st.divider()

                    # Display reasoning steps
                    if metadata:
                        _render_reasoning_steps(metadata)

                except Exception as e:
                    logger.error(f"Error processing query: {e}")
                    error_msg = "Sorry, I encountered an error processing your question. Please try again."
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })


def process_query(query: str) -> dict:
    """
    Process user query using RAG pipeline.

    Args:
        query: User query

    Returns:
        Response with answer and citations
    """
    try:
        # Get parameters from session state
        top_k = st.session_state.get("top_k", 10)
        min_score = st.session_state.get("min_score", None)
        use_llm = st.session_state.get("use_llm", True)
        strategy_override = st.session_state.get("retrieval_strategy", "auto")

        if use_llm:
            # Use full RAG pipeline with LLM
            pipeline = get_rag_pipeline()

            # Apply strategy override if not "auto"
            kwargs = {
                "query": query,
                "top_k": top_k,
                "min_score": min_score,
                "model": "deepseek-reasoner",
            }
            if strategy_override != "auto":
                kwargs["strategy_override"] = strategy_override

            response = pipeline.process(**kwargs)

            # Format citations for UI
            formatted_citations = []
            for cit in response['citations']:
                pages = ', '.join(map(str, cit['page_numbers'])) if cit['page_numbers'] else 'N/A'
                source = _resolve_doc_source(cit.get('doc_id', ''))
                formatted_citations.append({
                    'source': source,
                    'section': cit['section_path'],
                    'page': pages,
                    'text': cit['text_preview'],
                    'confidence': cit['score'],
                })

            return {
                "query_id": response['query_id'],
                "answer": response['answer'],
                "citations": formatted_citations,
                "confidence": response['confidence'],
                "metadata": response.get('metadata', {}),
            }

        else:
            # Fallback to simple vector search (legacy mode)
            query_id = str(uuid.uuid4())
            vector_store = st.session_state.qdrant_client

            results = vector_store.search(
                query=query,
                top_k=top_k,
                min_score=min_score
            )

            if not results:
                return {
                    "query_id": query_id,
                    "answer": "I couldn't find any relevant information. Please try rephrasing your question.",
                    "citations": [],
                    "confidence": 0.0,
                }

            # Simple answer without LLM
            top_result = results[0]
            answer = f"""**Relevant Information:**

{top_result['text'][:800]}...

*This is a simple retrieval result. Enable LLM mode for comprehensive answers with citations.*

**Top Match:** {top_result.get('section_title', 'N/A')} (Confidence: {top_result['score']:.2%})
"""

            citations = []
            for result in results[:5]:
                pages = ', '.join(map(str, result.get('page_numbers', [])))
                source = _resolve_doc_source(result.get('doc_id', ''))
                citations.append({
                    'source': source,
                    'section': result.get('section_title', 'N/A'),
                    'page': pages or 'N/A',
                    'text': result.get('text', '')[:300] + '...',
                    'confidence': result.get('score', 0.0),
                })

            return {
                "query_id": query_id,
                "answer": answer,
                "citations": citations,
                "confidence": results[0]['score'],
            }

    except Exception as e:
        logger.error(f"Error in process_query: {e}")
        return {
            "query_id": str(uuid.uuid4()),
            "answer": f"An error occurred: {str(e)}\n\nPlease check that your DeepSeek API key is set correctly.",
            "citations": [],
            "confidence": 0.0,
        }


def main():
    """Main application entry point."""
    # Initialize components
    initialize_components()

    # Render UI
    render_sidebar()
    render_chat_interface()

    # Footer
    st.divider()
    st.caption(
        "Storage Protocol Assistant - Built with Streamlit, Qdrant, and DeepSeek"
    )


if __name__ == "__main__":
    main()
