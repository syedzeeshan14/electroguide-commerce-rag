import unittest
import tempfile
from pathlib import Path
import tomllib
from unittest.mock import Mock,patch
from app.integrations import ConnectionFailure
from scripts.check_salesforce_oauth import compare_configuration,configure_local_credentials


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

    def test_verified_credentials_saved_privately_and_old_org_settings_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'.streamlit/secrets.toml';path.parent.mkdir()
            path.write_text('OPENAI_API_KEY="unrelated-fake-key"\nSALESFORCE_INSTANCE_URL="https://old.my.salesforce.com"\n')
            config={'SALESFORCE_INSTANCE_URL':'https://old.my.salesforce.com','SALESFORCE_ORDER_SYNC':'salesforce_draft'}
            with patch('scripts.check_salesforce_oauth.LightningClient') as client:
                updated=configure_local_credentials(root,config,'https://new.develop.my.salesforce.com','fake-consumer-key','fake-consumer-secret')
                client.return_value.authenticate.assert_called_once()
            saved=tomllib.loads(path.read_text())
            self.assertEqual(saved['OPENAI_API_KEY'],'unrelated-fake-key')
            self.assertEqual(saved['SALESFORCE_CLIENT_ID'],'fake-consumer-key')
            self.assertEqual(saved['SALESFORCE_ACCESS_TOKEN'],'')
            self.assertEqual(saved['SALESFORCE_ORDER_SYNC'],'off')
            self.assertEqual(saved['CATALOG_SOURCE'],'demo')

    def test_failed_login_never_overwrites_existing_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'.streamlit/secrets.toml';path.parent.mkdir()
            original='OPENAI_API_KEY="unchanged-fake-key"\n';path.write_text(original)
            with patch('scripts.check_salesforce_oauth.LightningClient') as client:
                client.return_value.authenticate.side_effect=ConnectionFailure('OAuth rejected')
                with self.assertRaises(ConnectionFailure):
                    configure_local_credentials(root,{},'https://new.my.salesforce.com','fake-key','fake-secret')
            self.assertEqual(path.read_text(),original)

if __name__=='__main__': unittest.main()
