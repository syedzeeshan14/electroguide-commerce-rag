import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from app.integrations import ConnectionFailure
from app.salesforce_orders import SalesforceOrderClient,cart_details,submit_order
from scripts.setup_salesforce_orders import save_local_settings

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'68.0',
        'SALESFORCE_ACCESS_TOKEN':'fake-test-token','SALESFORCE_ORDER_ACCOUNT_ID':'001000000000001AAA',
        'SALESFORCE_ORDER_PRICEBOOK_ID':'01s000000000001AAA'}
REFERENCE='EG-'+'a'*32
PRODUCT='01t000000000001AAA'
CART={'EG-000001':{'id':'EG-000001','salesforce_id':PRODUCT,'source':'salesforce_catalog_snapshot',
                   'currency':'USD','stock':10,'quantity':2,'price':100.25}}
RECEIPT={'id':'00000123','salesforce_id':'801000000000001AAA','subtotal':200.5,'source':'salesforce_draft','status':'Draft','currency':'USD'}


class SalesforceOrderTests(unittest.TestCase):
    def test_atomic_order_and_lines_use_salesforce_number(self):
        client=SalesforceOrderClient(CONFIG)
        entry={'Id':'01u000000000001AAA','Product2Id':PRODUCT,'UnitPrice':100.25,'IsActive':True,'Product2':{'IsActive':True}}
        with patch.object(client,'require_usd') as currency,patch.object(client,'configured_records',return_value=(CONFIG['SALESFORCE_ORDER_ACCOUNT_ID'],CONFIG['SALESFORCE_ORDER_PRICEBOOK_ID'])),patch.object(client,'find_order',side_effect=[None,RECEIPT]),patch.object(client,'entries',return_value=[entry]),patch.object(client,'_request',return_value={'compositeResponse':[
            {'referenceId':'order','httpStatusCode':201,'body':{'id':RECEIPT['salesforce_id']}},
            {'referenceId':'line0','httpStatusCode':201,'body':{'id':'802000000000001AAA'}}]}) as request:
            client.multi_currency=False
            result=client.create_draft(CART,REFERENCE)
        self.assertEqual(result['id'],'00000123')
        payload=request.call_args.kwargs['json']
        self.assertTrue(payload['allOrNone'])
        order,line=payload['compositeRequest']
        self.assertEqual(order['body']['Status'],'Draft')
        self.assertEqual(order['body']['PoNumber'],REFERENCE)
        self.assertEqual(line['body']['OrderId'],'@{order.id}')
        self.assertEqual(line['body']['Quantity'],2)
        self.assertEqual(line['body']['UnitPrice'],100.25)

    def test_recover_remote_order_before_attempting_another_write(self):
        client=SalesforceOrderClient(CONFIG)
        with patch.object(client,'require_usd'),patch.object(client,'configured_records',return_value=('001000000000001AAA','01s000000000001AAA')),patch.object(client,'find_order',return_value=RECEIPT),patch.object(client,'composite') as write:
            self.assertEqual(client.create_draft(CART,REFERENCE),RECEIPT)
            write.assert_not_called()

    def test_receipt_ledger_serializes_retries_and_checks_bag(self):
        with tempfile.TemporaryDirectory() as directory:
            client=Mock(base=CONFIG['SALESFORCE_INSTANCE_URL'])
            client.create_draft.return_value=RECEIPT
            self.assertEqual(submit_order(client,directory,CART,REFERENCE),RECEIPT)
            self.assertEqual(submit_order(client,directory,CART,REFERENCE),RECEIPT)
            client.create_draft.assert_called_once()
            changed={key:{**value,'quantity':3} for key,value in CART.items()}
            with self.assertRaises(ConnectionFailure): submit_order(client,directory,changed,REFERENCE)

    def test_currency_or_price_mismatch_prevents_order_creation(self):
        client=SalesforceOrderClient(CONFIG)
        with patch.object(client,'order_access',return_value={'usd_supported':False}),patch.object(client,'composite') as write:
            with self.assertRaisesRegex(ConnectionFailure,'INR'): client.create_draft(CART,REFERENCE)
            write.assert_not_called()
        entry={'Id':'01u000000000001AAA','Product2Id':PRODUCT,'UnitPrice':99,'IsActive':True,'Product2':{'IsActive':True}}
        with patch.object(client,'require_usd'),patch.object(client,'configured_records',return_value=('001000000000001AAA','01s000000000001AAA')),patch.object(client,'find_order',return_value=None),patch.object(client,'entries',return_value=[entry]),patch.object(client,'composite') as write:
            with self.assertRaisesRegex(ConnectionFailure,'price differs'): client.create_draft(CART,REFERENCE)
            write.assert_not_called()

    def test_atomic_error_and_invalid_cart_never_report_success(self):
        client=SalesforceOrderClient(CONFIG)
        with patch.object(client,'_request',return_value={'compositeResponse':[{'httpStatusCode':400,'body':[{'errorCode':'FIELD_CUSTOM_VALIDATION_EXCEPTION','message':'private details'}]}]}):
            with self.assertRaises(ConnectionFailure) as error: client.composite([{}])
            self.assertNotIn('private details',str(error.exception))
        for change in [{'quantity':0},{'quantity':True},{'price':float('nan')},{'source':'demo'},{'currency':'INR'},{'quantity':11}]:
            with self.assertRaises(ConnectionFailure): cart_details({'EG-000001':{**CART['EG-000001'],**change}})

    def test_single_currency_org_must_be_usd(self):
        client=SalesforceOrderClient(CONFIG)
        schemas=[]
        for fields in [('AccountId','EffectiveDate','Status','Pricebook2Id','PoNumber','Description','OrderNumber','TotalAmount','Id'),('OrderId','PricebookEntryId','Quantity','UnitPrice')]:
            schemas.append({'createable':True,'queryable':True,'fields':[{'name':field,'createable':True} for field in fields]})
        with patch.object(client,'_request',side_effect=schemas+[{'features':{'multiCurrency':False,'defaultCurrencyIsoCode':'INR'}}]):
            self.assertFalse(client.order_access()['usd_supported'])

    def test_local_setup_preserves_secrets_and_places_keys_above_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'secrets.toml'
            path.write_text('OPENAI_API_KEY="fake-secret"\nSALESFORCE_ORDER_SYNC="off"\n[other]\nvalue=1\n')
            save_local_settings(path,{'SALESFORCE_ORDER_SYNC':'salesforce_draft','CATALOG_SOURCE':'salesforce_catalog_snapshot'})
            import tomllib
            saved=tomllib.loads(path.read_text())
            self.assertEqual(saved['OPENAI_API_KEY'],'fake-secret')
            self.assertEqual(saved['CATALOG_SOURCE'],'salesforce_catalog_snapshot')
            self.assertEqual(saved['other']['value'],1)

    def test_demo_price_setup_creates_only_missing_entries_without_updates(self):
        from scripts.export_lightning_import import METADATA_MARKER
        client=SalesforceOrderClient(CONFIG);client.multi_currency=False
        lines,_,_=cart_details(CART)
        record={'Id':PRODUCT,'ProductCode':'EG-000001','IsActive':True,
                'Description':METADATA_MARKER+json.dumps({'demo_price_usd':100.25,'demo_stock':10})}
        with patch.object(client,'query',side_effect=[iter([record]),iter([{'Id':'01s000000000002AAA'}])]),patch.object(client,'entries',side_effect=[[],[]]),patch.object(client,'composite') as write:
            client.ensure_demo_prices(CONFIG['SALESFORCE_ORDER_PRICEBOOK_ID'],lines)
        self.assertEqual(write.call_count,2)
        for call in write.call_args_list:
            self.assertEqual(call.args[0][0]['method'],'POST')
            self.assertEqual(call.args[0][0]['body']['UnitPrice'],100.25)
        with patch.object(client,'query',side_effect=[iter([record]),iter([{'Id':'01s000000000002AAA'}])]),patch.object(client,'entries',return_value=[{'Product2Id':PRODUCT}]),patch.object(client,'composite') as write:
            client.ensure_demo_prices(CONFIG['SALESFORCE_ORDER_PRICEBOOK_ID'],lines)
            write.assert_not_called()

    def test_setup_blocked_currency_has_no_writes_and_rerun_reuses_records(self):
        from scripts.setup_salesforce_orders import setup_demo
        from app.salesforce_orders import BOOK_DESCRIPTION
        client=SalesforceOrderClient(CONFIG)
        with patch.object(client,'require_usd',side_effect=ConnectionFailure('USD unavailable')),patch.object(client,'composite') as write:
            with self.assertRaises(ConnectionFailure): setup_demo(client)
            write.assert_not_called()
        with patch.object(client,'require_usd'),patch.object(client,'query',side_effect=[
            iter([{'Id':'01s000000000002AAA'}]),iter([{'Id':CONFIG['SALESFORCE_ORDER_ACCOUNT_ID']}]),
            iter([{'Id':CONFIG['SALESFORCE_ORDER_PRICEBOOK_ID'],'Description':BOOK_DESCRIPTION,'IsActive':True}])]),patch.object(client,'composite') as write:
            updates=setup_demo(client)
            self.assertEqual(updates['SALESFORCE_ORDER_SYNC'],'salesforce_draft')
            write.assert_not_called()

    def test_conflicting_remote_reference_is_not_accepted(self):
        client=SalesforceOrderClient(CONFIG)
        _,signature,total=cart_details(CART)
        with patch.object(client,'query',return_value=iter([{'Id':RECEIPT['salesforce_id'],'OrderNumber':'00000123','TotalAmount':200.5,'Status':'Draft','Description':'different cart'}])):
            with self.assertRaisesRegex(ConnectionFailure,'conflicting'):
                client.find_order(REFERENCE,CONFIG['SALESFORCE_ORDER_ACCOUNT_ID'],CONFIG['SALESFORCE_ORDER_PRICEBOOK_ID'],signature,total)

    def test_ui_keeps_bag_after_failure_and_shows_salesforce_number_on_success(self):
        from streamlit.testing.v1 import AppTest
        from app.runtime import _prepare_product2_snapshot
        from app.salesforce_catalog import normalize_catalog_record
        from app.snapshots import publish_snapshot
        from scripts.export_salesforce_products import product2_row
        from scripts.generate_catalog import generate
        from scripts.export_lightning_import import METADATA_MARKER
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            row={**product2_row(next(generate(1))),'Id':PRODUCT,'IsActive':True}
            prose,raw=row['Description'].rsplit(METADATA_MARKER,1)
            metadata=json.loads(raw);metadata['demo_stock']=10
            row['Description']=prose+METADATA_MARKER+json.dumps(metadata)
            product=normalize_catalog_record(row)
            publish_snapshot([product],root/'data','salesforce_catalog_snapshot',{'price_source':'synthetic_usd_metadata'})
            config={**CONFIG,'CATALOG_SOURCE':'salesforce_catalog_snapshot','SALESFORCE_ORDER_SYNC':'salesforce_draft','OPENAI_API_KEY':''}
            with patch('app.runtime.ROOT',root),patch('app.runtime.settings',return_value=config),patch('app.salesforce_orders.submit_order',side_effect=[ConnectionFailure('Test rejection'),RECEIPT]) as submit:
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
                next(b for b in app.button if b.label=='Add to bag').click().run()
                next(b for b in app.button if b.label.startswith('Bag (')).click().run()
                next(b for b in app.button if b.label=='Save draft order').click().run()
                self.assertTrue(app.session_state['cart'])
                self.assertFalse(app.session_state['orders'])
                reference=app.session_state['pending_order']['reference']
                next(b for b in app.button if b.label=='Save draft order').click().run()
                self.assertFalse(app.exception)
                self.assertFalse(app.session_state['cart'])
                self.assertTrue(any('00000123' in success.value for success in app.success))
                self.assertEqual(submit.call_args.args[3],reference)
            _prepare_product2_snapshot.clear()

if __name__=='__main__': unittest.main()
