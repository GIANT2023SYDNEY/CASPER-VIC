# CASPER-VIC V4.1 CLEAN UI
# EPA Victoria-oriented Data Centre Site Selection & Regulatory Pre-Screening Platform
# Run:
#   conda activate casper
#   python -m pip install -r requirements_casper_v3.txt
#   python -m streamlit run casper_vic_v41_fixed.py

import os, io, json, math, hashlib
from pathlib import Path
from datetime import datetime, timezone
import requests
import pandas as pd
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage

st.set_page_config(page_title='CASPER-VIC V4 | Circular Site Intelligence', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
APP_VERSION='CASPER-VIC V4.1 clean UI build'
LEDGER_FILE=Path('casper_vic_ledger_v41.json')
HEADERS={'User-Agent':'CASPER-VIC-V4/0.5 EPA Victoria circular site intelligence'}
NOMINATIM='https://nominatim.openstreetmap.org'
OVERPASS='https://overpass-api.de/api/interpreter'
VICTORIA_BBOX=(-39.3,140.9,-33.8,150.1)
AUTH_ENDPOINTS={
 'recycled_water':os.getenv('CASPER_RECYCLED_WATER_WFS','').strip(),
 'planning':os.getenv('CASPER_PLANNING_WFS','').strip(),
 'environment':os.getenv('CASPER_ENVIRONMENT_WFS','').strip(),
 'grid':os.getenv('CASPER_GRID_API','').strip(),
}

st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--navy:#0b2943;--cyan:#16b7c9;--teal:#0f9f8f;--green:#219a69;--amber:#c98416;--red:#cf4e5f;--text:#163246}
.stApp{background:radial-gradient(circle at 10% 0%,rgba(22,183,201,.07),transparent 28%),linear-gradient(180deg,#f7fbfc,#edf5f7 55%,#f8fbfc);color:var(--text)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#f8fcfd,#edf5f7);border-right:1px solid rgba(16,67,94,.11)}
[data-testid="stSidebar"] *{color:#24485e}.block-container{padding-top:1.1rem;max-width:1760px}
h1,h2,h3{font-family:"Space Grotesk",Inter,sans-serif!important;color:#12344a!important}
.hero{border-radius:22px;padding:25px 30px 22px;background:linear-gradient(120deg,#0b2943,#125162);box-shadow:0 18px 48px rgba(24,68,91,.12);margin-bottom:18px}
.kicker{color:#68efe4;font-size:.76rem;text-transform:uppercase;letter-spacing:.17em;font-weight:800}.hero-title{font-family:"Space Grotesk";font-size:2.55rem;color:white;font-weight:700;margin:6px 0}.hero-sub{color:#d7ebf2;max-width:1080px}.pill{display:inline-block;margin:12px 5px 0 0;padding:5px 10px;border-radius:100px;border:1px solid rgba(128,242,235,.28);background:rgba(255,255,255,.055);color:#e0feff;font-size:.73rem}
.card,.metric-card{border:1px solid rgba(20,74,102,.12);background:rgba(255,255,255,.96);border-radius:18px;padding:17px 18px;box-shadow:0 10px 28px rgba(30,79,104,.06)}.metric-card{min-height:125px}.label{color:#698396;font-size:.70rem;text-transform:uppercase;letter-spacing:.12em;font-weight:800}.big{font-family:"Space Grotesk";font-size:1.85rem;font-weight:700;margin-top:5px}.note{color:#6d8393;font-size:.78rem;margin-top:7px}.good{color:#219a69}.mid{color:#c98416}.bad{color:#cf4e5f}.cyan{color:#168ca6}.tag{display:inline-block;border-radius:999px;padding:4px 8px;margin:2px 4px 2px 0;font-size:.68rem;font-weight:800}.obs{background:#e7f7f1;color:#147755}.inf{background:#e8f2fb;color:#1a6f9d}.ver{background:#fff3de;color:#a56808}.portal-head{border-left:5px solid #16b7c9;padding-left:14px;margin:8px 0 18px}.small{color:#708797;font-size:.78rem}.stButton button{border-radius:12px!important;background:linear-gradient(135deg,#0f6f83,#145f72)!important;color:#fff!important;font-weight:800!important}
</style>
''',unsafe_allow_html=True)

def haversine_km(lat1,lon1,lat2,lon2):
 r=6371.0088;p1,p2=math.radians(lat1),math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return r*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
def clamp(v): return max(0,min(100,v))
def conf_band(v): return 'HIGH' if v>=75 else 'MEDIUM' if v>=50 else 'LOW'
def fmt_asset(a): return 'Not identified' if not a else f'{a["name"]} · {a["distance_km"]:.2f} km'

@st.cache_data(ttl=3600,show_spinner=False)
def search_victoria(q,limit=8):
 if len(q.strip())<2:return []
 try:
  r=requests.get(f'{NOMINATIM}/search',params={'q':f'{q}, Victoria, Australia','format':'jsonv2','limit':limit,'countrycodes':'au','addressdetails':1},headers=HEADERS,timeout=12);r.raise_for_status();out=[]
  for x in r.json():
   lat,lon=float(x['lat']),float(x['lon'])
   if VICTORIA_BBOX[0]<=lat<=VICTORIA_BBOX[2] and VICTORIA_BBOX[1]<=lon<=VICTORIA_BBOX[3]:out.append({'display':x.get('display_name',q),'lat':lat,'lon':lon})
  return out
 except:return []

@st.cache_data(ttl=3600,show_spinner=False)
def reverse_geocode(lat,lon):
 try:
  r=requests.get(f'{NOMINATIM}/reverse',params={'lat':lat,'lon':lon,'format':'jsonv2','zoom':16},headers=HEADERS,timeout=12);r.raise_for_status();return r.json().get('display_name',f'{lat:.5f}, {lon:.5f}')
 except:return f'{lat:.5f}, {lon:.5f}'

def overpass(q):
 try:
  r=requests.post(OVERPASS,data={'data':q},headers=HEADERS,timeout=30);r.raise_for_status();return r.json().get('elements',[])
 except:return []
def point(el):
 if 'lat' in el:return float(el['lat']),float(el['lon'])
 c=el.get('center',{});return (float(c['lat']),float(c['lon'])) if 'lat' in c else None

@st.cache_data(ttl=1800,show_spinner=False)
def discover_assets(lat,lon,radius_m):
 q=f'''[out:json][timeout:25];(
 nwr["power"="substation"](around:{radius_m},{lat},{lon});
 nwr["power"="plant"](around:{radius_m},{lat},{lon});
 nwr["power"="line"](around:{radius_m},{lat},{lon});
 nwr["man_made"="wastewater_plant"](around:{radius_m},{lat},{lon});
 nwr["water"="wastewater"](around:{radius_m},{lat},{lon});
 nwr["industrial"="food"](around:{radius_m},{lat},{lon});
 nwr["industrial"="brewery"](around:{radius_m},{lat},{lon});
 nwr["industrial"="dairy"](around:{radius_m},{lat},{lon});
 nwr["industrial"="greenhouse"](around:{radius_m},{lat},{lon});
 nwr["landuse"="greenhouse_horticulture"](around:{radius_m},{lat},{lon});
 nwr["landuse"="industrial"](around:{min(radius_m,9000)},{lat},{lon});
 nwr["leisure"="swimming_pool"](around:{min(radius_m,6000)},{lat},{lon});
 nwr["amenity"="hospital"](around:{min(radius_m,8000)},{lat},{lon}););out center tags;'''
 out=[];seen=set()
 for el in overpass(q):
  pt=point(el)
  if not pt:continue
  elat,elon=pt;t=el.get('tags',{});key=(round(elat,5),round(elon,5),t.get('name',''),t.get('power',''),t.get('man_made',''))
  if key in seen:continue
  seen.add(key);out.append({'lat':elat,'lon':elon,'distance_km':haversine_km(lat,lon,elat,elon),'name':t.get('name') or t.get('operator') or 'Unnamed mapped asset','power':t.get('power'),'man_made':t.get('man_made'),'industrial':t.get('industrial'),'landuse':t.get('landuse'),'amenity':t.get('amenity'),'leisure':t.get('leisure'),'source':t.get('source','OpenStreetMap'),'tags':t})
 return sorted(out,key=lambda x:x['distance_km'])

def classify(assets):
 return ([a for a in assets if a['power']=='substation'],[a for a in assets if a['power']=='plant'],[a for a in assets if a['power']=='line'],[a for a in assets if a['man_made']=='wastewater_plant' or a['tags'].get('water')=='wastewater'],[a for a in assets if a['industrial'] or a['landuse'] in ('industrial','greenhouse_horticulture')],[a for a in assets if a['industrial'] in ('food','brewery','dairy','greenhouse') or a['landuse']=='greenhouse_horticulture' or a['amenity']=='hospital' or a['leisure']=='swimming_pool'])
def nearest(xs):return xs[0] if xs else None

def water_model(mw,cooling,water_strategy):
 # Screening WUE assumptions only; replace with vendor/project WUE during due diligence.
 wue={'Liquid cooling + heat recovery':0.20,'Air-cooled / minimal process water':0.05,'Hybrid cooling':0.60,'Evaporative / water-cooled':1.45}[cooling]
 ml_day=mw*24*1000*wue/1_000_000
 potable_frac={'Recycled water preferred':0.15,'Multiple-source circular water':0.30,'On-site rain/stormwater harvesting':0.60,'Potable water acceptable':1.00}[water_strategy]
 return {'wue_l_kwh':wue,'ml_day':round(ml_day,3),'ml_year':round(ml_day*365,1),'potable_fraction':potable_frac,'potable_ml_day':round(ml_day*potable_frac,3),'nonpotable_ml_day':round(ml_day*(1-potable_frac),3)}

def heat_model(mw,cooling):
 frac,use=(.72,.85) if cooling=='Liquid cooling + heat recovery' else ((.42,.72) if cooling=='Hybrid cooling' else ((.22,.60) if cooling=='Evaporative / water-cooled' else (.16,.55)))
 gross=mw*frac
 return {'gross_mwth':round(gross,1),'useful_mwth':round(gross*use,1),'fraction':frac,'annual_useful_gwh':round(gross*use*8760/1000,1)}

def prox(d,e,f,m):
 if d is None:return 8
 if d<=e:return 100
 if d<=f:return 100-30*(d-e)/max(f-e,.1)
 if d<=m:return 70-55*(d-f)/max(m-f,.1)
 return 10

def sector_name(a):
 raw=(a.get('industrial') or a.get('landuse') or a.get('amenity') or a.get('leisure') or 'industrial').replace('_',' ')
 return raw.title()

def heat_demand_estimate(a):
 typ=(a.get('industrial') or a.get('landuse') or a.get('amenity') or a.get('leisure') or '').lower()
 bench={
  'food':(18,75,'60–120°C'),'brewery':(12,45,'60–100°C'),'dairy':(25,90,'60–120°C'),
  'greenhouse':(8,35,'25–55°C'),'greenhouse_horticulture':(8,35,'25–55°C'),
  'hospital':(15,55,'55–90°C'),'swimming_pool':(4,18,'25–45°C'),'industrial':(10,60,'40–140°C')}
 lo,hi,temp=bench.get(typ,bench['industrial'])
 return lo,hi,temp

def build_heat_candidates(heat):
 out=[]
 for a in heat[:15]:
  lo,hi,temp=heat_demand_estimate(a)
  out.append({'candidate':a['name'],'industry':sector_name(a),'distance_km':round(a['distance_km'],2),'indicative_heat_GWh_yr':f'{lo}–{hi}','temperature_band':temp,'match':'High' if a['distance_km']<=3 else 'Medium' if a['distance_km']<=8 else 'Screen','evidence':'Observed asset + sector benchmark','confidence':'Medium' if a.get('industrial') or a.get('amenity') else 'Low–Medium'})
 return out

def build_ag_candidates(industry):
 ag=[]
 for a in industry:
  typ=(a.get('industrial') or a.get('landuse') or '').lower()
  if typ in ('greenhouse','greenhouse_horticulture','dairy'):
   annual='80–350 ML/yr' if 'greenhouse' in typ else '50–250 ML/yr'
   ag.append({'candidate':a['name'],'use':sector_name(a),'distance_km':round(a['distance_km'],2),'indicative_water_demand':annual,'seasonality':'High' if 'greenhouse' not in typ else 'Moderate','water_quality':'Fit-for-purpose assessment required','heat_synergy':'High' if 'greenhouse' in typ else 'Medium','evidence':'Observed asset + benchmark','confidence':'Low–Medium'})
 return ag[:12]

def scale_risk(mw):
 if mw<20:return 0
 if mw<50:return 5
 if mw<100:return 12
 if mw<200:return 22
 return 32

def assess(lat,lon,assets,mw,cooling,water_strategy):
 subs,plants,lines,ww,industry,heat=classify(assets)
 s,p,l,w,i=nearest(subs),nearest(plants),nearest(lines),nearest(ww),nearest(industry)
 wm=water_model(mw,cooling,water_strategy);hm=heat_model(mw,cooling)
 sd=s['distance_km'] if s else None;wd=w['distance_km'] if w else None;idd=i['distance_km'] if i else None
 # 1 Energy & grid: large projects are intentionally penalised non-linearly until capacity is verified.
 pp=round(prox(sd,3,8,20)*.45);pd=min(18,len(subs)*2);pl=12 if l else 0;pplant=min(8,len(plants)*2)
 grid=clamp(pp+pd+pl+pplant+25-scale_risk(mw)-12)
 # 2 Water availability & stress: cooling selection and water source now strongly influence outcome.
 wp=round(prox(wd,3,10,25)*.40);wdens=min(15,len(ww)*4)
 source_bonus={'Recycled water preferred':20,'Multiple-source circular water':24,'On-site rain/stormwater harvesting':10,'Potable water acceptable':-14}[water_strategy]
 cooling_penalty={'Air-cooled / minimal process water':16,'Liquid cooling + heat recovery':8,'Hybrid cooling':-2,'Evaporative / water-cooled':-22}[cooling]
 demand_pen=min(32,wm['ml_day']*5.0)
 potable_pen=min(28,wm['potable_ml_day']*8.0)
 water=clamp(45+wp+wdens+source_bonus+cooling_penalty-demand_pen-potable_pen)
 # 3 Circular water: reward realistic non-potable strategies and proximity, not just low demand.
 circ_water=clamp(25+round(prox(wd,3,10,25)*.35)+min(15,len(ww)*3)+{'Recycled water preferred':24,'Multiple-source circular water':28,'On-site rain/stormwater harvesting':14,'Potable water acceptable':-15}[water_strategy]-min(18,wm['ml_day']*2))
 # 4 Cooling & heat: technology compatibility plus nearby off-takers.
 cp=round(prox(idd,2,6,15)*.30);ch=min(22,len(heat)*3)
 tech={'Liquid cooling + heat recovery':28,'Hybrid cooling':18,'Evaporative / water-cooled':10,'Air-cooled / minimal process water':6}[cooling]
 heat_score=clamp(20+cp+ch+tech)
 # 5 Agricultural reuse: strongest where agricultural/greenhouse candidates exist and circular water selected.
 ag=build_ag_candidates(industry);agprox=prox(ag[0]['distance_km'],2,8,20) if ag else 10
 ag_score=clamp(18+0.45*agprox+min(24,len(ag)*8)+{'Recycled water preferred':18,'Multiple-source circular water':22,'On-site rain/stormwater harvesting':10,'Potable water acceptable':0}[water_strategy])
 # 6 Planning, 7 environment remain deliberately conservative until authoritative APIs are connected.
 plan=50;env=50
 # 8 Community/resource pressure responds strongly to scale + potable water burden.
 community=clamp(92-scale_risk(mw)*1.35-min(45,wm['potable_ml_day']*12)-({'Evaporative / water-cooled':8,'Hybrid cooling':3}.get(cooling,0)))
 # Confidence wheel: source confidence is explicitly separated from condition.
 gconf=clamp(28+(18 if s else 0)+min(15,len(subs))+(8 if l else 0)+(5 if p else 0))
 wconf=clamp(25+(18 if w else 0)+min(15,len(ww)*3)+(10 if AUTH_ENDPOINTS['recycled_water'] else 0))
 hconf=clamp(32+min(22,len(heat)*3));agconf=clamp(24+min(30,len(ag)*10))
 pconf=20 if not AUTH_ENDPOINTS['planning'] else 75;econf=20 if not AUTH_ENDPOINTS['environment'] else 75
 cwconf=clamp(wconf+8 if water_strategy!='Potable water acceptable' else wconf-4);cocomf=42
 lenses={
  'Planning & land':round(plan),'Water availability':round(water),'Energy & grid':round(grid),'Cooling & heat':round(heat_score),
  'Circular water':round(circ_water),'Agricultural reuse':round(ag_score),'Environment & regulatory':round(env),'Community / resources':round(community)}
 confidences={
  'Planning & land':round(pconf),'Water availability':round(wconf),'Energy & grid':round(gconf),'Cooling & heat':round(hconf),
  'Circular water':round(cwconf),'Agricultural reuse':round(agconf),'Environment & regulatory':round(econf),'Community / resources':round(cocomf)}
 weights={'Planning & land':.14,'Water availability':.18,'Energy & grid':.17,'Cooling & heat':.12,'Circular water':.12,'Agricultural reuse':.08,'Environment & regulatory':.12,'Community / resources':.07}
 raw=round(sum(lenses[k]*weights[k] for k in lenses));conf=round(sum(confidences[k]*weights[k] for k in confidences))
 # Critical constraints cap a deceptively high weighted average.
 cap=100
 if lenses['Planning & land']<30:cap=min(cap,49)
 if lenses['Water availability']<30:cap=min(cap,54)
 if lenses['Energy & grid']<25:cap=min(cap,54)
 if lenses['Environment & regulatory']<25:cap=min(cap,49)
 overall=min(raw,cap)
 opp='EXCELLENT' if overall>=82 else 'GOOD' if overall>=68 else 'CONDITIONAL' if overall>=52 else 'POOR' if overall>=35 else 'CRITICAL'
 heat_candidates=build_heat_candidates(heat)
 gates=[
  {'gate':f'{mw} MW grid connection feasibility','domain':'Energy & grid','severity':'CRITICAL','status':'VERIFY','reason':'Infrastructure proximity does not prove connection capacity.'},
  {'gate':'Planning / zoning compatibility','domain':'Planning','severity':'CRITICAL','status':'VERIFY','reason':'Authoritative zone and overlays required.'},
  {'gate':'Flood / waterway / environmental constraints','domain':'Environment','severity':'HIGH','status':'VERIFY','reason':'Authoritative environmental layers required.'},
  {'gate':'Recycled-water volume, quality and supplier commitment','domain':'Circular water','severity':'CRITICAL' if water_strategy in ('Recycled water preferred','Multiple-source circular water') else 'HIGH','status':'VERIFY','reason':'Mapped wastewater assets do not prove available supply.'}]
 if cooling=='Evaporative / water-cooled' and water_strategy=='Potable water acceptable':gates.append({'gate':'High potable-water dependency from evaporative cooling','domain':'Water','severity':'CRITICAL','status':'MITIGATE','reason':f'Screening potable demand is {wm["potable_ml_day"]:.2f} ML/day; consider recycled/non-potable source or alternative cooling.'})
 critical=sum(1 for g in gates if g['severity']=='CRITICAL' and g['status']!='CLEAR')
 rec='HOLD / REDESIGN' if overall<35 else 'CONDITIONAL PROCEED' if critical>=3 else 'TARGETED PRE-FEASIBILITY' if critical==2 else 'PROCEED TO DUE DILIGENCE'
 actions=['Confirm project-specific grid connection feasibility with the relevant network authority.','Interrogate authoritative planning zone and overlays at the candidate point.','Run flood, waterways, biodiversity, contamination and sensitive-receptor screening.']
 if water_strategy!='Potable water acceptable':actions.append('Confirm recycled/non-potable water source, indicative volume, quality, supplier and connection route.')
 if heat_candidates:actions.append(f'Validate the top mapped heat off-takers against approximately {hm["annual_useful_gwh"]:.1f} GWh/year of screening recoverable heat.')
 if ag:actions.append('Engage agricultural/greenhouse candidates to verify seasonal water demand, quality constraints and storage requirements.')
 return {'raw_score':raw,'overall_score':overall,'overall_condition':opp,'site_opportunity':opp,'recommendation':rec,'evidence_confidence':conf,'confidence_band':conf_band(conf),'critical_open_gates':critical,
  'lens_scores':lenses,'lens_confidence':confidences,'grid_score':round(grid),'grid_confidence':round(gconf),'water_score':round(water),'water_confidence':round(wconf),'circular_score':round(heat_score),'circular_confidence':round(hconf),'planning_score':plan,'planning_confidence':pconf,'environment_score':env,'environment_confidence':econf,
  'nearest_substation':s,'nearest_power_plant':p,'nearest_power_line':l,'nearest_wastewater':w,'nearest_industry':i,'asset_counts':{'substations':len(subs),'power_plants':len(plants),'power_lines':len(lines),'wastewater':len(ww),'industry':len(industry),'heat_candidates':len(heat),'agricultural_candidates':len(ag)},
  'water_model':wm,'heat_model':hm,'heat_candidates':heat_candidates,'heat_recommendations':heat_candidates,'agricultural_candidates':ag,
  'score_breakdown':{'power':{'Substation proximity':pp,'Mapped substation density':pd,'Transmission-line context':pl,'Mapped plant context':pplant,'Project scale penalty':-scale_risk(mw),'Unverified capacity penalty':-12},'water':{'Wastewater proximity':wp,'Mapped wastewater density':wdens,'Water-source effect':source_bonus,'Cooling effect':cooling_penalty,'Total water-demand penalty':round(-demand_pen,1),'Potable-demand penalty':round(-potable_pen,1)},'circularity':{'Industrial proximity':cp,'Mapped heat-user density':ch,'Cooling/heat compatibility':tech}},
  'gates':gates,'actions':actions,'source_register':[{'source':'OpenStreetMap / Overpass','use':'Supporting infrastructure, industry and reuse-candidate discovery','status':'Observed / supporting','authority':'Secondary'},{'source':'VicGrid / network provider','use':'Connection capacity and network pathway','status':'Required','authority':'Authoritative'},{'source':'DataVic recycled-water availability','use':'Recycled-water opportunity','status':'Required / connector-ready','authority':'Authoritative'},{'source':'EPA Victoria / DataVic','use':'Environmental and regulatory layers','status':'Required / connector-ready','authority':'Authoritative'},{'source':'Vicmap Planning / VicPlan','use':'Zone and overlays','status':'Required / connector-ready','authority':'Authoritative'},{'source':'CASPER sector benchmarks','use':'Indicative heat and agricultural demand ranges','status':'Derived — verify with off-taker','authority':'Model'}]}

def wheel_chart(values,title,centre_text):
 labels=list(values.keys());vals=[float(values[k]) for k in labels];n=len(labels)
 angles=[2*math.pi*i/n for i in range(n)];angles+=angles[:1];vals2=vals+vals[:1]
 fig=plt.figure(figsize=(6.2,6.2));ax=fig.add_subplot(111,polar=True)
 ax.plot(angles,vals2,linewidth=2);ax.fill(angles,vals2,alpha=.14)
 ax.set_ylim(0,100);ax.set_yticks([25,50,75,100]);ax.set_yticklabels(['25','50','75','100'],fontsize=7)
 ax.set_xticks(angles[:-1]);ax.set_xticklabels([x.replace(' & ',' &\n').replace(' / ',' /\n') for x in labels],fontsize=8)
 ax.set_title(title,pad=22,fontsize=13,fontweight='bold');ax.text(0,0,centre_text,ha='center',va='center',fontsize=11,fontweight='bold',bbox=dict(boxstyle='round,pad=.5',facecolor='white',alpha=.9,edgecolor='0.85'))
 fig.tight_layout();b=io.BytesIO();fig.savefig(b,format='png',dpi=160,bbox_inches='tight',transparent=True);plt.close(fig);b.seek(0);return b

# --- ledger ---
def b_hash(b):
 x=dict(b);x.pop('block_hash',None);return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def p_hash(p):return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def load_chain():
 if not LEDGER_FILE.exists():
  g={'index':0,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'assessment_id':'GENESIS','payload_hash':hashlib.sha256(b'CASPER-VIC-V4').hexdigest(),'previous_hash':'0'*64,'block_hash':''};g['block_hash']=b_hash(g);LEDGER_FILE.write_text(json.dumps([g],indent=2))
 try:return json.loads(LEDGER_FILE.read_text())
 except:return []
def append_block(payload):
 c=load_chain();prev=c[-1];b={'index':prev['index']+1,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'assessment_id':'CV4-'+datetime.now().strftime('%Y%m%d-%H%M%S'),'payload_hash':p_hash(payload),'previous_hash':prev['block_hash'],'block_hash':''};b['block_hash']=b_hash(b);c.append(b);LEDGER_FILE.write_text(json.dumps(c,indent=2));return b
def verify_chain():
 c=load_chain()
 for n,b in enumerate(c):
  if b_hash(b)!=b.get('block_hash'):return False,f'Block {n} hash mismatch'
  if n and b.get('previous_hash')!=c[n-1].get('block_hash'):return False,f'Block {n} chain-link mismatch'
 return True,f'{len(c)} blocks verified'

# --- report utilities ---
def styles():
 s=getSampleStyleSheet();return {'title':ParagraphStyle('title2',parent=s['Title'],fontSize=26,leading=30,textColor=colors.HexColor('#0B2943')),'h1':ParagraphStyle('h1x',parent=s['Heading1'],fontSize=17,leading=21,textColor=colors.HexColor('#0B2943')),'h2':ParagraphStyle('h2x',parent=s['Heading2'],fontSize=11,leading=14,textColor=colors.HexColor('#0F6F83')),'body':ParagraphStyle('bx',parent=s['BodyText'],fontSize=8.8,leading=12.5,textColor=colors.HexColor('#29495D')),'small':ParagraphStyle('sx',parent=s['BodyText'],fontSize=7.2,leading=10,textColor=colors.HexColor('#657F8F')),'decision':ParagraphStyle('dx',parent=s['Heading1'],fontSize=21,leading=24,textColor=colors.HexColor('#0F6F83'))}
def table(data,widths=None):
 t=Table(data,colWidths=widths,repeatRows=1);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.HexColor('#CBDCE3')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),7.6),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0B2943')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor('#29495D')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
def pagehead(story,s,title,sub=None):story.append(Paragraph(title,s['h1']));story.append(Paragraph(sub,s['small'])) if sub else None;story.append(Spacer(1,5))
def footer(canvas,doc):canvas.saveState();canvas.setFont('Helvetica',7);canvas.setFillColor(colors.HexColor('#6F8493'));canvas.drawString(18*mm,10*mm,APP_VERSION);canvas.drawRightString(195*mm,10*mm,f'Page {doc.page}');canvas.restoreState()
def chart(vals,labels,title,ylabel):
 fig,ax=plt.subplots(figsize=(7,3.2));ax.bar(labels,vals);ax.set_title(title);ax.set_ylabel(ylabel);ax.grid(axis='y',alpha=.18);fig.tight_layout();b=io.BytesIO();fig.savefig(b,format='png',dpi=160,bbox_inches='tight');plt.close(fig);b.seek(0);return b

def build_report(site,profile,a,ledger_status):
 b=io.BytesIO();doc=SimpleDocTemplate(b,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=16*mm,bottomMargin=16*mm);s=styles();story=[]
 # Cover
 story += [Spacer(1,25*mm),Paragraph('CASPER·VIC',s['title']),Paragraph('DATA CENTRE SITE INTELLIGENCE REPORT',s['title']),Spacer(1,8*mm),Paragraph(site['label'],s['body']),Paragraph(f'Proposed capacity: {profile["scale_mw"]} MW',s['body']),Paragraph(f'Cooling: {profile["cooling"]}',s['body']),Spacer(1,15*mm),Paragraph(a['recommendation'],s['decision']),Paragraph(f'Overall condition: <b>{a.get("overall_condition",a["site_opportunity"])}</b> · Evidence confidence: <b>{a["confidence_band"]}</b> · Critical gates open: <b>{a["critical_open_gates"]}</b>',s['body']),Spacer(1,18*mm),Paragraph('Pre-feasibility decision support only. Not an approval, grid offer, water-supply commitment or detailed design.',s['small']),PageBreak()]
 sections=[]
 sections.append(('1. Executive Decision Dashboard',table([['Decision element','Result'],['CASPER recommendation',a['recommendation']],['Site opportunity',a['site_opportunity']],['Raw opportunity score',f'{a["raw_score"]}/100'],['Evidence confidence',f'{a["evidence_confidence"]}/100 ({a["confidence_band"]})'],['Critical gates open',a['critical_open_gates']],['Grid',f'{a["grid_score"]}/100'],['Water',f'{a["water_score"]}/100'],['Circularity',f'{a["circular_score"]}/100']], [65*mm,110*mm]),'CASPER applies a gate-first approach: favourable opportunity cannot override unresolved critical constraints.'))
 sections.append(('2. Candidate Site and Project Definition',table([['Parameter','Value'],['Candidate',site['label']],['Latitude',f'{site["latitude"]:.6f}'],['Longitude',f'{site["longitude"]:.6f}'],['Scale',f'{profile["scale_mw"]} MW'],['Cooling',profile['cooling']],['Water strategy',profile['water_strategy']]], [55*mm,120*mm]),'Parcel title, easements and legal access remain outside this screening assessment.'))
 sections.append(('3. CASPER Methodology',table([['Stage','Purpose'],['Locality screen','Identify broadly promising areas'],['Candidate site','Assess selected point'],['Infrastructure','Screen power, wastewater and industry'],['Engineering model','Estimate water and recoverable heat'],['Critical gates','Prevent fatal constraints being hidden by score'],['Evidence confidence','Measure evidence completeness'],['Audit','Hash assessment content']], [52*mm,123*mm]),'V3 distinguishes observed evidence, model inference and authoritative verification requirements.'))
 scoreimg=chart([a['grid_score'],a['water_score'],a['circular_score'],a['planning_score'],a['environment_score']],['Grid','Water','Circularity','Planning','Environment'],'CASPER domain signals','Score / 100');sections.append(('4. Domain Scoring Overview',RLImage(scoreimg,width=175*mm,height=80*mm),'Planning and environment are provisional until authoritative data connectors are configured.'))
 confimg=chart([a['grid_confidence'],a['water_confidence'],a['circular_confidence'],a['planning_confidence'],a['environment_confidence']],['Grid','Water','Circularity','Planning','Environment'],'Evidence completeness','Confidence / 100');sections.append(('5. Evidence Confidence',RLImage(confimg,width=175*mm,height=80*mm),'Confidence measures completeness and authority of evidence, not probability of project success.'))
 sections.append(('6. Electricity and Grid Infrastructure',table([['Item','Finding','Status'],['Nearest substation',fmt_asset(a['nearest_substation']),'Observed'],['Nearest power line',fmt_asset(a['nearest_power_line']),'Observed'],['Nearest power plant',fmt_asset(a['nearest_power_plant']),'Observed'],['Connection capacity','Not verified','Critical verification'],['Grid score',a['grid_score'],'Inferred']], [55*mm,85*mm,35*mm]),'Project-specific capacity, redundancy, augmentation and timing require network-authority evidence.'))
 sections.append(('7. Explainable Grid Score',table([['Component','Points']]+[[k,v] for k,v in a['score_breakdown']['power'].items()],[120*mm,45*mm]),'The unverified-capacity penalty is retained even when nearby infrastructure appears favourable.'))
 sections.append(('8. Renewable Energy Context',table([['Question','Status'],['Transmission-scale renewable pathway','VERIFY'],['PPA opportunity','Commercial assessment required'],['Renewable-energy-zone context','VERIFY'],['Firming / redundancy','Project-specific design'],['On-site generation','Supplementary only']], [85*mm,90*mm]),'V3 deliberately excludes generic rooftop solar panels from meaningful grid-capacity evidence.'))
 sections.append(('9. Indicative Data-Centre Energy Profile',table([['Parameter','Value'],['Facility scale',f'{profile["scale_mw"]} MW'],['Daily energy',f'{profile["scale_mw"]*24:,.0f} MWh/day'],['Annual energy',f'{profile["scale_mw"]*24*365/1000:,.1f} GWh/year'],['Cooling',profile['cooling']]], [80*mm,95*mm]),'Actual demand depends on IT load, PUE, utilisation and staged build-out.'))
 wm=a['water_model'];wimg=chart([wm['ml_day'],wm['ml_year']/365],['Estimated ML/day','Annual avg ML/day'],'Screening water demand','ML/day');sections.append(('10. Water Demand Screening',RLImage(wimg,width=175*mm,height=80*mm),f'Screening WUE assumption: {wm["wue_l_kwh"]:.2f} L/kWh. Estimated demand: {wm["ml_day"]:.3f} ML/day or {wm["ml_year"]:.1f} ML/year.'))
 sections.append(('11. Recycled-Water Opportunity',table([['Item','Finding'],['Nearest wastewater asset',fmt_asset(a['nearest_wastewater'])],['Mapped assets in radius',a['asset_counts']['wastewater']],['Volume','Not verified'],['Quality / class','Not verified'],['Supplier','Not verified'],['Connection route','Not verified'],['Water score',a['water_score']]], [75*mm,100*mm]),'Authoritative recycled-water availability and direct supplier confirmation are required.'))
 sections.append(('12. Stormwater, Rainwater and Alternative Water',table([['Opportunity','Screening position'],['Roof rainwater capture','Potentially useful'],['Stormwater harvesting','Requires hydrology, storage and quality assessment'],['Blowdown reuse','Potential optimisation'],['Potable dependency','Quantify after recycled-water assessment'],['Drought resilience','Supply-security analysis required']], [75*mm,100*mm]),'Preferred hierarchy: avoid demand, minimise, substitute potable water, recover and reuse.'))
 sections.append(('13. Wastewater, Blowdown and Discharge',table([['Issue','Assessment requirement'],['Cooling blowdown','Characterise flow and quality'],['Treatment residuals','Assess disposal / recovery pathway'],['Trade waste','Confirm acceptance criteria'],['Emergency discharge','Define containment'],['Receiving-environment risk','Assess pathway']], [70*mm,105*mm]),'Detailed discharge pathways are project-specific.'))
 hm=a['heat_model'];himg=chart([hm['gross_mwth'],hm['useful_mwth']],['Gross recoverable','Useful recoverable'],'Waste-heat recovery','MWth');sections.append(('14. Waste-Heat Recovery Potential',RLImage(himg,width=175*mm,height=80*mm),f'Gross recoverable heat: {hm["gross_mwth"]:.1f} MWth; useful screening estimate: {hm["useful_mwth"]:.1f} MWth.'))
 # Heat off-taker table — resilient to evolving candidate schemas
 heat_recs=a.get('heat_recommendations') or a.get('heat_candidates') or []
 hrows=[['Opportunity','Basis','Distance km','Fit']]
 if heat_recs:
  for x in heat_recs:
   if not isinstance(x,dict):
    continue
   opportunity=(x.get('opportunity') or x.get('name') or x.get('industry') or x.get('facility') or x.get('type') or 'Potential off-taker')
   basis=(x.get('basis') or x.get('reason') or x.get('description') or x.get('sector') or 'Indicative mapped heat-use candidate')
   distance=x.get('distance_km',x.get('distance'))
   fit=(x.get('fit') or x.get('rating') or x.get('suitability') or 'Screen')
   hrows.append([opportunity,basis,'' if distance is None else distance,fit])
 if len(hrows)==1:
  hrows.append(['No candidate identified','No suitable heat off-taker identified from available screening data','','Low'])
 sections.append(('15. Heat Off-Taker and Industrial Symbiosis',table(hrows,[65*mm,48*mm,28*mm,28*mm]),'Bankable heat recovery requires temperature compatibility, load matching, route feasibility and commercial durability.'))
 sections.append(('16. Planning and Land-Use Screening',table([['Question','Status'],['Zone','VERIFY'],['Overlays','VERIFY'],['Data-centre land-use pathway','VERIFY'],['Industrial / residential interface','VERIFY'],['Airport constraints','VERIFY where relevant'],['Easements / title','VERIFY']], [90*mm,85*mm]),'Planning remains a critical verification gate.'))
 sections.append(('17. Flood and Waterway Screening',table([['Constraint','Status'],['Flood extent / floodway','VERIFY'],['Overland-flow path','VERIFY'],['Waterway proximity','VERIFY'],['Climate-change allowance','VERIFY'],['Emergency access','VERIFY'],['Stormwater discharge constraints','VERIFY']], [90*mm,85*mm]),'Authoritative flood and waterway datasets are required.'))
 sections.append(('18. Environmental Constraint Screening',table([['Constraint','Status'],['Biodiversity / habitat','VERIFY'],['Contaminated land','VERIFY'],['Noise receptors','VERIFY'],['Emergency-generator emissions','VERIFY'],['Waste / hazardous materials','VERIFY'],['Water-quality risk','VERIFY'],['Cultural heritage','VERIFY']], [95*mm,80*mm]),'Environmental evidence is deliberately left provisional rather than fabricated.'))
 sections.append(('19. Sensitive Receptors and Community Interface',table([['Receptor','Assessment need'],['Residential areas','Distance / noise / visual interface'],['Schools / childcare','Sensitive receptor mapping'],['Hospitals','Noise / resilience / traffic'],['Community infrastructure','Construction and operational impacts'],['Transport network','Heavy vehicles / access'],['Cumulative impacts','Other industrial / DC developments']], [75*mm,100*mm]),'Community and cumulative-impact screening should begin before site commitment.'))
 grows=[['Gate','Domain','Severity','Status','Reason']]+[[g['gate'],g['domain'],g['severity'],g['status'],g['reason']] for g in a['gates']];sections.append(('20. Critical Verification Gate Register',table(grows,[48*mm,25*mm,22*mm,20*mm,60*mm]),'Critical gates override the raw opportunity score.'))
 risks=[['Risk','Likelihood','Consequence','Status','Treatment'],['Insufficient grid capacity','Possible','Major','Open','Connection study'],['Planning incompatibility','Possible','Major','Open','Planning due diligence'],['Recycled water unavailable','Possible','Major','Open','Supplier confirmation'],['Flood / environment constraint','Unknown','Major','Open','Authoritative GIS'],['Heat off-taker not viable','Possible','Moderate','Open','Thermal feasibility'],['Community / noise interface','Unknown','Moderate','Open','Receptor + acoustic study']];sections.append(('21. Preliminary Risk Register',table(risks,[43*mm,24*mm,29*mm,22*mm,57*mm]),'Risk ratings are preliminary screening prompts, not formal project risk acceptance.'))
 er=[['Source','Use','Status','Authority']]+[[x['source'],x['use'],x['status'],x['authority']] for x in a['source_register']];sections.append(('22. Evidence Register',table(er,[45*mm,65*mm,35*mm,30*mm]),'CASPER should prefer authoritative government and utility sources and clearly flag secondary data.'))
 acts=[['Priority','Recommended action']]+[[idx,x] for idx,x in enumerate(a['actions'],1)];sections.append(('23. Investigation and Engagement Plan',table(acts,[25*mm,150*mm]),'Engage EPA, the relevant water corporation and network authority early once material risks are identified.'))
 sections.append(('24. Site-Selection Conclusion',Paragraph(a['recommendation'],s['decision']),f'The site presents {a["site_opportunity"]} opportunity with {a["confidence_band"]} evidence confidence and {a["critical_open_gates"]} open critical gate(s). Targeted due diligence is required before land commitment or regulatory reliance.'))
 sections.append(('25. Audit Trail, Integrity and Limitations',table([['Audit item','Status'],['CASPER version',APP_VERSION],['Ledger verification',ledger_status],['Hashing method','SHA-256'],['Ledger architecture','Local tamper-evident chain'],['Distributed blockchain','No']], [70*mm,105*mm]),'The ledger provides tamper-evidence, not a public distributed blockchain.'))
 for title,element,note in sections:
  pagehead(story,s,title);story.append(element);story.append(Spacer(1,7));story.append(Paragraph(note,s['body']));story.append(PageBreak())
 doc.build(story,onFirstPage=footer,onLaterPages=footer);b.seek(0);return b.getvalue()

def build_brief(site,profile,a):
 b=io.BytesIO();doc=SimpleDocTemplate(b,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=16*mm,bottomMargin=16*mm);s=styles();story=[Paragraph('CASPER·VIC Executive Site Brief',s['title']),Paragraph(site['label'],s['body']),Spacer(1,6),Paragraph(a['recommendation'],s['decision']),Spacer(1,6),table([['Decision element','Result'],['Opportunity',a['site_opportunity']],['Raw score',a['raw_score']],['Evidence confidence',f'{a["evidence_confidence"]}/100'],['Critical gates',a['critical_open_gates']],['Grid',a['grid_score']],['Water',a['water_score']],['Circularity',a['circular_score']]], [70*mm,105*mm]),PageBreak()];pagehead(story,s,'Key Findings');story += [Paragraph(f'Nearest substation: {fmt_asset(a["nearest_substation"])}',s['body']),Paragraph(f'Nearest wastewater asset: {fmt_asset(a["nearest_wastewater"])}',s['body']),Paragraph(f'Estimated water: {a["water_model"]["ml_day"]:.3f} ML/day',s['body']),Paragraph(f'Useful recoverable heat: {a["heat_model"]["useful_mwth"]:.1f} MWth',s['body']),PageBreak()];pagehead(story,s,'Open Gates');story.append(table([['Gate','Severity','Status']]+[[g['gate'],g['severity'],g['status']] for g in a['gates']],[105*mm,35*mm,35*mm]));story.append(PageBreak());pagehead(story,s,'Recommended Actions');[story.extend([Paragraph(f'{i}. {x}',s['body']),Spacer(1,4)]) for i,x in enumerate(a['actions'],1)];doc.build(story,onFirstPage=footer,onLaterPages=footer);b.seek(0);return b.getvalue()

# --- session ---
defaults={'site_lat':-37.8136,'site_lon':144.9631,'site_label':'Melbourne, Victoria, Australia','assessment':None,'assets':[],'portal':'overview','scenarios':[]}
for k,v in defaults.items():
 if k not in st.session_state:st.session_state[k]=v

st.markdown('''<div class="hero"><div class="kicker">EPA VICTORIA · CIRCULAR DATA CENTRE SITE INTELLIGENCE</div><div class="hero-title">CASPER<span style="color:#62f0e3">·VIC V4</span></div><div class="hero-sub">Eight-lens, evidence-aware site screening with dynamic condition and confidence wheels, sensitive water/cooling logic, heat off-taker intelligence and agricultural reuse.</div><span class="pill">8-lens condition wheel</span><span class="pill">Evidence confidence wheel</span><span class="pill">Cooling × water sensitivity</span><span class="pill">Heat off-takers</span><span class="pill">Agricultural reuse</span><span class="pill">20+ page report</span></div>''',unsafe_allow_html=True)

with st.sidebar:
 st.markdown('## ◈ CASPER Controls');st.caption('Pre-feasibility decision support — not a statutory determination.')
 st.markdown('### 1 · Site search');q=st.text_input('Victorian locality or address',placeholder='Start typing: Tru..., Lav..., Mall...')
 suggestions=search_victoria(q) if len(q.strip())>=2 else []
 if suggestions:
  labels=[x['display'] for x in suggestions];sel=st.selectbox('Matching Victorian locations',labels);chosen=suggestions[labels.index(sel)]
  if st.button('⌖ Use selected location',use_container_width=True):st.session_state.site_lat=chosen['lat'];st.session_state.site_lon=chosen['lon'];st.session_state.site_label=chosen['display'];st.session_state.assessment=None;st.session_state.assets=[];st.rerun()
 st.caption('After selecting a locality, click the map for a specific candidate point.')
 st.divider();st.markdown('### 2 · Data centre profile');dc_mw=st.slider('Facility / connection scale (MW)',5,300,100,5);cooling=st.selectbox('Cooling architecture',['Liquid cooling + heat recovery','Air-cooled / minimal process water','Hybrid cooling','Evaporative / water-cooled']);water_strategy=st.selectbox('Preferred water strategy',['Recycled water preferred','Multiple-source circular water','On-site rain/stormwater harvesting','Potable water acceptable']);radius_km=st.slider('Discovery radius (km)',5,30,15)
 live_wm=water_model(dc_mw,cooling,water_strategy)
 st.markdown(f'<div class="card" style="margin-top:10px"><div class="label">LIVE PROFILE IMPACT</div><b>{live_wm["ml_day"]:.2f} ML/day</b> total process water<br><b>{live_wm["potable_ml_day"]:.2f} ML/day</b> screening potable dependency<br><span class="small">WUE assumption: {live_wm["wue_l_kwh"]:.2f} L/kWh · updates with cooling and water strategy</span></div>',unsafe_allow_html=True)
 st.divider();st.markdown('### 3 · Evidence state');st.markdown('<span class="tag obs">OBSERVED</span> mapped/public evidence',unsafe_allow_html=True);st.markdown('<span class="tag inf">INFERRED</span> CASPER model',unsafe_allow_html=True);st.markdown('<span class="tag ver">VERIFY</span> authoritative evidence required',unsafe_allow_html=True)

# Re-score immediately when the project profile changes; asset discovery only needs to be rerun when site/radius changes.
if st.session_state.assets:
 st.session_state.assessment=assess(st.session_state.site_lat,st.session_state.site_lon,st.session_state.assets,dc_mw,cooling,water_strategy)

# portals
if st.session_state.portal!='overview' and st.session_state.assessment:
 a=st.session_state.assessment
 if st.button('← Back to site overview'):st.session_state.portal='overview';st.rerun()
 p=st.session_state.portal;st.markdown(f'<div class="portal-head"><div class="label">CASPER EVIDENCE PORTAL</div><h2>{p.upper()}</h2></div>',unsafe_allow_html=True)
 if p=='power':
  c1,c2,c3=st.columns(3);c1.metric('Grid signal',f'{a["grid_score"]}/100');c2.metric('Evidence confidence',f'{a["grid_confidence"]}/100');c3.metric('Connection capacity','NOT VERIFIED');st.warning('Nearby infrastructure does not establish available MW or a connection offer.');st.dataframe(pd.DataFrame([{'Component':k,'Points':v} for k,v in a['score_breakdown']['power'].items()]),hide_index=True,use_container_width=True);st.dataframe(pd.DataFrame([['Nearest substation',fmt_asset(a['nearest_substation']),'Observed'],['Nearest line',fmt_asset(a['nearest_power_line']),'Observed'],['Connection capacity','Not verified','Critical verification']],columns=['Question','Finding','Status']),hide_index=True,use_container_width=True)
 elif p=='water':
  wm=a['water_model'];c1,c2,c3=st.columns(3);c1.metric('Water signal',f'{a["water_score"]}/100');c2.metric('Estimated demand',f'{wm["ml_day"]:.3f} ML/day');c3.metric('Potable dependency',f'{wm["potable_ml_day"]:.3f} ML/day');st.dataframe(pd.DataFrame([{'Component':k,'Points':v} for k,v in a['score_breakdown']['water'].items()]),hide_index=True,use_container_width=True);st.info(f'Nearest mapped wastewater asset: {fmt_asset(a["nearest_wastewater"])}. Match estimated demand against authoritative recycled-water volumes next.')
 elif p=='circularity':
  hm=a['heat_model'];c1,c2,c3=st.columns(3);c1.metric('Cooling & heat',f'{a["lens_scores"]["Cooling & heat"]}/100');c2.metric('Useful heat',f'{hm["useful_mwth"]:.1f} MWth');c3.metric('Annual useful heat',f'{hm["annual_useful_gwh"]:.1f} GWh/yr');st.caption('Candidate heat demand is sector-benchmark derived, not measured facility demand.');st.dataframe(pd.DataFrame(a['heat_candidates']),hide_index=True,use_container_width=True)
 elif p=='agriculture':
  st.metric('Agricultural reuse',f'{a["lens_scores"]["Agricultural reuse"]}/100')
  st.caption('Nearby greenhouse/dairy candidates are mapped opportunities. Annual demand ranges are screening benchmarks and require off-taker verification.')
  if a['agricultural_candidates']:
   st.dataframe(pd.DataFrame(a['agricultural_candidates']),hide_index=True,use_container_width=True)
  else:
   st.info('No mapped agricultural / greenhouse reuse candidates found in the current discovery radius.')
 elif p=='planning':st.metric('Planning signal',f'{a["planning_score"]}/100');st.error('Planning remains a critical verification gate until authoritative zone and overlay layers are connected.');st.dataframe(pd.DataFrame([['Zone','VERIFY'],['Overlays','VERIFY'],['Land-use pathway','VERIFY'],['Airport constraints','VERIFY where relevant'],['Easements / title','VERIFY']],columns=['Question','Status']),hide_index=True,use_container_width=True)
 elif p=='environment':st.metric('Environmental signal',f'{a["environment_score"]}/100');st.error('Environmental status is provisional until authoritative layers are connected.');st.dataframe(pd.DataFrame([['Flood / floodway','VERIFY'],['Waterways','VERIFY'],['Biodiversity','VERIFY'],['Contamination','VERIFY'],['Sensitive receptors','VERIFY'],['Cultural heritage','VERIFY']],columns=['Question','Status']),hide_index=True,use_container_width=True)
 elif p=='gates':
  st.dataframe(pd.DataFrame(a['gates']),hide_index=True,use_container_width=True)
  for i,x in enumerate(a['actions'],1):
   st.write(f'**{i}.** {x}')
 elif p=='sources':st.dataframe(pd.DataFrame(a['source_register']),hide_index=True,use_container_width=True)
 st.stop()

left,right=st.columns([1.55,1],gap='large')
with left:
 st.markdown('### 01 · Locality → candidate site');st.caption('Search a Victorian locality/address, then click the map for a more precise point.')
 m=folium.Map(location=[st.session_state.site_lat,st.session_state.site_lon],zoom_start=11,tiles='CartoDB positron',control_scale=True);folium.CircleMarker([st.session_state.site_lat,st.session_state.site_lon],radius=10,color='#0f9f8f',weight=3,fill=True,fill_color='#16b7c9',fill_opacity=.35,tooltip='Current candidate').add_to(m)
 if st.session_state.assets:
  groups={'Power':MarkerCluster(name='Power'),'Water':MarkerCluster(name='Water / wastewater'),'Industry':MarkerCluster(name='Industry / heat users')}
  for g in groups.values():
   g.add_to(m)
  for asset in st.session_state.assets[:300]:
   if asset['power']:group,icon,col=groups['Power'],'bolt','orange'
   elif asset['man_made']=='wastewater_plant' or asset['tags'].get('water')=='wastewater':group,icon,col=groups['Water'],'tint','blue'
   else:group,icon,col=groups['Industry'],'industry','purple'
   folium.Marker([asset['lat'],asset['lon']],tooltip=f'{asset["name"]} · {asset["distance_km"]:.1f} km',icon=folium.Icon(color=col,icon=icon,prefix='fa')).add_to(group)
  folium.LayerControl(collapsed=True).add_to(m)
 ms=st_folium(m,height=570,use_container_width=True,returned_objects=['last_clicked'],key='v41map')
 if ms and ms.get('last_clicked'):
  c=ms['last_clicked'];lat2,lon2=c['lat'],c['lng']
  if abs(lat2-st.session_state.site_lat)>.00005 or abs(lon2-st.session_state.site_lon)>.00005:st.session_state.site_lat=lat2;st.session_state.site_lon=lon2;st.session_state.site_label=reverse_geocode(lat2,lon2);st.session_state.assessment=None;st.session_state.assets=[];st.rerun()
 st.markdown(f'''<div class="card"><div class="label">CURRENT CANDIDATE</div><b>{st.session_state.site_label}</b><br><span class="small">{st.session_state.site_lat:.6f}, {st.session_state.site_lon:.6f}</span></div>''',unsafe_allow_html=True)
with right:
 st.markdown('### 02 · Run CASPER intelligence scan');st.caption('V4 evaluates eight interconnected lenses and keeps condition separate from evidence confidence.')
 if st.button('◉ RUN SITE SCAN',use_container_width=True,type='primary'):
  with st.spinner('Scanning infrastructure and applying gate-first logic…'):
   assets=discover_assets(round(st.session_state.site_lat,5),round(st.session_state.site_lon,5),int(radius_km*1000));st.session_state.assets=assets;st.session_state.assessment=assess(st.session_state.site_lat,st.session_state.site_lon,assets,dc_mw,cooling,water_strategy);st.rerun()
 a=st.session_state.assessment
 if not a:st.markdown('<div class="card"><div class="label">READY</div><div class="big cyan">Awaiting site scan</div><div class="note">Run the assessment to create an explainable site intelligence record.</div></div>',unsafe_allow_html=True)
 else:
  rec_cls='good' if a['recommendation'] in ('PROCEED','PROCEED TO DUE DILIGENCE') else 'mid';st.markdown(f'<div class="metric-card"><div class="label">CASPER RECOMMENDATION</div><div class="big {rec_cls}">{a["recommendation"]}</div><div class="note">Gate-first decision — not an approval outcome</div></div>',unsafe_allow_html=True);st.write('');c1,c2,c3=st.columns(3);c1.metric('Overall condition',a['overall_condition'],f'{a["overall_score"]}/100');c2.metric('Evidence confidence',a['confidence_band'],f'{a["evidence_confidence"]}/100');c3.metric('Critical gates',f'{a["critical_open_gates"]} OPEN')
  lens_portals={'Planning & land':'planning','Water availability':'water','Energy & grid':'power','Cooling & heat':'circularity','Circular water':'water','Agricultural reuse':'agriculture','Environment & regulatory':'environment','Community / resources':'sources'}
  for idx,(name,score) in enumerate(a['lens_scores'].items()):
   conf=a['lens_confidence'][name];x1,x2,x3=st.columns([1.45,.45,.72]);x1.write(f'**{name}**');x2.write(f'**{score}/100**')
   with x3:
    if st.button('Evidence →',key=f'p{idx}',use_container_width=True):st.session_state.portal=lens_portals[name];st.rerun()
   st.caption(f'Evidence confidence: {conf}/100')
  ga,gb=st.columns(2)
  with ga:
   if st.button('⚠ Verification gates',use_container_width=True):st.session_state.portal='gates';st.rerun()
  with gb:
   if st.button('◫ Source register',use_container_width=True):st.session_state.portal='sources';st.rerun()


if st.session_state.assessment:
 a=st.session_state.assessment
 st.write('');st.markdown('### 03 · CASPER eight-lens assessment')
 wa,wb=st.columns(2,gap='large')
 with wa:st.image(wheel_chart(a['lens_scores'],'SITE CONDITION',f"{a['overall_score']}/100\n{a['overall_condition']}"),use_container_width=True)
 with wb:st.image(wheel_chart(a['lens_confidence'],'DATA SOURCE CONFIDENCE',f"{a['evidence_confidence']}/100\n{a['confidence_band']}"),use_container_width=True)
 st.caption('Condition answers “How suitable does the site currently look?” Confidence answers “How strong is the evidence behind that conclusion?” Scores are screening outputs, not approvals.')

if st.session_state.assessment:
 a=st.session_state.assessment;st.write('');st.markdown('### 04 · Engineering intelligence snapshot');wm=a['water_model'];hm=a['heat_model'];c1,c2,c3,c4=st.columns(4);c1.metric('Total process water',f'{wm["ml_day"]:.3f} ML/day');c2.metric('Potable dependency',f'{wm["potable_ml_day"]:.3f} ML/day');c3.metric('Useful recoverable heat',f'{hm["useful_mwth"]:.1f} MWth');c4.metric('Nearest wastewater',fmt_asset(a['nearest_wastewater']));st.caption('Screening estimates — replace with project-specific WUE, PUE, temperatures and operating profile during due diligence.')
 st.write('')
 st.markdown('### 05 · Recommended next actions')
 for i,x in enumerate(a['actions'],1):
  st.markdown(f'<div class="card" style="margin-bottom:8px"><b>{i:02d}</b> · {x}</div>',unsafe_allow_html=True)
 st.write('');st.markdown('### 06 · Save and compare candidate sites');s1,s2=st.columns([1,1.8])
 with s1:
  name=st.text_input('Scenario name',value='Candidate')
  if st.button('＋ Save current scenario',use_container_width=True):
   rec={'name':name,'site':st.session_state.site_label,'MW':dc_mw,'recommendation':a['recommendation'],'opportunity':a['site_opportunity'],'score':a['overall_score'],'confidence':a['evidence_confidence'],'grid':a['lens_scores']['Energy & grid'],'water':a['lens_scores']['Water availability'],'circularity':a['lens_scores']['Circular water'],'critical_gates':a['critical_open_gates'],'water_ML_day':wm['ml_day'],'useful_heat_MWth':hm['useful_mwth']};st.session_state.scenarios=[x for x in st.session_state.scenarios if x['name']!=name]+[rec];st.success('Scenario saved.')
 with s2:
  if st.session_state.scenarios:
   st.dataframe(pd.DataFrame(st.session_state.scenarios),hide_index=True,use_container_width=True)
  else:
   st.info('Save multiple candidates to compare them side-by-side.')
 st.write('');st.markdown('### 07 · Report and audit outputs');generated=datetime.now(timezone.utc).isoformat();site={'label':st.session_state.site_label,'latitude':st.session_state.site_lat,'longitude':st.session_state.site_lon};profile={'scale_mw':dc_mw,'cooling':cooling,'water_strategy':water_strategy,'generated_utc':generated};payload={'casper_version':APP_VERSION,'generated_utc':generated,'site':site,'data_centre':profile,'assessment':a,'limitations':['Grid capacity not confirmed','Recycled-water volume/quality/supplier not confirmed','Planning/environment provisional','Water/heat values are screening estimates','Ledger is a local hash chain']};valid,msg=verify_chain();ledger=f'{"VERIFIED" if valid else "FAILED"} — {msg}';e1,e2,e3,e4=st.columns(4)
 with e1:st.download_button('⇩ JSON record',json.dumps(payload,indent=2,default=str),'casper_vic_v41_assessment.json','application/json',use_container_width=True)
 with e2:
  if st.button('Build executive brief',use_container_width=True):st.session_state.exec_pdf=build_brief(site,profile,a)
  if 'exec_pdf' in st.session_state:st.download_button('⇩ Download brief PDF',st.session_state.exec_pdf,'CASPER_VIC_Executive_Brief.pdf','application/pdf',use_container_width=True)
 with e3:
  if st.button('Build 20+ page report',use_container_width=True):
   with st.spinner('Generating full Site Intelligence Report…'):st.session_state.full_pdf=build_report(site,profile,a,ledger)
  if 'full_pdf' in st.session_state:st.download_button('⇩ Download full PDF',st.session_state.full_pdf,'CASPER_VIC_Full_Site_Intelligence_Report.pdf','application/pdf',use_container_width=True)
 with e4:
  if st.button('⛓ Record assessment',use_container_width=True):b=append_block(payload);st.success(b['assessment_id'])
 st.caption(f'Ledger integrity: {ledger}')

st.markdown('---');st.markdown(f'<span class="small">{APP_VERSION} · Pre-feasibility data-centre site intelligence for Victoria. Observed evidence, model inference and authoritative verification are deliberately separated.</span>',unsafe_allow_html=True)
