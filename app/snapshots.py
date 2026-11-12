"""Publish complete local snapshots without activating a partially written catalog."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from app.catalog import Catalog

SOURCES={'lightning_snapshot':('lightning_snapshots','lightning-current.json'),
         'salesforce_catalog_snapshot':('salesforce_catalog_snapshots','salesforce-catalog-current.json')}


def publish_snapshot(products,output,source,extra=None):
    directory,pointer=SOURCES[source]
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    snapshot_id=uuid.uuid4().hex
    snapshot=output/directory/snapshot_id
    snapshot.mkdir(parents=True)
    temp=output/f'{pointer}-{snapshot_id}.tmp'
    try:
        path=snapshot/'products.jsonl'
        with path.open('w',encoding='utf-8') as handle:
            for product in products:
                handle.write(json.dumps(product,sort_keys=True)+'\n')
        catalog=Catalog(str(snapshot/'catalog.sqlite'))
        try:
            catalog.build(path)
        finally:
            catalog.connection.close()
        manifest={**(extra or {}),'snapshot_id':snapshot_id,'count':len(products),
                  'synced_at':datetime.now(timezone.utc).isoformat(),'source':source}
        (snapshot/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        temp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        os.replace(temp,output/pointer)
        return manifest
    except Exception:
        shutil.rmtree(snapshot,ignore_errors=True)
        temp.unlink(missing_ok=True)
        raise
