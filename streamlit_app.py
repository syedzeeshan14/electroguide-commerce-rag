from pathlib import Path
import json
from html import escape
import os
import sqlite3
import uuid
import zipfile
import streamlit as st
from app.catalog import Catalog
from app.design import CSS, illustration, LABELS
from scripts.generate_catalog import CATALOG_VERSION, BRANDS
from app.shopping import retrieve, subtotal
from app.integrations import ConnectionFailure, grounded_answer, salesforce_search
from scripts.generate_catalog import CATEGORIES

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='ElectroGuide | Thoughtful tech', page_icon='⚡',layout='wide')
st.markdown(CSS,unsafe_allow_html=True)

@st.cache_resource
def prepare_catalog():
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
    names=['OPENAI_API_KEY','OPENAI_MODEL','SALESFORCE_SHORT_CODE','SALESFORCE_ORGANIZATION_ID','SALESFORCE_SITE_ID','SALESFORCE_ACCESS_TOKEN']
    values={name:os.environ.get(name,'') for name in names}
    try:
        for name in names:
            if st.secrets.get(name):
                values[name]=str(st.secrets[name])
    except FileNotFoundError:
        pass
    return values

catalog=prepare_catalog()
config=settings()
for key,default in {'cart':{},'wishlist':{},'compare':{},'orders':[],'messages':[]}.items():
    if key not in st.session_state:
        st.session_state[key]=default

st.markdown('<div class="topline"><div class="brand">electro<span>guide.</span></div><div class="topnote">Thoughtful tech. A little more you. &nbsp; / &nbsp; US · USD</div></div>',unsafe_allow_html=True)
st.sidebar.markdown('<div class="brand">eg<span>.</span></div><div class="eyebrow">Your tech, discovered</div>',unsafe_allow_html=True)
page=st.sidebar.radio('Explore',['Shop','Shopping assistant','Compare','Wishlist','Cart & orders','Catalog dashboard','Connections'])
st.sidebar.divider()
st.sidebar.metric('Your bag',sum(p['quantity'] for p in st.session_state.cart.values()))
st.sidebar.caption(f"{len(st.session_state.wishlist)} saved · {len(st.session_state.compare)} to compare")
st.sidebar.caption('Academic demo · Fictional products · Simulated checkout')

def product_card(product, prefix):
    with st.container(border=True):
        st.markdown('<div class="product-art">'+illustration(product['category'])+'</div>',unsafe_allow_html=True)
        specs=product['specifications']
        highlights=[]
        for key,label in [('ram_gb','GB RAM'),('storage_gb','GB storage'),('screen_inches','″ display'),('resolution',''),('battery_hours','h battery'),('megapixels','MP'),('case_mm','mm'),('power_watts','W')]:
            if key in specs:
                highlights.append(f"{specs[key]}{label}")
        summary=' · '.join(highlights[:3]) or specs.get('form_factor',specs.get('color',''))
        st.markdown(f'<div class="category-label">{escape(LABELS[product["category"]])} / {escape(product["brand"])}</div><div class="product-name">{escape(product["name"])}</div><div class="spec-line">{escape(summary)}</div><div class="price-row"><span class="price">${product["price"]:,.2f}</span><span class="stock-pill">In stock · demo</span></div>',unsafe_allow_html=True)
        with st.expander('Explore details'):
            st.caption(f"{product['id']} · {product['sku']} · Synthetic product")
            for key,value in specs.items():
                st.write(f"**{key.replace('_',' ').title()}:** {value}")
            st.caption('Category illustration; not a photograph of this fictional model.')
        if st.button('Add to cart',width='stretch',type='primary',key=f"{prefix}-cart-{product['id']}",disabled=product['stock']<=0):
            existing=st.session_state.cart.get(product['id'])
            quantity=existing['quantity']+1 if existing else 1
            if quantity<=product['stock']:
                st.session_state.cart[product['id']]={**product,'quantity':quantity}
                st.rerun()
            else:
                st.warning('Demo stock limit reached.')
        b,c=st.columns(2)
        if b.button('Save',width='stretch',key=f"{prefix}-save-{product['id']}"):
            st.session_state.wishlist[product['id']]=product
            st.rerun()
        if c.button('Compare',width='stretch',key=f"{prefix}-compare-{product['id']}"):
            if len(st.session_state.compare)<4 or product['id'] in st.session_state.compare:
                st.session_state.compare[product['id']]=product
                st.rerun()
            else:
                st.warning('Compare up to four products. Clear the comparison to start again.')

if page=='Shop':
    st.markdown('<div class="hero"><div><div class="eyebrow">Good technology. Great possibilities.</div><h1>Find your next<br>everyday upgrade.</h1><p>From a better workday to a bigger movie night. Discover devices that fit your world, your needs, and your budget.</p><span class="hero-tag">Explore 10 categories &nbsp; ↗</span></div><div class="hero-art">'+illustration('laptop','#c4e8a5')+'</div></div>',unsafe_allow_html=True)
    category_columns=st.columns(5)
    for index,key in enumerate(['laptop','mobile','headphones','tv','smartwatch']):
        if category_columns[index].button(LABELS[key],key='category-'+key,width='stretch'):
            st.session_state['shop_category']=key
    st.markdown('<div class="section-heading"><div class="section-title">A good place to start</div><span>Find something that feels like you</span></div>',unsafe_allow_html=True)
    a,b,c,d=st.columns([2.3,1.2,1.1,1.2])
    query=a.text_input('Find a device',placeholder='Try laptops under $900, or 4K TV')
    category=b.selectbox('Category',['All',*CATEGORIES],format_func=lambda x: LABELS.get(x,x),key='shop_category')
    budget=c.number_input('Budget (USD)',min_value=0.0,value=3500.0,step=50.0)
    sort_label=d.selectbox('Sort by',['Featured','Price: low to high','Price: high to low'])
    from app.shopping import constraints
    parsed_category,parsed_budget=constraints(query)
    active_category=None if category=='All' else category
    if parsed_category and active_category is None:
        active_category=parsed_category
    active_budget=min(budget,parsed_budget) if parsed_budget is not None else budget
    # Natural-language category/budget queries use explicit filters; keyword queries use FTS.
    keywords='' if parsed_category and parsed_budget is not None else query
    if active_category and query.lower().strip() in (active_category,LABELS.get(active_category,'').lower()):
        keywords=''
    extra1,extra2=st.columns([1,3])
    brand=extra1.selectbox('Brand',['All brands',*BRANDS])
    page_number=extra2.number_input('Page',min_value=1,value=1,step=1)
    sort={'Featured':'featured','Price: low to high':'price_low','Price: high to low':'price_high'}[sort_label]
    products=catalog.search(query=keywords,category=active_category,max_price=active_budget,limit=12,sort=sort,offset=(page_number-1)*12,brand=None if brand=='All brands' else brand)
    st.caption(f"{len(products)} picks · Page {page_number} · Up to ${active_budget:,.0f}" + (' · '+LABELS[active_category] if active_category else ' · All categories'))
    if not products:
        st.markdown('<div class="empty"><h3>No matches this time.</h3><p>Try a broader search, a higher budget, or page 1.</p></div>',unsafe_allow_html=True)
    columns=st.columns(3)
    for index,product in enumerate(products):
        with columns[index%3]:
            product_card(product,'shop')

elif page=='Shopping assistant':
    st.markdown('<div class="assistant-banner"><div class="eyebrow">A little guidance goes a long way</div><h2>Let’s find your kind of tech.</h2><p>Tell us what you’re looking for and what you’d like to spend.</p></div>',unsafe_allow_html=True)
    st.caption('Try “Recommend a laptop under $900”. Category and budget filtering are supported; use-case ranking and vector search are future work.')
    for index,message in enumerate(st.session_state.messages):
        with st.chat_message(message['role']):
            st.write(message['content'])
            for product in message.get('products',[]):
                product_card(product,f'message-{index}')
    question=st.chat_input('What are you shopping for?')
    if question:
        st.session_state.messages.append({'role':'user','content':question})
        products=retrieve(catalog,question)
        policy=(ROOT/'knowledge/store-policies.md').read_text(encoding='utf-8')
        with st.chat_message('user'):
            st.write(question)
        with st.chat_message('assistant'):
            if config['OPENAI_API_KEY']:
                try:
                    with st.spinner('Reading matching products and demo policies…'):
                        answer=grounded_answer(config,question,products,policy)
                    st.caption('AI-generated explanation; verify details against the source cards below.')
                except ConnectionFailure as error:
                    st.warning(str(error))
                    answer='The AI service is unavailable. You can still review the local matching products below.'
            elif products:
                answer='Here are in-stock demo options matching the category and budget I could identify. Compare their listed specifications below. Enable OpenAI in Connections for a conversational explanation.'
            else:
                answer='Please name an electronics category and budget, such as “laptop under $900”. For store policies, see the demo policy document below.'
            st.write(answer)
            for product in products:
                product_card(product,f'message-{len(st.session_state.messages)}')
        st.session_state.messages.append({'role':'assistant','content':answer,'products':products})
    with st.expander('Source: demo store policies'):
        st.markdown((ROOT/'knowledge/store-policies.md').read_text(encoding='utf-8'))

elif page=='Compare':
    st.header('Compare devices')
    if st.session_state.compare:
        rows=[{'Product':p['name'],'ID':p['id'],'Price (USD)':p['price'],**p['specifications']} for p in st.session_state.compare.values()]
        st.dataframe(rows,width='stretch')
        if st.button('Clear comparison'):
            st.session_state.compare={}
            st.rerun()
    else:
        st.write('Choose Compare on up to four product cards.')

elif page=='Wishlist':
    st.header('Your saved devices')
    for product in list(st.session_state.wishlist.values()):
        product_card(product,'wishlist')
        if st.button('Remove saved item',key='remove-'+product['id']):
            del st.session_state.wishlist[product['id']]
            st.rerun()
    if not st.session_state.wishlist:
        st.write('Save products from the shop to see them here.')

elif page=='Cart & orders':
    st.header('Cart & demo orders')
    for key,product in list(st.session_state.cart.items()):
        a,b,c=st.columns([4,1,1])
        a.write(f"{product['name']} — ${product['price']:,.2f} each")
        quantity=b.number_input('Quantity',min_value=1,max_value=product['stock'],value=product['quantity'],key='qty-'+key)
        st.session_state.cart[key]['quantity']=quantity
        if c.button('Remove',key='cart-remove-'+key):
            del st.session_state.cart[key]
            st.rerun()
    total=subtotal(st.session_state.cart)
    st.metric('Subtotal',f'${total:,.2f}')
    st.caption('Tax and shipping are not calculated. No payment or Salesforce order will be created.')
    if st.button('Place simulated order',disabled=not st.session_state.cart):
        order={'id':'DEMO-'+uuid.uuid4().hex[:8].upper(),'status':'Simulated order placed','subtotal':total,'items':list(st.session_state.cart.values())}
        st.session_state.orders.append(order)
        st.session_state.cart={}
        st.rerun()
    for order in reversed(st.session_state.orders):
        with st.expander(f"{order['id']} · {order['status']} · ${order['subtotal']:,.2f}"):
            st.json(order)

elif page=='Catalog dashboard':
    st.header('Catalog overview')
    rows=catalog.connection.execute('SELECT category,COUNT(*) AS products,SUM(stock) AS units,ROUND(AVG(price),2) AS average_price FROM products GROUP BY category').fetchall()
    st.metric('Synthetic products',sum(row['products'] for row in rows))
    st.dataframe([dict(row) for row in rows],width='stretch')
    st.bar_chart({row['category']:row['products'] for row in rows})
    st.caption('Read-only local dashboard. Customer administration, real sales analytics, and Salesforce catalog writes are not connected.')

else:
    st.header('Local connections')
    st.write('Store your values in `.streamlit/secrets.toml` on your computer, then restart Streamlit. Values are never displayed here.')
    st.write('OpenAI key:', 'Configured locally' if config['OPENAI_API_KEY'] else 'Not configured')
    st.write('Salesforce identifiers and token:', 'Configured locally' if all(config[k] for k in ['SALESFORCE_SHORT_CODE','SALESFORCE_ORGANIZATION_ID','SALESFORCE_SITE_ID','SALESFORCE_ACCESS_TOKEN']) else 'Incomplete')
    st.caption('Configured does not mean verified. Test buttons make explicit external API requests. OpenAI requests incur provider charges.')
    if st.button('Test OpenAI connection'):
        try:
            with st.spinner('Testing OpenAI…'):
                grounded_answer(config,'Reply with a short greeting. Do not recommend products.',[], '')
            st.success('OpenAI responded successfully.')
        except ConnectionFailure as error:
            st.error(str(error))
    term=st.text_input('Salesforce test search',value='laptop')
    if st.button('Test Salesforce product search'):
        try:
            with st.spinner('Testing B2C Commerce SCAPI…'):
                result=salesforce_search(config,term)
            st.success('Salesforce product search responded successfully.')
            hits=result.get('hits',[])
            st.write([{'id':p.get('productId'),'name':p.get('productName'),'price':p.get('price')} for p in hits])
            st.caption('Read-only connection test. The storefront still uses the synthetic local catalog.')
        except ConnectionFailure as error:
            st.error(str(error))
    st.warning('A Lightning username/password is not a B2C SCAPI credential. Obtain the actual B2C identifiers and a SLAS shopper token; never enter your Salesforce password here.')

st.markdown('<div class="footer"><strong>electroguide.</strong> &nbsp; Thoughtful tech, made personal.<br>University research prototype · All brands, products, prices, and availability are synthetic. Original category illustrations are representative. No real payments. Session-only cart and orders.</div>',unsafe_allow_html=True)
