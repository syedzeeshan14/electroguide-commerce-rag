"""Standard Product2 CSV for catalog integration; no Commerce store required."""
import argparse
import csv
import json
from pathlib import Path
from scripts.export_lightning_import import import_row,METADATA_MARKER
from scripts.generate_catalog import generate

FIELDS=['Name','ProductCode','Description','IsActive']


def product2_row(product):
    legacy=import_row(product)
    description=legacy['Product Description']
    prose,raw=description.rsplit(METADATA_MARKER,1)
    metadata=json.loads(raw)
    metadata.update(sku=product['sku'],demo_price_usd=product['price'])
    return {'Name':product['name'],'ProductCode':product['id'],
            'Description':prose+METADATA_MARKER+json.dumps(metadata,sort_keys=True,separators=(',',':')),
            'IsActive':'true'}


def export_products(output,count=100):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader()
        for product in generate(count):
            writer.writerow(product2_row(product))
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=100)
    parser.add_argument('--output',default='imports/salesforce/product2-100.csv')
    args=parser.parse_args()
    if not 1<=args.count<=50000:
        parser.error('count must be between 1 and 50,000; start with 100 in Salesforce')
    print(export_products(args.output,args.count))
