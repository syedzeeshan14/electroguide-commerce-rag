"""Read-only owner check for Lightning Commerce; makes no OpenAI calls."""
import argparse
from app.runtime import settings
from app.lightning import LightningClient
from app.integrations import ConnectionFailure

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-stores',action='store_true')
    args=parser.parse_args()
    try:
        config=settings(); client=LightningClient(config)
        stores=client.stores()
        print('Salesforce OAuth/API read access verified.')
        for store in stores:
            print(f"{store['Id']}  {store['Name']}")
        if not stores:
            print('No WebStore records visible to this user. Check Commerce licensing and permissions.')
        if config.get('SALESFORCE_WEBSTORE_ID') and not args.list_stores:
            products=client.imported_products(limit=1)
            if not products:
                print('No active ElectroGuide products found. Import the 100-product Commerce CSV first.')
            else:
                client.store_product(products[0]['Id'])
                print('Imported product is readable through the configured Commerce store context.')
    except ConnectionFailure as error:
        parser.exit(1,str(error)+'\n')
