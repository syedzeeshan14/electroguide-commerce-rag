"""Owner-only Product2 CSV import. Existing project codes are skipped by default."""
import argparse
import json
from zipfile import BadZipFile
from app.runtime import settings
from app.salesforce_catalog import SalesforceCatalogClient,read_product_csv,import_product_records,plan_product_import
from app.integrations import ConnectionFailure

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',default='imports/salesforce/product2-100.csv')
    parser.add_argument('--dry-run',action='store_true',help='Validate the local CSV without API requests or writes')
    parser.add_argument('--update-existing',action='store_true',help='Explicitly overwrite matching EG- records with this CSV; otherwise they are skipped')
    parser.add_argument('--plan',action='store_true',help='Read Salesforce counts and org limits; make no writes')
    parser.add_argument('--batch-size',type=int,default=200,help='1–200 records per API write')
    args=parser.parse_args()
    if not 1<=args.batch_size<=200:
        parser.error('batch-size must be between 1 and 200')
    try:
        rows=read_product_csv(args.file)
        if args.dry_run:
            print(json.dumps({'validated_products':len(rows),'api_calls':0,'salesforce_writes':0},indent=2))
        elif args.plan:
            plan,_,_=plan_product_import(SalesforceCatalogClient(settings()),rows,args.update_existing,args.batch_size)
            print(json.dumps(plan,indent=2))
            if not plan['capacity_sufficient']:
                parser.exit(1,'Capacity estimate does not fit this org. No records were written.\n')
        else:
            result=import_product_records(SalesforceCatalogClient(settings()),rows,args.update_existing,args.batch_size,
                progress=lambda result:print(f"Created {result['created']} · Updated {result['updated']} · Skipped {result['skipped_existing']} · Remaining {result['remaining']}",flush=True))
            print(json.dumps(result,indent=2))
    except (ConnectionFailure,OSError,BadZipFile) as error:
        parser.exit(1,str(error)+'\nCompleted earlier batches may already exist; rerun without --update-existing to skip them.\n')
