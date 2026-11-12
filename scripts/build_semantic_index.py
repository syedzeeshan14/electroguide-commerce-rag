"""Run once locally; batches use OpenAI billing and are saved for resumable builds."""
import argparse
import json
from app.runtime import ROOT, prepare_catalog, settings
from app.semantic import EmbeddingIndex, SemanticUnavailable, product_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size',type=int,default=64)
    parser.add_argument('--dry-run',action='store_true',help='Count products and unique embedding documents without an API call')
    args=parser.parse_args()
    if not 1<=args.batch_size<=128:
        parser.error('batch-size must be between 1 and 128')
    config=settings()
    if not args.dry_run and not config.get('OPENAI_API_KEY','').strip():
        parser.exit(1,'Set OPENAI_API_KEY in .streamlit/secrets.toml or your environment first. Never put it in GitHub.\n')
    catalog=prepare_catalog()
    def products():
        for row in catalog.connection.execute('SELECT payload FROM products ORDER BY id'):
            yield json.loads(row['payload'])
    if args.dry_run:
        items=list(products())
        documents={product_document(p) for p in items}
        print(json.dumps({'products':len(items),'unique_documents':len(documents),'document_characters':sum(map(len,documents)),'api_calls':0},indent=2))
        return
    index=EmbeddingIndex(ROOT/'data/semantic.sqlite')
    print('Generating catalog embeddings using your OpenAI account. Identical descriptions are deduplicated; saved batches are reused.',flush=True)
    try:
        report=index.build(products(),config,args.batch_size,progress=lambda item:print(f"{item['cached']} cached · {item['embedded']} embedded · {item['remaining']} remaining",flush=True))
    except SemanticUnavailable as error:
        parser.exit(1,str(error)+'\nRerun the same command to resume.\n')
    print('Semantic index ready. '+json.dumps(report),flush=True)

if __name__=='__main__':
    main()
