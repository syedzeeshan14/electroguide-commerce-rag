# MS project proposal

**Title:** Grounded Conversational Product Recommendation for an Electronics Store Using Salesforce B2C Commerce.

## Research question
Does hybrid retrieval with a grounded conversational assistant improve product relevance and shopping-task completion compared with lexical search on a controlled electronics catalog?

## Scope
US English, USD, ten electronics categories, 50,000 fictional SKUs. Target a focused customer storefront with product search, filters, details, one best catalog match plus up to two alternatives, a bag, and simulated checkout. Use three top navigation buttons: Shop, Find my match, and Bag. Keep owner diagnostics in a terminal tool. Clearly identify simulated payments, identities, fulfillment, analytics, and policies. Prefer test payment integration only if time permits. Do not process real money.

## Architecture to implement
Current implementation: Streamlit storefront → local SQLite catalog → hard filters, optional OpenAI embeddings cached in SQLite, NumPy cosine similarity, hybrid relevance/feature ranking, factual requirement comparisons, and grounded OpenAI explanations. Live embedding relevance is not yet evaluated. Planned research extension: PostgreSQL + pgvector for hybrid catalog/knowledge retrieval. A server-side provider calls OpenAI for grounded answers and embeddings. A separate Commerce adapter connects Salesforce B2C Commerce SCAPI for supported shopper operations; validate API availability and licensing first. SQLite FTS5 is the implemented offline baseline and is not the final vector system.

Salesforce should own its connected catalog, current commerce price/stock, baskets, and orders. The retrieval index is a derived cache. A local 50k catalog supports load experiments even if the sandbox cannot hold that volume. Initially sync a representative subset after checking limits; never imply all 50k were imported. Refresh commerce facts when presenting recommendations and before basket/checkout actions. Shopper OAuth/SLAS must follow the sandbox's actual configuration; do not assume a Lightning session authorizes SCAPI.

## Recommendation pipeline
1. Extract explicit constraints such as budget, category, intended use, and required specifications; ask one targeted question when necessary.
2. Apply price, stock, and specification filters before ranking.
3. Combine lexical and embedding retrieval; rerank a small candidate set using stated preferences.
4. Supply only retrieved products and cited policy passages to the answer model. Keep catalog/policy content separate from system instructions.
5. Validate structured model output against retrieved IDs and current facts. Return product cards, reasons, tradeoffs, and source references. Never allow the model to execute checkout.
6. Handle no matches, unavailable models, missing facts, and stale stock explicitly.

## Milestones and acceptance gates
1. **Foundation (this repository):** reproducible 50k generator, data provenance, offline search API, meaningful tests, integration checklist.
2. **Storefront:** responsive catalog, filters, details, product finder, local bag, and visibly simulated order flow. Use minimal top navigation and label session-only persistence.
3. **Salesforce:** verify sandbox type and API access, configure SLAS, sync a small catalog, demonstrate a basket and supported test order flow; document limitations.
4. **RAG:** embeddings and policy ingestion, grounded explanations with citations, preference-based ranking, cost controls and failure handling.
5. **Integration quality:** validate fresh commerce price/stock at recommendation and basket time; keep technical diagnostics outside the customer interface.
6. **Evaluation/report:** reproducible experiments, user study if approved, limitations, architecture diagram, demo script, dissertation and presentation.

## Evaluation
Create at least 100 held-out shopping queries with explicit budgets/constraints and human relevance labels. Keep templates and variants from the same product family in a single evaluation partition to reduce leakage. Record generation seed, catalog hash, retrieval versions, model identifier, prompt version, hardware, and date.

Compare (A) lexical retrieval, (B) hybrid retrieval, and (C) hybrid retrieval plus grounded explanation. Report Recall@10 and nDCG@10 against independently labeled products; budget and stock violation rate; factual support/citation accuracy assessed against actual records; median/p95 latency and per-query API cost. Conduct an ablation for preference reranking if time permits. A small voluntary task study can measure completion, perceived usefulness, and satisfaction, subject to university rules. Synthetic data cannot establish real conversion uplift or real consumer behavior. Do not fabricate study results.

## Risks and limits
Salesforce edition/API mismatch; sandbox capacity; model cost; hallucinations; synthetic distribution bias; repetitive catalog variants; limited external validity. Use bounded retrieval, server-only keys, anonymous study IDs, no raw payment details, and explicit distinction between implemented, simulated, and planned behavior.
