# Standard Salesforce Product2 import — current project path

Use `product2-100.csv` with `python -m scripts.import_salesforce_catalog` after the Product2 API-access check passes. A `--dry-run` validates the local file without making requests. API-enabled Data Loader is another supported object-import path.

The columns are standard Product2 fields, not Commerce-import headings. Description stores structured synthetic specifications, original SKU, simulated stock, and USD demo price. No WebStore, Commerce store, category assignment, custom fields, or native USD price book is required for the initial demonstration. Existing project product codes are skipped by the CLI unless `--update-existing` is explicitly requested.

[Full setup guide](../../docs/SALESFORCE_CATALOG.md)
