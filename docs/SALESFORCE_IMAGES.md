# Salesforce product images in Streamlit

The Product2 catalog sync imports product data. Images uploaded under the Salesforce **Media** tab are separate ProductMedia/CMS records; the storefront previously displayed only category illustrations. The image sync command now downloads one product's image into a private local cache. The same card renderer displays it in Shop and recommendation results.

## Update and sync one image

Update the project source from GitHub while preserving your local `.streamlit/secrets.toml`, `data`, and `.venv-sf` directories. Stop Streamlit before updating. Open PowerShell in the project root (the directory containing `streamlit_app.py`). For the current Windows installation:

```powershell
Set-Location 'D:\ElectroGuide50K'
.\.venv-sf\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-sf\Scripts\python.exe -m scripts.sync_salesforce_image --product-id 01tkO0000003MmtQAE
.\.venv-sf\Scripts\python.exe -m streamlit run streamlit_app.py
```

Your local configuration must contain the working Salesforce OAuth settings and:

```toml
CATALOG_SOURCE = "salesforce_catalog_snapshot"
```

The product must already exist in your completed catalog snapshot. An image-only update needs neither another product import nor an embedding rebuild. Refresh the browser after a successful image sync. Search for the product's name in Shop or recommendations.

The command prefers Product List Images, then Product Detail Images. Your screenshot's featured Product Detail Image is therefore eligible even though Product List Image is empty. Adding a separate listing image is optional. Images attached via Related → Files provide a fallback, using the most recently modified supported image file.

## If image download fails

Run:

```powershell
.\.venv-sf\Scripts\python.exe -m scripts.sync_salesforce_image --product-id 01tkO0000003MmtQAE --diagnose
```

This reports media IDs, groups, file references and sanitized access errors. It does not print tokens or download URLs. Share this output if troubleshooting is needed, without your secrets file.

Product2 read permission does not automatically grant CMS workspace/content access. The connector resolves common ManagedContent/ManagedContentInfo and external-media URL representations, but CMS delivery differs by org and has not been verified against your live instance. An unresolved CMS image reports an error rather than claiming success. Check that the integration user can read the media's workspace/content. If your trial cannot expose the CMS image, attach the same PNG/JPEG/WebP/GIF to that product under Related → Files, then rerun the command. This is a separate file association; a Media-tab upload is not assumed to be a File attachment.

OAuth credentials are sent only to your configured Salesforce My Domain. Redirects to supported Salesforce content hosts receive no OAuth token. For a trusted public external image CDN, add its exact hostname to the optional local `SALESFORCE_IMAGE_HOSTS` comma-separated setting. Do not paste session URLs or make private media public solely to bypass an access error.

## Cache behavior and limits

Images must be valid PNG, JPEG, WebP or GIF, at most 10 MB and 25 megapixels. Raw bytes are stored beneath ignored `data/product_images`, scoped to the configured org. Cache metadata contains product/media IDs and a timestamp, with no credentials or source URLs. Images are not automatically refreshed on every storefront request; rerun the targeted sync after replacing a picture. A failed sync preserves the previous cached image. To clear all local cached images, stop the app and remove only `data/product_images`, then sync the desired pictures again. Product snapshots and embeddings are separate.

This remains a Salesforce Product2 catalog integration with a Streamlit storefront and simulated checkout.

## Enhanced CMS authoring URLs

A content document can expose a file source reference (for example an ID beginning `0sN`) and `/cms/media/MC...`. That is an authoring-media URL and can return a login page even when the metadata API succeeds. The connector now reads the existing channels of the content's workspace, fetches the channel delivery document for that content key, and uses its media URL. It does not create channels or publish content. The `0sN` source reference is not treated as a ContentVersion ID.

For a delivery URL on the same tenant's Lightning host, only `/cms/delivery/` paths are mapped to the configured My Domain for authenticated download. Arbitrary Lightning pages and authoring URLs are not rewritten. Access to metadata and an `isPublished` flag alone do not prove that a delivery channel is accessible to this OAuth user. A missing channel/delivery URL reports that limitation explicitly. This route is covered by mocked regression tests; the owner must still verify the actual image download against their org.

Salesforce API references: [CMS Space Channels](https://developer.salesforce.com/docs/platform/connect-rest-api/guide/connect_resources_cms_space_channels.html) and [Connect REST API guide](https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/salesforce_chatter_rest_api.pdf), Enhanced CMS Workspaces Resources, CMS Delivery Content.

## Download succeeds but the card still shows an illustration

Use the exact product code, not just its name: synthetic variants can share names. Shop now accepts an exact `EG-040683` query without rebuilding the index, and cards display the product code. Restart the actual Streamlit process after updating the renderer.

Run `python -m scripts.check_salesforce_image --product-code EG-040683` from the same project directory used to launch the app. This local-only diagnostic reports the project folder, active catalog source, whether that exact product is present, its Salesforce ID, whether an image is cached for that ID, and whether the installed renderer supports cached images. It makes no Salesforce/OpenAI request and prints no credentials. A demo catalog, a different Salesforce record ID, an older source file, or a different project folder can each explain a successful download followed by an illustration.

Shop includes out-of-stock products so their details and pictures remain visible. Cards show `Out of stock` and disable Add to bag when the snapshot's synthetic stock is zero. Recommendations still consider in-stock products only. EG-040683 has zero stock in the bundled synthetic dataset; stock is not increased just to display its image.

## Category photo fallbacks

All ten categories (laptop, mobile, headphones, camera, TV, tablet, smartwatch, monitor, speaker and gaming) use bundled representative category photographs when no synced Salesforce picture exists. These photos are examples, not SKU-specific manufacturer images; their cards are labeled `Representative photo`. A missing local category photo falls back to an SVG illustration. Salesforce pictures still take priority. The same renderer serves Shop and recommendation cards. See `assets/categories/CREDITS.md` for photo sources and license.
