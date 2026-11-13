"""Local-only image display diagnostic; does not call Salesforce or OpenAI."""
import argparse
import json
from app.runtime import ROOT,settings,prepare_catalog
from app.product_images import cached_image_path,cache_directory


def inspect_image(product_code):
    config=settings()
    catalog=prepare_catalog()
    row=catalog.connection.execute('SELECT payload FROM products WHERE id=?',(product_code.upper(),)).fetchone()
    product=json.loads(row['payload']) if row else None
    directory=cache_directory(ROOT,config.get('SALESFORCE_INSTANCE_URL',''))
    try:
        index=json.loads((directory/'index.json').read_text(encoding='utf-8')) if directory else {}
    except (OSError,ValueError):
        index={}
    path=cached_image_path(product,ROOT,config) if product else None
    renderer=(ROOT/'streamlit_app.py').read_text(encoding='utf-8')
    return {'project_folder':str(ROOT),'catalog_source':getattr(catalog,'source','demo'),
            'product_code':product_code.upper(),'product_found':bool(product),
            'product_name':product.get('name') if product else None,
            'product_source':product.get('source','demo') if product else None,
            'salesforce_id':product.get('salesforce_id') if product else None,
            'cached_image_for_this_product':bool(path),
            'cached_salesforce_ids':list(index)[:20],
            'storefront_supports_cached_images':'cached_image_path(product,ROOT,config)' in renderer and 'st.image(str(photo)' in renderer}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-code',default='EG-040683')
    args=parser.parse_args()
    try:
        print(json.dumps(inspect_image(args.product_code),indent=2))
    except (OSError,ValueError) as error:
        parser.exit(1,str(error)+'\n')
