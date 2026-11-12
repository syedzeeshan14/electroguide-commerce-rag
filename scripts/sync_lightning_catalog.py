"""Publish an owner-operated Salesforce-linked catalog snapshot; never writes to Salesforce."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from app.catalog import Catalog
from app.runtime import ROOT,settings
from app.lightning import LightningClient,normalize_imported_product
from app.integrations import ConnectionFailure


def sync_catalog(client,output,limit=100):
    records=client.imported_products(limit)
    if not records:
        raise ConnectionFailure('No active ElectroGuide products found. Import the Commerce CSV first.')
    prices=client.pricebook_entries([record['Id'] for record in records])
    products=[]
    seen=set()
    for index,record in enumerate(records,1):
        if record['Id'] not in prices:
            raise ConnectionFailure('A product has no active price in the configured price book. Fix pricing before syncing.')
        detail=client.store_product(record['Id'])
        if not isinstance(detail,dict):
            raise ConnectionFailure('A product did not return a valid Commerce detail response.')
        product=normalize_imported_product(record,prices[record['Id']])
        if product['id'] in seen:
            raise ConnectionFailure('Duplicate ElectroGuide ProductCode values found. Resolve duplicates in Salesforce first.')
        seen.add(product['id']);products.append(product)
        if index%25==0:
            print(f'Validated {index}/{len(records)} imported records in the configured store context.',flush=True)
    # Immutable snapshot plus an atomic pointer: an interrupted sync never publishes half a catalog.
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    snapshot_id=uuid.uuid4().hex
    snapshot=output/'lightning_snapshots'/snapshot_id
    snapshot.mkdir(parents=True)
    try:
        path=snapshot/'products.jsonl'
        with path.open('w',encoding='utf-8') as handle:
            for product in products:
                handle.write(json.dumps(product,sort_keys=True)+'\n')
        catalog=Catalog(str(snapshot/'catalog.sqlite'))
        try:
            catalog.build(path)
        finally:
            catalog.connection.close()
        manifest={'snapshot_id':snapshot_id,'count':len(products),'synced_at':datetime.now(timezone.utc).isoformat(),
                  'source':'lightning_snapshot','webstore_id':client.settings.get('SALESFORCE_WEBSTORE_ID',''),
                  'price_source':'selected_pricebook_snapshot','stock_source':'synthetic_metadata',
                  'scope':'owner-operated demo; not per-shopper authorization or live pricing'}
        temp=output/f'lightning-current-{snapshot_id}.tmp'
        temp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        os.replace(temp,output/'lightning-current.json')
        return manifest
    except Exception:
        shutil.rmtree(snapshot,ignore_errors=True)
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=100,help='1–1000 records, start with 100')
    args=parser.parse_args()
    if not 1<=args.limit<=1000:
        parser.error('limit must be between 1 and 1000')
    try:
        report=sync_catalog(LightningClient(settings()),ROOT/'data',args.limit)
        print(json.dumps(report,indent=2))
        print('Snapshot ready. Set CATALOG_SOURCE="lightning_snapshot" locally, stop the old app, and relaunch Streamlit. Availability and checkout remain simulated.')
    except ConnectionFailure as error:
        parser.exit(1,str(error)+'\nNo new snapshot was activated.\n')
