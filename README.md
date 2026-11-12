# ElectroGuide Commerce + RAG

An MS final-year project foundation for a US electronics storefront with Salesforce B2C Commerce integration and grounded shopping recommendations.

**Current status:** runnable local Streamlit electronics shop, synthetic catalog, lexical search, optional OpenAI explanations, and a read-only Salesforce B2C connection test. Real Salesforce catalog/cart/order integration, automatic OAuth login, vector retrieval, payment processing, and durable customer accounts are not implemented.

## Run the Streamlit website (recommended)

[Windows and VS Code setup guide](docs/WINDOWS_STREAMLIT.md)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Visit http://localhost:8501. The bundled catalog is extracted and indexed automatically. No credentials are needed for local shopping. To enable external calls, copy `.streamlit/secrets.toml.example` to the ignored `.streamlit/secrets.toml`, enter values locally, and use Connections to test. Never paste secrets into chat or commit them.

## Run the standalone catalog API (optional)
Requires Python 3.10+ with SQLite FTS5; no third-party dependencies or API key needed.

```bash
python scripts/generate_catalog.py --count 50000 --seed 42
python -m scripts.build_index
python -m unittest discover -s tests -v
python -m app.server
```

Then visit:
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/products?q=laptop&max_price=900&limit=5`
- `http://127.0.0.1:8000/products?category=tv&max_price=1000`

Use keyword queries for this baseline. Natural-language intent and budget extraction are planned. The API is a local development server, not a production deployment.

## Data

[Download the full 50,000-product catalog ZIP](data/electroguide-catalog-50000.zip?raw=true), containing CSV, JSONL, and a provenance/checksum manifest. Extract it into `data/` to skip catalog generation, then build the index as above.
50,000 unique fictional SKUs, 5,000 per category: TV, mobile, laptop, tablet, smartwatch, headphones, camera, monitor, speaker, and gaming console. Prices, stock, brands, and specifications are synthetic; images are absent. This is a controlled experimental dataset, not 50,000 real-world models. Uncompressed generated exports and the SQLite index are ignored by Git; regenerate them with the command above. A small committed sample makes the schema easy to inspect. The generator writes `data/manifest.json` with provenance, count, seed, and JSONL checksum.

## Credentials
No API key is included. Local catalog features require none; OpenAI explanations require a key configured locally. Revoke any key previously posted in chat. Supply a replacement only through secure environment configuration when the server-side LLM integration is ready. `.streamlit/secrets.toml.example` documents the active Streamlit settings. A `.env` file is not automatically loaded. Never expose an LLM key in browser code.

## Academic and implementation documents
- [Project scope, architecture, milestones, and evaluation](docs/PROJECT_PLAN.md)
- [Salesforce integration checklist](docs/SALESFORCE_SETUP.md)
- [Fictional store policies for future RAG](knowledge/store-policies.md)

All policies and inventory are academic examples. This project accepts no real purchases and makes no real product or warranty claims.
