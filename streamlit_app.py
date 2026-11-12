"""Minimal customer storefront. Owner diagnostics live in scripts/check_connections.py."""
from html import escape
import uuid
import streamlit as st
from app.design import CSS, illustration, LABELS
from app.runtime import ROOT, prepare_catalog, settings
from app.semantic import EmbeddingIndex
from app.shopping import recommend, constraints, subtotal, comparison_rows
from app.integrations import ConnectionFailure, grounded_answer, extract_preferences
from scripts.generate_catalog import CATEGORIES

st.set_page_config(page_title='ElectroGuide | Find your fit',page_icon='⚡',layout='wide',initial_sidebar_state='collapsed')
st.markdown(CSS,unsafe_allow_html=True)
st.markdown('''<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none}
[data-testid="stToolbar"]{visibility:hidden}
.block-container{max-width:1260px}
.nav-logo{padding:3px 0 22px}.match-label{font-size:11px;letter-spacing:1.5px;font-weight:800;text-transform:uppercase;color:#55735c;margin-bottom:12px}.best-label{background:#1b503d;color:#fff;padding:9px 14px;border-radius:9px;display:inline-block}.match-reason{font-size:13px;line-height:1.7;color:#45644e;margin:0 0 15px}.finder-intro{font-size:15px;color:#5c7161;line-height:1.7;max-width:720px}.match-question{padding:12px 18px;border-left:3px solid #6a8f68;background:#eef3e8;border-radius:0 10px 10px 0;font-size:14px;margin:15px 0}.hero{min-height:280px}.hero h1{font-size:48px}.product-name{min-height:54px}.footer{margin-top:30px}.stForm{border-radius:18px}
@media(max-width:760px){.hero h1{font-size:34px}.nav-logo{padding-bottom:0}.hero{min-height:240px}}
</style>''',unsafe_allow_html=True)
catalog=prepare_catalog()
config=settings()
for key,default in {'page':'Shop','cart':{},'orders':[],'match':None,'shop_page':0}.items():
    if key not in st.session_state:
        st.session_state[key]=default

def navigate(page):
    st.session_state.page=page

logo,shop,match,bag=st.columns([3,1,1.4,1.2],vertical_alignment='center')
logo.markdown('<div class="brand nav-logo">electro<span>guide.</span></div>',unsafe_allow_html=True)
shop.button('Shop',width='stretch',on_click=navigate,args=('Shop',))
match.button('Find my match',width='stretch',on_click=navigate,args=('Match',))
count=sum(p['quantity'] for p in st.session_state.cart.values())
bag.button(f'Bag ({count})',width='stretch',on_click=navigate,args=('Bag',))
st.divider()
if getattr(catalog,'source','demo')=='lightning_snapshot':
    st.caption('Catalog synced from Salesforce · Availability and checkout are simulated')
elif getattr(catalog,'source','demo')=='salesforce_catalog_snapshot':
    st.caption('Salesforce product catalog · USD demo prices, availability and checkout are simulated' if catalog.price_source=='synthetic_usd_metadata' else 'Salesforce product catalog · Selected USD price-book snapshot · Availability and checkout are simulated')

def product_card(product,prefix,reason=None):
    with st.container(border=True):
        st.markdown('<div class="product-art">'+illustration(product['category'])+'</div>',unsafe_allow_html=True)
        specs=product['specifications']
        highlights=[]
        for key,label in [('ram_gb','GB RAM'),('storage_gb','GB storage'),('screen_inches','″ display'),('resolution',''),('battery_hours','h battery'),('megapixels','MP'),('case_mm','mm'),('power_watts','W')]:
            if key in specs:
                highlights.append(f'{specs[key]}{label}')
        summary=' · '.join(highlights[:3]) or specs.get('form_factor',specs.get('color',''))
        st.markdown(f'<div class="category-label">{escape(LABELS[product["category"]])}</div><div class="product-name">{escape(product["name"])}</div><div class="spec-line">{escape(summary)}</div><div class="price-row"><span class="price">${product["price"]:,.2f}</span><span class="stock-pill">Available</span></div>',unsafe_allow_html=True)
        if reason:
            st.markdown(f'<div class="match-reason">{escape(reason)}</div>',unsafe_allow_html=True)
        with st.expander('Product details'):
            for key,value in specs.items():
                st.write(f"**{key.replace('_',' ').title()}:** {value}")
            st.caption(f"{product['id']} · Representative illustration")
        if st.button('Add to bag',type='primary',width='stretch',key=f"{prefix}-{product['id']}"):
            existing=st.session_state.cart.get(product['id'])
            quantity=existing['quantity']+1 if existing else 1
            if quantity<=product['stock']:
                st.session_state.cart[product['id']]={**product,'quantity':quantity}
                st.rerun()
            else:
                st.warning('Available quantity reached.')

def finder():
    with st.form('product-finder'):
        st.markdown('**What would make a good fit for you?**')
        request=st.text_input('What are you looking for?',placeholder='A laptop for studying under $1500, with at least 16GB RAM',label_visibility='collapsed',max_chars=2000)
        submitted=st.form_submit_button('Find my best match',type='primary')
    if submitted:
        if not request.strip():
            st.warning('Tell us what kind of device you need and your budget.')
            return
        preferences=None
        ai_available=False
        answer=''
        with st.spinner('Finding your fit…'):
            if config['OPENAI_API_KEY']:
                try:
                    preferences=extract_preferences(config,request)
                    ai_available=True
                except ConnectionFailure:
                    pass
            result=recommend(catalog,request,preferences,semantic_index=EmbeddingIndex(ROOT/'data/semantic.sqlite'),settings=config)
            if result['products'] and ai_available:
                try:
                    question=('In at most 70 words, explain the first supplied product as the best catalog match under the given constraints, then briefly distinguish the next two alternatives. '
                              'Keep the supplied order. Describe only listed facts; do not claim verified performance or an exact match for unsupported requirements. '
                              f'User request: {request}. Unverified requirements: {result["notes"]}. Verified comparison: {comparison_rows(result)}')
                    answer=grounded_answer(config,question,result['products'],'')
                except ConnectionFailure:
                    ai_available=False
        st.session_state.match={**result,'request':request,'explanation':answer,'ai':ai_available}
        st.session_state.page='Match'
        st.rerun()

if st.session_state.page=='Shop':
    st.markdown('<div class="hero"><div><div class="eyebrow">Less searching. More finding.</div><h1>Good tech.<br>The right fit for you.</h1><p>Tell us what matters. We’ll narrow the catalog to one best match and two thoughtful alternatives.</p></div><div class="hero-art">'+illustration('laptop','#c4e8a5')+'</div></div>',unsafe_allow_html=True)
    finder()
    st.markdown('<div class="section-heading"><div class="section-title">Explore the collection</div><span>A little inspiration to get started</span></div>',unsafe_allow_html=True)
    a,b,c=st.columns([2,1,1])
    query=a.text_input('Search products',placeholder='Search laptops, headphones, 4K…')
    category=b.selectbox('Category',['All',*CATEGORIES],format_func=lambda x:LABELS.get(x,x))
    budget=c.number_input('Up to (USD)',min_value=0.0,value=3500.0,step=50.0)
    parsed_category,parsed_budget=constraints(query)
    active_category=parsed_category if category=='All' else category
    active_budget=min(budget,parsed_budget) if parsed_budget is not None else budget
    keywords='' if parsed_category and parsed_budget is not None else query
    fingerprint=(query,category,budget)
    if st.session_state.get('shop_filters')!=fingerprint:
        st.session_state.shop_page=0
        st.session_state.shop_filters=fingerprint
    products=catalog.search(query=keywords,category=active_category,max_price=active_budget,limit=9,sort='featured',offset=st.session_state.shop_page*9)
    if not products:
        st.info('No products match. Try a broader search or a higher budget.')
    columns=st.columns(3)
    for index,product in enumerate(products):
        with columns[index%3]:
            product_card(product,'shop')
    previous,number,next_page=st.columns([1,3,1])
    if previous.button('Previous',disabled=st.session_state.shop_page==0,width='stretch'):
        st.session_state.shop_page-=1
        st.rerun()
    number.caption(f'Page {st.session_state.shop_page+1}')
    if next_page.button('Next',disabled=len(products)<9,width='stretch'):
        st.session_state.shop_page+=1
        st.rerun()

elif st.session_state.page=='Match':
    st.markdown('<div class="eyebrow">Made a little more personal</div>',unsafe_allow_html=True)
    st.header('Your next device, narrowed down.')
    st.markdown('<p class="finder-intro">Share your budget and the specifications that matter. Get one best match and up to two alternatives from the available catalog.</p>',unsafe_allow_html=True)
    finder()
    result=st.session_state.match
    if result:
        st.markdown(f'<div class="match-question">{escape(result["request"])}</div>',unsafe_allow_html=True)
        if result['message']:
            st.info(result['message'])
        for note in result['notes']:
            st.warning(note)
        products=result['products']
        if products:
            st.caption('Semantic matches · Compared with your requirements' if result['retrieval_mode']=='semantic' else 'AI-guided picks · Checked against listed specifications' if result['ai'] else 'Based on your budget and requested specifications')
            if result['explanation']:
                st.write(result['explanation'])
            columns=st.columns([1.15,1,1])
            for index,product in enumerate(products):
                with columns[index]:
                    label=['Your best match','Another good option','One more to consider'][index]
                    css='match-label best-label' if index==0 else 'match-label'
                    st.markdown(f'<div class="{css}">{label}</div>',unsafe_allow_html=True)
                    product_card(product,'match',result['reasons'][product['id']])
            with st.expander('How these match your request'):
                st.dataframe(comparison_rows(result),hide_index=True,width='stretch')
            st.caption('Matches use the specifications listed here. Any requirements we could not verify are shown above.')

else:
    st.header('Your shopping bag')
    if not st.session_state.cart:
        st.write('Something good belongs here. Explore the collection or find your match.')
    for key,product in list(st.session_state.cart.items()):
        with st.container(border=True):
            a,b,c=st.columns([4,1.3,1])
            a.write(f"**{product['name']}**")
            a.caption(f"${product['price']:,.2f} each")
            quantity=b.number_input('Quantity',min_value=1,max_value=product['stock'],value=product['quantity'],key='qty-'+key)
            st.session_state.cart[key]['quantity']=quantity
            if c.button('Remove',key='remove-'+key):
                del st.session_state.cart[key]
                st.rerun()
    total=subtotal(st.session_state.cart)
    if st.session_state.cart:
        st.metric('Subtotal',f'${total:,.2f}')
        st.caption('Demo checkout. Tax and shipping are excluded. No payment is collected.')
        if st.button('Complete demo order',type='primary'):
            st.session_state.orders.append({'id':'EG-'+uuid.uuid4().hex[:8].upper(),'subtotal':total})
            st.session_state.cart={}
            st.rerun()
    if st.session_state.orders:
        order=st.session_state.orders[-1]
        st.success(f"Demo order {order['id']} confirmed · ${order['subtotal']:,.2f}")

st.markdown('<div class="footer"><strong>electroguide.</strong> &nbsp; Find your fit.<br>Demo storefront · Synthetic products and representative illustrations · No real payments</div>',unsafe_allow_html=True)
