"""Test the minimal customer journey offline using Streamlit's runner."""
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from streamlit.testing.v1 import AppTest

class StreamlitTests(unittest.TestCase):
    def test_minimal_navigation_finder_and_order(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.sidebar.radio)
        labels=[button.label for button in app.button]
        for removed in ['Compare','Wishlist','Connections','Catalog dashboard','Shopping assistant']:
            self.assertNotIn(removed,labels)
        next(b for b in app.button if b.label=='Add to bag' and not b.disabled).click().run()
        self.assertTrue(app.session_state['cart'])
        next(b for b in app.button if b.label.startswith('Bag (')).click().run()
        next(b for b in app.button if b.label=='Complete demo order').click().run()
        self.assertTrue(app.session_state['orders'])
        self.assertFalse(app.session_state['cart'])
        next(b for b in app.button if b.label=='Find my match').click().run()
        with patch('app.integrations.requests.post',side_effect=AssertionError('Unexpected external request')),patch.dict('os.environ',{'OPENAI_API_KEY':''}):
            app.text_input[0].set_value('laptop under $1500 with 16GB RAM')
            next(b for b in app.button if b.label=='Find my best match').click().run()
        self.assertFalse(app.exception)
        products=app.session_state['match']['products']
        self.assertEqual(len(products),3)
        self.assertTrue(all(p['price']<=1500 and p['specifications']['ram_gb']>=16 for p in products))
        next(b for b in app.button if b.label=='Add to bag' and not b.disabled).click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state['cart'])
        self.assertEqual(len(app.session_state['match']['products']),3)


    def test_configured_key_powers_request_interpretation_and_explanation(self):
        intent=Mock(status_code=200)
        intent.json.return_value={'choices':[{'message':{'content':'{"category":"mobile","max_price":5000,"min_ram_gb":4}'}}]}
        explanation=Mock(status_code=200)
        explanation.json.return_value={'choices':[{'message':{'content':'These options match the listed budget and RAM requirements.'}}]}
        with patch('app.runtime.settings',return_value={'OPENAI_API_KEY':'fake-unit-test-key','OPENAI_MODEL':'test-model'}),patch('app.integrations.requests.post',side_effect=[intent,explanation]) as post:
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
            app.text_input[0].set_value('laptop under $1500 with 16GB RAM')
            next(b for b in app.button if b.label=='Find my best match').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(post.call_count,2)
            result=app.session_state['match']
            self.assertTrue(result['ai'])
            self.assertTrue(result['explanation'])
            self.assertEqual(len(result['products']),3)
            self.assertTrue(all(p['category']=='laptop' and p['price']<=1500 and p['specifications']['ram_gb']>=16 for p in result['products']))


    def test_semantic_result_labels_and_comparison(self):
        intent=Mock(status_code=200)
        intent.json.return_value={'choices':[{'message':{'content':'{"category":"laptop","max_price":1500,"min_ram_gb":16}'}}]}
        explanation=Mock(status_code=200)
        explanation.json.return_value={'choices':[{'message':{'content':'Here are three catalog-grounded matches.'}}]}
        def similarities(index,products,question,settings):
            return {product['id']:0.5 for product in products}
        with patch('app.runtime.settings',return_value={'OPENAI_API_KEY':'fake-unit-test-key'}),patch('app.integrations.requests.post',side_effect=[intent,explanation]),patch('app.semantic.EmbeddingIndex.similarities',new=similarities):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
            app.text_input[0].set_value('laptop under $1500 with 16GB RAM')
            next(b for b in app.button if b.label=='Find my best match').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['match']['retrieval_mode'],'semantic')
            self.assertTrue(any('Semantic matches' in caption.value for caption in app.caption))
            self.assertEqual(len(app.dataframe),1)
            self.assertIn('Your request',app.dataframe[0].value.columns)

if __name__=='__main__': unittest.main()
