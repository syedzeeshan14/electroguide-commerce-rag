"""Store-independent Product2 catalog integration; no Commerce endpoints are used."""
import csv
from contextlib import contextmanager
import io
from zipfile import ZipFile
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
        if not 1<=limit<=50000:
            raise ConnectionFailure('Use a catalog sync limit between 1 and 50,000.')
        return list(self.query("SELECT Id,Name,ProductCode,Description,IsActive FROM Product2 WHERE IsActive=true AND ProductCode LIKE 'EG-%' ORDER BY ProductCode LIMIT "+str(int(limit))))

    def project_product_count(self):
        rows=list(self.query("SELECT COUNT(Id) total FROM Product2 WHERE IsActive=true AND ProductCode LIKE 'EG-%'"))
        if len(rows)!=1 or not isinstance(rows[0].get('total'),int):
            raise ConnectionFailure('Salesforce did not return a valid product count.')
        return rows[0]['total']

    def limits(self):
        result=self._request('GET',self.api_root()+'/limits')
        if not isinstance(result,dict):
            raise ConnectionFailure('Salesforce did not return org limits.')
        return result

    def existing_codes(self,codes):
        if any(not re.fullmatch(r'EG-\d{6}',code) for code in codes):
            raise ConnectionFailure('Only EG-000001-style product codes can be imported by this tool.')
        records={};requested=set(codes)
        def remember(record):
            if record['ProductCode'] not in requested:
                return
            if record['ProductCode'] in records:
                raise ConnectionFailure('Duplicate project ProductCode values exist in Salesforce. Resolve them before importing.')
            records[record['ProductCode']]=record['Id']
        if len(codes)>1000:
            # One paginated prefix query is cheaper than hundreds of small IN queries.
            for record in self.query("SELECT Id,ProductCode FROM Product2 WHERE ProductCode LIKE 'EG-%' ORDER BY ProductCode"):
                remember(record)
        else:
            for start in range(0,len(codes),100):
                literals=','.join("'"+code+"'" for code in codes[start:start+100])
                for record in self.query(f'SELECT Id,ProductCode FROM Product2 WHERE ProductCode IN ({literals})'):
                    remember(record)
        return records

    def write_products(self,records,update=False):
        method='PATCH' if update else 'POST'
        result=self._request(method,self.api_root()+'/composite/sobjects',json={'allOrNone':True,'records':[{'attributes':{'type':'Product2'},**record} for record in records]})
        if not isinstance(result,list) or len(result)!=len(records) or any(not isinstance(row,dict) or row.get('success') is not True for row in result):
            raise ConnectionFailure('Salesforce rejected the Product2 batch. Check required fields, validation rules, and write permissions. The batch requested allOrNone; rerun the access check before retrying.')
        return len(result)


@contextmanager
def product_csv_stream(path):
    path=Path(path)
    if path.suffix.lower()=='.zip':
        with ZipFile(path) as archive:
            members=archive.infolist()
            if len(members)!=1 or not members[0].filename.lower().endswith('.csv') or members[0].file_size>100*1024*1024:
                raise ConnectionFailure('Use a ZIP containing one Product2 CSV no larger than 100 MB.')
            with archive.open(members[0]) as binary,io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as handle:
                yield handle
    else:
        with path.open(encoding='utf-8-sig',newline='') as handle:
            yield handle


def read_product_csv(path):
    with product_csv_stream(path) as handle:
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
            if len(rows)>50000:
                raise ConnectionFailure('Maximum supported Product2 import is 50,000 rows.')
    if not 1<=len(rows)<=50000:
        raise ConnectionFailure('Use 1–50,000 rows per owner import.')
    return rows


def plan_product_import(client,rows,update_existing=False,batch_size=200):
    if not 1<=batch_size<=200:
        raise ConnectionFailure('REST batch size must be between 1 and 200.')
    access=client.check_access()
    existing=client.existing_codes([row['ProductCode'] for row in rows])
    creates=[row for row in rows if row['ProductCode'] not in existing]
    updates=[{'Id':existing[row['ProductCode']],**row} for row in rows if row['ProductCode'] in existing] if update_existing else []
    if creates and not access['product2_create'] or updates and not access['product2_update']:
        raise ConnectionFailure('This API user lacks Product2 create/update permission for the requested operation.')
    plan={'file_products':len(rows),'create_count':len(creates),'update_count':len(updates),
          'skipped_existing':len(existing) if not update_existing else 0,
          'estimated_write_requests':math.ceil(len(creates)/batch_size)+math.ceil(len(updates)/batch_size),
          'capacity_checked':False,'capacity_sufficient':True}
    if len(rows)>1000:
        limits=client.limits()
        def remaining(key):
            value=limits.get(key,{}).get('Remaining')
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ConnectionFailure('Cannot read reliable Salesforce '+key+' remaining limits. No large import was started.')
            return value
        # Planning estimate only: common Salesforce record allocation ~2 KB, plus 25% and 5 MB headroom.
        # Org automation and asynchronously updated limits can require additional storage.
        storage=math.ceil(len(creates)*2/1024*1.25)+5 if creates else 0
        available_storage=remaining('DataStorageMB');available_calls=remaining('DailyApiRequests')
        api_needed=plan['estimated_write_requests']+10 if plan['estimated_write_requests'] else 0
        plan.update(capacity_checked=True,estimated_storage_mb=storage,remaining_data_storage_mb=available_storage,
                    remaining_api_requests=available_calls,estimated_api_requests_after_plan=api_needed,
                    capacity_sufficient=storage<=available_storage and api_needed<=available_calls)
    return plan,creates,updates


def import_product_records(client,rows,update_existing=False,batch_size=200,progress=None):
    plan,creates,updates=plan_product_import(client,rows,update_existing,batch_size)
    if not plan['capacity_sufficient']:
        raise ConnectionFailure('Insufficient Salesforce capacity for this import plan: estimated storage '+str(plan['estimated_storage_mb'])+
                                ' MB; available '+str(plan['remaining_data_storage_mb'])+' MB; required API requests '+str(plan['estimated_api_requests_after_plan'])+
                                '; available '+str(plan['remaining_api_requests'])+'. No records were written. Use --plan for details.')
    report={'created':0,'updated':0,'skipped_existing':plan['skipped_existing']}
    for group,updating,key in [(creates,False,'created'),(updates,True,'updated')]:
        for start in range(0,len(group),batch_size):
            report[key]+=client.write_products(group[start:start+batch_size],update=updating)
            if progress:
                progress({**report,'file_products':len(rows),'remaining':len(creates)+len(updates)-report['created']-report['updated']})
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
