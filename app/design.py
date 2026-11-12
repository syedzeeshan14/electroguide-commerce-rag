"""Local SVG illustrations and shared storefront styles. No remote image service."""
from html import escape
from pathlib import Path

LABELS={'tv':'Televisions','mobile':'Phones','laptop':'Laptops','tablet':'Tablets','smartwatch':'Watches','headphones':'Headphones','camera':'Cameras','monitor':'Monitors','speaker':'Speakers','gaming':'Gaming'}

def illustration(category, color='#c4e8dc'):
    screen='<rect x="95" y="53" width="170" height="112" rx="9" fill="#162c35"/><rect x="102" y="60" width="156" height="98" rx="5" fill="url(#screen)"/><path d="M105 145L155 85 195 128 230 77 255 113V155H105Z" fill="#5ab8a2" opacity=".65"/>'
    shapes={
      'laptop':screen+'<path d="M95 165H265L289 182Q292 189 278 190H82Q68 189 71 182Z" fill="#b6c5cc"/><path d="M160 167H200L207 177H153Z" fill="#899ca6"/>',
      'tv':screen+'<path d="M132 165L120 188M228 165L240 188" stroke="#263d47" stroke-width="8"/>',
      'monitor':screen+'<path d="M180 165V186M146 190H214" stroke="#263d47" stroke-width="9" stroke-linecap="round"/>',
      'mobile':'<rect x="139" y="24" width="83" height="177" rx="18" fill="#253d48"/><rect x="145" y="31" width="71" height="163" rx="13" fill="url(#screen)"/><rect x="165" y="36" width="30" height="8" rx="4" fill="#203741"/><circle cx="167" cy="106" r="45" fill="#c5efb3" opacity=".6"/>',
      'tablet':'<rect x="104" y="24" width="152" height="180" rx="14" fill="#293f48"/><rect x="112" y="32" width="136" height="164" rx="7" fill="url(#screen)"/><path d="M115 172L192 68 244 126V193H115Z" fill="#8ad7bd"/>',
      'smartwatch':'<rect x="160" y="3" width="42" height="218" rx="17" fill="#6b8e81"/><rect x="137" y="65" width="88" height="96" rx="25" fill="#263c45"/><rect x="143" y="71" width="76" height="84" rx="20" fill="#102a2d"/><circle cx="181" cy="111" r="27" fill="none" stroke="#bef782" stroke-width="7" stroke-dasharray="130 40"/><path d="M181 92V112L193 119" stroke="white" stroke-width="3" fill="none"/>',
      'headphones':'<path d="M112 133V100A68 68 0 01248 100V133" fill="none" stroke="#233b43" stroke-width="17"/><path d="M114 87A69 69 0 01246 87" fill="none" stroke="#8aa89c" stroke-width="9"/><rect x="100" y="111" width="37" height="74" rx="16" fill="#365b51"/><rect x="223" y="111" width="37" height="74" rx="16" fill="#365b51"/><rect x="127" y="119" width="12" height="58" rx="6" fill="#1b3336"/><rect x="221" y="119" width="12" height="58" rx="6" fill="#1b3336"/>',
      'camera':'<rect x="91" y="76" width="178" height="109" rx="18" fill="#28413e"/><path d="M121 77L133 56H184L197 77" fill="#28413e"/><circle cx="187" cy="131" r="46" fill="#172a31" stroke="#73978b" stroke-width="6"/><circle cx="187" cy="131" r="30" fill="url(#screen)"/><circle cx="179" cy="121" r="10" fill="#d4f0e9" opacity=".6"/><rect x="105" y="92" width="31" height="12" rx="3" fill="#abc4b8"/>',
      'speaker':'<rect x="128" y="31" width="104" height="167" rx="27" fill="#2d514b"/><rect x="137" y="39" width="86" height="148" rx="21" fill="#3c6159"/><circle cx="180" cy="140" r="30" fill="#203e3a"/><circle cx="180" cy="140" r="20" fill="#52796c"/><circle cx="180" cy="82" r="18" fill="#203e3a"/><circle cx="180" cy="82" r="9" fill="#88a99a"/>',
      'gaming':'<rect x="143" y="26" width="80" height="163" rx="12" fill="#e1e9e5"/><path d="M163 26V189" stroke="#29423d" stroke-width="8"/><path d="M100 145Q105 126 124 130L165 134Q180 134 185 153L195 181Q198 199 183 196L160 181H128L107 196Q89 201 94 180Z" fill="#3b5d51"/><path d="M114 151V173M104 162H125" stroke="#d4e9de" stroke-width="5"/><circle cx="169" cy="155" r="4" fill="#c8ed8e"/><circle cx="178" cy="165" r="4" fill="#c8ed8e"/>'}
    # Every illustration is an original category depiction, not a manufacturer photograph.
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 230" role="img" aria-label="{escape(LABELS[category])} illustration"><defs><linearGradient id="screen" x2="1" y2="1"><stop stop-color="#163d50"/><stop offset=".55" stop-color="{color}"/><stop offset="1" stop-color="#539888"/></linearGradient></defs><ellipse cx="180" cy="204" rx="110" ry="10" fill="#173b32" opacity=".09"/>{shapes[category]}</svg>'

CSS='''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"], [data-testid="stApp"]{font-family:'DM Sans',sans-serif;color:#16342c}
.stApp{background:#f7f8f5} h1,h2,h3{font-family:'Manrope',sans-serif!important;letter-spacing:-.045em!important;color:#143a30!important}
.block-container{max-width:1440px;padding-top:2rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#eef2ec;border-right:1px solid #dfe7dd}
[data-testid="stSidebar"] .block-container{padding-top:1.5rem}
[data-testid="stHeader"]{background:#f7f8f5ee}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:18px!important;border-color:#e0e7df!important;background:white}
.stButton>button{border-radius:10px;border:1px solid #d8e3d8;font-weight:600;min-height:2.6rem}
.stButton>button:hover{border-color:#225b44;color:#225b44;background:#edf5e8}
.stButton>button[kind="primary"]{background:#1b503d;color:white;border-color:#1b503d}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{background:white}
.brand{font-family:'Manrope',sans-serif;font-weight:800;font-size:26px;letter-spacing:-1.4px;color:#143a30}.brand span{color:#5c856c}
.eyebrow{font-size:11px;letter-spacing:2px;font-weight:700;text-transform:uppercase;color:#58705d;margin-bottom:12px}
.topline{display:flex;align-items:center;justify-content:space-between;padding-bottom:24px;border-bottom:1px solid #dde4da;margin-bottom:24px}.topnote{font-size:12px;color:#6c7e70}
.hero{position:relative;overflow:hidden;border-radius:24px;background:#e5eddc;min-height:310px;padding:42px 45px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between;gap:20px}
.hero h1{font-size:52px;line-height:1.08;margin:0 0 18px;max-width:530px;font-weight:800}.hero p{font-size:15px;line-height:1.7;color:#526856;max-width:410px}.hero-art{width:40%;transform:rotate(-5deg);background:radial-gradient(ellipse,#cbdcc0,transparent 68%);position:relative}.hero-art svg{width:100%}.hero-tag{display:inline-block;background:#fbfff4;border:1px solid #d5dfcd;border-radius:30px;padding:7px 13px;font-size:11px;font-weight:700;color:#3d6449;margin-top:10px}
.category-label{color:#728575;font-size:10px;letter-spacing:1.8px;font-weight:700;text-transform:uppercase}.product-name{font:700 18px/1.4 'Manrope',sans-serif;letter-spacing:-.4px;color:#203d32;min-height:51px;margin:6px 0 8px}.spec-line{font-size:12px;color:#6e7c71;min-height:36px;line-height:1.6}.price-row{display:flex;align-items:center;justify-content:space-between;margin-top:14px;margin-bottom:8px}.price{font:800 25px 'Manrope',sans-serif;letter-spacing:-1px}.stock-pill{background:#eef5e9;border-radius:20px;padding:4px 8px;color:#547341;font-size:10px}.product-art{border-radius:13px;background:linear-gradient(145deg,#f0f3eb,#e9eee5);margin-bottom:15px}.product-art svg{display:block;width:100%;height:175px}.section-heading{display:flex;justify-content:space-between;align-items:end;margin:18px 0 14px}.section-title{font:800 25px 'Manrope',sans-serif;letter-spacing:-1px;color:#143a30}.section-heading>span{font-size:12px;color:#778476}.footer{border-top:1px solid #dce4d8;margin-top:38px;padding:20px 0;color:#788477;font-size:11px;line-height:1.8}.empty{padding:45px;text-align:center;background:#edf2e8;border-radius:18px}.assistant-banner{padding:26px 32px;background:#e5eddc;border-radius:20px;margin-bottom:20px}.assistant-banner h2{margin:0 0 8px}.mini-note{font-size:12px;color:#67806c}
@media(max-width:760px){.hero{padding:26px;min-height:260px}.hero h1{font-size:34px}.hero-art{display:none}.topnote{display:none}.block-container{padding:1rem}.product-name{font-size:16px}}
</style>'''
