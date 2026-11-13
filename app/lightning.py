"""Read-only Salesforce-platform Commerce connector for a local owner-operated demo.

OAuth client credentials act as the configured integration user, NOT an anonymous
shopper. No customer/checkout actions are performed by this connector.
"""
from datetime import datetime,timezone
import json
import re
from urllib.parse import urlparse
import requests
from app.integrations import ConnectionFailure
from scripts.export_lightning_import import METADATA_MARKER
from scripts.generate_catalog import CATEGORIES,BRANDS


def salesforce_id(value,prefix=None):
    if not re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?',value or '') or (prefix and not value.startswith(prefix)):
        raise ConnectionFailure('Invalid Salesforce record ID. Use the 15- or 18-character ID from your org.')
    return value


class LightningClient:
    def __init__(self,settings):
        self.settings=settings
        parsed=urlparse(settings.get('SALESFORCE_INSTANCE_URL','').strip())
        if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.my.salesforce.com') or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ConnectionFailure('Set SALESFORCE_INSTANCE_URL to your HTTPS My Domain base URL, for example https://your-domain.my.salesforce.com. Do not use a Lightning page URL.')
        self.base='https://'+parsed.hostname
        self.token=settings.get('SALESFORCE_ACCESS_TOKEN','').strip()
        self.version=settings.get('SALESFORCE_API_VERSION','').strip()
        if self.version and not re.fullmatch(r'\d{2,3}\.0',self.version):
            raise ConnectionFailure('API version must resemble 65.0 or be left blank for discovery.')

    def authenticate(self):
        if self.token:
            return
        client=self.settings.get('SALESFORCE_CLIENT_ID','').strip()
        secret=self.settings.get('SALESFORCE_CLIENT_SECRET','').strip()
        if not client or not secret:
            raise ConnectionFailure('Configure a Salesforce OAuth access token or External Client App ID/secret locally. Do not enter a Salesforce password.')
        payload=self._request('POST','/services/oauth2/token',authenticated=False,data={'grant_type':'client_credentials','client_id':client,'client_secret':secret})
        if not isinstance(payload,dict):
            raise ConnectionFailure('Salesforce did not return valid OAuth credentials.')
        self.token=payload.get('access_token','')
        if not isinstance(self.token,str) or not self.token:
            raise ConnectionFailure('Salesforce did not return a valid OAuth access token.')

    def _request(self,method,path,authenticated=True,**kwargs):
        # Pagination must stay on the configured Salesforce host and API path.
        if not path.startswith('/services/') or '..' in path or '://' in path or path.startswith('//'):
            raise ConnectionFailure('Invalid Salesforce API path.')
        if authenticated:
            self.authenticate()
        headers={'Authorization':'Bearer '+self.token} if authenticated else {}
        operation=method.upper()+' '+path.split('?',1)[0]
        try:
            response=requests.request(method,self.base+path,headers=headers,timeout=30,allow_redirects=False,**kwargs)
        except requests.Timeout:
            raise ConnectionFailure('Salesforce request timed out during '+operation+'. A write may already have completed. Rerun the same setup or checkout reference to recover its result.') from None
        except requests.exceptions.SSLError:
            raise ConnectionFailure('TLS certificate validation failed during '+operation+'. Check the local certificate/proxy configuration; keep TLS verification enabled.') from None
        except requests.ConnectionError:
            raise ConnectionFailure('Could not connect to Salesforce during '+operation+'. Check connectivity and the configured My Domain.') from None
        except requests.RequestException:
            raise ConnectionFailure('Salesforce request did not complete during '+operation+'. No response body or credentials were logged.') from None
        if response.status_code!=200:
            error_code='';hint=''
            try:
                body=response.json()
                candidate=body[0].get('errorCode','') if isinstance(body,list) and body and isinstance(body[0],dict) else ''
                if isinstance(candidate,str) and re.fullmatch(r'[A-Z_]{3,80}',candidate):
                    error_code=' ('+candidate+')'
                if path=='/services/oauth2/token' and isinstance(body,dict):
                    code=body.get('error')
                    oauth_hints={
                        'invalid_client':'Verify the new org consumer key and current consumer secret; ensure the app is enabled.',
                        'invalid_client_id':'The consumer key was not accepted. Use the Consumer Key from this org External Client App.',
                        'invalid_client_credentials':'The client credentials were not accepted. Recopy the current consumer key and secret privately.',
                        'invalid_grant':'Check Client Credentials Flow and its active Run As user in this org app policies.',
                        'unauthorized_client':'Check that Client Credentials Flow is enabled for this app.',
                        'unsupported_grant_type':'This app or domain did not accept the client-credentials grant.',
                        'invalid_scope':'Check the app OAuth API scope.',
                        'invalid_request':'Check the app OAuth configuration and configured My Domain.',
                        'access_denied':'The app or execution user is denied by OAuth policy.',
                        'server_error':'Salesforce could not process the OAuth request.',
                        'temporarily_unavailable':'Salesforce OAuth is temporarily unavailable.'}
                    if isinstance(code,str) and code in oauth_hints:
                        error_code=' (OAuth '+code+')'
                        hint=oauth_hints[code]
                        known_descriptions={
                            'no client credentials user enabled':'Select an active Run As user under the app Policies Client Credentials Flow settings and save.',
                            'request not supported on this domain':'Use the new org My Domain base URL ending in .my.salesforce.com.',
                            'user is inactive':'The configured Run As user must be active.',
                            'user is frozen':'Unfreeze or select an active permitted Run As user.',
                            'client credentials flow not enabled':'Enable Client Credentials Flow in the app settings and policies.'}
                        description=body.get('error_description')
                        if isinstance(description,str):
                            hint=known_descriptions.get(description.strip().lower(),hint)

            except (ValueError,TypeError):
                pass
            raise ConnectionFailure(f'Salesforce returned HTTP {response.status_code}{error_code}. '+(hint or 'Check API entitlement, OAuth policy, user permissions, and token expiration.'))
        try:
            payload=response.json()
        except (ValueError,TypeError):
            raise ConnectionFailure('Salesforce returned HTTP '+str(response.status_code)+' with non-JSON content during '+operation+'. It may be a proxy or login response. No response body or credentials were logged.') from None
        if not isinstance(payload,(dict,list)):
            raise ConnectionFailure('Salesforce returned an unexpected JSON value during '+operation+'. No response body was logged.')
        return payload

    def api_root(self):
        if not self.version:
            versions=self._request('GET','/services/data/',authenticated=False)
            if not isinstance(versions,list) or not versions:
                raise ConnectionFailure('Salesforce API version discovery failed.')
            available=[row.get('version','') for row in versions if isinstance(row,dict) and re.fullmatch(r'\d{2,3}\.0',str(row.get('version','')))]
            if not available:
                raise ConnectionFailure('Salesforce did not advertise a usable API version.')
            self.version=max(available,key=float)
        return '/services/data/v'+self.version

    def query(self,soql):
        path=self.api_root()+'/query'
        params={'q':soql}
        while path:
            payload=self._request('GET',path,params=params)
            if not isinstance(payload,dict) or not isinstance(payload.get('records'),list):
                raise ConnectionFailure('Unexpected Salesforce query response.')
            yield from payload['records']
            path=payload.get('nextRecordsUrl')
            params=None
            if path and (not isinstance(path,str) or not path.startswith(self.api_root()+'/query/')):
                raise ConnectionFailure('Salesforce returned an invalid pagination path.')

    def stores(self):
        return list(self.query('SELECT Id, Name FROM WebStore ORDER BY Name LIMIT 100'))

    def imported_products(self,limit=100):
        if not 1<=limit<=1000:
            raise ConnectionFailure('Start with a sync limit between 1 and 1000.')
        return list(self.query("SELECT Id,Name,ProductCode,StockKeepingUnit,Description,IsActive FROM Product2 WHERE IsActive=true AND ProductCode LIKE 'EG-%' ORDER BY ProductCode LIMIT "+str(int(limit))))

    def store_product(self,product_id):
        store=salesforce_id(self.settings.get('SALESFORCE_WEBSTORE_ID',''))
        product=salesforce_id(product_id,'01t')
        params={}
        account=self.settings.get('SALESFORCE_EFFECTIVE_ACCOUNT_ID','').strip()
        if account:
            params['effectiveAccountId']=salesforce_id(account,'001')
        return self._request('GET',self.api_root()+f'/commerce/webstores/{store}/products/{product}',params=params)

    def pricebook_entries(self,product_ids):
        pricebook=salesforce_id(self.settings.get('SALESFORCE_PRICEBOOK_ID',''),'01s')
        entries={}
        # Read explicit catalog/list prices. These are NOT buyer-specific checkout prices.
        for start in range(0,len(product_ids),100):
            batch=[salesforce_id(value,'01t') for value in product_ids[start:start+100]]
            ids=','.join("'"+value+"'" for value in batch)
            query=f"SELECT Product2Id,UnitPrice FROM PricebookEntry WHERE IsActive=true AND Pricebook2Id='{pricebook}' AND Product2Id IN ({ids})"
            if self.settings.get('SALESFORCE_MULTI_CURRENCY','').lower()=='true':
                query+=" AND CurrencyIsoCode='USD'"
            for row in self.query(query):
                product=row['Product2Id']
                if product in entries:
                    raise ConnectionFailure('Multiple prices found for a product. Check the selected price book and USD currency configuration.')
                try:
                    price=float(row['UnitPrice'])
                except (ValueError,TypeError,KeyError):
                    raise ConnectionFailure('An imported product has an invalid price.') from None
                import math
                if not math.isfinite(price) or price<0:
                    raise ConnectionFailure('An imported product has an invalid price.')
                entries[product]=price
        return entries


def normalize_imported_product(record,price):
    """Only accept our import metadata; never invent specs for unrelated org products."""
    description=record.get('Description') or ''
    if METADATA_MARKER not in description:
        raise ConnectionFailure('Imported product metadata is missing. Use the Lightning Commerce import file supplied with this project.')
    prose,raw=description.rsplit(METADATA_MARKER,1)
    try:
        metadata=json.loads(raw)
    except (ValueError,TypeError):
        raise ConnectionFailure('An imported product has invalid ElectroGuide metadata.') from None
    if not isinstance(metadata,dict):
        raise ConnectionFailure('Imported product metadata must be a JSON object.')
    if metadata.get('category') not in CATEGORIES or metadata.get('brand') not in BRANDS or not isinstance(metadata.get('specifications'),dict) or metadata.get('synthetic') is not True:
        raise ConnectionFailure('Imported metadata does not match the supported demo catalog schema.')
    numeric={'ram_gb','storage_gb','battery_hours','screen_inches','refresh_hz','case_mm','megapixels','power_watts'}
    import math
    for key,value in metadata['specifications'].items():
        if key in numeric and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
            raise ConnectionFailure('An imported specification has an invalid numeric value.')
        if key=='noise_cancelling' and not isinstance(value,bool):
            raise ConnectionFailure('Noise cancellation metadata must be true or false.')
        if not isinstance(value,(str,int,float,bool)) or isinstance(value,str) and len(value)>500:
            raise ConnectionFailure('An imported specification has an unsupported value.')
    code=record.get('ProductCode','')
    if not re.fullmatch(r'EG-\d{6}',code) or not record.get('StockKeepingUnit') or not record.get('Name'):
        raise ConnectionFailure('A product is missing its ElectroGuide code, SKU, or name.')
    stock=metadata.get('demo_stock')
    if isinstance(stock,bool) or not isinstance(stock,int) or stock<0:
        raise ConnectionFailure('An imported product has invalid simulated stock metadata.')
    return {'id':code,'sku':record['StockKeepingUnit'],'name':record['Name'],'brand':metadata['brand'],
            'category':metadata['category'],'price':price,'currency':'USD','stock':stock,
            'description':prose.strip(),'specifications':metadata['specifications'],'synthetic':True,
            'image_url':None,'use_case':metadata.get('use_case',''),'catalog_version':metadata.get('catalog_version',2),
            'salesforce_id':salesforce_id(record['Id'],'01t'),'source':'lightning_snapshot',
            'stock_source':'synthetic_metadata','price_source':'selected_pricebook_snapshot',
            'synced_at':datetime.now(timezone.utc).isoformat()}
