"""Standard Product2 CSV for catalog integration; no Commerce store required."""
import argparse
import csv
import json
import hashlib
from zipfile import ZipFile,ZIP_DEFLATED
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
    parser.add_argument('--zip',action='store_true',help='Also write a ZIP containing the CSV and a separate checksum manifest')
    args=parser.parse_args()
    if not 1<=args.count<=50000:
        parser.error('count must be between 1 and 50,000; start with 100 in Salesforce')
    path=export_products(args.output,args.count)
    if args.zip:
        archive=Path(str(path)+'.zip')
        with ZipFile(archive,'w',ZIP_DEFLATED) as handle:
            handle.write(path,path.name)
        manifest={'products':args.count,'format':'standard Product2 object CSV','csv':path.name,
                  'csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'synthetic':True,'existing_codes_skipped_by_default':True}
        path.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(archive)
    else:
        print(path)
