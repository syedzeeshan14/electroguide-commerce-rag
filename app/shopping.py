"""Catalog-grounded matching: hard filters first, transparent ranking second."""
import json
import math
import re
from app.catalog import ALIASES
from scripts.generate_catalog import CATEGORIES, BRANDS


def constraints(question):
    intent = parse_intent(question)
    return intent['category'], intent['max_price']


def parse_intent(question):
    text=question.lower().replace(',','')
    tokens=re.findall(r'[a-z0-9]+',text)
    normalized=[ALIASES.get(token,token) for token in tokens]
    category=next((token for token in normalized if token in CATEGORIES),None)
    if not category:
        for phrase,value in [('earbuds','headphones'),('noise cancelling','headphones'),('noise-cancelling','headphones'),('coding','laptop'),('programming','laptop'),('iphone','mobile'),('macbook','laptop')]:
            if phrase in text:
                category=value
                break
    match=re.search(r'(?:under|below|less than|up to|budget(?: of)?|maximum|max)\s*\$?\s*(\d+(?:\.\d{1,2})?)',text)
    if not match:
        match=re.search(r'\$\s*(\d+(?:\.\d{1,2})?)',text)
    intent={'category':category,'max_price':float(match.group(1)) if match else None,
            'min_ram_gb':None,'min_storage_gb':None,'min_battery_hours':None,
            'screen_inches':None,'resolution':None,'noise_cancelling':False,
            'brand':next((brand for brand in BRANDS if brand.lower() in tokens),None),
            'purpose':None,'unsupported':[]}
    for pattern,key in [(r'(\d+)\s*gb\s*(?:of\s+)?ram','min_ram_gb'),
                        (r'(\d+)\s*gb\s*(?:ssd|storage)','min_storage_gb'),
                        (r'(\d+)\s*(?:hours?|hrs?|h)\s*(?:of\s+)?battery','min_battery_hours'),
                        (r'(\d+(?:\.\d+)?)\s*(?:inch|inches|["″])','screen_inches')]:
        found=re.search(pattern,text)
        if found:
            intent[key]=float(found.group(1))
    found=re.search(r'(\d+)\s*tb\s*(?:ssd|storage)?',text)
    if found:
        intent['min_storage_gb']=float(found.group(1))*1024
    for resolution in ['8K','4K','1440p','1080p']:
        if resolution.lower() in tokens:
            intent['resolution']=resolution
            break
    if re.search(r'noise[ -]cancell?(?:ing|ation)|\banc\b',text):
        intent['noise_cancelling']=True
    for words,purpose in [(['coding','programming','work','study','student'],'productivity'),(['travel','portable','lightweight'],'portable'),(['creative','editing','design'],'creative')]:
        if any(word in tokens for word in words):
            intent['purpose']=purpose
            break
    if any(word in tokens for word in ['apple','iphone','macbook','samsung','sony','dell','lenovo','hp']):
        intent['unsupported'].append('The requested manufacturer is not in this fictional catalog.')
    for words,note in [(['gaming','gpu','rtx'],'Gaming performance and GPU specifications are not verified in this catalog.'),(['waterproof','ip68'],'Water resistance is not verified in this catalog.'),(['compatible','compatibility'],'Device compatibility is not verified in this catalog.')]:
        if any(word in tokens for word in words):
            intent['unsupported'].append(note)
    return intent


def merge_intent(question, extracted=None):
    """Explicit locally parsed constraints cannot be loosened by model output."""
    local=parse_intent(question)
    if not isinstance(extracted,dict):
        return local
    for key in ['category','purpose','resolution','brand']:
        allowed={'category':list(CATEGORIES),'purpose':['productivity','portable','creative'],
                 'resolution':['4K','8K','1440p','1080p'],'brand':BRANDS}[key]
        if local[key] is None and extracted.get(key) in allowed:
            local[key]=extracted[key]
    for key in ['max_price','min_ram_gb','min_storage_gb','min_battery_hours','screen_inches']:
        value=extracted.get(key)
        if local[key] is None and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1000000:
            local[key]=float(value)
    if extracted.get('noise_cancelling') is True:
        local['noise_cancelling']=True
    if isinstance(extracted.get('unsupported'),list):
        local['unsupported'].extend(str(x)[:180] for x in extracted['unsupported'][:3] if isinstance(x,str))
    local['unsupported']=list(dict.fromkeys(local['unsupported']))
    return local


def recommend(catalog, question, extracted=None):
    intent=merge_intent(question,extracted)
    result={'intent':intent,'products':[],'reasons':{},'notes':intent['unsupported'],'message':''}
    if not intent['category']:
        result['message']='What kind of device would you like? Try “a laptop for studying under $900”.'
        return result
    # Do not substitute an invented brand for an explicitly requested real manufacturer.
    if any('manufacturer' in note for note in intent['unsupported']):
        result['message']='That manufacturer is not available here. Try a device category without a manufacturer name to explore the catalog.'
        return result
    sql='SELECT payload FROM products WHERE category=? AND stock>0'
    params=[intent['category']]
    if intent['max_price'] is not None:
        sql+=' AND price<=?'
        params.append(intent['max_price'])
    if intent['brand']:
        sql+=" AND json_extract(payload,'$.brand')=?"
        params.append(intent['brand'])
    candidates=[]
    for row in catalog.connection.execute(sql,params):
        product=json.loads(row['payload']); specs=product['specifications']
        if any(intent[key] is not None and (specs.get(spec) is None or specs[spec]<intent[key]) for key,spec in [('min_ram_gb','ram_gb'),('min_storage_gb','storage_gb'),('min_battery_hours','battery_hours')]):
            continue
        if intent['screen_inches'] is not None and specs.get('screen_inches')!=intent['screen_inches']:
            continue
        if intent['resolution'] and specs.get('resolution')!=intent['resolution']:
            continue
        if intent['noise_cancelling'] and specs.get('noise_cancelling') is not True:
            continue
        candidates.append(product)
    if not candidates:
        result['message']='No in-stock products meet these requirements. Try increasing your budget or relaxing a specification.'
        return result
    def score(product):
        specs=product['specifications']
        # A fixed heuristic, not a learned quality/performance rating.
        capability=(min(specs.get('ram_gb',0)/32,1)*3 + min(specs.get('storage_gb',0)/1024,1)*2
                    + min(specs.get('battery_hours',0)/50,1) + min(specs.get('megapixels',0)/45,1)
                    + {'4K':1,'8K':1.2,'1440p':.6,'1080p':.3}.get(specs.get('resolution'),0))
        if intent['purpose']=='portable':
            capability+=min(specs.get('battery_hours',0)/12,1)*3
            if specs.get('screen_inches'):
                capability+=max(0,17-specs['screen_inches'])
        if intent['purpose'] in ('productivity','creative'):
            capability+=min(specs.get('ram_gb',0)/32,1)*3
        # Normalize price within eligible candidates, so value matters across categories.
        return capability-product['price']/price_scale
    price_scale=max(product['price'] for product in candidates) or 1
    ranked=sorted(candidates,key=lambda p:(-score(p),p['price'],p['id']))
    fingerprints=set()
    diverse=[]
    for product in ranked:
        spec_key=tuple(sorted((k,str(v)) for k,v in product['specifications'].items() if k!='color'))
        if spec_key not in fingerprints:
            diverse.append(product)
            fingerprints.add(spec_key)
    diverse_ids={p['id'] for p in diverse}
    diverse.extend(p for p in ranked if p['id'] not in diverse_ids)
    fingerprints=set()
    for product in diverse:
        specs=product['specifications']
        fingerprint=(product['brand'],tuple(sorted((k,str(v)) for k,v in specs.items() if k!='color')))
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        result['products'].append(product)
        facts=[f"${product['price']:,.2f}" + (f" within your ${intent['max_price']:,.0f} budget" if intent['max_price'] is not None else '')]
        for key,label in [('ram_gb','GB RAM'),('storage_gb','GB storage'),('battery_hours','h listed battery'),('screen_inches','″ display'),('resolution',''),('megapixels','MP')]:
            if key in specs:
                facts.append(f'{specs[key]}{label}')
        if specs.get('noise_cancelling'):
            facts.append('Noise cancellation listed')
        result['reasons'][product['id']]=' · '.join(facts[:4])
        if len(result['products'])==3:
            break
    if result['products']:
        best=result['products'][0]
        for product in result['products'][1:]:
            differences=[]
            if product['price']<best['price']:
                differences.append(f"Saves ${best['price']-product['price']:,.2f} against your best match")
            elif product['price']>best['price']:
                differences.append(f"${product['price']-best['price']:,.2f} more than your best match")
            for key,label in [('storage_gb','GB storage'),('ram_gb','GB RAM'),('battery_hours','h listed battery'),('screen_inches','″ display')]:
                value=product['specifications'].get(key)
                top=best['specifications'].get(key)
                if value is not None and top is not None and value!=top:
                    differences.append(f'{value}{label}, compared with {top} in your best match')
            result['reasons'][product['id']]='. '.join(differences[:2]) or f"An alternative from {product['brand']} with equivalent listed key specifications."
    return result


def retrieve(catalog, question):
    return recommend(catalog,question)['products']


def subtotal(cart):
    return round(sum(item['price']*item['quantity'] for item in cart.values()),2)
