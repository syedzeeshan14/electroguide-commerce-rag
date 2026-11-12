"""Owner-only Product2 CSV import. Existing project codes are skipped by default."""
import argparse
import json
from app.runtime import settings
from app.salesforce_catalog import SalesforceCatalogClient,read_product_csv,import_product_records
from app.integrations import ConnectionFailure

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',default='imports/salesforce/product2-100.csv')
    parser.add_argument('--dry-run',action='store_true',help='Validate the local CSV without API requests or writes')
    parser.add_argument('--update-existing',action='store_true',help='Explicitly overwrite matching EG- records with this CSV; otherwise they are skipped')
    args=parser.parse_args()
    try:
        rows=read_product_csv(args.file)
        if args.dry_run:
            print(json.dumps({'validated_products':len(rows),'api_calls':0,'salesforce_writes':0},indent=2))
        else:
            result=import_product_records(SalesforceCatalogClient(settings()),rows,args.update_existing)
            print(json.dumps(result,indent=2))
    except (ConnectionFailure,OSError) as error:
        parser.exit(1,str(error)+'\nCompleted earlier batches may already exist; rerun without --update-existing to skip them.\n')
