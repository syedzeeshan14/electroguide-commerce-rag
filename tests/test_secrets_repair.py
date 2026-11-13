from pathlib import Path
import tempfile
import tomllib
import unittest
from scripts.repair_local_secrets import repair


class SecretsRepairTests(unittest.TestCase):
    def test_repairs_invalid_line_preserves_valid_keys_and_private_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'.streamlit/secrets.toml';path.parent.mkdir()
            text='OPENAI_API_KEY="fake-private-key"\nSALESFORCE_CLIENT_SECRET="fake-private-secret"\nhttps://new.my.salesforce.com\nSALESFORCE_ORDER_SYNC="salesforce_draft"\n'
            path.write_text(text)
            result=repair(root)
            recovered=tomllib.loads(path.read_text())
            self.assertEqual(recovered['OPENAI_API_KEY'],'fake-private-key')
            self.assertEqual(recovered['SALESFORCE_CLIENT_SECRET'],'fake-private-secret')
            self.assertEqual(recovered['SALESFORCE_ORDER_SYNC'],'off')
            self.assertEqual(recovered['CATALOG_SOURCE'],'demo')
            self.assertEqual(Path(result['backup_file']).read_text(),text)
            self.assertNotIn('fake-private',str(result))

    def test_valid_file_is_not_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'.streamlit/secrets.toml';path.parent.mkdir()
            text='OPENAI_API_KEY="fake-private-key"\n';path.write_text(text)
            result=repair(root)
            self.assertEqual(path.read_text(),text)
            self.assertNotIn('backup_file',result)

if __name__=='__main__': unittest.main()
