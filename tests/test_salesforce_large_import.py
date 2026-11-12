import unittest
from unittest.mock import Mock,patch
from app.integrations import ConnectionFailure
from app.salesforce_catalog import SalesforceCatalogClient,plan_product_import,import_product_records

CONFIG={'SALESFORCE_INSTANCE_URL':'https://demo.my.salesforce.com','SALESFORCE_API_VERSION':'65.0','SALESFORCE_ACCESS_TOKEN':'fake-test-token'}


class LargeImportTests(unittest.TestCase):
    def test_large_plan_reads_limits_and_insufficient_storage_blocks_all_writes(self):
        rows=[{'ProductCode':f'EG-{i:06d}'} for i in range(1,1002)]
        client=Mock();client.check_access.return_value={'product2_create':True,'product2_update':True}
        client.existing_codes.return_value={}
        client.limits.return_value={'DataStorageMB':{'Remaining':1},'DailyApiRequests':{'Remaining':15000}}
        plan,_,_=plan_product_import(client,rows)
        self.assertTrue(plan['capacity_checked'])
        self.assertFalse(plan['capacity_sufficient'])
        with self.assertRaises(ConnectionFailure): import_product_records(client,rows)
        client.write_products.assert_not_called()
        client.limits.return_value={'DataStorageMB':{'Remaining':1000},'DailyApiRequests':{'Remaining':15000}}
        plan,_,_=plan_product_import(client,rows)
        self.assertTrue(plan['capacity_sufficient'])
        self.assertEqual(plan['estimated_write_requests'],6)
        client.limits.return_value={'DataStorageMB':{'Remaining':1000},'DailyApiRequests':{'Remaining':1}}
        with self.assertRaises(ConnectionFailure): import_product_records(client,rows)
        client.write_products.assert_not_called()

    def test_interrupted_run_resumes_by_skipping_committed_remote_codes(self):
        rows=[{'ProductCode':f'EG-{i:06d}'} for i in range(1,501)]
        saved={};calls=0
        client=Mock();client.check_access.return_value={'product2_create':True,'product2_update':True}
        client.existing_codes.side_effect=lambda codes:{code:saved[code] for code in codes if code in saved}
        def write(batch,update=False):
            nonlocal calls
            calls+=1
            if calls==2:
                raise ConnectionFailure('Temporary transport failure')
            self.assertLessEqual(len(batch),200)
            for row in batch:
                self.assertNotIn(row['ProductCode'],saved)
                saved[row['ProductCode']]='fake-id'
            return len(batch)
        client.write_products.side_effect=write
        with self.assertRaises(ConnectionFailure): import_product_records(client,rows)
        self.assertEqual(len(saved),200)
        report=import_product_records(client,rows)
        self.assertEqual(report,{'created':300,'updated':0,'skipped_existing':200})
        self.assertEqual(len(saved),500)

    def test_full_file_existing_lookup_uses_paginated_prefix_query(self):
        codes=[f'EG-{i:06d}' for i in range(1,1002)]
        client=SalesforceCatalogClient(CONFIG)
        first=Mock(status_code=200);first.json.return_value={'records':[{'Id':'first','ProductCode':codes[0]}],'nextRecordsUrl':'/services/data/v65.0/query/next'}
        second=Mock(status_code=200);second.json.return_value={'records':[{'Id':'last','ProductCode':codes[-1]}],'done':True}
        with patch('app.lightning.requests.request',side_effect=[first,second]) as request:
            result=client.existing_codes(codes)
            self.assertEqual(result,{codes[0]:'first',codes[-1]:'last'})
            self.assertEqual(request.call_count,2)
            self.assertIn("LIKE 'EG-%'",request.call_args_list[0].kwargs['params']['q'])
        with patch.object(client,'query',return_value=iter([])) as query:
            client.imported_products(50000)
            self.assertTrue(query.call_args.args[0].endswith('LIMIT 50000'))
        with patch.object(client,'query',return_value=iter([{'total':50000}])):
            self.assertEqual(client.project_product_count(),50000)

    def test_unknown_limits_block_large_import_and_bad_batch_size_rejected(self):
        rows=[{'ProductCode':f'EG-{i:06d}'} for i in range(1,1002)]
        client=Mock();client.check_access.return_value={'product2_create':True,'product2_update':True}
        client.existing_codes.return_value={};client.limits.return_value={}
        with self.assertRaises(ConnectionFailure): import_product_records(client,rows)
        client.write_products.assert_not_called()
        with self.assertRaises(ConnectionFailure): plan_product_import(client,rows,batch_size=201)

if __name__=='__main__': unittest.main()
