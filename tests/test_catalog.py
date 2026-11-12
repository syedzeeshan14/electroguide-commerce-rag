import json
import tempfile
import unittest
from pathlib import Path
from app.catalog import Catalog
from scripts.generate_catalog import generate

class CatalogTests(unittest.TestCase):
    def test_reproducible_unique_balanced_catalog(self):
        items = list(generate(1000))
        self.assertEqual(items,list(generate(1000)))
        self.assertEqual(len({p['sku'] for p in items}),1000)
        self.assertEqual(len({p['id'] for p in items}),1000)
        self.assertEqual({sum(p['category']==c for p in items) for c in {p['category'] for p in items}},{100})
        self.assertTrue(all(p['synthetic'] and p['currency']=='USD' and p['price']>0 for p in items))
        self.assertTrue(all('storage_gb' in p['specifications'] for p in items if p['category']=='laptop'))

    def test_budget_stock_and_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'products.jsonl'
            items = list(generate(1000))
            source.write_text('\n'.join(json.dumps(p) for p in items))
            catalog = Catalog(':memory:')
            catalog.build(source)
            results = catalog.search('phones', max_price=700, limit=50)
            self.assertTrue(results)
            self.assertTrue(all(p['category']=='mobile' and p['price']<=700 and p['stock']>0 for p in results))
            self.assertEqual(catalog.search('laptop',max_price=1),[])
            self.assertEqual(catalog.search('" OR * --'),[])
            with self.assertRaises(ValueError):
                catalog.search(max_price=-10)
            catalog.connection.close()

if __name__ == '__main__':
    unittest.main()
