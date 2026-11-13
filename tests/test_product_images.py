from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image
from app.product_images import ProductImageClient,cache_directory,cached_image_path,store_cached_image,image_format,sync_product_image,MAX_BYTES
from app.integrations import ConnectionFailure

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'65.0','SALESFORCE_ACCESS_TOKEN':'fake-unit-test-token'}
PRODUCT='01t000000000001AAA'
MEDIA='0cu000000000001AAA'


def png_bytes():
    output=BytesIO();Image.new('RGB',(20,20),(10,80,40)).save(output,format='PNG');return output.getvalue()


def response(data,status=200,headers=None):
    reply=Mock(status_code=status,headers=headers or {})
    reply.iter_content.return_value=[data]
    reply.__enter__=Mock(return_value=reply);reply.__exit__=Mock(return_value=False)
    return reply


class ProductImageTests(unittest.TestCase):
    def test_listing_preferred_then_detail_other_media_excluded(self):
        client=ProductImageClient(CONFIG)
        rows=[{'Id':'1','ElectronicMediaGroup':{'UsageType':'Standard'},'SortOrder':0},
              {'Id':'2','ElectronicMediaGroup':{'UsageType':'Listing'},'SortOrder':3},
              {'Id':'3','ElectronicMediaGroup':{'UsageType':'Attachment'},'SortOrder':0}]
        with patch.object(client,'query',return_value=iter(rows)):
            result=client.product_media(PRODUCT)
        self.assertEqual([row['Id'] for row in result],['2','1'])

    def test_cms_content_body_resolves_media_url(self):
        client=ProductImageClient(CONFIG)
        with patch.object(client,'_object_for_id',return_value='ManagedContentInfo'),patch.object(client,'_request',side_effect=[
            {'ContentKey':'MCEXAMPLECONTENTKEY'},
            {'contentBody':{'sfdc_cms:media':{'url':'/cms/delivery/media/MCEXAMPLECONTENTKEY'}}}]) as request:
            self.assertEqual(client.media_urls(MEDIA),['/cms/delivery/media/MCEXAMPLECONTENTKEY'])
            self.assertIn('/connect/cms/contents/MCEXAMPLECONTENTKEY',request.call_args.args[1])

    def test_enhanced_authoring_preview_uses_workspace_delivery_document(self):
        client=ProductImageClient(CONFIG)
        key='MCWA5MYGI6YNE4THPYPQHWPFKWRQ'
        content={'contentKey':key,'contentSpace':{'id':'0Zu000000000001AAA'},
                 'contentBody':{'sfdc_cms:media':{'source':{'type':'file','ref':'0sN000000000001AAA'},'url':'/cms/media/'+key}}}
        delivered={'contentBody':{'sfdc_cms:media':{'url':'https://demo.lightning.force.com/cms/delivery/media/'+key+'?channelId=0ap000000000001AAA'}}}
        with patch.object(client,'_object_for_id',return_value='ManagedContent'),patch.object(client,'_request',side_effect=[
            {'ContentKey':key},content,
            {'spaceChannels':[{'status':'Added','channelSummary':{'id':'0ap000000000001AAA'}}]},delivered]) as request:
            urls=client.media_urls(MEDIA)
        self.assertEqual(urls,['/cms/delivery/media/'+key+'?channelId=0ap000000000001AAA'])
        self.assertIn('/spaces/0Zu000000000001AAA/channels',request.call_args_list[2].args[1])
        self.assertIn('/delivery/channels/0ap000000000001AAA/contents/'+key,request.call_args_list[3].args[1])

    def test_missing_delivery_channel_reports_access_problem(self):
        client=ProductImageClient(CONFIG)
        content={'contentKey':'MCEXAMPLECONTENTKEY','contentSpace':{'id':'0Zu000000000001AAA'}}
        with patch.object(client,'_request',return_value={'spaceChannels':[]}):
            with self.assertRaisesRegex(ConnectionFailure,'existing workspace channels'):
                client.cms_delivery_urls(content)

    def test_authenticated_download_never_forwards_token_to_cdn_on_redirect(self):
        client=ProductImageClient(CONFIG)
        first=response(b'',302,{'Location':'https://demo.file.force.com/image.png'})
        second=response(png_bytes())
        with patch('app.product_images.requests.get',side_effect=[first,second]) as get:
            data=client.download_image('/cms/media/example')
            self.assertEqual(data,png_bytes())
            self.assertEqual(get.call_args_list[0].kwargs['headers']['Authorization'],'Bearer '+CONFIG['SALESFORCE_ACCESS_TOKEN'])
            self.assertEqual(get.call_args_list[1].kwargs['headers'],{})
            self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_unsafe_hosts_and_non_images_are_rejected(self):
        client=ProductImageClient(CONFIG)
        for url in ['http://demo.my.salesforce.com/a','https://attacker.example/a','https://127.0.0.1/a','https://demo.my.salesforce.com/a?access_token=secret','https://demo.my.salesforce.com:bad/a']:
            with self.assertRaises(ConnectionFailure): client._download_target(url)
        with patch('app.product_images.requests.get',return_value=response(b'<html>login</html>')):
            with self.assertRaises(ConnectionFailure): client.download_image('/cms/media/a')
        with patch('app.product_images.requests.get',return_value=response(b'',headers={'Content-Length':str(MAX_BYTES+1)})):
            with self.assertRaises(ConnectionFailure): client.download_image('/cms/media/a')

    def test_local_cache_and_path_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=cache_directory(root,CONFIG['SALESFORCE_INSTANCE_URL'])
            store_cached_image(cache,PRODUCT,png_bytes(),{'source':'salesforce_product_media'})
            product={'source':'salesforce_catalog_snapshot','salesforce_id':PRODUCT}
            self.assertTrue(cached_image_path(product,root,CONFIG).is_file())
            self.assertIsNone(cached_image_path({**product,'source':'demo'},root,CONFIG))
            self.assertIsNone(cached_image_path(product,root,{**CONFIG,'SALESFORCE_INSTANCE_URL':'https://another.my.salesforce.com'}))
            (cache/'index.json').write_text(json.dumps({PRODUCT:{'filename':'../../secret.toml'}}))
            self.assertIsNone(cached_image_path(product,root,CONFIG))

    def test_detail_image_sync_and_files_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            client=Mock();client.base=CONFIG['SALESFORCE_INSTANCE_URL']
            client.product_media.return_value=[{'ElectronicMediaId':MEDIA,'ElectronicMediaGroup':{'UsageType':'Standard'}}]
            client.file_media.return_value=[];client.media_urls.return_value=['/cms/media/example'];client.download_image.return_value=png_bytes()
            report=sync_product_image(client,directory,PRODUCT)
            self.assertEqual(report['usage'],'Standard')
            self.assertTrue(cached_image_path({'source':'salesforce_catalog_snapshot','salesforce_id':PRODUCT},directory,CONFIG))
            client.product_media.side_effect=ConnectionFailure('CMS unavailable')
            client.file_media.return_value=[{'ElectronicMediaId':'068000000000001AAA','ElectronicMediaGroup':{'UsageType':'Files'},'_download_url':'/services/data/v65.0/sobjects/ContentVersion/068000000000001AAA/VersionData'}]
            report=sync_product_image(client,directory,PRODUCT)
            self.assertEqual(report['source'],'salesforce_files')

if __name__=='__main__': unittest.main()
