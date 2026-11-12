"""Exercise user flows through Streamlit's application test runner, offline."""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class StreamlitTests(unittest.TestCase):
    def test_shop_cart_order_and_pages(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label=='Add to cart').click().run()
        self.assertTrue(app.session_state['cart'])
        app.sidebar.radio[0].set_value('Cart & orders').run()
        next(b for b in app.button if b.label=='Place simulated order').click().run()
        self.assertTrue(app.session_state['orders'])
        self.assertFalse(app.session_state['cart'])
        for page in ['Compare','Wishlist','Catalog dashboard','Connections','Shopping assistant']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception,page)
        with patch('app.integrations.requests.post',side_effect=AssertionError('Unexpected external request')):
            # No external provider calls are needed: use the offline branch.
            with patch.dict('os.environ',{'OPENAI_API_KEY':''}):
                app.chat_input[0].set_value('laptop under $900').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state['messages'][-1]['products'])
        self.assertTrue(all(p['price']<=900 for p in app.session_state['messages'][-1]['products']))
        next(b for b in app.button if b.label=='Add to cart').click().run()
        self.assertTrue(app.session_state['cart'])
        self.assertFalse(app.exception)

if __name__=='__main__': unittest.main()
