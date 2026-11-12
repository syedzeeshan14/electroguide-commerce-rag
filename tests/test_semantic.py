import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np
from app.catalog import Catalog
from app.semantic import EmbeddingIndex, SemanticUnavailable, product_document, embed_texts, document_key
from app.shopping import recommend,comparison_rows

CONFIG={'OPENAI_API_KEY':'fake-unit-test-key','OPENAI_EMBEDDING_DIMENSIONS':'16'}


def vector(axis):
    result=np.zeros(16,dtype=np.float32)
    result[axis]=1
    return result


def products():
    return [
        {'id':'A','sku':'A','name':'Desk laptop','brand':'Aster','category':'laptop','description':'Synthetic laptop','use_case':'office work', 'price':700,'stock':5,'specifications':{'ram_gb':16,'storage_gb':512,'battery_hours':5}},
        {'id':'B','sku':'B','name':'Travel laptop','brand':'Aster','category':'laptop','description':'Synthetic laptop','use_case':'portable study', 'price':750,'stock':5,'specifications':{'ram_gb':16,'storage_gb':512,'battery_hours':15}},
        {'id':'C','sku':'C','name':'Creative laptop','brand':'Aster','category':'laptop','description':'Synthetic laptop','use_case':'creative', 'price':780,'stock':5,'specifications':{'ram_gb':32,'storage_gb':1024,'battery_hours':5}},
        {'id':'D','sku':'D','name':'Unavailable','brand':'Aster','category':'laptop','description':'Synthetic laptop','use_case':'portable study', 'price':600,'stock':0,'specifications':{'ram_gb':16,'storage_gb':512,'battery_hours':20}},
        {'id':'E','sku':'E','name':'Over budget','brand':'Aster','category':'laptop','description':'Synthetic laptop','use_case':'portable study', 'price':1500,'stock':5,'specifications':{'ram_gb':16,'storage_gb':512,'battery_hours':20}},
    ]


def fake_embeddings(settings,texts):
    vectors=[]
    for text in texts:
        if text.startswith('Electronics product.'):
            vectors.append(vector(0 if 'portable study' in text else 1))
        else:
            vectors.append(vector(0))
    return vectors,len(texts)*20


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.index=EmbeddingIndex(Path(self.directory.name)/'semantic.sqlite')

    def tearDown(self):
        self.directory.cleanup()

    def test_embedding_api_order_dimensions_and_redaction(self):
        response=Mock(status_code=200)
        response.json.return_value={'data':[{'index':1,'embedding':vector(1).tolist()},{'index':0,'embedding':vector(0).tolist()}],'usage':{'total_tokens':10}}
        with patch('app.semantic.requests.post',return_value=response) as post:
            vectors,tokens=embed_texts(CONFIG,['a','b'])
            self.assertEqual(tokens,10)
            self.assertTrue(np.array_equal(vectors[0],vector(0)))
            self.assertTrue(np.array_equal(vectors[1],vector(1)))
            self.assertEqual(post.call_args.kwargs['json']['dimensions'],16)
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
        response.status_code=401
        with patch('app.semantic.requests.post',return_value=response):
            with self.assertRaises(SemanticUnavailable) as error:
                embed_texts(CONFIG,['a'])
            self.assertNotIn(CONFIG['OPENAI_API_KEY'],str(error.exception))
        response.status_code=200
        response.json.return_value={'data':[{'index':0,'embedding':[0]*16}]}
        with patch('app.semantic.requests.post',return_value=response):
            with self.assertRaises(SemanticUnavailable): embed_texts(CONFIG,['a'])

    def test_cache_deduplication_and_query_similarity(self):
        items=products()[:2]
        duplicate={**items[0],'id':'clone','price':999,'stock':0}
        self.assertEqual(product_document(items[0]),product_document(duplicate))
        with patch('app.semantic.embed_texts',side_effect=fake_embeddings) as embed:
            report=self.index.build([*items,duplicate],CONFIG,batch_size=1)
            self.assertEqual(report['products'],3)
            self.assertEqual(report['embedded'],2)
            self.assertEqual(embed.call_count,2)
            self.index.build(items,CONFIG)
            self.assertEqual(embed.call_count,2) # no repeat embedding requests
            scores=self.index.similarities(items,'A portable laptop',CONFIG)
            self.assertGreater(scores['B'],scores['A'])
        self.assertTrue(self.index.status(CONFIG)['ready'])
        self.assertFalse(self.index.status({**CONFIG,'OPENAI_EMBEDDING_DIMENSIONS':'32'})['ready'])

    def test_interrupted_build_resumes_without_repaying_completed_batch(self):
        items=products()[:2]
        with patch('app.semantic.embed_texts',side_effect=[([vector(0)],10),SemanticUnavailable('temporary failure')]):
            with self.assertRaises(SemanticUnavailable): self.index.build(items,CONFIG,batch_size=1)
        self.assertFalse(self.index.status(CONFIG)['ready'])
        with patch('app.semantic.embed_texts',side_effect=fake_embeddings) as embed:
            report=self.index.build(items,CONFIG,batch_size=1)
            self.assertEqual(report['cached'],1)
            self.assertEqual(report['embedded'],1)
            self.assertEqual(embed.call_count,1)

    def test_semantic_ranking_preserves_constraints_and_comparison_facts(self):
        items=products()
        source=Path(self.directory.name)/'products.jsonl'
        source.write_text(''.join(json.dumps(p)+'\n' for p in items))
        catalog=Catalog(':memory:')
        catalog.build(source)
        with patch('app.semantic.embed_texts',side_effect=fake_embeddings):
            self.index.build(items,CONFIG)
            result=recommend(catalog,'A laptop under $800 with 16GB RAM',semantic_index=self.index,settings=CONFIG)
        self.assertEqual(result['retrieval_mode'],'semantic')
        self.assertEqual(result['products'][0]['id'],'B')
        self.assertTrue(all(p['price']<=800 and p['stock']>0 for p in result['products']))
        self.assertEqual(len(result['products']),3)
        rows=comparison_rows(result)
        price_row=next(row for row in rows if row['Feature']=='Price')
        self.assertEqual(price_row['Best match'],'$750.00')
        self.assertEqual(price_row['Your request'],'Up to $800.00')
        with patch('app.semantic.embed_texts',side_effect=AssertionError('Must filter first')):
            empty=recommend(catalog,'laptop under $1',semantic_index=self.index,settings=CONFIG)
        self.assertFalse(empty['products'])
        catalog.connection.close()

    def test_changed_descriptions_and_missing_index_fall_back_honestly(self):
        items=products()[:2]
        with patch('app.semantic.embed_texts',side_effect=fake_embeddings): self.index.build(items,CONFIG)
        items[0]['specifications']={**items[0]['specifications'],'ram_gb':64}
        with patch('app.semantic.embed_texts',side_effect=AssertionError('Do not pay for a query against stale catalog')):
            with self.assertRaises(SemanticUnavailable): self.index.similarities(items,'laptop',CONFIG)
        source=Path(self.directory.name)/'products.jsonl'
        source.write_text(''.join(json.dumps(p)+'\n' for p in items))
        catalog=Catalog(':memory:'); catalog.build(source)
        result=recommend(catalog,'laptop under $900',semantic_index=EmbeddingIndex(Path(self.directory.name)/'missing.sqlite'),settings=CONFIG)
        self.assertEqual(result['retrieval_mode'],'specification')
        self.assertEqual(result['semantic_status'],'unavailable')
        self.assertTrue(result['products'])
        catalog.connection.close()

if __name__=='__main__': unittest.main()
