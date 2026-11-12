"""Check Product2 API access only; no Commerce API or OpenAI calls."""
import argparse
import json
from app.runtime import settings
from app.salesforce_catalog import SalesforceCatalogClient
from app.integrations import ConnectionFailure

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        client=SalesforceCatalogClient(settings())
        result=client.check_access()
        result['active_project_products_visible']=len(client.imported_products(100))
        print('Salesforce Product2 API access verified. No Commerce store is required.')
        print(json.dumps(result,indent=2))
    except ConnectionFailure as error:
        parser.exit(1,str(error)+'\nIf this org reports API_DISABLED_FOR_ORG, obtain an API-enabled academic/developer org; additional Commerce permissions will not fix API entitlement.\n')
