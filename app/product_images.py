"""Owner-side ProductMedia/CMS image download and private local rendering cache."""
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urljoin,urlparse,parse_qs
import warnings
import requests
from PIL import Image,UnidentifiedImageError
from app.integrations import ConnectionFailure
from app.lightning import salesforce_id
from app.salesforce_catalog import SalesforceCatalogClient

MAX_BYTES=10*1024*1024
MAX_PIXELS=25000000
FORMATS={'PNG':'png','JPEG':'jpg','WEBP':'webp','GIF':'gif'}


def image_format(data):
    if not data or len(data)>MAX_BYTES:
        raise ConnectionFailure('Product image is empty or exceeds 10 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in FORMATS or image.width*image.height>MAX_PIXELS:
                    raise ConnectionFailure('Use a PNG, JPEG, WebP or GIF image below 25 megapixels.')
                extension=FORMATS[image.format]
                image.verify()
                return extension
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ConnectionFailure('The returned content is not a supported product image; it may be a login or CMS preview page.') from None


def cache_directory(root,instance_url):
    parsed=urlparse(instance_url.strip())
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.my.salesforce.com'):
        return None
    scope=hashlib.sha256(('https://'+parsed.hostname).encode()).hexdigest()[:20]
    return Path(root)/'data/product_images'/scope


def cached_image_path(product,root,settings):
    if product.get('source')!='salesforce_catalog_snapshot' or not product.get('salesforce_id'):
        return None
    directory=cache_directory(root,settings.get('SALESFORCE_INSTANCE_URL',''))
    if directory is None:
        return None
    try:
        index=json.loads((directory/'index.json').read_text(encoding='utf-8'))
        filename=index.get(product['salesforce_id'],{}).get('filename','')
        if not isinstance(filename,str) or not re.fullmatch(r'[a-f0-9]{64}\.(png|jpg|webp|gif)',filename):
            return None
        path=directory/filename
        return path if path.is_file() else None
    except (OSError,ValueError,AttributeError,TypeError):
        return None


def store_cached_image(directory,product_id,data,metadata):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    extension=image_format(data)
    filename=hashlib.sha256(data).hexdigest()+'.'+extension
    (directory/filename).write_bytes(data)
    index_path=directory/'index.json'
    index=json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    index[product_id]={**metadata,'filename':filename,'fetched_at':datetime.now(timezone.utc).isoformat()}
    temp=directory/'index.tmp'
    temp.write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')
    temp.replace(index_path)
    return filename


class ProductImageClient(SalesforceCatalogClient):
    def product_media(self,product_id):
        product_id=salesforce_id(product_id,'01t')
        rows=list(self.query("SELECT Id,ElectronicMediaId,SortOrder,ElectronicMediaGroup.UsageType,ElectronicMediaGroup.DeveloperName FROM ProductMedia WHERE ProductId='"+product_id+"'"))
        def priority(row):
            group=row.get('ElectronicMediaGroup') or {}
            usage=group.get('UsageType','')
            name=group.get('DeveloperName','')
            rank=0 if usage=='Listing' or name=='productListImage' else 1 if usage=='Standard' or name=='productDetailImage' else 9
            order=row.get('SortOrder')
            return rank,order if isinstance(order,int) else 999,str(row.get('Id',''))
        return [row for row in sorted(rows,key=priority) if priority(row)[0]<9]

    def file_media(self,product_id):
        product_id=salesforce_id(product_id,'01t')
        rows=list(self.query("SELECT ContentDocumentId,ContentDocument.FileExtension,ContentDocument.LatestPublishedVersionId,ContentDocument.ContentModifiedDate FROM ContentDocumentLink WHERE LinkedEntityId='"+product_id+"'"))
        result=[]
        for row in rows:
            document=row.get('ContentDocument') or {}
            if str(document.get('FileExtension','')).lower() in ('png','jpg','jpeg','webp','gif'):
                version=document.get('LatestPublishedVersionId','')
                salesforce_id(version,'068')
                result.append({'Id':row['ContentDocumentId'],'ElectronicMediaId':version,'ElectronicMediaGroup':{'UsageType':'Files'},
                               '_download_url':self.api_root()+f'/sobjects/ContentVersion/{version}/VersionData',
                               '_modified':document.get('ContentModifiedDate','')})
        return sorted(result,key=lambda row:row['_modified'],reverse=True)

    def _object_for_id(self,record_id):
        record_id=salesforce_id(record_id)
        if not hasattr(self,'_image_object_prefixes'):
            result=self._request('GET',self.api_root()+'/sobjects')
            allowed={'ManagedContent','ManagedContentInfo','ExternalMedia','ContentDocument','ContentVersion'}
            self._image_object_prefixes={row['keyPrefix']:row['name'] for row in result.get('sobjects',[]) if row.get('name') in allowed and row.get('keyPrefix')}
        return self._image_object_prefixes.get(record_id[:3])

    def _cms_image_urls(self,payload):
        """Only inspect content bodies/media nodes, not API record/navigation links."""
        def walk(node,depth=0):
            if depth>10:
                return
            if isinstance(node,dict):
                for key,value in node.items():
                    if key.lower() in ('url','unauthenticatedurl','downloadurl','versiondataurl','mediaurl') and isinstance(value,str):
                        yield value
                    elif isinstance(value,(dict,list)):
                        yield from walk(value,depth+1)
            elif isinstance(node,list):
                for value in node:
                    yield from walk(value,depth+1)
        for key in ('contentBody','contentNodes'):
            if key in payload:
                yield from walk(payload[key])

    def media_urls(self,media_id):
        media_id=salesforce_id(media_id)
        kind=self._object_for_id(media_id)
        if not kind:
            raise ConnectionFailure('The product media refers to an unsupported object type. Run the image diagnostic and check CMS access.')
        record=self._request('GET',self.api_root()+f'/sobjects/{kind}/{media_id}')
        if kind=='ContentVersion':
            return [self.api_root()+f'/sobjects/ContentVersion/{media_id}/VersionData']
        if kind=='ContentDocument':
            version=salesforce_id(record.get('LatestPublishedVersionId',''),'068')
            return [self.api_root()+f'/sobjects/ContentVersion/{version}/VersionData']
        # Common direct URL/binary references exposed by external/CMS records.
        urls=[value for key,value in record.items() if key.lower() in ('url','mediaurl','externalurl','contenturl','sourceurl','versiondataurl') and isinstance(value,str) and value]
        version=record.get('ContentVersionId') or record.get('LatestPublishedVersionId')
        if isinstance(version,str) and version.startswith('068'):
            salesforce_id(version,'068')
            urls.insert(0,self.api_root()+f'/sobjects/ContentVersion/{version}/VersionData')
        if kind in ('ManagedContent','ManagedContentInfo'):
            key=record.get('ContentKey') or record.get('ManagedContentId') or media_id
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_]{15,80}',key):
                raise ConnectionFailure('CMS media did not expose a valid content key or managed-content ID.')
            try:
                content=self._request('GET',self.api_root()+'/connect/cms/contents/'+key)
                urls.extend(self._cms_image_urls(content))
            except ConnectionFailure:
                if not urls:
                    raise ConnectionFailure('The OAuth user can see ProductMedia but cannot resolve this CMS image. Check its CMS workspace access and the media diagnostic.') from None
        if not urls:
            raise ConnectionFailure('The media record exposes no downloadable image URL. Check CMS workspace access and image publication/delivery configuration.')
        return list(dict.fromkeys(urls))

    def _download_target(self,url):
        target=urljoin(self.base+'/',url)
        try:
            parsed=urlparse(target)
            port=parsed.port
        except ValueError:
            raise ConnectionFailure('Invalid image URL.') from None
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or port or parsed.fragment or '\\' in target or any(character in target for character in '\r\n'):
            raise ConnectionFailure('The image URL must be a valid HTTPS URL without embedded credentials.')
        try:
            ipaddress.ip_address(parsed.hostname)
            raise ConnectionFailure('IP-address image hosts are not supported.')
        except ValueError:
            pass
        if any(key.lower() in ('access_token','sessionid','sid','authorization') for key in parse_qs(parsed.query)):
            raise ConnectionFailure('Image URLs containing OAuth/session credentials are not supported.')
        host=urlparse(self.base).hostname
        configured={value.strip().lower() for value in self.settings.get('SALESFORCE_IMAGE_HOSTS','').split(',') if value.strip()}
        sf_suffixes=('.file.force.com','.content.force.com','.my.site.com','.salesforce-experience.com')
        if parsed.hostname!=host and not parsed.hostname.endswith(sf_suffixes) and parsed.hostname not in configured:
            raise ConnectionFailure('Image host is not approved: '+parsed.hostname+'. Add only a trusted public image hostname to SALESFORCE_IMAGE_HOSTS.')
        # OAuth headers go ONLY to the explicitly configured My Domain host.
        headers={}
        if parsed.hostname==host:
            self.authenticate()
            headers={'Authorization':'Bearer '+self.token}
        return target,headers

    def download_image(self,url):
        for _ in range(4):
            target,headers=self._download_target(url)
            try:
                with requests.get(target,headers=headers,timeout=30,stream=True,allow_redirects=False) as response:
                    if response.status_code in (301,302,303,307,308):
                        location=response.headers.get('Location')
                        if not location:
                            raise ConnectionFailure('Image redirect has no destination.')
                        url=urljoin(target,location)
                        continue
                    if response.status_code!=200:
                        raise ConnectionFailure(f'Image download returned HTTP {response.status_code}. Check file/CMS access and delivery configuration.')
                    length=response.headers.get('Content-Length')
                    if length and (not length.isdigit() or int(length)>MAX_BYTES):
                        raise ConnectionFailure('Image exceeds the 10 MB download limit.')
                    parts=[];size=0
                    for part in response.iter_content(65536):
                        size+=len(part)
                        if size>MAX_BYTES:
                            raise ConnectionFailure('Image exceeds the 10 MB download limit.')
                        parts.append(part)
                    data=b''.join(parts)
                    image_format(data)
                    return data
            except requests.RequestException:
                raise ConnectionFailure('Image download failed. Check connectivity and file/CMS access.') from None
        raise ConnectionFailure('Too many image redirects.')


def sync_product_image(client,root,product_id):
    product_id=salesforce_id(product_id,'01t')
    failures=[]
    try:
        rows=client.product_media(product_id)
    except ConnectionFailure as error:
        rows=[];failures.append(str(error))
    try:
        rows.extend(client.file_media(product_id))
    except ConnectionFailure as error:
        failures.append(str(error))
    if not rows:
        raise ConnectionFailure('No readable Product List/Detail Images or attached image Files found. '+(' '.join(failures))[:600])
    for row in rows:
        try:
            urls=[row['_download_url']] if row.get('_download_url') else client.media_urls(row['ElectronicMediaId'])
            for url in urls:
                try:
                    data=client.download_image(url)
                    directory=cache_directory(root,client.base)
                    metadata={'product_id':product_id,'media_id':row['ElectronicMediaId'],'usage':(row.get('ElectronicMediaGroup') or {}).get('UsageType',''),
                              'source':'salesforce_files' if row.get('_download_url') else 'salesforce_product_media'}
                    filename=store_cached_image(directory,product_id,data,metadata)
                    return {**metadata,'cached_file':filename,'status':'image cached'}
                except ConnectionFailure as error:
                    failures.append(str(error))
        except (ConnectionFailure,KeyError) as error:
            failures.append(str(error))
    raise ConnectionFailure('No product image could be downloaded. '+(' '.join(dict.fromkeys(failures)))[:1200])
