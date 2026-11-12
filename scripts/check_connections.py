"""Owner-only CLI diagnostics; not part of the customer storefront."""
from app.runtime import settings, ROOT
from app.lightning import LightningClient
from app.semantic import EmbeddingIndex, SemanticUnavailable
from app.integrations import ConnectionFailure, grounded_answer, salesforce_search

if __name__=='__main__':
    config=settings()
    commerce_name='Salesforce Lightning OAuth/read access' if config.get('SALESFORCE_INSTANCE_URL') else 'Salesforce B2C'
    commerce_call=(lambda:LightningClient(config).stores()) if config.get('SALESFORCE_INSTANCE_URL') else (lambda:salesforce_search(config))
    for name,call in [('OpenAI',lambda:grounded_answer(config,'Reply with a brief greeting.',[],'')),
                      (commerce_name,commerce_call)]:
        try:
            call()
            print(name+': connection verified')
        except ConnectionFailure as error:
            print(name+': '+str(error))

    try:
        status=EmbeddingIndex(ROOT/'data/semantic.sqlite').status(config)
        print('Semantic index: '+('ready' if status['ready'] else 'not ready; run python -m scripts.build_semantic_index'))
    except SemanticUnavailable as error:
        print('Semantic index: '+str(error))
