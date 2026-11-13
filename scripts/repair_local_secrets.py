"""Recover valid flat project settings from malformed local TOML; never print values."""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import tomllib
import uuid

ROOT=Path(__file__).resolve().parents[1]
SETTING=re.compile(r'^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=')


def repair(root):
    root=Path(root);path=root/'.streamlit/secrets.toml'
    raw=path.read_bytes()
    text=raw.decode('utf-8-sig')
    try:
        tomllib.loads(text)
        return {'status':'TOML is already valid; no changes made.'}
    except tomllib.TOMLDecodeError:
        pass
    recovered={}
    for line in text.splitlines():
        match=SETTING.match(line)
        if not match:
            continue
        key=match.group(1)
        if not (key.startswith(('OPENAI_','SALESFORCE_')) or key in ('CATALOG_SOURCE','api_key')):
            continue
        try:
            parsed=tomllib.loads(line)
            value=parsed.get(key)
            if isinstance(value,(str,int,float,bool)):
                json.dumps(value,allow_nan=False)
                recovered[key]=value
        except (ValueError,TypeError):
            continue
    # New-org migration must not place orders or use old snapshots until verified.
    recovered['SALESFORCE_ACCESS_TOKEN']=''
    recovered['SALESFORCE_ORDER_SYNC']='off'
    recovered['SALESFORCE_ORDER_ACCOUNT_ID']=''
    recovered['SALESFORCE_ORDER_PRICEBOOK_ID']=''
    recovered['SALESFORCE_ORDER_DEMO_PRICING']='false'
    recovered['CATALOG_SOURCE']='demo'
    cleaned='# Recovered local settings. Keep this file private.\n'+''.join(key+' = '+json.dumps(value,allow_nan=False)+'\n' for key,value in recovered.items())
    tomllib.loads(cleaned)
    directory=root/'data/private_config_backups';directory.mkdir(parents=True,exist_ok=True)
    backup=directory/('secrets-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.toml')
    backup.write_bytes(raw)
    path.write_text(cleaned,encoding='utf-8')
    return {'status':'Repaired local TOML. Re-enter Salesforce credentials through --configure-local.',
            'backup_file':str(backup),'recovered_setting_count':len(recovered),
            'note':'Only valid single-line project settings were recovered. Unrecoverable or custom/nested settings remain in the private backup. No values were printed.'}


if __name__=='__main__':
    try:
        print(json.dumps(repair(ROOT),indent=2))
    except (OSError,ValueError):
        raise SystemExit('Could not repair the local file. Confirm .streamlit/secrets.toml exists and is UTF-8. No contents were printed.') from None
