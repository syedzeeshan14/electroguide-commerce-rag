from pathlib import Path
import os
import json
import sqlite3
import zipfile
import streamlit as st
from app.catalog import Catalog
from scripts.generate_catalog import CATALOG_VERSION
ROOT=Path(__file__).resolve().parents[1]

@st.cache_resource
def _prepare_demo_catalog():
    data=ROOT/'data'
    source=data/'products.jsonl'
    database=data/f'catalog-v{CATALOG_VERSION}.sqlite'
    manifest_path=data/'manifest.json'
    try:
        local_version=json.loads(manifest_path.read_text()).get('catalog_version',1)
    except (FileNotFoundError,ValueError):
        local_version=0
    if not source.exists() or local_version<CATALOG_VERSION:
        with zipfile.ZipFile(data/'electroguide-catalog-50000.zip') as archive:
            # Extract only the known data members, never arbitrary paths.
            for name in ('products.jsonl','products.csv','manifest.json'):
                (data/name).write_bytes(archive.read(name))
    catalog=Catalog(str(database))
    try:
        count=catalog.connection.execute('SELECT count(*) FROM products').fetchone()[0]
        if count == 0:
            catalog.build(source)
    except sqlite3.OperationalError:
        catalog.build(source)
    return catalog

def settings():
    names=['OPENAI_API_KEY','OPENAI_MODEL','OPENAI_EMBEDDING_MODEL','OPENAI_EMBEDDING_DIMENSIONS','SALESFORCE_SHORT_CODE','SALESFORCE_ORGANIZATION_ID','SALESFORCE_SITE_ID','SALESFORCE_ACCESS_TOKEN','CATALOG_SOURCE','SALESFORCE_INSTANCE_URL','SALESFORCE_API_VERSION','SALESFORCE_CLIENT_ID','SALESFORCE_CLIENT_SECRET','SALESFORCE_WEBSTORE_ID','SALESFORCE_PRICEBOOK_ID','SALESFORCE_EFFECTIVE_ACCOUNT_ID','SALESFORCE_MULTI_CURRENCY']
    values={name:os.environ.get(name,'') for name in names}
    try:
        if not values['OPENAI_API_KEY'] and st.secrets.get('api_key'):
            values['OPENAI_API_KEY']=str(st.secrets['api_key'])
        for name in names:
            if st.secrets.get(name):
                values[name]=str(st.secrets[name])
    except FileNotFoundError:
        pass
    return values



@st.cache_resource
def _prepare_lightning_snapshot(snapshot_id):
    import re
    if not re.fullmatch(r'[a-f0-9]{32}',snapshot_id):
        raise ValueError('Invalid Lightning snapshot ID. Rerun the owner sync command.')
    database=ROOT/'data/lightning_snapshots'/snapshot_id/'catalog.sqlite'
    if not database.is_file():
        raise ValueError('The selected Lightning snapshot is missing. Rerun the owner sync command.')
    catalog=Catalog(str(database))
    catalog.source='lightning_snapshot'
    return catalog


def prepare_catalog():
    config=settings()
    source=config.get('CATALOG_SOURCE') or 'demo'
    if source=='demo':
        return _prepare_demo_catalog()
    if source!='lightning_snapshot':
        raise ValueError('CATALOG_SOURCE must be demo or lightning_snapshot.')
    manifest_path=ROOT/'data/lightning-current.json'
    if not manifest_path.is_file():
        raise ValueError('No Salesforce-linked snapshot is ready. Run python -m scripts.sync_lightning_catalog first, or set CATALOG_SOURCE="demo".')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    return _prepare_lightning_snapshot(manifest['snapshot_id'])
