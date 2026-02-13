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
    # TODO: Implement full agentic pipeline
    # For now, return a placeholder response

    query_id = str(uuid.uuid4())

    # Placeholder response
    response = {
        "query_id": query_id,
        "answer": """
        This is a placeholder response. The full agentic pipeline is being implemented.

        The system will:
        1. Route your query through the Query Router Agent
        2. Perform hybrid retrieval (vector + keyword search)
        3. Generate an answer with citations using DeepSeek

        Please check back after the agents are implemented!
        """,
        "citations": [],
        "confidence": 0.0,
    }

    return response


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
