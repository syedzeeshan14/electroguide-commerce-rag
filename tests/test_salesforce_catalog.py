import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from app.integrations import ConnectionFailure
from app.salesforce_catalog import SalesforceCatalogClient,read_product_csv,import_product_records,sync_product_catalog,normalize_catalog_record
from scripts.export_salesforce_products import export_products,product2_row
from scripts.generate_catalog import generate
from app.catalog import Catalog

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'65.0','SALESFORCE_ACCESS_TOKEN':'fake-unit-test-token'}


def record():
    row=product2_row(next(generate(1)))
    return {**row,'IsActive':True,'Id':'01t000000000001AAA'}


class SalesforceCatalogTests(unittest.TestCase):
    def test_product2_csv_and_metadata_round_trip_without_commerce_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=export_products(Path(directory)/'products.csv')
            rows=read_product_csv(path)
            self.assertEqual(len(rows),100)
            self.assertNotIn('StockKeepingUnit',rows[0])
            product=normalize_catalog_record({**rows[0],'Id':'01t000000000001AAA'})
            self.assertEqual(product['source'],'salesforce_catalog_snapshot')
            self.assertEqual(product['price_source'],'synthetic_usd_metadata')
            self.assertEqual(product['currency'],'USD')
            self.assertEqual(product['price'],next(generate(1))['price'])

    def test_access_check_uses_only_standard_product2_endpoints(self):
        schema={'queryable':True,'createable':True,'updateable':False,'fields':[{'name':name} for name in ['Id','Name','ProductCode','Description','IsActive']]}
        response=Mock(status_code=200);response.json.return_value=schema
        client=SalesforceCatalogClient(CONFIG)
        with patch('app.lightning.requests.request',return_value=response) as request,patch.object(client,'query',return_value=iter([])):
            access=client.check_access()
            self.assertTrue(access['product2_create'])
            self.assertTrue(request.call_args.args[1].endswith('/sobjects/Product2/describe'))
            self.assertNotIn('/commerce/',request.call_args.args[1])
        client=SalesforceCatalogClient(CONFIG)
        blocked=Mock(status_code=403);blocked.json.return_value=[{'errorCode':'API_DISABLED_FOR_ORG','message':'private provider details'}]
        with patch('app.lightning.requests.request',return_value=blocked):
            with self.assertRaises(ConnectionFailure) as error: client.check_access()
            self.assertIn('API_DISABLED_FOR_ORG',str(error.exception))
            self.assertNotIn('private provider details',str(error.exception))
            self.assertNotIn(CONFIG['SALESFORCE_ACCESS_TOKEN'],str(error.exception))

    def test_idempotent_import_skips_existing_records_and_write_permissions_checked(self):
        rows=[{**product2_row(p),'IsActive':True} for p in generate(2)]
        client=Mock()
        client.check_access.return_value={'product2_create':True,'product2_update':True}
        client.existing_codes.return_value={rows[0]['ProductCode']:'01t000000000001AAA'}
        client.write_products.side_effect=lambda group,update=False:len(group)
        report=import_product_records(client,rows)
        self.assertEqual(report,{'created':1,'updated':0,'skipped_existing':1})
        self.assertEqual(client.write_products.call_args.args[0],[rows[1]])
        client.write_products.reset_mock()
        report=import_product_records(client,rows,update_existing=True)
        self.assertEqual(report['updated'],1)
        self.assertTrue(client.write_products.call_args.kwargs['update'])
        client.check_access.return_value={'product2_create':False,'product2_update':False}
        with self.assertRaises(ConnectionFailure): import_product_records(client,rows)

    def test_batch_requests_are_product2_only_and_all_or_none(self):
        client=SalesforceCatalogClient(CONFIG)
        response=Mock(status_code=200);response.json.return_value=[{'success':True,'id':'01t000000000001AAA'}]
        with patch('app.lightning.requests.request',return_value=response) as request:
            self.assertEqual(client.write_products([{'Name':'Demo','ProductCode':'EG-000001'}]),1)
            body=request.call_args.kwargs['json']
            self.assertIs(body['allOrNone'],True)
            self.assertEqual(body['records'][0]['attributes']['type'],'Product2')
            self.assertTrue(request.call_args.args[1].endswith('/composite/sobjects'))
        response.json.return_value=[{'success':False,'errors':[{'message':'private error'}]}]
        with patch('app.lightning.requests.request',return_value=response):
            with self.assertRaises(ConnectionFailure): client.write_products([{'Name':'Demo'}])

    def test_snapshot_sync_never_calls_commerce_or_pricebook_in_default_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            client=Mock();client.settings={}
            client.imported_products.return_value=[record()]
            report=sync_product_catalog(client,directory)
            client.store_product.assert_not_called()
            client.stores.assert_not_called()
            client.pricebook_entries.assert_not_called()
            path=Path(directory)/'salesforce_catalog_snapshots'/report['snapshot_id']/'catalog.sqlite'
            catalog=Catalog(str(path))
            self.assertEqual(catalog.search(in_stock=False)[0]['salesforce_id'],record()['Id'])
            catalog.connection.close()
            pointer=Path(directory)/'salesforce-catalog-current.json'
            before=pointer.read_bytes()
            bad=record();bad['Description']='missing metadata'
            client.imported_products.return_value=[bad]
            with self.assertRaises(ConnectionFailure): sync_product_catalog(client,directory)
            self.assertEqual(pointer.read_bytes(),before)

    def test_pricebook_mode_requires_explicit_usd_verification(self):
        client=Mock();client.settings={'SALESFORCE_CATALOG_PRICING':'pricebook'}
        client.imported_products.return_value=[record()]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConnectionFailure): sync_product_catalog(client,directory)
            client.pricebook_entries.assert_not_called()
            client.settings['SALESFORCE_PRICEBOOK_CURRENCY']='USD'
            client.pricebook_entries.return_value={record()['Id']:123.45}
            report=sync_product_catalog(client,directory)
            self.assertEqual(report['price_source'],'selected_usd_pricebook_snapshot')

    def test_runtime_loads_store_free_snapshot(self):
        from app.runtime import prepare_catalog,_prepare_product2_snapshot
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=Mock();client.settings={}
            client.imported_products.return_value=[record()]
            sync_product_catalog(client,root/'data')
            with patch('app.runtime.ROOT',root),patch('app.runtime.settings',return_value={'CATALOG_SOURCE':'salesforce_catalog_snapshot'}):
                catalog=prepare_catalog()
                self.assertEqual(catalog.source,'salesforce_catalog_snapshot')
                self.assertEqual(catalog.price_source,'synthetic_usd_metadata')
                self.assertEqual(catalog.connection.execute('SELECT count(*) FROM products').fetchone()[0],1)
                catalog.connection.close();_prepare_product2_snapshot.clear()


    def test_streamlit_displays_product2_snapshot_without_store_setup(self):
        from streamlit.testing.v1 import AppTest
        from app.runtime import _prepare_product2_snapshot
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=Mock();client.settings={}
            row=record()
            # Ensure the single synthetic test product is available in the demo bag flow.
            from scripts.export_lightning_import import METADATA_MARKER
            prose,raw=row['Description'].rsplit(METADATA_MARKER,1)
            metadata=json.loads(raw);metadata['demo_stock']=10
            row['Description']=prose+METADATA_MARKER+json.dumps(metadata)
            row['Name']='Salesforce test product'
            client.imported_products.return_value=[row]
            sync_product_catalog(client,root/'data')
            with patch('app.runtime.ROOT',root),patch('app.runtime.settings',return_value={'CATALOG_SOURCE':'salesforce_catalog_snapshot','OPENAI_API_KEY':''}):
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
                self.assertFalse(app.exception)
                self.assertTrue(any('USD demo prices' in caption.value for caption in app.caption))
                self.assertTrue(any('Salesforce test product' in item.value for item in app.markdown))
                self.assertEqual(sum(button.label=='Add to bag' for button in app.button),1)
                next(button for button in app.button if button.label=='Add to bag').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(next(iter(app.session_state['cart'].values()))['salesforce_id'],row['Id'])
                _prepare_product2_snapshot.clear()

if __name__=='__main__': unittest.main()
