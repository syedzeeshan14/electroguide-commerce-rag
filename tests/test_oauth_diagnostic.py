import unittest
from scripts.check_salesforce_oauth import compare_configuration


class OAuthDiagnosticTests(unittest.TestCase):
    def test_compare_key_and_org_without_returning_credentials(self):
        config={'SALESFORCE_CLIENT_ID':'fake-key-value','SALESFORCE_INSTANCE_URL':'https://new.develop.my.salesforce.com'}
        result=compare_configuration(config,'fake-key-value','https://new.develop.my.salesforce.com/')
        self.assertTrue(all(result.values()))
        self.assertNotIn('fake-key-value',str(result))
        result=compare_configuration(config,'other-app-key','https://old.my.salesforce.com')
        self.assertFalse(result['consumer_key_matches_selected_app'])
        self.assertFalse(result['my_domain_matches_selected_org'])
        result=compare_configuration(config,'fake-key-value','https://new.lightning.force.com')
        self.assertFalse(result['entered_my_domain_valid'])
        self.assertFalse(compare_configuration({},'','')['consumer_key_matches_selected_app'])

if __name__=='__main__': unittest.main()
