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
