# Import and sync the full 50,000-product Salesforce catalog

This extends the selected **standard Product2 catalog integration**, not a Salesforce Commerce store. It brings the original sample to **50,000 total project products**; it does not add another 50,000 copies on top of the sample. Existing ElectroGuide product codes are skipped by default, preserving names/prices/metadata you have edited in Salesforce.

The code, full CSV, and importer have been checked locally. No live 50k upload or capacity check has been performed in your org from this workspace.

## 1. Update the project

Download the latest repository ZIP and open its project root in VS Code. Keep your local `.streamlit/secrets.toml` private and copy it into the updated checkout. If this is a new folder, recreate the environment:

```powershell
py -m venv .venv-sf
.\.venv-sf\Scripts\python.exe -m pip install -r requirements.txt
```

The file `imports/salesforce/product2-50000.csv.zip` is included. The importer reads this ZIP directly; Data Loader users can extract its single CSV instead. It contains standard Product2 fields Name, ProductCode, Description, IsActive. It is not the earlier Commerce store/category CSV. [Download the full package](../imports/salesforce/product2-50000.csv.zip?raw=true).

## 2. Validate the full file locally

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.import_salesforce_catalog --file imports/salesforce/product2-50000.csv.zip --dry-run
```

Expected: 50,000 validated products, 0 API calls, 0 Salesforce writes. ZIP validation, project-code uniqueness, metadata, required fields, and description lengths are checked. The importer accepts one CSV in a ZIP, capped at 100 MB uncompressed, and at most 50,000 rows.

## 3. Read the import plan before writing

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.import_salesforce_catalog --file imports/salesforce/product2-50000.csv.zip --plan
```

This authenticates with your existing local Salesforce configuration, verifies Product2 permissions, queries existing project codes, and reads `/limits`. It makes **no Product2 writes**. The plan reports:

- File count, new records, existing records skipped, and any explicitly requested updates.
- Remaining data storage in MB.
- A planning estimate of storage for new records.
- Remaining daily API calls and estimated write requests.
- `capacity_sufficient`.

The estimate assumes about 2 KB per new record, adds 25% headroom and 5 MB, and is not a guarantee or reservation. For roughly 49,900 new records after a 100-record sample, it is about 127 MB. Salesforce documents approximately 2 KB for most record types, but object-specific behavior and org automation can consume more. Storage/limits reporting is asynchronous; other users or jobs can consume capacity after the check. Review Setup → Storage Usage as well if the estimate is close.

If the plan does not fit or reliable limits are unavailable, the large importer stops before any writes. Do not delete unrelated records or buy an upgrade automatically. Keep a smaller Salesforce subset and the full local research catalog, or arrange an org with sufficient capacity. [Salesforce storage estimates](https://help.salesforce.com/s/articleView?id=000383664&language=en_US&type=1) · [Limits API](https://developer.salesforce.com/docs/platform/api-rest/guide/resources-limits.html).

## 4. Import after the plan fits

Run **one import process at a time**:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.import_salesforce_catalog --file imports/salesforce/product2-50000.csv.zip
```

The importer repeats its preflight rather than assuming an earlier plan is still current. It uses **batched REST sObject Collections**, not Bulk API 2.0. Batches contain up to 200 Product2 records and request `allOrNone` for each batch. About 250 write requests are needed for 50k creates. Existing-code discovery uses one paginated project-prefix query for large files to reduce API requests. [Salesforce collection limit](https://developer.salesforce.com/docs/platform/api-rest/guide/resources-composite-sobjects-collections-create.html).

Progress is printed after each batch. If you already imported 100 products, typical totals are `created: 49900`, `updated: 0`, `skipped_existing: 100`. Actual totals depend on the existing records.

Do not use `--update-existing` unless you deliberately want the file to overwrite matching Salesforce records, including manually edited prices in metadata. The normal command preserves them.

If the process is interrupted or reports an API/storage error, stop and resolve the error, then rerun the same normal import command. Completed batches remain in Salesforce and are discovered/skipped; no local checkpoint is needed. Do not run concurrent imports, because ProductCode is not a database-enforced unique external ID in this implementation. Automatic POST retries are intentionally avoided when the server outcome is ambiguous. A rerun rechecks Salesforce first.

Each batch is atomic, **not the entire 50,000-record job**. There is no automatic rollback of earlier successful batches. Tokens configured manually can expire; if using client credentials with an empty SALESFORCE_ACCESS_TOKEN, a new command obtains a fresh token. There is no in-run token refresh.

## 5. Verify the count and sync all products

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.check_salesforce_catalog
.\.venv-sf\Scripts\python.exe -m scripts.sync_salesforce_catalog --limit 50000
```

The access checker now reports the actual aggregate count of active `EG-...` records, rather than a 100-record sample. Sync follows Salesforce query pagination and publishes a completed local snapshot. Inactive products are intentionally excluded; the active count may be lower than the total number ever imported. Validation failures leave the previous snapshot active.

Keep:

```toml
CATALOG_SOURCE = "salesforce_catalog_snapshot"
SALESFORCE_CATALOG_PRICING = "demo_metadata"
```

The selected path stores USD demo prices and availability in Description metadata. It does not populate a Commerce catalog, inventory, or native price book. Your org's INR values are not converted or relabeled.

## 6. Refresh the semantic index and launch

Stop the old Streamlit process with Ctrl+C, then run:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.build_semantic_index
.\.venv-sf\Scripts\python.exe -m streamlit run streamlit_app.py
```

Embedding builds reuse unchanged cached descriptions and can resume. New descriptions use your OpenAI account. If the full original catalog was already embedded locally with the same model/dimensions, many or all vectors can be reused; copying only the project source into a new folder does not copy the ignored local index.

The app then searches the synced Salesforce-derived catalog. Availability and checkout remain simulated. For the MS report, describe this accurately as Salesforce Product2 catalog integration with semantic product recommendation, not a provisioned Commerce Cloud store or checkout.
