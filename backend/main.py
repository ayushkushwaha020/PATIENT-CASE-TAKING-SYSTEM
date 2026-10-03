from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, csv, json, re, datetime, os, shutil, tempfile

BASE=os.path.dirname(os.path.abspath(__file__)); DB=os.path.join(BASE,'algominds.db'); FRONT=os.path.join(os.path.dirname(BASE),'frontend')
app=FastAPI(title='ALGOMINDS Patient Case-Taking API',version='1.1')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
app.mount('/static', StaticFiles(directory=FRONT), name='static')

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
 c=conn(); c.executescript('''CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,age INTEGER,gender TEXT,phone TEXT,language TEXT,consent INTEGER,created_at TEXT); CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY AUTOINCREMENT,patient_id INTEGER,raw_text TEXT,summary_json TEXT,ayush_json TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT,entity TEXT,entity_id INTEGER,actor TEXT,created_at TEXT);'''); c.commit(); c.close()
init()
class Patient(BaseModel): name:str; age:int|None=None; gender:str|None=None; phone:str|None=None; language:str='English'; consent:bool=False
class Analyze(BaseModel): text:str; language:str='English'
class Case(BaseModel): patient_id:int; raw_text:str; summary:dict; ayush:dict={}

def audit(a,e,i=None):
 c=conn(); c.execute('INSERT INTO audit(action,entity,entity_id,actor,created_at) VALUES(?,?,?,?,?)',(a,e,i,'demo-user',datetime.datetime.utcnow().isoformat())); c.commit(); c.close()

@app.get('/')
def home(): return FileResponse(os.path.join(FRONT,'index.html'))
@app.get('/api/health')
def health(): return {'status':'ok','project':'ALGOMINDS'}
@app.post('/api/patients')
def add_patient(p:Patient):
 if not p.consent: raise HTTPException(400,'Patient consent is required before saving personal data.')
 c=conn(); cur=c.execute('INSERT INTO patients(name,age,gender,phone,language,consent,created_at) VALUES(?,?,?,?,?,?,?)',(p.name,p.age,p.gender,p.phone,p.language,int(p.consent),datetime.datetime.utcnow().isoformat())); c.commit(); pid=cur.lastrowid; c.close(); audit('CREATE','patient',pid); return {'id':pid,**p.model_dump()}
@app.get('/api/patients')
def list_patients():
 c=conn(); x=[dict(r) for r in c.execute('SELECT * FROM patients ORDER BY id DESC')]; c.close(); return x

def detect_language(text: str, selected: str = 'English'):
    if re.search(r'[\u0900-\u097F]', text): return 'Hindi'
    low=text.lower()
    hindi_words=['mujhe','mera','meri','mere','hai','ho raha','ho rahi','dard','bukhar','bimari','dawai','dava','saans','ulti','ghutne','aalas','bhookh','neend','man nahi','pata','kab se','kitne saal']
    if sum(1 for w in hindi_words if w in low) >= 2: return 'Hindi'
    return selected or 'English'

def extract(t, language='English'):
    original=t.strip(); detected=detect_language(original, language); low=original.lower()
    groups={
      'fever':['fever','hararat','bukhar','बुखार','तापमान'],'headache':['headache','head ache','sar dard','sir dard','sar-dard','सिर दर्द','सर दर्द'],
      'loss of appetite':['loss of appetite','poor appetite','bhookh kam','bhukh kam','bhook kam','भूख कम','भूख नहीं','भूख कम लगना'],
      'fatigue / low energy':['fatigue','tired','aalas','alas','thakan','kamzori','कमजोरी','आलस','थकान','कुछ करने का मन नहीं','काम करने का मन नहीं'],
      'sleep difficulty':['sleep problem','cannot sleep','cant sleep','not able to sleep','so nahi pata','so nahi pa raha','नींद आती है पर सो नहीं','सो नहीं पाता','सो नहीं पा रहा','नींद की समस्या'],
      'cough':['cough','khansi','खांसी'],'cold':['cold','sardi','सर्दी','जुकाम'],'body ache':['body ache','body pain','badan dard','बदन दर्द'],
      'vomiting':['vomiting','vomit','ulti','उल्टी','उल्टियां','उल्टियाँ'],'diarrhea':['diarrhea','dast','दस्त'],
      'breathlessness':['breathlessness','difficulty breathing','saans lene mein dikkat','saans','सांस लेने में दिक्कत','सांस फूल','सांस लेने में कठिनाई','साथ देने में दिक्कत','साथ देने में भी दिक्कत'],
      'chest pain':['chest pain','seene mein dard','सीने में दर्द'],'sore throat':['sore throat','gale mein dard','गले में दर्द'],
      'dizziness':['dizziness','chakkar','चक्कर'],'nausea':['nausea','ji michlana','जी मिचलाना'],'abdominal pain':['abdominal pain','stomach pain','pet dard','पेट दर्द'],
      'knee pain':['knee pain','ghutne mein dard','ghutno mein dard','घुटनों में दर्द','घुटने में दर्द']}
    symptoms=[k for k,v in groups.items() if any(x in low for x in v)]
    hist=[]; history_groups={
      'diabetes':['diabetes','sugar ki bimari','sugar ki dawa','sugar ki medicine','sugar','मधुमेह','शुगर','शुगर की बीमारी','शुगर की दवा'],
      'hypertension':['hypertension','high bp','high blood pressure','blood pressure','bp','ब्लड प्रेशर','उच्च रक्तचाप'],
      'asthma':['asthma','दमा'],'allergy':['allergy','एलर्जी'],'heart disease':['heart disease','दिल की बीमारी','हृदय की बीमारी'],
      'pregnancy':['pregnant','pregnancy','गर्भवती'],'previous surgery':['surgery','operation','सर्जरी','ऑपरेशन'],
      'previous knee disease / knee problem':['knee disease','knee problem','ghutne ki bimari','ghutne ki problem','घुटनों की बीमारी','घुटने की बीमारी','घुटने की समस्या']}
    for k,v in history_groups.items():
      if any(x in low for x in v): hist.append(k)
    knee_years=re.search(r'(\d+)\s*(?:saal|years|year|साल)\s*(?:se|से)?\s*(?:ghutne|ghutno|घुटने|घुटनों)',low)
    if knee_years and 'previous knee disease / knee problem' not in hist: hist.append('previous knee disease / knee problem')
    meds=[x for x in ['paracetamol','metformin','amlodipine','azithromycin','ibuprofen','cetirizine','omeprazole','insulin','इंसुलिन'] if x in low]
    if any(x in low for x in ['sugar ki dawa','sugar ki medicine','शुगर की दवा','शुगर की दवाई','sugar की दवा']) and not meds: meds.append('diabetes medicine (name not provided)')
    if ('tata 1mg' in low or '1mg' in low) and not any(m in low for m in ['paracetamol','metformin','amlodipine','azithromycin','ibuprofen','cetirizine','omeprazole','insulin']): meds.append('medicine mentioned; exact name not provided (Tata 1mg)')
    vit={}; patterns=[
      ('temperature',r'(?:temp(?:erature)?|hararat|तापमान)\s*[:=]?\s*(\d+(?:\.\d+)?)'),
      ('temperature',r'(?:^|\s)(\d{2,3}(?:\.\d+)?)\s*(?:degree|°?f|°?c|बुखार)\b'),
      ('temperature',r'(?:fever|bukhar|बुखार)\s*(?:is|hai|है)?\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)'),
      ('pulse',r'(?:pulse|hr|heart rate|नाड़ी|नब्ज|धमनी)\s*(?:is|hai|है|बराबर|normal|ठीक|सही)?\s*[:=]?\s*(\d+)'),
      ('spo2',r'(?:spo2|oxygen|o2|ऑक्सीजन)\s*(?:level|लेवल)?\s*[:=]?\s*(\d+)\s*%?'),
      ('bp',r'(?:bp|blood pressure|ब्लड प्रेशर)\s*[:=]?\s*(\d{2,3}\s*/\s*\d{2,3})')]
    for k,pat in patterns:
      m=re.search(pat,low)
      if m and k not in vit: vit[k]=m.group(1)
    if re.search(r'(oxygen|ऑक्सीजन).{0,30}(low|कम|kam|down)',low): vit.setdefault('oxygen_status','reported low; numeric value not provided')
    if re.search(r'(pulse|नाड़ी|नब्ज|धमनी).{0,30}(normal|ठीक|बराबर|theek|सही)',low): vit.setdefault('pulse_status','reported normal; numeric value not provided')
    if 'temperature' in vit:
      try:
        if float(vit['temperature']) > 110: vit['temperature_verification']='Reported temperature is unusually high; re-check the thermometer/unit.'
      except ValueError: pass
    flags=[]; flag_terms={'severe chest pain':['severe chest pain','bahut tez seene mein dard','सीने में बहुत तेज दर्द'],'unconscious':['unconscious','बेहोश'],'fainting':['fainting','behoshi','बेहोशी'],'blood in vomit':['blood in vomit','khun ki ulti','खून की उल्टी'],'severe breathlessness':['severe breathlessness','severe difficulty breathing','bahut zyada saans','बहुत ज्यादा सांस','सांस लेने में बहुत दिक्कत']}
    for k,terms in flag_terms.items():
      if any(x in low for x in terms): flags.append(k)
    if 'breathlessness' in symptoms: flags.append('breathing difficulty reported')
    if 'vomiting' in symptoms: flags.append('vomiting reported')
    if vit.get('temperature'):
      try:
        if float(vit['temperature']) >= 103: flags.append('high reported temperature')
      except: pass
    hindi=detected=='Hindi'; q=[]
    if not re.search(r'\b\d+\s*(day|days|din|घंटे|दिन|week|weeks|हफ्ते|mahine|months|महीने|saal|years|साल)\b',low): q.append('Ye takleef kab se hai? Kitne din/ghante se?' if hindi else 'How long have you had these symptoms?')
    if not hist: q.append('Kya aapko pehle se diabetes, BP, asthma, allergy, ghutne ki koi bimari ya koi aur badi bimari hai?' if hindi else 'Do you have diabetes, high BP, asthma, allergies, a knee problem, previous surgery, or another major illness?')
    if not meds: q.append('Kya aap abhi koi medicine le rahe hain? Naam aur dose pata ho to bataiye.' if hindi else 'Are you currently taking any medicines? Please give the name and dose if known.')
    if not vit: q.append('Agar pata ho to temperature, BP, pulse ya oxygen level batayein.' if hindi else 'If known, please provide temperature, blood pressure, pulse or oxygen level.')
    chief=symptoms[0] if symptoms else 'Not clearly stated'
    score=min(100,20+len(symptoms)*7+len(hist)*10+len(meds)*10+len(vit)*10+(10 if re.search(r'\b\d+\s*(day|days|din|दिन|saal|years|साल)\b',low) else 0))
    return {'chief_complaint':chief,'symptoms':symptoms,'history':hist,'medications':meds,'vitals':vit,'red_flags':list(dict.fromkeys(flags)),'missing_questions':q,'completeness_score':score,'patient_statement':original,'detected_language':detected,'clinical_note':'AI-assisted draft only. Qualified clinician verification required.'}

@app.post('/api/cases/analyze')
def analyze(a:Analyze): return extract(a.text,a.language)
@app.post('/api/cases')
def save_case(x:Case):
 c=conn(); cur=c.execute('INSERT INTO cases(patient_id,raw_text,summary_json,ayush_json,created_at) VALUES(?,?,?,?,?)',(x.patient_id,x.raw_text,json.dumps(x.summary,ensure_ascii=False),json.dumps(x.ayush,ensure_ascii=False),datetime.datetime.utcnow().isoformat())); c.commit(); cid=cur.lastrowid; c.close(); audit('CREATE','case',cid); return {'id':cid,'message':'Case saved successfully'}
@app.get('/api/cases/{cid}')
def get_case(cid:int):
 c=conn(); r=c.execute('SELECT cases.*,patients.name,patients.age,patients.gender,patients.language FROM cases JOIN patients ON patients.id=cases.patient_id WHERE cases.id=?',(cid,)).fetchone(); c.close()
 if not r: raise HTTPException(404,'Case not found')
 x=dict(r); x['summary']=json.loads(x.pop('summary_json')); x['ayush']=json.loads(x.pop('ayush_json')); return x
@app.post('/api/cases/csv')
def save_csv(x:Case):
    os.makedirs('data', exist_ok=True); path=os.path.abspath(os.path.join('data','cases.csv')); s=x.summary or {}
    row={'saved_at':datetime.datetime.now().isoformat(timespec='seconds'),'patient_id':x.patient_id,'patient_name':'','chief_complaint':s.get('chief_complaint',''),'symptoms':'; '.join(s.get('symptoms',[])),'history':'; '.join(s.get('history',[])),'medications':'; '.join(s.get('medications',[])),'vitals':json.dumps(s.get('vitals',{}),ensure_ascii=False),'red_flags':'; '.join(s.get('red_flags',[])),'completeness_score':s.get('completeness_score',''),'detected_language':s.get('detected_language',''),'patient_statement':x.raw_text}
    headers=list(row.keys()); exists=os.path.exists(path) and os.path.getsize(path)>0
    with open(path,'a',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=headers)
      if not exists:w.writeheader()
      w.writerow(row)
    return {'message':'Case saved to CSV','path':path}
@app.get('/api/cases/csv/download')
def download_csv():
    path=os.path.abspath(os.path.join('data','cases.csv'))
    if not os.path.exists(path): raise HTTPException(404,'No CSV case data saved yet.')
    return FileResponse(path,media_type='text/csv',filename='ALGOMINDS_cases.csv')
@app.get('/api/cases/{cid}/fhir')
def fhir(cid:int):
 x=get_case(cid); pid=f'algominds-patient-{x["patient_id"]}'; s=x['summary']; patient={'resourceType':'Patient','id':pid,'name':[{'text':x['name']}],'gender':(x['gender'] or '').lower() or None}; entries=[{'resource':patient}]
 for i,sym in enumerate(s.get('symptoms',[]),1): entries.append({'resource':{'resourceType':'Condition','id':f'condition-{cid}-{i}','subject':{'reference':f'Patient/{pid}'},'code':{'text':sym},'clinicalStatus':{'text':'active'}}})
 for i,h in enumerate(s.get('history',[]),1): entries.append({'resource':{'resourceType':'Condition','id':f'history-{cid}-{i}','subject':{'reference':f'Patient/{pid}'},'code':{'text':h},'clinicalStatus':{'text':'history'}}})
 for i,m in enumerate(s.get('medications',[]),1): entries.append({'resource':{'resourceType':'MedicationStatement','id':f'med-{cid}-{i}','subject':{'reference':f'Patient/{pid}'},'medicationCodeableConcept':{'text':m},'status':'active'}})
 for k,v in s.get('vitals',{}).items(): entries.append({'resource':{'resourceType':'Observation','id':f'obs-{cid}-{k}','subject':{'reference':f'Patient/{pid}'},'code':{'text':k},'valueString':str(v)}})
 return {'resourceType':'Bundle','id':f'algominds-case-{cid}','type':'collection','entry':entries}
