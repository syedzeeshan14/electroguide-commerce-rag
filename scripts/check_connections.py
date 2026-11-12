"""Owner-only CLI diagnostics; not part of the customer storefront."""
from app.runtime import settings
from app.integrations import ConnectionFailure, grounded_answer, salesforce_search

if __name__=='__main__':
    config=settings()
    for name,call in [('OpenAI',lambda:grounded_answer(config,'Reply with a brief greeting.',[],'')),
                      ('Salesforce B2C',lambda:salesforce_search(config))]:
        try:
            call()
            print(name+': connection verified')
        except ConnectionFailure as error:
            print(name+': '+str(error))
