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
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help="Minimum confidence threshold for answers",
        )
        st.session_state.min_confidence = min_confidence

        st.divider()

        # System info
        st.subheader("System Info")
        if documents:
            st.metric("Documents", len(documents))
            total_chunks = sum([doc.total_chunks for doc in documents])
            st.metric("Total Chunks", total_chunks)

        st.caption(f"Version: 0.1.0 (MVP)")


def render_chat_interface():
    """Render main chat interface."""
    st.title("💬 Ask About Storage Protocols")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Display citations if available
            if "citations" in message:
                with st.expander("📖 Citations", expanded=False):
                    for i, citation in enumerate(message["citations"], 1):
                        st.markdown(f"""
                        **{i}. {citation.get('source', 'Unknown')}** - Page {citation.get('page', 'N/A')}

                        Section: *{citation.get('section', 'N/A')}*

                        > {citation.get('text', '')}

                        Confidence: {citation.get('confidence', 0):.2%}
                        """)
                        st.divider()

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

                    # Add assistant message
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "citations": response.get("citations", []),
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
    Process user query and generate response.

    Args:
        query: User query

    Returns:
        Response with answer and citations
    """
    query_id = str(uuid.uuid4())

    try:
        # Get retrieval parameters from session state
        top_k = st.session_state.get("top_k", 10)

        # Perform vector search
        vector_store = st.session_state.qdrant_client
        query_vector = vector_store.embed_text(query)

        # Search Qdrant
        search_results = vector_store.client.query_points(
            collection_name='protocol_specs',
            query=query_vector,
            limit=top_k,
            with_payload=True
        )

        if not search_results.points:
            return {
                "query_id": query_id,
                "answer": "I couldn't find any relevant information in the protocol specifications. Please try rephrasing your question.",
                "citations": [],
                "confidence": 0.0,
            }

        # Format citations
        citations = []
        context_parts = []

        for i, point in enumerate(search_results.points[:5], 1):  # Top 5 for context
            payload = point.payload
            score = point.score

            section = payload.get('section_title', 'N/A')
            pages = payload.get('page_numbers', [])
            text = payload.get('text', '')
            doc_id = payload.get('doc_id', 'N/A')

            # Extract protocol and version from doc_id (e.g., "eMMC_5_1_...")
            protocol = "eMMC"
            version = "5.1"

            citation = {
                'source': f"{protocol} {version}",
                'section': section,
                'page': ', '.join(map(str, pages)) if pages else 'N/A',
                'text': text[:300] + '...' if len(text) > 300 else text,
                'confidence': score,
            }
            citations.append(citation)

            # Add to context for answer
            context_parts.append(f"[{i}] From {section} (pages {citation['page']}):\n{text[:500]}")

        # Create context-aware answer
        context = "\n\n".join(context_parts[:3])  # Top 3 chunks

        # Simple answer format (without LLM for now)
        answer = f"""Based on the {protocol} {version} specification:

**Relevant Information:**

{search_results.points[0].payload.get('text', '')[:800]}...

*Please see the citations below for complete details and additional context.*

**Top Match:** {search_results.points[0].payload.get('section_title', 'N/A')} (Confidence: {search_results.points[0].score:.2%})
"""

        response = {
            "query_id": query_id,
            "answer": answer,
            "citations": citations,
            "confidence": search_results.points[0].score if search_results.points else 0.0,
        }

        logger.info(f"Processed query: {query_id}, found {len(citations)} results")
        return response

    except Exception as e:
        logger.error(f"Error in process_query: {e}")
        return {
            "query_id": query_id,
            "answer": f"An error occurred while processing your query: {str(e)}",
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
