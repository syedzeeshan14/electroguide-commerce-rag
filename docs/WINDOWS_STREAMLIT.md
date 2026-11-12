# Windows and VS Code setup

## Update into a clean folder
Download the latest GitHub ZIP and extract it under `D:\Downloads-2\Imp Docs\UMASSD\Project-2026`. Open the **inner folder containing `streamlit_app.py` and `requirements.txt`** in VS Code. Avoid opening an outer ZIP folder or running `app/server.py` directly.

Keep any existing `.streamlit/secrets.toml` privately, and copy it into the corresponding folder in the new checkout. It is not included in the download and must not be uploaded to GitHub. Back up manual changes to generated `data/products.jsonl`, `products.csv`, and `manifest.json`; older generated catalogs are replaced by the bundled catalog v2 on first launch. The app does not modify your secrets.

## Install and launch
Install a current Python version (Python 3.12 recommended) and Microsoft's Python/Python Debugger extensions for VS Code. Stop the old Streamlit server with Ctrl+C in its terminal. In the new project's terminal:

```powershell
Get-Item requirements.txt, streamlit_app.py
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Run one command at a time; stop if installation fails and inspect the first actual error. The pip update notice is informational. Visit **http://localhost:8501**. The first run extracts/indexes the included catalog. No separate catalog API server is needed.

For F5 launching, select `.venv\Scripts\python.exe` using “Python: Select Interpreter”, then use “ElectroGuide: Streamlit” in Run and Debug. Do not click Run Python File on `app/server.py`.

## Local API settings (owner only)
If `.streamlit/secrets.toml` does not exist, copy `.streamlit/secrets.toml.example` to that name and edit it in VS Code. It is a plain text, Git-ignored local file, so keep it in a private folder. A populated secrets file takes precedence over environment variables. No `.env` file is loaded.

Use a NEW OpenAI key after revoking any key exposed in chat. Set `OPENAI_MODEL` to a supported model (default `gpt-4o-mini`). Restart Streamlit. For semantic retrieval, first follow [the semantic index setup](SEMANTIC_SEARCH.md). The Find my match submission uses OpenAI to extract preferences and embed the query, filters local catalog records, ranks them against cached product embeddings, and asks OpenAI for a concise explanation. Without a ready index, the finder uses its labeled specification-based fallback. Requests and selected synthetic product records are sent to OpenAI; usage can incur charges. If OpenAI is unavailable, the app uses and labels specification-based matching.

Salesforce settings are `SALESFORCE_SHORT_CODE`, `SALESFORCE_ORGANIZATION_ID`, `SALESFORCE_SITE_ID`, and `SALESFORCE_ACCESS_TOKEN` (a valid SLAS shopper OAuth access token). Never use your Salesforce password. A Lightning Commerce Stores URL alone does not establish B2C SCAPI access. Verify the licensed product and B2C API configuration with your administrator. Tokens currently must be obtained/refreshed outside this app.

Test credentials privately in the terminal:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_connections
```

The owner diagnostic performs an OpenAI test request and a read-only Salesforce product-search request when configured. It prints connection status without credential values. There is no customer-facing Connections page. **Salesforce currently does not supply the shop or create orders.** Live catalog, price/stock, basket, and checkout integration remains pending valid setup and implementation.

## What shoppers see
- Three top buttons: Shop, Find my match, Bag.
- A search/requirements form, simple catalog filters, and product cards.
- One best catalog match plus up to two alternatives; unsupported requirements and no-match cases are explicit.
- Session-only bag and clearly labeled demo checkout.
- No sidebar, compare, wishlist, catalog dashboard, or setup controls.

The catalog is synthetic; “best” means best under the implemented feature/price heuristic among eligible records. It is not a guarantee about real-world performance. Learned personalization, real customer accounts, durable orders, live Salesforce inventory, and real payments are not implemented. Vector retrieval is available after building the local semantic index with your OpenAI account.

## Troubleshooting
- `No module named streamlit`: install requirements with the exact `.venv\Scripts\python.exe` command above. Read the first installation error before trying to launch again.
- Missing requirements/app file: open the inner extracted project folder.
- Port 8501 occupied: stop the older app, or append `--server.port 8502` and visit localhost:8502.
- Import errors after replacing files: stop the old server and launch a fresh process from the updated folder.
- OpenAI 401/429: verify key, model access, billing/quota locally.
- Salesforce 401/403: verify SLAS token expiration, scopes, organization, and site assignment.
- Never share screenshots containing secret values.
