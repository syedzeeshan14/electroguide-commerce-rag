"""Export synthetic data for the Lightning Commerce CSV importer (not Data Loader)."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from scripts.generate_catalog import generate
from app.design import LABELS

METADATA_MARKER='ElectroGuide metadata: '
FIELDS=['Product Name','SKU','Product ProductCode','Product Description','Product isActive','Category 1','Price USD']


def import_row(product,entitlement=None):
    metadata={key:product[key] for key in ['category','brand','specifications','use_case','synthetic','catalog_version']}
    metadata['demo_stock']=product['stock']
    description=product['description']+'\n'+METADATA_MARKER+json.dumps(metadata,sort_keys=True,separators=(',',':'))
    if len(description)>4000:
        raise ValueError('Product description exceeds the supported export length.')
    row={'Product Name':product['name'],'SKU':product['sku'],'Product ProductCode':product['id'],
         'Product Description':description,'Product isActive':'true','Category 1':'Electronics/'+LABELS[product['category']],
         'Price USD':f"{product['price']:.2f}"}
    if entitlement:
        row['Entitlement']=entitlement
    return row


def write_csv(path,items,entitlement=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS+(['Entitlement'] if entitlement else []))
        writer.writeheader()
        for product in items:
            writer.writerow(import_row(product,entitlement))


def export(output,count=50000,batch_size=10000,entitlement=None):
    if count<100 or not 1<=batch_size<=10000:
        raise ValueError('Export count must be at least 100 and batch size must be 1–10,000.')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    items=list(generate(count))
    sample=output/'commerce-products-100.csv'
    write_csv(sample,items[:100],entitlement)
    archive_path=output/'commerce-products-50000-batches.zip' if count==50000 else output/f'commerce-products-{count}-batches.zip'
    with ZipFile(archive_path,'w',ZIP_DEFLATED) as archive:
        import io
        for index,start in enumerate(range(0,count,batch_size),1):
            buffer=io.StringIO(newline='')
            writer=csv.DictWriter(buffer,fieldnames=FIELDS+(['Entitlement'] if entitlement else []))
            writer.writeheader()
            writer.writerows(import_row(product,entitlement) for product in items[start:start+batch_size])
            archive.writestr(f'commerce-products-batch-{index:02d}.csv',buffer.getvalue().encode('utf-8'))
    manifest={'count':count,'sample_count':100,'max_batch_size':batch_size,'format':'Lightning Commerce CSV Import (not generic Product2 Data Loader)',
              'sample_sha256':hashlib.sha256(sample.read_bytes()).hexdigest(),'archive_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
              'synthetic':True,'notes':['Sample overlaps batch 1. Match by existing SKU when importing again; review duplicate handling.',
                                      'Select the correct catalog and USD price book in the Commerce importer.',
                                      'Stock is metadata for simulation only; this file does not populate Salesforce inventory.',
                                      'No image URLs or real brand/manufacturer claims are included.',
                                      'Store entitlement, search indexing, permissions, and extra org validation rules must be checked.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='imports/lightning')
    parser.add_argument('--count',type=int,default=50000)
    parser.add_argument('--batch-size',type=int,default=10000)
    parser.add_argument('--entitlement',help='Name of an already-created entitlement policy; omit if not configured')
    args=parser.parse_args()
    print(json.dumps(export(args.output,args.count,args.batch_size,args.entitlement),indent=2))
