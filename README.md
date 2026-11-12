# ElectroGuide

A minimal electronics storefront for an MS project: browse products, describe what you need, and see **one best catalog match plus up to two alternatives**.

![Storefront](assets/storefront-preview.png)

![Three recommendations](assets/matches-preview.png)

## Run on Windows / VS Code

Open the folder containing `streamlit_app.py` in VS Code, then run these commands one at a time:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open http://localhost:8501. Stop an older running server with Ctrl+C before starting the new version. [Full Windows guide](docs/WINDOWS_STREAMLIT.md).

## Customer experience

Three top navigation buttons: **Shop**, **Find my match**, and **Bag**. No sidebar, compare, wishlist, dashboard, or connection settings in the customer interface. The shop has a short discovery form and a searchable, paginated collection. The finder returns at most three distinct catalog configurations, with factual specification/price reasons; the bag supports a clearly labeled simulated checkout. State is session-only.

Try: `A laptop for studying under $1500 with at least 16GB RAM`.

## Where OpenAI and Salesforce are used

| Component | Current role | Current limitation |
| --- | --- | --- |
| Local catalog | Supplies the storefront and all product recommendations | 50,000 fictional SKUs; prices, stock, and specifications are synthetic |
| OpenAI API key | Server-side calls interpret requests, embed catalog/query text for semantic retrieval, and explain the selected products | Optional; requires a valid locally configured replacement key and billing/model access. Without it, specification-based matching still works and is labeled accordingly |
| Salesforce B2C Commerce | Read-only SCAPI product-search diagnostic, run by the owner from the terminal | Not connected to storefront inventory, recommendations, baskets, or orders; no live credentials have been verified |

The app does **not** claim that Salesforce is already powering the shopping flow. The next Salesforce integration step requires the actual B2C Business Manager/API identifiers and a configured shopper OAuth flow, followed by catalog mapping, price/stock validation, and basket integration. A Lightning Commerce Stores URL alone does not verify these capabilities.

## Matching behavior

[Enable semantic search and requirements comparison](docs/SEMANTIC_SEARCH.md). Build the local embedding index once with `python -m scripts.build_semantic_index`; embeddings use your OpenAI account. A no-cost `--dry-run` reports the document count.

Category, budget, in-stock status, and supported requested specifications are hard filters. Supported specifications include minimum RAM, storage and battery hours, exact screen size, resolution, listed noise cancellation, and available fictional brand. When an embedding index and key are available, eligible products are ranked using OpenAI query/catalog cosine similarity, feature/price signals, and keyword overlap. Otherwise a labeled feature/price fallback is used. Alternatives favor different specifications. A collapsible factual table compares the selected products against the shopper’s requirements.

The LLM can extract requirements but cannot override explicitly parsed budget/spec constraints. Final cards and prices come from actual catalog records. Known unsupported requirements are flagged. If no records qualify, no product is invented and constraints are not silently relaxed. The first card is a **best catalog match under this heuristic**, not a guaranteed best real-world product. Real-brand requests cannot be satisfied by the fictional catalog. Learned personalization and a comprehensive natural-language constraint engine remain future work. Semantic ranking weights are initial experimental settings; live embedding relevance has not been evaluated here. Generated explanations should be verified against the displayed facts.

## Configure credentials locally

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` only if your local file does not already exist. Enter a replacement OpenAI key there privately; revoke any key previously posted in chat. Never commit or share the completed file. Environment variables with the same names are also supported. No `.env` file is automatically loaded.

Owner diagnostics have moved out of the storefront:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_connections
```

This explicitly calls OpenAI (which may incur a charge) and the Salesforce search endpoint when their configuration is present, and prints sanitized connection status. No Salesforce password is accepted; B2C SCAPI uses short code, organization ID, site ID, and a valid SLAS shopper access token. Automatic OAuth/token refresh is not implemented.

## Data and checks

[Download the full catalog ZIP](data/electroguide-catalog-50000.zip?raw=true). It contains JSONL, CSV, and a provenance/checksum manifest. Ten categories contain 5,000 synthetic SKUs each. Category illustrations are original local SVG depictions, not manufacturer photographs. The app extracts the bundled v2 catalog and builds its index on first run. Back up manually edited generated data before upgrading.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For the optional standalone lexical API: `python scripts/generate_catalog.py`, `python -m scripts.build_index`, then `python -m app.server`. Streamlit does not require that server.

[Project research plan](docs/PROJECT_PLAN.md) · [Salesforce prerequisites](docs/SALESFORCE_SETUP.md)

No real payments, persistent customer accounts, real orders, live inventory synchronization, or Salesforce checkout are implemented.
