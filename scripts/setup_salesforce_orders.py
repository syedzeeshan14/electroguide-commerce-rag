"""Check draft-Order access; optionally prepare a dedicated academic demo account/book."""
import argparse
import json
from pathlib import Path
import re
import tomllib
from app.runtime import ROOT,settings
from app.salesforce_orders import SalesforceOrderClient,BOOK_NAME,BOOK_DESCRIPTION,ACCOUNT_NAME
from app.integrations import ConnectionFailure
from app.lightning import salesforce_id


def save_local_settings(path,updates):
    path=Path(path)
    text=path.read_text(encoding='utf-8-sig') if path.exists() else ''
    current=tomllib.loads(text)
    for key,value in updates.items():
        line=key+' = '+json.dumps(value)
        if key in current:
            text=re.sub(r'(?m)^[ \t]*'+key+r'[ \t]*=.*$',lambda match:line,text,count=1)
        else:
            text=line+'\n'+text
    parsed=tomllib.loads(text)
    if any(parsed.get(key)!=value for key,value in updates.items()):
        raise ConnectionFailure('Could not update the local TOML settings safely.')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')


def setup_demo(client,progress=None):
    def stage(message):
        if progress: progress(message)
    stage('Checking Order access and USD support…')
    client.require_usd()
    stage('Checking the active Standard Price Book…')
    standards=list(client.query('SELECT Id FROM Pricebook2 WHERE IsStandard=true AND IsActive=true LIMIT 1'))
    if not standards:
        raise ConnectionFailure('Activate the Standard Price Book in Salesforce first. No records were written.')
    stage('Looking up the academic demo account…')
    accounts=list(client.query("SELECT Id FROM Account WHERE Name='"+ACCOUNT_NAME+"' LIMIT 2"))
    stage('Looking up the academic demo price book…')
    books=list(client.query("SELECT Id,Description,IsActive FROM Pricebook2 WHERE Name='"+BOOK_NAME+"' LIMIT 2"))
    if len(accounts)>1 or len(books)>1:
        raise ConnectionFailure('Duplicate academic demo accounts or price books exist; resolve them before setup.')
    if books and (books[0].get('Description')!=BOOK_DESCRIPTION or not books[0].get('IsActive')):
        raise ConnectionFailure('The existing academic price book has a different purpose or is inactive; setup did not change it.')
    batch=[]
    if not accounts:
        batch.append({'method':'POST','url':client.api_root()+'/sobjects/Account','referenceId':'account',
                      'body':{'Name':ACCOUNT_NAME,'Description':'Shared fictional customer for the ElectroGuide academic demo.'}})
    if not books:
        batch.append({'method':'POST','url':client.api_root()+'/sobjects/Pricebook2','referenceId':'book',
                      'body':{'Name':BOOK_NAME,'Description':BOOK_DESCRIPTION,'IsActive':True}})
    stage('Creating missing demo records atomically…' if batch else 'Reusing the existing academic demo account and price book.')
    created=client.composite(batch) if batch else {}
    account=salesforce_id(accounts[0]['Id'] if accounts else created['account']['id'],'001')
    book=salesforce_id(books[0]['Id'] if books else created['book']['id'],'01s')
    return {'SALESFORCE_ORDER_ACCOUNT_ID':account,'SALESFORCE_ORDER_PRICEBOOK_ID':book,
            'SALESFORCE_ORDER_DEMO_PRICING':'true','SALESFORCE_ORDER_SYNC':'salesforce_draft',
            'CATALOG_SOURCE':'salesforce_catalog_snapshot'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Create the dedicated demo Account/price book and enable on-demand demo USD pricing')
    parser.add_argument('--configure-local',action='store_true',help='Save non-secret order settings in the existing local secrets.toml; requires --apply')
    parser.add_argument('--diagnose',action='store_true',help='Read-only object and field capability report; no setup writes')
    args=parser.parse_args()
    if args.diagnose and (args.apply or args.configure_local):
        parser.error('--diagnose cannot be combined with setup-write flags')
    if args.configure_local and not args.apply:
        parser.error('--configure-local requires --apply')
    try:
        client=SalesforceOrderClient(settings())
        if args.diagnose:
            print(json.dumps(client.access_diagnostic(),indent=2))
            parser.exit(0)
        access=client.order_access()
        print(json.dumps(access,indent=2))
        if args.apply:
            updates=setup_demo(client,progress=lambda message:print(message,flush=True))
            if args.configure_local:
                print('Saving local non-secret order settings…',flush=True)
                save_local_settings(ROOT/'.streamlit/secrets.toml',updates)
                print('Saved local draft-order settings. Restart Streamlit. No order was placed during setup.')
            else:
                print(json.dumps(updates,indent=2))
        else:
            print('Read-only check completed. No records or local settings were changed.')
    except (ConnectionFailure,OSError,ValueError) as error:
        parser.exit(1,str(error)+'\n')
