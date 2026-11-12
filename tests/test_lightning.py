import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from zipfile import ZipFile
from app.catalog import Catalog
from app.integrations import ConnectionFailure
from app.lightning import LightningClient,normalize_imported_product
from scripts.export_lightning_import import export,import_row,FIELDS
from scripts.generate_catalog import generate
from scripts.sync_lightning_catalog import sync_catalog

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'65.0',
        'SALESFORCE_ACCESS_TOKEN':'fake-unit-test-token','SALESFORCE_WEBSTORE_ID':'0ZE000000000001AAA',
        'SALESFORCE_PRICEBOOK_ID':'01s000000000001AAA'}


def sf_record(product=None):
    p=product or next(generate(1))
    row=import_row(p)
    return {'Id':'01t000000000001AAA','Name':row['Product Name'],'ProductCode':row['Product ProductCode'],
            'StockKeepingUnit':row['SKU'],'Description':row['Product Description'],'IsActive':True}


class LightningTests(unittest.TestCase):
    def test_commerce_import_schema_and_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            report=export(directory,count=100,batch_size=40)
            sample=Path(directory)/'commerce-products-100.csv'
            with sample.open(encoding='utf-8',newline='') as handle:
                reader=csv.DictReader(handle);rows=list(reader)
                self.assertEqual(reader.fieldnames,FIELDS)
            self.assertEqual(len(rows),100)
            self.assertEqual(len({row['SKU'] for row in rows}),100)
            self.assertTrue(all(row['Product isActive']=='true' for row in rows))
            with ZipFile(Path(directory)/'commerce-products-100-batches.zip') as archive:
                self.assertEqual(len(archive.namelist()),3)
                total=sum(len(list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8'))))) for name in archive.namelist())
                self.assertEqual(total,100)
            product=next(generate(1))
            restored=normalize_imported_product(sf_record(product),product['price'])
            self.assertEqual(restored['specifications'],product['specifications'])
            self.assertEqual(restored['id'],product['id'])
            self.assertEqual(restored['stock_source'],'synthetic_metadata')
            self.assertEqual(report['sample_count'],100)

    def test_oauth_scoped_urls_pagination_and_error_redaction(self):
        for url in ['http://demo.my.salesforce.com','https://attacker.example','https://demo.my.salesforce.com.evil.test','https://demo.my.salesforce.com/path']:
            with self.assertRaises(ConnectionFailure): LightningClient({**CONFIG,'SALESFORCE_INSTANCE_URL':url})
        client=LightningClient(CONFIG)
        first=Mock(status_code=200);first.json.return_value={'records':[{'Id':'one'}],'nextRecordsUrl':'/services/data/v65.0/query/next'}
        second=Mock(status_code=200);second.json.return_value={'records':[{'Id':'two'}],'done':True}
        with patch('app.lightning.requests.request',side_effect=[first,second]) as request:
            self.assertEqual(len(list(client.query('SELECT Id FROM WebStore'))),2)
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
        first.json.return_value={'records':[],'nextRecordsUrl':'https://attacker.example'}
        with patch('app.lightning.requests.request',return_value=first):
            with self.assertRaises(ConnectionFailure): list(client.query('SELECT Id FROM WebStore'))
        with patch('app.lightning.requests.request',return_value=Mock(status_code=401)):
            with self.assertRaises(ConnectionFailure) as error: client.stores()
            self.assertNotIn(CONFIG['SALESFORCE_ACCESS_TOKEN'],str(error.exception))

    def test_external_client_oauth_is_server_side(self):
        config={**CONFIG,'SALESFORCE_ACCESS_TOKEN':'','SALESFORCE_CLIENT_ID':'fake-client','SALESFORCE_CLIENT_SECRET':'fake-secret'}
        response=Mock(status_code=200);response.json.return_value={'access_token':'fake-returned-token','instance_url':'https://ignored.example'}
        client=LightningClient(config)
        with patch('app.lightning.requests.request',return_value=response) as request:
            client.authenticate()
            self.assertEqual(request.call_args.args,('POST','https://demo.my.salesforce.com/services/oauth2/token'))
            self.assertEqual(request.call_args.kwargs['data']['grant_type'],'client_credentials')
            self.assertEqual(client.token,'fake-returned-token')
            self.assertEqual(client.base,'https://demo.my.salesforce.com')

    def test_snapshot_activated_only_after_all_records_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            client=Mock();client.settings=CONFIG
            product=next(generate(1));record=sf_record(product)
            client.imported_products.return_value=[record]
            client.pricebook_entries.return_value={record['Id']:399.99}
            client.store_product.return_value={'id':record['Id']}
            report=sync_catalog(client,directory)
            pointer=Path(directory)/'lightning-current.json'
            before=pointer.read_bytes()
            catalog=Catalog(str(Path(directory)/'lightning_snapshots'/report['snapshot_id']/'catalog.sqlite'))
            rows=catalog.search(in_stock=False)
            self.assertEqual(rows[0]['price'],399.99)
            self.assertEqual(rows[0]['salesforce_id'],record['Id'])
            catalog.connection.close()
            client.store_product.side_effect=ConnectionFailure('Not entitled')
            with self.assertRaises(ConnectionFailure): sync_catalog(client,directory)
            self.assertEqual(pointer.read_bytes(),before)

    def test_missing_metadata_and_duplicate_price_fail_closed(self):
        record=sf_record();record['Description']='Unrelated product'
        with self.assertRaises(ConnectionFailure): normalize_imported_product(record,100)
        client=LightningClient(CONFIG)
        with patch.object(client,'query',return_value=iter([{'Product2Id':'01t000000000001AAA','UnitPrice':100},{'Product2Id':'01t000000000001AAA','UnitPrice':200}])):
            with self.assertRaises(ConnectionFailure): client.pricebook_entries(['01t000000000001AAA'])


    def test_app_catalog_selection_uses_only_the_completed_snapshot(self):
        from app.runtime import prepare_catalog,_prepare_lightning_snapshot
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            client=Mock();client.settings=CONFIG
            record=sf_record()
            client.imported_products.return_value=[record]
            client.pricebook_entries.return_value={record['Id']:123.45}
            client.store_product.return_value={'id':record['Id']}
            sync_catalog(client,root/'data')
            with patch('app.runtime.ROOT',root),patch('app.runtime.settings',return_value={'CATALOG_SOURCE':'lightning_snapshot'}):
                catalog=prepare_catalog()
                self.assertEqual(catalog.source,'lightning_snapshot')
                self.assertEqual(catalog.connection.execute('SELECT count(*) FROM products').fetchone()[0],1)
                self.assertEqual(catalog.search(in_stock=False)[0]['price'],123.45)
                catalog.connection.close()
                _prepare_lightning_snapshot.clear()

if __name__=='__main__': unittest.main()
