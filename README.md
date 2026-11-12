# ElectroGuide Commerce + RAG

An MS final-year project foundation for a US electronics storefront with Salesforce B2C Commerce integration and grounded shopping recommendations.

**Current status: milestone 1 implemented.** Includes a 50,000-product synthetic dataset generator, CSV/JSONL export, SQLite lexical search baseline, local read API, tests, academic plan, and Salesforce prerequisites. The storefront, vector RAG, OpenAI integration, Salesforce connection, authentication, dashboard, and checkout are planned; they are not implemented or deployed yet.

## Run locally
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
No API key is included, needed, or used at this stage. Revoke any key previously posted in chat. Supply a replacement only through secure environment configuration when the server-side LLM integration is ready. `.env.example` documents planned names and contains no values. Milestone 1 does not load a `.env` file. Never expose an LLM key in browser code.

## Academic and implementation documents
- [Project scope, architecture, milestones, and evaluation](docs/PROJECT_PLAN.md)
- [Salesforce integration checklist](docs/SALESFORCE_SETUP.md)
- [Fictional store policies for future RAG](knowledge/store-policies.md)

All policies and inventory are academic examples. This project currently accepts no purchases and makes no real product or warranty claims.
