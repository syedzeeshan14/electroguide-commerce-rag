# Import the electronics catalog into Lightning D2C Commerce

This package targets Salesforce-platform Commerce, not B2C Business Manager. The user has identified their store as D2C. Column names follow Salesforce's documented Commerce CSV format; the import has not been run in your org. First compare them with the simple template offered by your own Commerce import screen and test 100 rows. Org validation rules, permissions, and edition-specific UI can differ.

## 1. Download the prepared files

- [100-product test CSV](../imports/lightning/commerce-products-100.csv?raw=true)
- [50,000 products in five CSV batches](../imports/lightning/commerce-products-50000-batches.zip?raw=true)
- [Export provenance and checksums](../imports/lightning/manifest.json)

If the browser displays CSV text, use Save As and keep the `.csv` extension and UTF-8 encoding. The bulk ZIP must be extracted before import. The initial sample overlaps the first 100 rows of batch 1: preserve SKUs and choose the matching/update behavior offered by your importer when reimporting, rather than creating duplicates.

**Use the 100-row sample first.** Check Setup → Storage Usage and your Commerce allocations before loading the larger batches. Having a 50,000-row local research dataset does not mean the development org can store that volume.

## 2. Open the Commerce product importer

1. Log in to Salesforce in your browser normally.
2. Open the Commerce app and select your D2C store.
3. Open **Products**, or **Merchandising → Products** if that navigation is present.
4. Click **Import**, then **Upload Files**. If available, download its simple CSV template and check the headers below.
5. Choose `commerce-products-100.csv`.
6. Select the catalog assigned to your D2C store and the correct active USD price book. If the importer requires a CMS workspace, select the store's appropriate workspace; this package contains no media references.
7. Start the import and wait for its completion notification.
8. Review the Import Summary, and retain the error file if any rows fail. Do not repeatedly import the same file without understanding row matching and errors.

If your screen has no Import action or only offers Data Import Wizard, stop and identify the actual Commerce product-import screen. **Do not upload this Commerce-format file into generic Data Loader without converting/mapping it.**

Official workflow: [Import product data](https://help.salesforce.com/s/articleView?id=commerce.comm_product_import_process.htm&language=en_US&type=5). Salesforce's current help article is titled for B2B stores; use your D2C org's offered template and capabilities as the final compatibility check.

## 3. File mapping

| CSV heading | Purpose |
| --- | --- |
| Product Name | Display name |
| SKU | Stable synthetic SKU |
| Product ProductCode | Stable `EG-000001`-style project identifier |
| Product Description | Human description plus structured ElectroGuide metadata |
| Product isActive | `true` |
| Category 1 | Category path under Electronics |
| Price USD | Price to assign to the price book selected during import |

[Official CSV column reference](https://help.salesforce.com/s/articleView?id=sf.comm_prod_import_csv.htm&language=en_US&type=5).

There are no custom Product2 field prerequisites for this initial package. The metadata section in Description preserves category, fictional brand, specifications, intended use, and a clearly named **demo_stock** quantity for the Python project. Do not delete that metadata section before syncing with this connector. A later integration can replace it with properly defined custom fields.

The CSV does not create inventory records or real product images. It does not configure tax, shipping, payment services, or checkout readiness. Images shown in Streamlit remain local category illustrations.

## 4. Verify store readiness

Open one imported product in Salesforce and confirm its code, SKU, active status, price, and category. Then check that the catalog is assigned to the store, its price book is configured for the intended audience, and the product is entitled/visible to that audience. Update the Commerce search index through the store's search administration when required. Verify a product in the store preview using the intended guest/registered shopper context, not just the Products administration list.

If the importer asks for an entitlement policy, use an existing policy appropriate to this store. You can regenerate files with `python -m scripts.export_lightning_import --entitlement "EXISTING POLICY NAME"`; this references the policy and does not create it. Do not broaden permissions just to make an import pass.

Upload further CSV batches one at a time after the sample succeeds. Salesforce documents a 10,000-product CSV session limit and one running Commerce import at a time: [Import/export limits](https://help.salesforce.com/s/articleView?id=commerce.comm_data_import.htm&language=en_US&type=5).

## 5. Connect the project

Follow [Lightning OAuth and snapshot setup](LIGHTNING_CONNECTION.md). Uploading a CSV and connecting Python are separate operations. This workspace has not accessed your org or uploaded records for you.
