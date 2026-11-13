"""Compare active local OAuth configuration with the app, without printing secrets."""
import argparse
import getpass
import hmac
import json
from pathlib import Path
import tomllib
from urllib.parse import urlparse
from app.runtime import ROOT,settings
from app.lightning import LightningClient
from app.integrations import ConnectionFailure


def compare_configuration(config,expected_key,expected_domain):
    actual_key=config.get('SALESFORCE_CLIENT_ID','').strip()
    def host(value):
        parsed=urlparse(value.strip())
        return parsed.hostname.lower() if parsed.scheme=='https' and parsed.hostname else None
    expected_host=host(expected_domain)
    actual_host=host(config.get('SALESFORCE_INSTANCE_URL',''))
    return {'consumer_key_matches_selected_app':bool(actual_key and expected_key.strip()) and hmac.compare_digest(actual_key.encode(),expected_key.strip().encode()),
            'my_domain_matches_selected_org':bool(actual_host and expected_host) and actual_host==expected_host,
            'entered_my_domain_valid':bool(expected_host and expected_host.endswith('.my.salesforce.com'))}


def local_report(config):
    candidates=[ROOT/'.streamlit/secrets.toml',Path.cwd()/'.streamlit/secrets.toml']
    paths=[]
    for path in dict.fromkeys(candidates):
        row={'path':str(path),'exists':path.is_file()}
        if path.is_file():
            try:
                stored=tomllib.loads(path.read_text(encoding='utf-8-sig'))
                row['client_id_matches_active_config']=stored.get('SALESFORCE_CLIENT_ID')==config.get('SALESFORCE_CLIENT_ID')
                row['domain_matches_active_config']=stored.get('SALESFORCE_INSTANCE_URL')==config.get('SALESFORCE_INSTANCE_URL')
            except (OSError,ValueError):
                row['readable_toml']=False
        paths.append(row)
    try:
        parsed=urlparse(config.get('SALESFORCE_INSTANCE_URL',''))
        safe_url='https://'+parsed.hostname if parsed.scheme=='https' and parsed.hostname else '<invalid HTTPS URL>'
    except ValueError:
        safe_url='<invalid HTTPS URL>'
    return {'project_folder':str(ROOT),'current_folder':str(Path.cwd()),
            'configured_instance_url':safe_url,
            'client_id_present':bool(config.get('SALESFORCE_CLIENT_ID','').strip()),
            'client_secret_present':bool(config.get('SALESFORCE_CLIENT_SECRET','').strip()),
            'access_token_override_present':bool(config.get('SALESFORCE_ACCESS_TOKEN','').strip()),
            'local_settings_files':paths}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-app',action='store_true',help='Compare the selected app Consumer Key privately and its My Domain')
    parser.add_argument('--test-login',action='store_true',help='Request an OAuth token; token is never printed or stored')
    args=parser.parse_args()
    try:
        config=settings()
        print(json.dumps(local_report(config),indent=2))
        if args.compare_app:
            expected_domain=input('Paste Current My Domain URL from the SAME org as the app: ')
            expected_key=getpass.getpass('Paste that app Consumer Key (hidden; press Enter): ')
            comparison=compare_configuration(config,expected_key,expected_domain)
            del expected_key
            print(json.dumps(comparison,indent=2))
            if not all(comparison.values()):
                parser.exit(1,'Configuration mismatch. Update the local secrets file using that same org/app, then rerun. No credentials were changed or stored.\n')
        if args.test_login:
            client=LightningClient(config)
            if client.token:
                parser.exit(1,'Clear the optional SALESFORCE_ACCESS_TOKEN locally to test the client-credentials flow itself.\n')
            client.authenticate()
            print('Client-credentials OAuth succeeded. Token not printed or stored.')
    except (ConnectionFailure,OSError,ValueError,EOFError) as error:
        parser.exit(1,str(error)+'\n')
