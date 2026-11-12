"""Read Product2 catalog records into the app; never uses a Commerce store."""
import argparse
import json
from app.runtime import ROOT,settings
from app.salesforce_catalog import SalesforceCatalogClient,sync_product_catalog
from app.integrations import ConnectionFailure

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=100)
    args=parser.parse_args()
    if not 1<=args.limit<=1000:
        parser.error('Use 1–1000 records; start with 100')
    try:
        result=sync_product_catalog(SalesforceCatalogClient(settings()),ROOT/'data',args.limit)
        print(json.dumps(result,indent=2))
        print('Snapshot ready. Set CATALOG_SOURCE="salesforce_catalog_snapshot", then restart Streamlit. This is catalog integration, not Commerce checkout.')
    except ConnectionFailure as error:
        parser.exit(1,str(error)+'\nNo new catalog snapshot was activated.\n')
