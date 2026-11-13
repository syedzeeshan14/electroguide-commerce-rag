# Show the same order number in Streamlit and Salesforce

The optional connector creates standard Salesforce **Order** and **OrderItem** records in **Draft** status. Streamlit displays the OrderNumber returned by Salesforce, with the same products, quantities and USD subtotal. It does not generate a second customer order number. This is a standard Salesforce order-record integration, not a provisioned Commerce store checkout or an Order Management OrderSummary.

No payment, tax calculation, shipping, order activation, inventory reservation or fulfillment occurs. The project still uses synthetic availability. Only new orders placed after setup are synced; previous session-only demo confirmations are not uploaded.

## 1. Update the local project

Stop Streamlit. Update the source files from this repository while preserving `.streamlit/secrets.toml`, `data` and your virtual environment. New files include `app/salesforce_orders.py` and `scripts/setup_salesforce_orders.py`. Updated files include `app/runtime.py` and `streamlit_app.py`. The default order mode remains off until the owner enables it.

## 2. Read-only access and currency check

From the project root:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.setup_salesforce_orders
```

The tool checks Order/OrderItem read/create access, required fields and whether USD is supported. It does not create records. If Orders are unavailable, find **Order Settings** in Salesforce Setup and enable Orders where the edition supports them, then grant the API user the necessary Order and Order Product permissions. Org validation rules can require additional fields beyond the standard demo payload.

**The org previously showed INR as its currency.** USD prices in a Product2 Description are sufficient for the simulated storefront but do not enable native USD Orders. The connector requires either a single-currency USD org or active USD in a correctly configured multi-currency org. If `usd_supported` is false, use a suitable USD academic org or have the org owner configure supported currencies. Enabling multi-currency has wider org implications and is not performed by this project. There is no automatic INR/USD conversion or relabeling.

## 3. Prepare the academic demo

In Salesforce, activate the Standard Price Book if it is inactive. Its list can be opened at your My Domain followed by `/lightning/o/Pricebook2/list` where your edition exposes it.

Once the access check succeeds and USD is supported:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.setup_salesforce_orders --apply --configure-local
```

This explicitly:

- Creates or reuses one shared fictional Account named **ElectroGuide Academic Demo Customer**.
- Creates or reuses a dedicated active **ElectroGuide Academic USD** price book, with a marker description to protect other price books.
- Enables on-demand academic USD pricing for products ordered through this app. Missing USD Standard Price Book and dedicated demo price-book entries are created only for those products. Existing entries are never overwritten or activated. Creating a failed order can leave successfully prepared pricing entries, but order/header line writes use a separate atomic transaction.
- Saves the non-secret settings automatically into your existing local secrets file, preserving credentials. You do not need to enter TOML assignments into PowerShell.

No order is placed by setup. It performs no writes when USD is unsupported. It does not change org currencies or activate the Standard Price Book automatically. This setup is for the academic org, not a live company's shared customer and pricing configuration.

The settings it saves are `CATALOG_SOURCE="salesforce_catalog_snapshot"`, `SALESFORCE_ORDER_SYNC="salesforce_draft"`, the Account/Pricebook IDs, and `SALESFORCE_ORDER_DEMO_PRICING="true"`.

Alternatively, configure an existing Account and active USD price book with `SALESFORCE_ORDER_DEMO_PRICING="false"`. Every bag product must have an active matching USD price-book entry. The connector refuses stale/mismatched prices instead of creating a different subtotal. With automatic academic pricing enabled, fresh Product2 demo metadata is checked before preparing missing entries.

## 4. Place and demonstrate a draft order

Restart Streamlit:

```powershell
.\.venv-sf\Scripts\python.exe -m streamlit run streamlit_app.py
```

Add available Salesforce-catalog products to the bag (at most 20 distinct products). Choose **Save draft order**. Wait for the confirmation containing the Salesforce order number, such as `00000123`. Select **View in Salesforce**, log in with your own Salesforce browser session, and show the same Order Number and its Order Products.

You can also open your org's `/lightning/o/Order/list`, select All Orders, and locate that number. These records appear under standard Orders, not the unprovisioned Commerce Store page. OrderNumber is an automatically generated Salesforce value; the connector's `EG-...` reference is internal retry metadata, not the displayed order number.

## Failure and retry behavior

The bag clears only after a verified Salesforce confirmation. API failures preserve the bag and pending checkout reference. Retry from the same Streamlit session with the same bag: the connector first searches Salesforce for that reference and fingerprint, recovering an already saved order after an uncertain network response. A local SQLite receipt ledger serializes requests from this project instance and remembers confirmed responses across process restarts. Do not refresh/close the session during an uncertain checkout, since session state holds the pending reference. Separate browser sessions are independent orders, even if their bags are identical.

Order and OrderItem creation share an `allOrNone` composite batch. Invalid lines cannot intentionally leave an orphan order header. If Salesforce responds with a validation error or lacks required fields, the app reports failure rather than inventing an order number. This is a locally owner-operated academic app using the configured integration account; public multi-user authorization and per-customer accounts are not implemented.

## Verification scope

Automated tests cover Salesforce-generated number display, atomic parent/line requests, price/currency checks, stale reference rejection, receipt recovery, preservation of the bag on failure and local configuration updates. These use mocked Salesforce responses. The owner must run the access check and verify an actual draft order in their org; no live order was created from the development workspace.

## Diagnose missing order permissions

Run `python -m scripts.setup_salesforce_orders --diagnose` for a read-only report of Order/OrderItem query/create flags and missing readable/writable fields. This mode cannot be combined with `--apply` or `--configure-local`. It makes no setup or order writes and prints no credentials.

In Setup → Order Settings, enable Orders if the edition provides this setting. In Setup → External Client App Manager → ElectroGuide Catalog Integration → Policies, identify the configured Client Credentials Run As user. Grant Order read/create access and the indicated field access to that user, not merely to a different browser-login user. Order Products access must also be available; Salesforce can derive its access from the parent Order. If Order Settings or relevant object access is unavailable in this Starter edition, the org may need a suitable edition/entitlement. Additional Commerce Admin permissions alone do not establish Order creation entitlement. Rerun the read-only check after changes.

## Orgs without PoNumber

`PoNumber` is not mandatory. The connector inspects Order metadata and chooses the first readable, writable, filterable reference field with room for the 35-character retry value: `ElectroGuide_Checkout_Reference__c`, `PoNumber`, `OrderReferenceNumber`, or `Name`. The selected field is shown in the check and diagnostic output. When Name is selected, the newly created Order's name holds the internal retry reference, while the customer still sees Salesforce's generated OrderNumber. The connector does not rename existing Orders. If no candidate is usable, it stops before creating an order and reports the required field access; a Text(80) unique external-ID custom field named `ElectroGuide_Checkout_Reference__c` is an optional explicit setup path. Keep reference-field access stable during pending checkouts.

### Setup transport failures

Setup prints stages for access/currency checks, Standard Price Book lookup, demo record lookups, atomic creation and local configuration saving. Transport errors distinguish timeout, TLS validation, connection failure and HTTP 200 non-JSON responses and identify the method/API path, without logging credentials, query strings or response bodies. A timeout during a write can leave the result uncertain: rerun the same setup so it checks for existing dedicated demo records before creating missing ones. Do not delete records solely because a response was lost. TLS verification stays enabled.

## 50K local catalog with on-demand Salesforce products

A free Developer Edition storage plan can reject 50K Product2 records even when API calls are available (the observed plan needed 127 MB with only 5 MB free). Do not force that import. Enable the hybrid academic mode instead:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.setup_salesforce_orders --apply --configure-local --local-50k
.\.venv-sf\Scripts\python.exe -m streamlit run streamlit_app.py
```

This reuses the dedicated demo Account/price book, sets the catalog source to the bundled local 50K dataset, enables draft orders and enables `SALESFORCE_ORDER_IMPORT_ON_DEMAND`. No 50K Salesforce import is attempted. Shop and semantic recommendations use all 50K local fictional products; the UI shows the actual local count. If the local demo data has an older or smaller manifest, its known source files are backed up under ignored `data/catalog_backups` before restoring the bundled 50K catalog and rebuilding the local index.

When saving a draft order, the connector:

1. Validates the local USD bag and checks for an existing Salesforce order with the same request reference before doing any import.
2. Looks up bag product codes in Salesforce, reusing existing records and rejecting ambiguous duplicates.
3. Checks conservative remaining storage headroom for the bag's product, price, order and line records.
4. Creates only missing bag Product2 records, then resolves their IDs. Existing products are not overwritten, activated or repriced. Differing prices or availability still block checkout rather than silently changing the order.
5. Prepares missing dedicated academic USD pricing and creates the standard Draft Order and its lines as before, displaying the Salesforce-generated OrderNumber.

The bag holds at most 20 distinct products. Product/price setup can remain after an order failure; retries reuse those records. Order header/line creation remains atomic, and a lost confirmation can be recovered using the original local-cart fingerprint. This mode does not make the local dataset a Salesforce catalog snapshot, nor does it store all 50K products in Salesforce. During a demonstration, accurately describe it as **a 50K local recommendation catalog with on-demand Salesforce product and draft-order integration**.

The org still has finite storage as more distinct products and orders accumulate; this is not unlimited capacity. Checks use estimates and Salesforce-reported limits, which may update asynchronously. For bulk experiments requiring all 50K records inside Salesforce, use an appropriately provisioned org.

Local product-code → current-org Salesforce-ID mappings are saved after on-demand binding, so subsequently synced Salesforce product images can override category photos for those codes. Old-org images/IDs are not reused. Existing category photos remain available for the other local products. OpenAI embeddings continue to use the local catalog; the owner can keep the existing compatible embedding cache.
