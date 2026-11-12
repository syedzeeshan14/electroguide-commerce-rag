# Lightning Commerce import package

Start with `commerce-products-100.csv`. Use it with your store’s **Commerce product importer**, not generic Data Import Wizard/Data Loader. Confirm its headings against the template offered by your D2C org. The files have not been imported into your live org.

`commerce-products-50000-batches.zip` contains five 10,000-row CSVs for later use. Check org storage/Commerce allocations first. The 100-row sample overlaps batch 1; preserve SKU matching to avoid duplicate products.

All data is synthetic. Stock in description metadata is for project simulation and does not populate Salesforce inventory. Images are omitted. Choose the correct catalog and USD price book, verify entitlement/search readiness, and inspect import errors before retrying.

[Step-by-step import guide](../../docs/LIGHTNING_D2C_IMPORT.md) · [Connect the Python project](../../docs/LIGHTNING_CONNECTION.md)
