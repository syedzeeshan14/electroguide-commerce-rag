"""Download one product's Media-tab image; no product writes or OpenAI calls."""
import argparse
import json
from app.runtime import ROOT,settings
from app.product_images import ProductImageClient,sync_product_image
from app.integrations import ConnectionFailure
from app.lightning import salesforce_id

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-id',required=True)
    parser.add_argument('--diagnose',action='store_true',help='Print media IDs/group types only; do not download or print credentials/URLs')
    args=parser.parse_args()
    try:
        product_id=salesforce_id(args.product_id,'01t')
        client=ProductImageClient(settings())
        if args.diagnose:
            media=[];files=[];errors=[]
            for name,method in [('product_media',client.product_media),('files',client.file_media)]:
                try:
                    rows=method(product_id)
                    public=[{key:value for key,value in row.items() if not key.startswith('_')} for row in rows]
                    if name=='product_media': media=public
                    else: files=public
                except ConnectionFailure as error:
                    errors.append(str(error))
            print(json.dumps({'product_media':media,'files':files,'errors':errors},indent=2))
        else:
            print(json.dumps(sync_product_image(client,ROOT,product_id),indent=2))
            print('Image cached locally. Refresh Streamlit. No embedding rebuild is needed for an image-only change.')
    except (ConnectionFailure,OSError,ValueError) as error:
        parser.exit(1,str(error)+'\n')
