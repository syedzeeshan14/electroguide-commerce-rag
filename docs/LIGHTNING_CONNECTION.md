# Connect the project to Lightning D2C Commerce

## Scope of this implementation

This connector supports an **owner-operated academic demonstration**. It can read imported ElectroGuide products, verify that a product detail request succeeds in a configured Commerce store context, read prices from an explicitly chosen price book, and publish a local catalog snapshot used by the existing Streamlit shop and semantic finder.

It does not implement public shopper login, per-visitor entitlements, real-time buyer pricing, Salesforce inventory, cart/checkout writes, or anonymous guest API access. A server-side integration user's access must not be treated as authorization for arbitrary shoppers. D2C guest/registered shopper authentication requires its own properly scoped implementation before production use.

## 1. Import the sample first

Complete the [100-product CSV import](LIGHTNING_D2C_IMPORT.md). The connector identifies those products using their stable ProductCode/SKU and reads structured metadata from Description; it will not invent attributes for unrelated products.

## 2. Configure OAuth through an External Client App

Use Salesforce Setup → External Client App Manager and create a local app for this integration. Enable OAuth and the API scope needed for REST access. For the server-to-server client credentials flow, enable that flow and configure its permitted/run-as integration user in the app's policies. The exact settings depend on the org's enabled External Client App capabilities. The user must have API access and the required read permissions for Product2, WebStore, PricebookEntry and the target Commerce store, with appropriate field-level access. Use an existing approved integration app/user if provided by your administrator.

Do not use a Salesforce login password in this project. Keep client secrets or OAuth access tokens only in local secrets/environment settings. The OAuth app must be configured in your org; putting values in a file does not enable permissions. Salesforce currently recommends External Client Apps for new integrations: [OAuth setup](https://developer.salesforce.com/docs/revenue/placeorder-rest-api/guide/intro-oauth-and-connected-apps.html).

## 3. Enter local configuration

Add these settings to your existing `.streamlit/secrets.toml` without removing the OpenAI settings:

```toml
CATALOG_SOURCE = "demo"
SALESFORCE_INSTANCE_URL = "https://YOUR-MY-DOMAIN.my.salesforce.com"
SALESFORCE_API_VERSION = ""
SALESFORCE_CLIENT_ID = "YOUR_EXTERNAL_CLIENT_APP_ID"
SALESFORCE_CLIENT_SECRET = "YOUR_LOCAL_SECRET"
SALESFORCE_WEBSTORE_ID = ""
SALESFORCE_PRICEBOOK_ID = ""
SALESFORCE_EFFECTIVE_ACCOUNT_ID = ""
SALESFORCE_MULTI_CURRENCY = "false"
```

Copy the real **My Domain** base URL from your org configuration. Sandboxes can use a hostname containing `.sandbox.my.salesforce.com`; do not guess it, use a `lightning.force.com` page URL, or append `/lightning/...`. Leave the API version blank to discover an advertised version, or set one supported by your org.

If you already have a valid Salesforce-platform OAuth bearer token, set `SALESFORCE_ACCESS_TOKEN` instead of using client credentials. This shared setting takes precedence: clear an old B2C SLAS token if one was configured previously. The two platforms' tokens are not interchangeable. Client credentials are used only when no bearer token is supplied. A fresh client is created by each owner CLI run; automatic token refresh within a run is not implemented.

For a single-currency org, confirm its currency and selected price book are **USD** before sync. For multicurrency, set `SALESFORCE_MULTI_CURRENCY = "true"`; the price-book query then filters USD. This connector is intentionally USD-only.

## 4. Find store and price book IDs

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_lightning_connection --list-stores
```

This uses Salesforce REST read access and prints accessible WebStore IDs/names. It does not call OpenAI. Set `SALESFORCE_WEBSTORE_ID` to your D2C store's ID.

Find the active price book actually assigned/configured for your store in Salesforce, copy its Pricebook2 record ID (starts with `01s`), and set `SALESFORCE_PRICEBOOK_ID`. The connector does not infer or validate store-to-price-book assignment for you. If the Commerce product API requires an effective buyer/person-account context, set `SALESFORCE_EFFECTIVE_ACCOUNT_ID` to an authorized account ID; otherwise leave it blank. Do not use arbitrary customers' account IDs.

Check an imported product through the configured store:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_lightning_connection
```

A 401 means OAuth/token issues; a 403 generally means permission/store/buyer context issues; a 404 can mean a wrong ID or a product not accessible through that store. Successful admin Product2 reads alone do not establish shopper visibility. [Commerce product APIs](https://developer.salesforce.com/docs/commerce/salesforce-commerce/guide/b2b-d2c-comm-product-category-apis.html).

## 5. Sync the first 100 products

```powershell
.\.venv\Scripts\python.exe -m scripts.sync_lightning_catalog --limit 100
```

The command reads only active products with `EG-...` codes, uses each Salesforce Product2 ID for a store product-detail request, and reads the selected price book's active entries. Any missing metadata, missing price, duplicate project code, or unsuccessful store request prevents a new snapshot from becoming active. Existing snapshots are retained. If a partial import created fewer than 100 matching products, the snapshot includes only the records returned; check the reported count against the import summary.

The first connector supports **1–1,000 products per snapshot**, intentionally limiting API requests during development. The full 50k research catalog can remain local. Bulk scalable synchronization is a separate extension; do not assume all imported 50k have been synced.

Snapshot files are saved under ignored `data/lightning_snapshots/`, and an atomic pointer identifies the completed snapshot. No credentials are written to it. Salesforce IDs are preserved as `salesforce_id`; the original project IDs remain stable for the app and embedding cache.

## 6. Switch the app to that snapshot

Only after sync succeeds, change:

```toml
CATALOG_SOURCE = "lightning_snapshot"
```

Stop the old app with Ctrl+C and relaunch:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_semantic_index
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The semantic index now builds/checks against the chosen snapshot, reusing unchanged cached descriptions. The storefront displays a concise notice that the catalog was synced from Salesforce and availability/checkout are simulated. Only the snapshot's products are available in the shop and finder. Set `CATALOG_SOURCE = "demo"` to return to the bundled catalog.

Prices are **snapshots of a selected price book**, not buyer-specific offers or live checkout quotes. Stock is **synthetic metadata**, not verified Salesforce inventory. Product/category/specification metadata originates from our demo import, while Salesforce Product2 names/IDs and selected price-book values are read back from the org. Public shopper authorization, current prices and stock, taxes, shipping, Salesforce baskets, and payment integration remain future work.

The connector has been tested with mocked Salesforce responses. No live login/import/sync has been performed from this workspace.
