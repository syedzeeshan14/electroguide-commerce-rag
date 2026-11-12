# Salesforce integration prerequisites

User reports B2C Commerce. The supplied URL is a Lightning Commerce Stores URL, which alone does not verify a B2C Commerce instance or SCAPI access. No Salesforce connection has been made.

Please locate these non-secret configuration identifiers:
- B2C Commerce Business Manager hostname, if available.
- SCAPI short code and organization ID (organization IDs commonly resemble `f_ecom_...`).
- Storefront site ID and an existing catalog ID, if present.
- Availability of SLAS administration and the intended shopper application configuration.

Never paste passwords, access tokens, client secrets, or a replacement OpenAI key in chat. Store secrets through environment settings. A public shopper client ID may be configured separately; any confidential client secret belongs only on the server.

Before implementing writes:
1. Confirm B2C Commerce versus Salesforce-platform B2B/D2C. If only Lightning Commerce Stores is available, adapt the API layer to the actual licensed product rather than guessing endpoint URLs.
2. Confirm permitted API scopes, shopper OAuth flow, site assignment, API version, and sandbox quotas.
3. Map a 100-product representative sample to the actual Salesforce catalog schema; validate before bulk import. `products.csv` is generic and cannot be directly assumed to be a Salesforce import.
4. Verify products, prices, inventory, shopper context, and basket operations in the sandbox.
5. Configure test checkout only with supported sandbox services. Keep simulation available while integrations are incomplete.

Do not scrape Best Buy or claim its policies/specifications as this project's data. Optional real-data API integration can be researched separately after checking current access, coverage, quotas, and permitted reuse; no external product API has been validated or enabled yet.
