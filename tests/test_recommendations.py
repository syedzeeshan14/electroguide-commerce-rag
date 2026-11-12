import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from app.catalog import Catalog
from app.shopping import recommend,merge_intent
from app.integrations import extract_preferences

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.catalog=Catalog(':memory:')
        products=[]
        for i,(ram,price,stock,storage) in enumerate([(8,350,10,256),(16,700,10,512),(16,750,10,1024),(32,850,10,1024),(32,650,0,1024),(32,1500,10,2048),(16,800,10,512)]):
            products.append({'id':f'EG-{i:06d}','sku':f'DEMO-{i}','name':f'Laptop {i}','description':'Synthetic laptop','category':'laptop','brand':'Aster','price':price,'stock':stock,'currency':'USD','specifications':{'ram_gb':ram,'storage_gb':storage,'color':'black','battery_hours':10}})
        source=Path(self.directory.name)/'products.jsonl'
        source.write_text(''.join(json.dumps(p)+'\n' for p in products))
        self.catalog.build(source)

    def tearDown(self):
        self.catalog.connection.close()
        self.directory.cleanup()

    def test_three_unique_matches_honor_hard_filters(self):
        result=recommend(self.catalog,'laptop for coding under $900 with 16GB RAM')
        products=result['products']
        self.assertEqual(len(products),3)
        self.assertTrue(all(p['price']<=900 and p['stock']>0 and p['specifications']['ram_gb']>=16 for p in products))
        self.assertEqual(products[0]['specifications']['ram_gb'],32)
        self.assertEqual(len({p['id'] for p in products}),3)
        self.assertNotIn('EG-000006',[p['id'] for p in products]) # duplicate spec/brand of a cheaper candidate

    def test_no_invented_matches_or_relaxed_constraints(self):
        self.assertEqual(recommend(self.catalog,'laptop under $100')['products'],[])
        self.assertEqual(recommend(self.catalog,'laptop under $900 with 64GB RAM')['products'],[])
        self.assertEqual(recommend(self.catalog,'Apple laptop under $900')['products'],[])
        self.assertIn('What kind',recommend(self.catalog,'help me choose')['message'])
        intent=merge_intent('laptop under $900 with 16GB RAM',{'category':'mobile','max_price':5000,'min_ram_gb':4})
        self.assertEqual((intent['category'],intent['max_price'],intent['min_ram_gb']),('laptop',900,16))

    def test_model_output_is_bounded_and_validated(self):
        intent=merge_intent('a device',{'category':'not-a-category','min_ram_gb':float('inf'),'screen_inches':-20})
        self.assertIsNone(intent['category'])
        self.assertIsNone(intent['min_ram_gb'])
        self.assertIsNone(intent['screen_inches'])
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':'{"category":"laptop","max_price":900}'}}]}
        with patch('app.integrations.requests.post',return_value=response) as post:
            result=extract_preferences({'OPENAI_API_KEY':'fake-unit-test-key'},'Need a laptop')
            self.assertEqual(result['category'],'laptop')
            self.assertEqual(post.call_args.kwargs['json']['response_format'],{'type':'json_object'})

if __name__=='__main__': unittest.main()
