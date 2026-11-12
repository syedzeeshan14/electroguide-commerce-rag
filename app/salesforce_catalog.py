"""Store-independent Product2 catalog integration; no Commerce endpoints are used."""
import csv
import json
import math
from pathlib import Path
import re
from app.integrations import ConnectionFailure
from app.lightning import LightningClient,normalize_imported_product
from app.snapshots import publish_snapshot
from scripts.export_lightning_import import METADATA_MARKER


def demo_metadata(record):
    try:
        value=json.loads(record['Description'].rsplit(METADATA_MARKER,1)[1])
    except (KeyError,AttributeError,IndexError,TypeError,ValueError):
        raise ConnectionFailure('Product Description is missing valid ElectroGuide catalog metadata. Use imports/salesforce/product2-100.csv.') from None
    if not isinstance(value,dict):
        raise ConnectionFailure('ElectroGuide catalog metadata must be a JSON object.')
    return value


def normalize_catalog_record(record,price=None):
    metadata=demo_metadata(record)
    metadata_price=price is None
    if metadata_price:
        price=metadata.get('demo_price_usd')
    if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<0:
        raise ConnectionFailure('Product is missing a valid USD demo price, or the selected price-book price is invalid.')
    sku=metadata.get('sku')
    if not isinstance(sku,str) or not sku.strip():
        raise ConnectionFailure('Product SKU is missing from catalog metadata. Use the standard Product2 import package.')
    normalized=normalize_imported_product({**record,'StockKeepingUnit':sku},float(price))
    normalized['source']='salesforce_catalog_snapshot'
    normalized['price_source']='synthetic_usd_metadata' if metadata_price else 'selected_usd_pricebook_snapshot'
    return normalized


class SalesforceCatalogClient(LightningClient):
    """Reuse platform OAuth/query transport; never access WebStore/Commerce APIs."""
    def check_access(self):
        schema=self._request('GET',self.api_root()+'/sobjects/Product2/describe')
        if not isinstance(schema,dict) or schema.get('queryable') is not True:
            raise ConnectionFailure('Product2 is not queryable for this API user.')
        fields={field.get('name') for field in schema.get('fields',[]) if isinstance(field,dict)}
        if not {'Id','Name','ProductCode','Description','IsActive'}<=fields:
            raise ConnectionFailure('The API user cannot read the required Product2 fields.')
        list(self.query('SELECT Id FROM Product2 LIMIT 1'))
        return {'product2_read':True,'product2_create':schema.get('createable') is True,
                'product2_update':schema.get('updateable') is True}

    def imported_products(self,limit=100):
        if not 1<=limit<=1000:
            raise ConnectionFailure('Use a catalog sync limit between 1 and 1000; start with 100.')
        return list(self.query("SELECT Id,Name,ProductCode,Description,IsActive FROM Product2 WHERE IsActive=true AND ProductCode LIKE 'EG-%' ORDER BY ProductCode LIMIT "+str(int(limit))))

    def existing_codes(self,codes):
        records={}
        for start in range(0,len(codes),100):
            batch=codes[start:start+100]
            if any(not re.fullmatch(r'EG-\d{6}',code) for code in batch):
                raise ConnectionFailure('Only EG-000001-style product codes can be imported by this tool.')
            literals=','.join("'"+code+"'" for code in batch)
            for record in self.query(f'SELECT Id,ProductCode FROM Product2 WHERE ProductCode IN ({literals})'):
                if record['ProductCode'] in records:
                    raise ConnectionFailure('Duplicate project ProductCode values exist in Salesforce. Resolve them before importing.')
                records[record['ProductCode']]=record['Id']
        return records

    def write_products(self,records,update=False):
        method='PATCH' if update else 'POST'
        result=self._request(method,self.api_root()+'/composite/sobjects',json={'allOrNone':True,'records':[{'attributes':{'type':'Product2'},**record} for record in records]})
        if not isinstance(result,list) or len(result)!=len(records) or any(not isinstance(row,dict) or row.get('success') is not True for row in result):
            raise ConnectionFailure('Salesforce rejected the Product2 batch. Check required fields, validation rules, and write permissions. The batch requested allOrNone; rerun the access check before retrying.')
        return len(result)


def read_product_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=['Name','ProductCode','Description','IsActive']:
            raise ConnectionFailure('Use the standard Product2 CSV with Name,ProductCode,Description,IsActive columns; not the Commerce CSV.')
        rows=[];seen=set()
        for row in reader:
            code=row.get('ProductCode') or ''
            if not re.fullmatch(r'EG-\d{6}',code) or code in seen:
                raise ConnectionFailure('The CSV contains an invalid or duplicate project ProductCode.')
            if not row.get('Name') or len(row['Name'])>255 or len(row.get('Description') or '')>4000 or row.get('IsActive') not in ('true','false'):
                raise ConnectionFailure('A CSV row has an invalid name, description length, or active flag.')
            normalize_catalog_record({**row,'Id':'01t000000000001AAA'})
            seen.add(code)
            rows.append({**row,'IsActive':row['IsActive']=='true'})
    if not 1<=len(rows)<=1000:
        raise ConnectionFailure('Use 1–1000 rows per owner import; start with the provided 100-product CSV.')
    return rows


def import_product_records(client,rows,update_existing=False):
    access=client.check_access()
    existing=client.existing_codes([row['ProductCode'] for row in rows])
    creates=[row for row in rows if row['ProductCode'] not in existing]
    updates=[{'Id':existing[row['ProductCode']],**row} for row in rows if row['ProductCode'] in existing] if update_existing else []
    if creates and not access['product2_create'] or updates and not access['product2_update']:
        raise ConnectionFailure('This API user lacks Product2 create/update permission for the requested operation.')
    report={'created':0,'updated':0,'skipped_existing':len(existing) if not update_existing else 0}
    for group,updating,key in [(creates,False,'created'),(updates,True,'updated')]:
        for start in range(0,len(group),100):
            report[key]+=client.write_products(group[start:start+100],update=updating)
    return report


def sync_product_catalog(client,output,limit=100):
    client.check_access()
    records=client.imported_products(limit)
    if not records:
        raise ConnectionFailure('No active EG- product records found. Import the standard Product2 sample first.')
    mode=client.settings.get('SALESFORCE_CATALOG_PRICING') or 'demo_metadata'
    if mode not in ('demo_metadata','pricebook'):
        raise ConnectionFailure('SALESFORCE_CATALOG_PRICING must be demo_metadata or pricebook.')
    prices={}
    if mode=='pricebook':
        # Never relabel the INR org's numbers as USD; require deliberate currency setup.
        if client.settings.get('SALESFORCE_PRICEBOOK_CURRENCY')!='USD':
            raise ConnectionFailure('Verify the selected price book is actually USD and set SALESFORCE_PRICEBOOK_CURRENCY="USD" before pricebook mode. No currency conversion is performed.')
        prices=client.pricebook_entries([record['Id'] for record in records])
    products=[];seen=set()
    for record in records:
        if mode=='pricebook' and record['Id'] not in prices:
            raise ConnectionFailure('A product has no active USD price in the selected price book.')
        product=normalize_catalog_record(record,prices.get(record['Id']) if mode=='pricebook' else None)
        if product['id'] in seen:
            raise ConnectionFailure('Duplicate project ProductCode values found. No new snapshot was activated.')
        seen.add(product['id']);products.append(product)
    return publish_snapshot(products,output,'salesforce_catalog_snapshot',{
        'price_source':'synthetic_usd_metadata' if mode=='demo_metadata' else 'selected_usd_pricebook_snapshot',
        'stock_source':'synthetic_metadata','scope':'Product2 catalog integration; no Commerce store or checkout',
        'pricebook_currency_verified_by_owner':mode=='pricebook'})
