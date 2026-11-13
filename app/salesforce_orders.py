"""Academic draft Orders, not Commerce checkout, payment, or inventory reservation."""
from datetime import date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from app.integrations import ConnectionFailure
from app.lightning import salesforce_id
from app.salesforce_catalog import SalesforceCatalogClient,demo_metadata

BOOK_NAME='ElectroGuide Academic USD'
BOOK_DESCRIPTION='ElectroGuide academic demo pricing; not a live storefront price book.'
ACCOUNT_NAME='ElectroGuide Academic Demo Customer'
REQUIRED_FIELDS={'Order':{'AccountId','EffectiveDate','Status','Pricebook2Id','Description'},
                 'OrderItem':{'OrderId','PricebookEntryId','Quantity','UnitPrice'}}
REFERENCE_FIELDS=('ElectroGuide_Checkout_Reference__c','PoNumber','OrderReferenceNumber','Name')


def reference_capabilities(schema):
    fields={field['name']:field for field in schema.get('fields',[])}
    candidates={name:{'readable':name in fields,'writable':fields.get(name,{}).get('createable') is True,
                      'filterable':fields.get(name,{}).get('filterable') is True,
                      'length':fields.get(name,{}).get('length',0)} for name in REFERENCE_FIELDS}
    selected=next((name for name,flags in candidates.items() if flags['readable'] and flags['writable'] and flags['filterable'] and flags['length']>=35),None)
    return selected,candidates


def money(value):
    try:
        amount=Decimal(str(value))
        if not amount.is_finite() or amount<0 or isinstance(value,bool):
            raise ValueError()
        return amount.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    except (InvalidOperation,ValueError,TypeError):
        raise ConnectionFailure('Invalid USD order amount.') from None


def cart_details(cart,allow_local=False):
    if not isinstance(cart,dict) or not 1<=len(cart)<=20:
        raise ConnectionFailure('Use 1–20 distinct products per academic order.')
    lines=[];seen=set()
    for product in cart.values():
        is_local=product.get('source','demo')=='demo' and product.get('synthetic') is True
        if product.get('currency')!='USD' or not (product.get('source')=='salesforce_catalog_snapshot' or allow_local and is_local):
            raise ConnectionFailure('Use a synced Salesforce catalog, or enable academic on-demand import for the local USD catalog.')
        if is_local:
            if not re.fullmatch(r'EG-[0-9]{6}',product.get('id','')):
                raise ConnectionFailure('Only EG-000001-style local demo products can be ordered.')
            product_id='local:'+product['id']
        else:
            product_id=salesforce_id(product.get('salesforce_id',''),'01t')
        quantity=product.get('quantity')
        if isinstance(quantity,bool) or not isinstance(quantity,int) or not 1<=quantity<=product.get('stock',0):
            raise ConnectionFailure('Order quantity exceeds the listed demo stock.')
        if product_id in seen:
            raise ConnectionFailure('Duplicate Salesforce product in the bag.')
        seen.add(product_id)
        lines.append({'product_id':product_id,'code':product['id'],'quantity':quantity,'price':str(money(product['price']))})
    lines.sort(key=lambda line:line['product_id'])
    signature=hashlib.sha256(json.dumps(lines,sort_keys=True).encode()).hexdigest()
    total=sum((money(line['price'])*line['quantity'] for line in lines),Decimal(0))
    return lines,signature,money(total)


class SalesforceOrderClient(SalesforceCatalogClient):
    def access_diagnostic(self):
        report={}
        for name,required in REQUIRED_FIELDS.items():
            try:
                schema=self._request('GET',self.api_root()+f'/sobjects/{name}/describe')
                fields={field['name']:field for field in schema.get('fields',[])}
                report[name]={'queryable':schema.get('queryable') is True,
                              'createable':schema.get('createable') is True,
                              'missing_readable_fields':sorted(required-set(fields)),
                              'missing_writable_fields':sorted(field for field in required if not fields.get(field,{}).get('createable'))}
                if name=='Order':
                    selected,candidates=reference_capabilities(schema)
                    report[name].update(reference_field=selected,reference_candidates=candidates)
            except ConnectionFailure as error:
                report[name]={'error':str(error)}
        return report

    def order_access(self):
        schemas={name:self._request('GET',self.api_root()+f'/sobjects/{name}/describe') for name in ('Order','OrderItem')}
        needed=REQUIRED_FIELDS
        for name,schema in schemas.items():
            writable={field['name'] for field in schema.get('fields',[]) if field.get('createable')}
            if not schema.get('createable') or not schema.get('queryable') or not needed[name]<=writable:
                raise ConnectionFailure(name+' access check failed: queryable='+str(schema.get('queryable') is True)+', createable='+str(schema.get('createable') is True)+', missing writable fields='+', '.join(sorted(needed[name]-writable))+'. Check Order Settings and permissions for the External Client App Run As user; use --diagnose for both objects.')
        self._order_reference_field,_=reference_capabilities(schemas['Order'])
        if not self._order_reference_field:
            raise ConnectionFailure('No readable, writable, filterable Order reference field of at least 35 characters is available. Run --diagnose. Grant access to a supported reference field, or create ElectroGuide_Checkout_Reference__c as a Text(80) unique external-ID field and grant access.')
        fields={field['name'] for field in schemas['Order'].get('fields',[])}
        if not {'OrderNumber','TotalAmount','Id'}<=fields:
            raise ConnectionFailure('The API user must be able to read OrderNumber and TotalAmount.')
        self.multi_currency='CurrencyIsoCode' in fields
        single_currency=None
        if self.multi_currency:
            currencies=list(self.query("SELECT IsoCode FROM CurrencyType WHERE IsoCode='USD' AND IsActive=true"))
            usd=bool(currencies)
        else:
            features=self._request('GET',self.api_root()+'/connect/organization').get('features',{})
            single_currency=features.get('defaultCurrencyIsoCode')
            usd=features.get('multiCurrency') is False and single_currency=='USD'
        return {'order_create':True,'order_item_create':True,'multi_currency':self.multi_currency,'single_currency':single_currency,'usd_supported':usd,'reference_field':self._order_reference_field}

    def require_usd(self):
        access=self.order_access()
        if not access['usd_supported']:
            raise ConnectionFailure('This org cannot currently create USD Orders. Enable USD through an appropriate multi-currency setup, or use a USD academic org. INR amounts will not be relabeled as USD. No records were written.')
        return access

    def composite(self,requests):
        response=self._request('POST',self.api_root()+'/composite',json={'allOrNone':True,'collateSubrequests':False,'compositeRequest':requests})
        results=response.get('compositeResponse',[])
        if len(results)!=len(requests) or any(not 200<=row.get('httpStatusCode',0)<300 for row in results):
            codes=[]
            for row in results:
                body=row.get('body',[])
                for error in body if isinstance(body,list) else []:
                    code=error.get('errorCode','') if isinstance(error,dict) else ''
                    if re.fullmatch(r'[A-Z_]{3,80}',code): codes.append(code)
            raise ConnectionFailure('Salesforce rejected the atomic batch'+(' ('+', '.join(dict.fromkeys(codes))+')' if codes else '')+'. No partial batch was requested; check required fields, validation rules and permissions.')
        return {row['referenceId']:row.get('body') for row in results}

    def configured_records(self):
        account=salesforce_id(self.settings.get('SALESFORCE_ORDER_ACCOUNT_ID',''),'001')
        book=salesforce_id(self.settings.get('SALESFORCE_ORDER_PRICEBOOK_ID',''),'01s')
        if not list(self.query(f"SELECT Id FROM Account WHERE Id='{account}' LIMIT 1")):
            raise ConnectionFailure('The configured order Account is not readable.')
        rows=list(self.query(f"SELECT Id,Name,Description,IsActive FROM Pricebook2 WHERE Id='{book}' LIMIT 1"))
        if not rows or not rows[0].get('IsActive'):
            raise ConnectionFailure('The configured order price book must be readable and active.')
        if self.settings.get('SALESFORCE_ORDER_DEMO_PRICING','').lower()=='true' and (rows[0].get('Name')!=BOOK_NAME or rows[0].get('Description')!=BOOK_DESCRIPTION):
            raise ConnectionFailure('Automatic demo pricing is limited to the dedicated ElectroGuide academic price book.')
        return account,book

    def entries(self,book,lines):
        ids=','.join("'"+line['product_id']+"'" for line in lines)
        currency=" AND CurrencyIsoCode='USD'" if self.multi_currency else ''
        return list(self.query(f"SELECT Id,Product2Id,UnitPrice,IsActive,Product2.IsActive FROM PricebookEntry WHERE Pricebook2Id='{book}' AND Product2Id IN ({ids})"+currency))

    def ensure_demo_prices(self,book,lines):
        """Only fill missing demo entries; never overwrite an existing price or activate products."""
        ids=','.join("'"+line['product_id']+"'" for line in lines)
        records=list(self.query(f'SELECT Id,ProductCode,Description,IsActive FROM Product2 WHERE Id IN ({ids})'))
        products={record['Id']:record for record in records}
        for line in lines:
            record=products.get(line['product_id'])
            if not record or not record.get('IsActive') or record.get('ProductCode')!=line['code']:
                raise ConnectionFailure('A bag product is no longer an active Salesforce project product.')
            metadata=demo_metadata(record)
            if money(metadata.get('demo_price_usd'))!=money(line['price']) or isinstance(metadata.get('demo_stock'),bool) or not isinstance(metadata.get('demo_stock'),int) or metadata['demo_stock']<line['quantity']:
                raise ConnectionFailure('Salesforce demo price or availability changed. Sync the catalog and rebuild your bag before ordering.')
        standard=list(self.query('SELECT Id FROM Pricebook2 WHERE IsStandard=true AND IsActive=true LIMIT 1'))
        if not standard:
            raise ConnectionFailure('An active Standard Price Book is required. Activate it in Salesforce before using demo order pricing.')
        standard_id=salesforce_id(standard[0]['Id'],'01s')
        # Standard prices must exist before custom prices. Separate atomic batches are
        # intentional: setup entries can remain if an eventual order is rejected.
        for selected in dict.fromkeys((standard_id,book)):
            existing={row['Product2Id'] for row in self.entries(selected,lines)}
            missing=[line for line in lines if line['product_id'] not in existing]
            if missing:
                batch=[]
                for index,line in enumerate(missing):
                    body={'Pricebook2Id':selected,'Product2Id':line['product_id'],'UnitPrice':float(money(line['price'])),'IsActive':True}
                    if self.multi_currency: body['CurrencyIsoCode']='USD'
                    batch.append({'method':'POST','url':self.api_root()+'/sobjects/PricebookEntry','referenceId':f'price{index}','body':body})
                self.composite(batch)

    def reference_field(self):
        field=getattr(self,'_order_reference_field',None)
        if field not in REFERENCE_FIELDS:
            raise ConnectionFailure('Order reference field has not been verified. Rerun the order access check.')
        return field

    def find_order(self,reference,account,book,signature,total):
        field=self.reference_field()
        rows=list(self.query("SELECT Id,OrderNumber,TotalAmount,Status,Description FROM Order WHERE "+field+"='"+reference+f"' AND AccountId='{account}' AND Pricebook2Id='{book}' LIMIT 2"))
        if not rows: return None
        if len(rows)!=1 or rows[0].get('Description')!='ElectroGuide academic demo '+signature or money(rows[0].get('TotalAmount'))!=total:
            raise ConnectionFailure('The order reference has conflicting Salesforce data. Review it before retrying; no new order was created.')
        row=rows[0]
        record_id=salesforce_id(row.get('Id',''),'801')
        number=row.get('OrderNumber')
        if not isinstance(number,str) or not number.strip():
            raise ConnectionFailure('Salesforce has not returned an order number yet. Keep the bag and retry the same request.')
        return {'id':number,'salesforce_id':record_id,'subtotal':float(total),'source':'salesforce_draft','status':row.get('Status'),'currency':'USD',
                'url':self.base+'/lightning/r/Order/'+record_id+'/view'}

    def bind_local_products(self,cart):
        """Create/reuse only local bag products. Never bulk-import the 50K catalog."""
        from scripts.export_salesforce_products import product2_row
        local=[product for product in cart.values() if product.get('source','demo')=='demo']
        if not local:
            return cart
        if str(self.settings.get('SALESFORCE_ORDER_IMPORT_ON_DEMAND','')).lower()!='true' or str(self.settings.get('SALESFORCE_ORDER_DEMO_PRICING','')).lower()!='true':
            raise ConnectionFailure('Local-catalog orders require explicit on-demand import and dedicated academic demo pricing setup.')
        # Validate the complete bag before doing any import writes.
        cart_details(cart,allow_local=True)
        codes=[product['id'] for product in local]
        existing=self.existing_codes(codes)
        missing=[product for product in local if product['id'] not in existing]
        remaining=self.limits().get('DataStorageMB',{}).get('Remaining')
        # Product2 + up to two price entries + OrderItems/header, with headroom.
        estimated=math.ceil((len(missing)+3*len(cart)+1)*2*1.25/1024)+1
        if isinstance(remaining,bool) or not isinstance(remaining,(int,float)) or not math.isfinite(remaining) or remaining<estimated:
            raise ConnectionFailure('Insufficient Salesforce storage headroom for this order and its product/price records. No new bag products were imported. Archive demo records through an approved org process or use a larger org.')
        if missing:
            if not self.check_access()['product2_create']:
                raise ConnectionFailure('Product2 create permission is needed to add new bag products.')
            rows=[{**product2_row(product),'IsActive':True} for product in missing]
            self.write_products(rows)
            existing=self.existing_codes(codes)
        bound={}
        for key,product in cart.items():
            if product.get('source','demo')=='demo':
                record_id=existing.get(product['id'])
                if not record_id:
                    raise ConnectionFailure('A bag product import could not be verified. Keep the bag and retry; existing codes are reused.')
                bound[key]={**product,'salesforce_id':salesforce_id(record_id,'01t'),'source':'salesforce_catalog_snapshot'}
            else:
                bound[key]=product
        if getattr(self,'local_root',None) is not None:
            from app.product_images import cache_directory
            directory=cache_directory(self.local_root,self.base)
            directory.mkdir(parents=True,exist_ok=True)
            path=directory/'product-links.json'
            links=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            links.update({product['id']:existing[product['id']] for product in local})
            temporary=directory/'product-links.tmp'
            temporary.write_text(json.dumps(links,sort_keys=True)+'\n',encoding='utf-8')
            temporary.replace(path)
        return bound

    def create_draft(self,cart,reference):
        if not re.fullmatch(r'EG-[a-f0-9]{32}',reference):
            raise ConnectionFailure('Invalid checkout request reference.')
        allow_local=str(self.settings.get('SALESFORCE_ORDER_IMPORT_ON_DEMAND','')).lower()=='true'
        lines,signature,total=cart_details(cart,allow_local=allow_local)
        self.require_usd()
        account,book=self.configured_records()
        existing=self.find_order(reference,account,book,signature,total)
        if existing: return existing
        if any(line['product_id'].startswith('local:') for line in lines):
            bound=self.bind_local_products(cart)
            lines,_,_=cart_details(bound)
        if self.settings.get('SALESFORCE_ORDER_DEMO_PRICING','').lower()=='true':
            self.ensure_demo_prices(book,lines)
        entries=self.entries(book,lines)
        selected={}
        for entry in entries:
            if entry['Product2Id'] in selected:
                raise ConnectionFailure('Duplicate USD price-book entries found.')
            selected[entry['Product2Id']]=entry
        for line in lines:
            entry=selected.get(line['product_id'])
            if not entry or not entry.get('IsActive') or not (entry.get('Product2') or {}).get('IsActive'):
                raise ConnectionFailure('A product has no active USD entry in the order price book. Prepare demo pricing or select a complete USD price book.')
            if money(entry['UnitPrice'])!=money(line['price']):
                raise ConnectionFailure('The bag price differs from the Salesforce USD price book. Sync matching prices and rebuild the bag; no order was created.')
        body={'AccountId':account,'Pricebook2Id':book,'EffectiveDate':date.today().isoformat(),'Status':'Draft',
              self.reference_field():reference,'Description':'ElectroGuide academic demo '+signature}
        if self.multi_currency: body['CurrencyIsoCode']='USD'
        batch=[{'method':'POST','url':self.api_root()+'/sobjects/Order','referenceId':'order','body':body}]
        for index,line in enumerate(lines):
            batch.append({'method':'POST','url':self.api_root()+'/sobjects/OrderItem','referenceId':f'line{index}',
                          'body':{'OrderId':'@{order.id}','PricebookEntryId':salesforce_id(selected[line['product_id']]['Id'],'01u'),
                                  'Quantity':line['quantity'],'UnitPrice':float(money(line['price']))}})
        self.composite(batch)
        result=self.find_order(reference,account,book,signature,total)
        if not result:
            raise ConnectionFailure('The create request completed but its order number could not be verified. Keep the bag and retry the same request; do not submit a new reference.')
        return result


def submit_order(client,root,cart,reference):
    """Serialize local retries and retain confirmed receipts across process restarts."""
    allow_local=str(client.settings.get('SALESFORCE_ORDER_IMPORT_ON_DEMAND','')).lower()=='true'
    _,signature,_=cart_details(cart,allow_local=allow_local)
    scope=hashlib.sha256(client.base.encode()).hexdigest()[:20]
    directory=Path(root)/'data/order_receipts';directory.mkdir(parents=True,exist_ok=True)
    try:
        with sqlite3.connect(directory/(scope+'.sqlite'),timeout=60) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS receipts (reference TEXT PRIMARY KEY, signature TEXT, receipt TEXT)')
            connection.execute('BEGIN IMMEDIATE')
            row=connection.execute('SELECT signature,receipt FROM receipts WHERE reference=?',(reference,)).fetchone()
            if row:
                if row[0]!=signature:
                    raise ConnectionFailure('This checkout reference belongs to a different bag.')
                return json.loads(row[1])
            client.local_root=Path(root)
            result=client.create_draft(cart,reference)
            connection.execute('INSERT INTO receipts VALUES (?,?,?)',(reference,signature,json.dumps(result)))
            return result
    except sqlite3.Error:
        raise ConnectionFailure('The local order receipt store is busy or unavailable. Keep your bag and retry the same request.') from None
