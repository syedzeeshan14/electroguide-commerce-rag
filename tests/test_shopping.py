import unittest
from unittest.mock import patch, Mock
from app.shopping import constraints, subtotal
from app.integrations import ConnectionFailure, salesforce_search, grounded_answer

class ShoppingTests(unittest.TestCase):
    def test_budget_and_alias(self):
        self.assertEqual(constraints('Please find laptops under $1,200'),('laptop',1200.0))
        self.assertEqual(constraints('phone below 500'),('mobile',500.0))
        self.assertEqual(constraints('What is the return policy?'),(None,None))
        self.assertEqual(subtotal({'a':{'price':12.25,'quantity':2}}),24.5)

    def test_missing_credentials_do_not_call_network(self):
        with patch('app.integrations.requests.get') as get, patch('app.integrations.requests.post') as post:
            with self.assertRaises(ConnectionFailure): salesforce_search({})
            with self.assertRaises(ConnectionFailure): grounded_answer({},'hello',[],'')
            get.assert_not_called()
            post.assert_not_called()

    def test_salesforce_limits_destination_and_redacts_errors(self):
        settings={'SALESFORCE_SHORT_CODE':'demo','SALESFORCE_ORGANIZATION_ID':'f_ecom_demo','SALESFORCE_SITE_ID':'test','SALESFORCE_ACCESS_TOKEN':'test-not-a-real-token'}
        with patch('app.integrations.requests.get',return_value=Mock(status_code=401)) as get:
            with self.assertRaises(ConnectionFailure) as error:
                salesforce_search(settings)
            self.assertNotIn(settings['SALESFORCE_ACCESS_TOKEN'],str(error.exception))
            self.assertTrue(get.call_args.args[0].startswith('https://demo.api.commercecloud.salesforce.com/'))
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        settings['SALESFORCE_SHORT_CODE']='attacker.example/path'
        with self.assertRaises(ConnectionFailure): salesforce_search(settings)

    def test_openai_context_and_failure_redaction(self):
        settings={'OPENAI_API_KEY':'test-not-a-real-key','OPENAI_MODEL':'test-model'}
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':'Demo response'}}]}
        with patch('app.integrations.requests.post',return_value=response) as post:
            self.assertEqual(grounded_answer(settings,'laptop', [{'id':'EG-000001'}],'policy'),'Demo response')
            self.assertIn('EG-000001',post.call_args.kwargs['json']['messages'][0]['content'])
        with patch('app.integrations.requests.post',return_value=Mock(status_code=401)):
            with self.assertRaises(ConnectionFailure) as error: grounded_answer(settings,'hello',[],'')
            self.assertNotIn(settings['OPENAI_API_KEY'],str(error.exception))

if __name__=='__main__': unittest.main()
