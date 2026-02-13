# Storage Protocol Assistant - Agentic RAG System

A high-precision Q&A system for storage protocol specifications (eMMC, UFS, etc.) with zero-tolerance for hallucinations and complete answer traceability.

## Features

- **Multi-Agent Architecture**: Query routing, hybrid retrieval, and answer generation
- **Citation Tracking**: Every answer includes exact page numbers and section references
- **Hybrid Search**: Combines vector similarity and keyword matching
- **Docker-Native**: Easy deployment with docker-compose
- **Streamlit UI**: Interactive chat interface with document viewer

## Quick Start

### Prerequisites

- Docker and Docker Compose
- DeepSeek API key ([Get one here](https://platform.deepseek.com))

### Setup

1. Clone the repository:
```bash
cd storage-protocol-assistant
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
```

3. Launch the system:
```bash
docker-compose up -d
```

4. Upload your first specification:
```bash
# Place your PDF in the specs/ directory
docker-compose exec app python src/ingestion/ingest_spec.py \
  --file /app/specs/your_spec.pdf \
  --protocol "eMMC" \
  --version "5.1"
```

5. Access the UI:
```bash
open http://localhost:8501
```

## Project Structure

```
storage-protocol-assistant/
├── src/
│   ├── agents/              # Agentic components
│   │   ├── query_router.py
│   │   ├── retriever.py
│   │   └── answer_generator.py
│   ├── ingestion/           # Document processing
│   │   ├── pdf_parser.py
│   │   ├── chunker.py
│   │   └── ingest_spec.py
│   ├── retrieval/           # Search components
│   │   ├── vector_search.py
│   │   ├── keyword_search.py
│   │   └── hybrid_search.py
│   ├── models/              # Data models
│   │   └── schemas.py
│   ├── utils/               # Utilities
│   │   ├── config.py
│   │   └── logger.py
│   └── database/            # Database clients
│       ├── qdrant_client.py
│       └── sqlite_client.py
├── app.py                   # Main Streamlit app
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Development

### Local Development (without Docker)

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start Qdrant locally:
```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

4. Run the Streamlit app:
```bash
streamlit run app.py
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black src/ tests/
flake8 src/ tests/
```

## Architecture

This MVP implements a simplified 3-agent pipeline:

1. **Query Router Agent**: Classifies queries and extracts key terms
2. **Hybrid Retriever Agent**: Combines vector and keyword search
3. **Answer Generator Agent**: Produces citations-backed answers

For detailed architecture, see [docs/PRD_V2.md](docs/PRD_V2.md).

## Configuration

Key configuration options in `.env`:

- `DEEPSEEK_API_KEY`: Your DeepSeek API key
- `QDRANT_URL`: Qdrant connection URL
- `TOP_K`: Number of chunks to retrieve (default: 10)
- `CHUNK_SIZE`: Size of text chunks (default: 500 tokens)

## Monitoring

- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Application Logs**: `docker-compose logs -f app`
- **Query Audit**: Stored in `data/metadata.db`

## Troubleshooting

### Qdrant connection issues
```bash
# Check Qdrant is running
docker-compose ps qdrant
# View logs
docker-compose logs qdrant
```

### PDF parsing errors
- Ensure PDFs are text-based (not scanned images)
- Check file permissions in the specs/ directory

### API rate limits
- DeepSeek API has rate limits; implement exponential backoff if needed
- Consider caching frequent queries

## Roadmap

### Week 1 (MVP) ✅
- [x] Docker setup
- [x] Basic PDF ingestion
- [x] 3-agent pipeline
- [x] Streamlit UI

### Week 2-3 (Enhancements)
- [ ] React UI with PDF highlighting
- [ ] LangGraph orchestration
- [ ] Advanced table extraction
- [ ] Multi-document comparison

### Week 4+ (Production)
- [ ] PostgreSQL migration
- [ ] Monitoring & logging
- [ ] Performance optimization
- [ ] User feedback system

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourorg/storage-protocol-assistant/issues)
- Documentation: [docs/](docs/)

## Acknowledgments

Built with:
- [Streamlit](https://streamlit.io/)
- [Qdrant](https://qdrant.tech/)
- [DeepSeek](https://deepseek.com/)
- [Unstructured.io](https://unstructured.io/)
