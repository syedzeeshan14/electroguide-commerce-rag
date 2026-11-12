import json
import tempfile
import unittest
from pathlib import Path
from scripts.generate_catalog import generate
from app.catalog import Catalog

class CatalogV2Tests(unittest.TestCase):
    def test_prices_follow_laptop_specification_tiers(self):
        products=[p for p in generate(1000) if p['category']=='laptop']
        tiers={ram:[p['price'] for p in products if p['specifications']['ram_gb']==ram] for ram in [8,16,32]}
        self.assertLess(max(tiers[8]),min(tiers[16]))
        self.assertLess(max(tiers[16]),min(tiers[32]))
        self.assertTrue(all(p['catalog_version']==2 for p in products))

    def test_pagination_sort_and_brand_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'products.jsonl'
            path.write_text(''.join(json.dumps(p)+'\n' for p in generate(1000)))
            catalog=Catalog(':memory:')
            catalog.build(path)
            first=catalog.search(sort='featured',limit=12)
            second=catalog.search(sort='featured',limit=12,offset=12)
            self.assertFalse({p['id'] for p in first}&{p['id'] for p in second})
            self.assertGreaterEqual(len({p['category'] for p in first}),5)
            products=catalog.search(category='laptop',sort='price_high',brand='Aster',limit=50)
            self.assertTrue(products)
            self.assertTrue(all(p['brand']=='Aster' for p in products))
            self.assertEqual([p['price'] for p in products],sorted([p['price'] for p in products],reverse=True))
            catalog.connection.close()
