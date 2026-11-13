# Salesforce product-catalog integration — selected project path

This project now uses **standard Product2 records with the existing Streamlit storefront and semantic finder**. It does not require a Commerce store, WebStore ID, catalog assignment, D2C provisioning, Business Manager, SLAS, or Commerce checkout.

The connection has been implemented and tested with mocked responses; this workspace has not logged into or changed your Salesforce org. API access in your current Starter trial is still unverified. Check API access before importing or spending more time on Commerce setup.

## 1. Download the update and prepare VS Code

Download the latest repository ZIP and open the inner folder containing `streamlit_app.py` and `requirements.txt` in VS Code. Keep your existing secrets privately and copy them to `.streamlit/secrets.toml` in the updated folder. Stop the old server with Ctrl+C.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The app continues to run with `CATALOG_SOURCE = "demo"` while you configure Salesforce. No need to modify Commerce permissions or assign the empty catalog to a store.

## 2. Verify your org can authorize a platform API integration

In Salesforce Setup, search for **External Client App Manager**. If available, create an app for this local integration:

- Name: `ElectroGuide Catalog Integration`.
- Enable OAuth and select **Manage user data via APIs (api)**.
- Enable the **Client Credentials Flow** if supported by the org/app type.
- In the app's OAuth policies, configure the permitted/run-as user. This user needs API access, Product2 read access, access to Name/ProductCode/Description/IsActive, and Product2 create permission for the import. Update permission is needed only if you explicitly update existing records.
- Save and retrieve the client ID and secret privately. If the app is admin-approved, authorize the integration user according to the app's policy.

Exact app settings depend on the org's available features and policies. Use an approved existing OAuth app if provided by your administrator. If External Client App creation/client credentials/API access is unavailable in this trial, stop and request an API-enabled developer/university org. A basic Salesforce product catalog does not need Commerce licenses, but **it still needs platform API entitlement**. Do not purchase an upgrade solely to try this project without confirming requirements.

[Salesforce OAuth guidance](https://developer.salesforce.com/docs/revenue/placeorder-rest-api/guide/intro-oauth-and-connected-apps.html).

## 3. Add private local settings

Copy the actual My Domain base URL from Setup → My Domain. Use the HTTPS `.my.salesforce.com` domain, including `.develop` or `.sandbox` where your org specifies it. Do not use a `lightning.force.com/lightning/...` page URL.

Add/update these entries in `.streamlit/secrets.toml`, retaining your OpenAI settings:

```toml
CATALOG_SOURCE = "demo"
SALESFORCE_INSTANCE_URL = "https://YOUR-MY-DOMAIN.my.salesforce.com"
SALESFORCE_API_VERSION = ""
SALESFORCE_CLIENT_ID = "YOUR_EXTERNAL_CLIENT_APP_ID"
SALESFORCE_CLIENT_SECRET = "YOUR_LOCAL_CLIENT_SECRET"
SALESFORCE_ACCESS_TOKEN = ""
SALESFORCE_CATALOG_PRICING = "demo_metadata"
```

Never put the completed secrets file or a real token in GitHub or chat. No Salesforce login password is used. If you already have an approved Salesforce-platform OAuth token, it can be supplied via `SALESFORCE_ACCESS_TOKEN` instead; it takes precedence over client credentials. Clear any old B2C SLAS token, which cannot authorize platform Product2 requests. Automatic token refresh during an operation is not implemented; a fresh client-credentials token is obtained by a new owner CLI run when no token is supplied.

Run the gate check:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_salesforce_catalog
```

Success explicitly reports **Product2 API access verified**, not merely that an unauthenticated version endpoint responded. It also reports whether the API user may create/update products and the aggregate count of active project records visible to that user.

If you see `API_DISABLED_FOR_ORG`, this org cannot provide the required API access under its current entitlement. Use an API-enabled academic/developer org and reuse this code and CSV. If you see 401, check OAuth credentials/policy/token expiration. If you see 403 or an object/field access error, have the administrator check API and Product2 permissions. Do not share credential values while troubleshooting.

## 4. Import the standard Product2 sample

Use **[imports/salesforce/product2-100.csv](../imports/salesforce/product2-100.csv?raw=true)**. It has only these standard object fields:

```text
Name,ProductCode,Description,IsActive
```

This file is different from the earlier Commerce-format CSV. Do not upload the earlier `Product Name`/`Category 1`/`Price USD` file into Product2.

Validate locally first — no API calls or writes:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_salesforce_catalog --dry-run
```

After the API check passes and Product2 create access is available, import:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_salesforce_catalog
```

The owner import command **creates Product2 records in your configured Salesforce org**. It is limited to `EG-000001`-style project codes. Existing codes are skipped by default to avoid duplicate creation on reruns; duplicate codes already in Salesforce cause an error. Each batch requests `allOrNone`. If a later batch fails, earlier completed batches remain; rerun normally to skip those already created. The first sample is one 100-record batch. The importer supports up to 50,000 rows, with capacity preflight for files larger than 1,000 rows. Start with 100, then follow the [50k import guide](SALESFORCE_50000.md).

Only when you intentionally want to overwrite matching existing project records with the sample, add `--update-existing`. This option updates Name, ProductCode, Description, and IsActive for matched project records; it is not required for the first import.

Alternatively, an API-enabled Salesforce Data Loader can import this CSV into **Product2** with matching field names. Preserve Description metadata and save success/error reports. Do not assume the generic Data Import Wizard supports Products. Check org storage before expanding beyond the sample.

In Salesforce, open Products and look for an `EG-...` product code. The **catalog record and category hierarchy previously created are not needed by this integration** and can be left as they are.

## 5. Sync products back into the project

```powershell
.\.venv\Scripts\python.exe -m scripts.sync_salesforce_catalog --limit 100
```

The connector reads actual Salesforce Product2 IDs, names, descriptions, active state, and the metadata stored in Description. The project ID stays stable while `salesforce_id` preserves the real Product2 ID. Records without supported demo metadata are rejected rather than assigned invented specifications. A complete validated snapshot is published locally; failed validation leaves the previous snapshot active.

Change this local setting only after sync succeeds:

```toml
CATALOG_SOURCE = "salesforce_catalog_snapshot"
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_semantic_index
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The index uses the selected Salesforce-derived snapshot, reusing unchanged embeddings. The app's one-best-match/two-alternative flow remains. The app does not query Salesforce on every visitor request; rerun sync to pick up changes and rebuild/check the semantic index when descriptions/specifications change.

## 6. Pricing and availability — especially for this INR org

Your earlier org screenshot showed INR. The initial integration deliberately avoids relabeling those values as USD:

- `demo_metadata` mode stores the synthetic USD price and simulated stock in the product Description metadata (`demo_price_usd`, `demo_stock`). The price is read back from Salesforce, but remains an explicitly synthetic demonstration value, not a native price-book offer.
- Product names and descriptions are Salesforce records; category, fictional brand, SKU and technical specs are preserved in the structured demo metadata. No custom Product2 fields or StockKeepingUnit field are required by this path.
- The storefront shows a concise notice that USD demo prices, availability, and checkout are simulated.

An optional `pricebook` mode can read native PricebookEntry prices, but requires a correctly configured price book with **actual USD values**:

```toml
SALESFORCE_CATALOG_PRICING = "pricebook"
SALESFORCE_PRICEBOOK_ID = "YOUR_PRICEBOOK2_ID"
SALESFORCE_PRICEBOOK_CURRENCY = "USD"
SALESFORCE_MULTI_CURRENCY = "true"
```

Set multicurrency true only when it is actually enabled; the query then filters USD. For a single-currency org, the org/selected book must genuinely be USD. The owner must verify this before setting the currency confirmation; the app performs no currency conversion or independent audit of a single-currency org's currency. Do not set this confirmation on an INR book just to pass validation. Price-book read permission and active entries for every synced product are also required. Native prices are snapshots, not live buyer-specific checkout quotes.

## What this demonstrates

**Salesforce product-catalog integration + semantic product recommendation + a Streamlit shopping prototype.** No Commerce store, Salesforce baskets, native inventory, real payments, customer identity system, or Salesforce Commerce checkout is claimed. This is a smaller, accurate MS project scope that retains the existing recommendation work.

### OAuth HTTP 400 troubleshooting

The platform connector now displays recognized OAuth error codes from the token response, such as `invalid_client` or `invalid_grant`, with fixed troubleshooting guidance. It does not print token response bodies, secrets, or arbitrary provider descriptions. `invalid_client` calls for checking the new org's current Consumer Key/Secret and enabled app; `invalid_grant` calls for checking Client Credentials Flow and its active Run As user. A generic HTTP 400 is not evidence of `API_DISABLED_FOR_ORG`. The latter is an explicit API error code, not the conditional explanatory footer printed by the catalog check.

If Settings and Policies both show Client Credentials enabled but authentication still reports no execution user, compare the active local configuration with the exact org/app being edited:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.check_salesforce_oauth --compare-app --test-login
```

The script prints project/current folders, settings-file existence and match flags, a sanitized My Domain base URL, and credential-presence flags. Enter the Current My Domain URL and paste the selected app's Consumer Key at the hidden terminal prompt. The entered key is compared in memory, not printed or written to disk. Do not enter the Consumer Secret at this prompt. A mismatch stops before login. A matching configuration can request a token to reproduce the OAuth result without printing or storing it; no Salesforce records are written. Do not share screenshots of consumer details or secrets.toml.
