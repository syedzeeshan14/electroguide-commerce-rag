from pathlib import Path
import json
import os
import sqlite3
import uuid
import zipfile
import streamlit as st
from app.catalog import Catalog
from app.shopping import retrieve, subtotal
from app.integrations import ConnectionFailure, grounded_answer, salesforce_search
from scripts.generate_catalog import CATEGORIES

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='ElectroGuide | Electronics', page_icon='⚡',layout='wide')

@st.cache_resource
def prepare_catalog():
    data=ROOT/'data'
    source=data/'products.jsonl'
    database=data/'catalog.sqlite'
    if not source.exists():
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

st.title('⚡ ElectroGuide')
st.caption('Your electronics discovery desk • United States • USD')
st.info('Academic demo: fictional products and stock. Checkout is simulated. Cart, wishlist, and orders last only for this browser session.')
page=st.sidebar.radio('Explore',['Shop','Shopping assistant','Compare','Wishlist','Cart & orders','Catalog dashboard','Connections'])
st.sidebar.caption('Local catalog • 50,000 synthetic products')

def product_card(product, prefix):
    with st.container(border=True):
        st.subheader(product['name'])
        st.caption(f"{product['category'].title()} · {product['id']}")
        st.markdown(f"**${product['price']:,.2f}** · {product['stock']} available (demo)")
        with st.expander('Specifications'):
            st.json(product['specifications'])
        a,b,c=st.columns(3)
        if a.button('Add to cart',key=f"{prefix}-cart-{product['id']}",disabled=product['stock']<=0):
            existing=st.session_state.cart.get(product['id'])
            quantity=existing['quantity']+1 if existing else 1
            if quantity<=product['stock']:
                st.session_state.cart[product['id']]={**product,'quantity':quantity}
                st.toast('Added to cart')
            else:
                st.warning('Demo stock limit reached.')
        if b.button('Save',key=f"{prefix}-save-{product['id']}"):
            st.session_state.wishlist[product['id']]=product
            st.toast('Saved to wishlist')
        if c.button('Compare',key=f"{prefix}-compare-{product['id']}"):
            if len(st.session_state.compare)<4 or product['id'] in st.session_state.compare:
                st.session_state.compare[product['id']]=product
                st.toast('Added to comparison')
            else:
                st.warning('Compare up to four products. Clear the comparison to start again.')

if page=='Shop':
    st.header('Find your next device')
    a,b,c=st.columns([2,1,1])
    query=a.text_input('Search keywords',placeholder='e.g. laptop, 4K, black')
    category=b.selectbox('Category',['All',*CATEGORIES])
    budget=c.number_input('Maximum price (USD)',min_value=0.0,value=3500.0,step=50.0)
    products=catalog.search(query=query,category=None if category=='All' else category,max_price=budget,limit=12)
    st.caption('Showing up to 12 in-stock matches. Use filters to narrow results.')
    if not products:
        st.warning('No products match. Try fewer keywords or increase your budget.')
    columns=st.columns(3)
    for index,product in enumerate(products):
        with columns[index%3]:
            product_card(product,'shop')

elif page=='Shopping assistant':
    st.header('Let’s find a good fit')
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
