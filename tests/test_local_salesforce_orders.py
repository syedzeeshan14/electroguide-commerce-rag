from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.integrations import ConnectionFailure
from app.salesforce_orders import SalesforceOrderClient,cart_details
from scripts.generate_catalog import generate

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'68.0','SALESFORCE_ACCESS_TOKEN':'fake-token',
        'SALESFORCE_ORDER_IMPORT_ON_DEMAND':'true','SALESFORCE_ORDER_DEMO_PRICING':'true'}
PRODUCT='01t000000000001AAA'
REFERENCE='EG-'+'b'*32


def local_cart():
    product=next(p for p in generate(40100) if p['id']>'EG-040000' and p['stock']>0)
    return {product['id']:{**product,'quantity':1}}


class LocalSalesforceOrderTests(unittest.TestCase):
    def test_local_catalog_requires_explicit_opt_in(self):
        cart=local_cart()
        with self.assertRaises(ConnectionFailure): cart_details(cart)
        lines,_,_=cart_details(cart,allow_local=True)
        self.assertTrue(lines[0]['product_id'].startswith('local:EG-040'))

    def test_import_only_missing_bag_product_and_reuse_on_retry(self):
        cart=local_cart();code=next(iter(cart));client=SalesforceOrderClient(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            client.local_root=Path(directory)
            with patch.object(client,'existing_codes',side_effect=[{}, {code:PRODUCT}]),patch.object(client,'limits',return_value={'DataStorageMB':{'Remaining':5}}),patch.object(client,'check_access',return_value={'product2_create':True}),patch.object(client,'write_products') as write:
                bound=client.bind_local_products(cart)
            self.assertEqual(len(write.call_args.args[0]),1)
            self.assertEqual(write.call_args.args[0][0]['ProductCode'],code)
            self.assertEqual(bound[code]['salesforce_id'],PRODUCT)
            self.assertEqual(bound[code]['source'],'salesforce_catalog_snapshot')
            self.assertNotIn('salesforce_id',cart[code])
            with patch.object(client,'existing_codes',return_value={code:PRODUCT}),patch.object(client,'limits',return_value={'DataStorageMB':{'Remaining':5}}),patch.object(client,'write_products') as write:
                client.bind_local_products(cart)
                write.assert_not_called()
            # A later Salesforce image sync can render against the local product code.
            from app.product_images import cache_directory,store_cached_image,cached_image_path
            from io import BytesIO
            from PIL import Image
            image=BytesIO();Image.new('RGB',(20,20),'green').save(image,format='PNG')
            store_cached_image(cache_directory(directory,client.base),PRODUCT,image.getvalue(),{})
            self.assertTrue(cached_image_path(cart[code],directory,CONFIG))

    def test_capacity_failure_prevents_import_and_no_flag_prevents_write(self):
        cart=local_cart();client=SalesforceOrderClient(CONFIG)
        with patch.object(client,'existing_codes',return_value={}),patch.object(client,'limits',return_value={'DataStorageMB':{'Remaining':0}}),patch.object(client,'write_products') as write:
            with self.assertRaisesRegex(ConnectionFailure,'storage headroom'): client.bind_local_products(cart)
            write.assert_not_called()
        client=SalesforceOrderClient({**CONFIG,'SALESFORCE_ORDER_IMPORT_ON_DEMAND':'false'})
        with patch.object(client,'write_products') as write:
            with self.assertRaises(ConnectionFailure): client.bind_local_products(cart)
            write.assert_not_called()

    def test_create_order_preserves_local_request_signature_after_binding(self):
        cart=local_cart();code=next(iter(cart));product=cart[code]
        client=SalesforceOrderClient(CONFIG);client._order_reference_field='PoNumber';client.multi_currency=False
        bound={code:{**product,'source':'salesforce_catalog_snapshot','salesforce_id':PRODUCT}}
        entry={'Id':'01u000000000001AAA','Product2Id':PRODUCT,'UnitPrice':product['price'],'IsActive':True,'Product2':{'IsActive':True}}
        receipt={'id':'00000042','salesforce_id':'801000000000001AAA','subtotal':product['price'],'status':'Draft','source':'salesforce_draft'}
        with patch.object(client,'require_usd'),patch.object(client,'configured_records',return_value=('001000000000001AAA','01s000000000001AAA')),patch.object(client,'find_order',side_effect=[None,receipt]) as find,patch.object(client,'bind_local_products',return_value=bound) as bind,patch.object(client,'ensure_demo_prices'),patch.object(client,'entries',return_value=[entry]),patch.object(client,'composite') as write:
            self.assertEqual(client.create_draft(cart,REFERENCE),receipt)
        _,signature,_=cart_details(cart,allow_local=True)
        self.assertEqual(find.call_args_list[0].args[3],signature)
        self.assertEqual(find.call_args_list[1].args[3],signature)
        self.assertEqual(write.call_args.args[0][1]['body']['PricebookEntryId'],entry['Id'])
        bind.assert_called_once()
        # If the first response was lost, recover before doing another import.
        with patch.object(client,'require_usd'),patch.object(client,'configured_records',return_value=('001000000000001AAA','01s000000000001AAA')),patch.object(client,'find_order',return_value=receipt),patch.object(client,'bind_local_products') as bind:
            self.assertEqual(client.create_draft(cart,REFERENCE),receipt)
            bind.assert_not_called()

    def test_ui_50k_catalog_can_submit_local_bag_to_order_connector(self):
        from streamlit.testing.v1 import AppTest
        receipt={'id':'00000042','salesforce_id':'801000000000001AAA','subtotal':10,'source':'salesforce_draft','status':'Draft'}
        with patch('app.runtime.settings',return_value={**CONFIG,'CATALOG_SOURCE':'demo','SALESFORCE_ORDER_SYNC':'salesforce_draft','OPENAI_API_KEY':''}),patch('app.salesforce_orders.submit_order',return_value=receipt) as submit:
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('50,000 locally stored products' in caption.value for caption in app.caption))
            next(button for button in app.button if button.label=='Add to bag' and not button.disabled).click().run()
            next(button for button in app.button if button.label.startswith('Bag (')).click().run()
            next(button for button in app.button if button.label=='Save draft order').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('00000042' in success.value for success in app.success))
            self.assertTrue(next(iter(submit.call_args.args[2].values()))['synthetic'])

    def test_partial_local_catalog_is_backed_up_and_restored_to_50k(self):
        import json
        import shutil
        from app.runtime import ROOT,_prepare_demo_catalog
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir()
            original=json.dumps(next(generate(1)))+'\n'
            (data/'products.jsonl').write_text(original)
            (data/'manifest.json').write_text(json.dumps({'catalog_version':2,'count':1}))
            shutil.copy2(ROOT/'data/electroguide-catalog-50000.zip',data/'electroguide-catalog-50000.zip')
            _prepare_demo_catalog.clear()
            try:
                with patch('app.runtime.ROOT',root):
                    catalog=_prepare_demo_catalog()
                    self.assertEqual(catalog.connection.execute('SELECT count(*) FROM products').fetchone()[0],50000)
                    catalog.connection.close()
                backup=next((data/'catalog_backups').glob('*/products.jsonl'))
                self.assertEqual(backup.read_text(),original)
            finally:
                _prepare_demo_catalog.clear()

if __name__=='__main__': unittest.main()
