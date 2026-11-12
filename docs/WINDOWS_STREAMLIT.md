# Run ElectroGuide in VS Code on Windows

## 1. Update your project
Download the latest ZIP from GitHub (Code → Download ZIP). Extract it under:

`D:\Downloads-2\Imp Docs\UMASSD\Project-2026`

Open the folder that actually contains `streamlit_app.py`, `requirements.txt`, and `README.md` in VS Code. A ZIP download usually adds a nested `electroguide-commerce-rag-main` directory. Existing local secrets should be kept separately and copied back to the ignored secrets path after updating; never overwrite them with an example file. Do not upload your completed secrets file to GitHub.

## 2. Install and launch
Install the Microsoft Python and Python Debugger extensions in VS Code. Open Terminal → New Terminal (PowerShell). No administrator permissions or execution-policy changes are needed:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open **http://localhost:8501**. The first launch extracts the bundled 50,000-product catalog and builds the search index automatically. You do not need to run `app.server`; Streamlit reads the catalog directly. Press Ctrl+C in the terminal to stop.

In VS Code, run “Python: Select Interpreter” and choose `.venv\Scripts\python.exe`. The included Run and Debug configuration “ElectroGuide: Streamlit” then supports F5 launching.

## 3. Add local secrets
In VS Code Explorer enable viewing dot folders if needed. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`:

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Run that copy command only when the destination does not already contain your values. Edit the new file in VS Code. Insert a NEW OpenAI key locally after revoking the key exposed in chat. Do not paste secrets back into chat. The file is ignored by Git and not displayed by the app. It is a plain text local file, so keep it out of public/shared folders and cloud-sync destinations you do not trust. Environment variables with the same names are also supported; a populated secrets file takes precedence.

Set `OPENAI_MODEL` to a model available to your account (default `gpt-4o-mini`). Restart Streamlit, open Connections, and click “Test OpenAI connection”. Tests and assistant questions use your account and may incur charges. Questions, the retrieved synthetic products, and demo policies are sent to OpenAI when configured; credentials are sent only to the corresponding provider.

## 4. Salesforce B2C connection
Do not enter your Salesforce username or password. The app needs `SALESFORCE_SHORT_CODE`, `SALESFORCE_ORGANIZATION_ID`, `SALESFORCE_SITE_ID`, and a current `SALESFORCE_ACCESS_TOKEN` obtained through your sandbox's configured SLAS shopper OAuth flow.

A Lightning Commerce Stores URL alone does not establish that these B2C APIs are available. Obtain these identifiers through B2C administration or your Salesforce administrator; if you only have Salesforce-platform Commerce, the integration must be adapted to that product.

The Connections page makes a read-only product-search request and shows a small sanitized result. It does not import products, synchronize your catalog, create baskets, or place Salesforce orders. Tokens expire and must currently be refreshed outside this app. Automated OAuth login/token refresh remains future work.

## 5. What works and what is simulated
- Shop, specifications, category/budget filters, compare up to four devices, cart, wishlist.
- Demo orders and read-only catalog dashboard. Browser-session storage only; closing/reloading the session can lose these records.
- Category/budget retrieval with an optional OpenAI explanation using retrieved product records and policy sources. This is an initial lexical grounding pipeline, not vector retrieval or full personalized recommendation. Review generated explanations against source cards.
- Read-only external B2C product-search test when valid credentials are configured.
- No real payments, customer login, durable order storage, live inventory synchronization, or Salesforce order placement.

## Troubleshooting
- `No module named streamlit`: use the exact `.venv\Scripts\python.exe` install and launch commands above.
- `File does not exist: streamlit_app.py`: the terminal is in the wrong folder. Open the folder containing that file.
- Port 8501 is occupied: append `--server.port 8502` and open http://localhost:8502.
- Invalid secrets TOML: put values inside double quotes and avoid stray quotation marks/newlines. Never share a screenshot containing values.
- OpenAI HTTP 401/429: check the replacement key, model access, billing, or quota locally.
- Salesforce HTTP 401/403: check SLAS token expiration, shopper scopes, organization, and site assignment.
