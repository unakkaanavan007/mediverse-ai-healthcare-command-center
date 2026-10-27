import os, re, json
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mediverse.db').replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'local-demo-only-change-this-secret')
if os.getenv('VERCEL') and (not os.getenv('DATABASE_URL') or not os.getenv('JWT_SECRET_KEY') or not os.getenv('DEMO_ADMIN_PASSWORD')):
 raise RuntimeError('Set DATABASE_URL, JWT_SECRET_KEY and DEMO_ADMIN_PASSWORD for Vercel')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=2)
CORS(app, origins=os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173').split(','))
db = SQLAlchemy(app); jwt = JWTManager(app)

class User(db.Model):
 id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(100), nullable=False); email=db.Column(db.String(120), unique=True, nullable=False); password=db.Column(db.String(255), nullable=False); role=db.Column(db.String(20), default='patient')
class Patient(db.Model):
 id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(100), nullable=False); age=db.Column(db.Integer); gender=db.Column(db.String(30)); condition=db.Column(db.String(200)); owner_id=db.Column(db.Integer, db.ForeignKey('user.id'))
class Doctor(db.Model):
 id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(100), nullable=False); specialty=db.Column(db.String(100)); availability=db.Column(db.String(100))
class Appointment(db.Model):
 id=db.Column(db.Integer, primary_key=True); patient_id=db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False); doctor_id=db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False); date=db.Column(db.String(10), nullable=False); time=db.Column(db.String(5), nullable=False); status=db.Column(db.String(30), default='Confirmed')
class Audit(db.Model):
 id=db.Column(db.Integer, primary_key=True); actor=db.Column(db.String(120)); action=db.Column(db.String(200)); created=db.Column(db.DateTime, default=lambda:datetime.now(timezone.utc))

def current(): return db.session.get(User, int(get_jwt_identity()))
def roles(*allowed):
 def dec(fn):
  @wraps(fn)
  @jwt_required()
  def wrapped(*a, **kw):
   u=current()
   if not u or u.role not in allowed: return jsonify(error='Access denied'),403
   return fn(*a, **kw)
  return wrapped
 return dec
def audit(action):
 db.session.add(Audit(actor=current().email,action=action)); db.session.commit()
def patient_json(p): return {'id':p.id,'name':p.name,'age':p.age,'gender':p.gender,'condition':p.condition}
def doctor_json(d): return {'id':d.id,'name':d.name,'specialty':d.specialty,'availability':d.availability}
def appointment_json(a):
 p=db.session.get(Patient,a.patient_id); d=db.session.get(Doctor,a.doctor_id)
 return {'id':a.id,'patient_id':a.patient_id,'patient':p.name if p else 'Unknown','doctor_id':a.doctor_id,'doctor':d.name if d else 'Unknown','date':a.date,'time':a.time,'status':a.status}
def visible_patients():
 u=current(); return Patient.query if u.role in ('admin','doctor') else Patient.query.filter_by(owner_id=u.id)
def visible_appts():
 return Appointment.query.join(Patient).filter(Patient.id.in_([p.id for p in visible_patients().all()]))
@app.errorhandler(413)
def too_large(e): return jsonify(error='File exceeds 5 MB'),413
@app.post('/api/register')
def register():
 b=request.get_json(silent=True) or {}; name=str(b.get('name','')).strip(); email=str(b.get('email','')).strip().lower(); pw=str(b.get('password',''))
 if not name or len(name)>100 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(pw)<8: return jsonify(error='Enter a name, valid email and password of at least 8 characters.'),400
 if User.query.filter_by(email=email).first(): return jsonify(error='Email already registered'),409
 u=User(name=name,email=email,password=generate_password_hash(pw),role='patient'); db.session.add(u); db.session.flush(); db.session.add(Patient(name=name,owner_id=u.id)); db.session.commit(); return jsonify(message='Account created'),201
@app.post('/api/login')
def login():
 b=request.get_json(silent=True) or {}; u=User.query.filter_by(email=str(b.get('email','')).strip().lower()).first()
 if not u or not check_password_hash(u.password,str(b.get('password',''))): return jsonify(error='Invalid email or password'),401
 return jsonify(token=create_access_token(identity=str(u.id)),user={'name':u.name,'email':u.email,'role':u.role})
@app.get('/api/me')
@jwt_required()
def me():
 u=current()
 if not u:return jsonify(error='Account unavailable'),401
 return jsonify(name=u.name,email=u.email,role=u.role)
@app.get('/api/patients')
@jwt_required()
def patients(): return jsonify([patient_json(p) for p in visible_patients().all()])
@app.post('/api/patients')
@roles('admin','doctor')
def add_patient():
 b=request.get_json(silent=True) or {}; name=str(b.get('name','')).strip()
 try: age=int(b.get('age',0))
 except (ValueError,TypeError): return jsonify(error='Invalid age'),400
 if not name or len(name)>100 or not 0<=age<=120:return jsonify(error='Enter a valid name and age'),400
 p=Patient(name=name,age=age,gender=str(b.get('gender',''))[:30],condition=str(b.get('condition',''))[:200]);db.session.add(p);db.session.commit();audit('Created patient');return jsonify(patient_json(p)),201
@app.get('/api/doctors')
@jwt_required()
def doctors(): return jsonify([doctor_json(d) for d in Doctor.query.all()])
@app.post('/api/doctors')
@roles('admin')
def add_doctor():
 b=request.get_json(silent=True) or {}; name=str(b.get('name','')).strip()
 if not name or len(name)>100:return jsonify(error='Enter a valid name'),400
 d=Doctor(name=name,specialty=str(b.get('specialty',''))[:100],availability=str(b.get('availability',''))[:100]);db.session.add(d);db.session.commit();audit('Created doctor');return jsonify(doctor_json(d)),201
@app.get('/api/appointments')
@jwt_required()
def appointments(): return jsonify([appointment_json(a) for a in visible_appts().order_by(Appointment.id.desc()).all()])
@app.post('/api/appointments')
@jwt_required()
def add_appointment():
 b=request.get_json(silent=True) or {}
 try:
  p=visible_patients().filter_by(id=int(b.get('patient_id'))).first(); d=db.session.get(Doctor,int(b.get('doctor_id'))); dt=datetime.strptime(str(b.get('date'))+' '+str(b.get('time')),'%Y-%m-%d %H:%M')
 except (ValueError,TypeError): return jsonify(error='Choose a valid patient, doctor, date and time'),400
 if not p or not d:return jsonify(error='Patient or doctor unavailable'),400
 if dt < datetime.now():return jsonify(error='Choose a future time'),400
 if Appointment.query.filter_by(doctor_id=d.id,date=b['date'],time=b['time'],status='Confirmed').first():return jsonify(error='Time slot already booked'),409
 a=Appointment(patient_id=p.id,doctor_id=d.id,date=b['date'],time=b['time']);db.session.add(a);db.session.commit();audit('Booked appointment');return jsonify(appointment_json(a)),201
@app.patch('/api/appointments/<int:id>')
@jwt_required()
def update_appointment(id):
 a=visible_appts().filter(Appointment.id==id).first()
 if not a:return jsonify(error='Appointment not found'),404
 b=request.get_json(silent=True) or {}
 if b.get('status')=='Cancelled':a.status='Cancelled'
 else:
  try: dt=datetime.strptime(str(b.get('date'))+' '+str(b.get('time')),'%Y-%m-%d %H:%M')
  except ValueError:return jsonify(error='Invalid date or time'),400
  if dt<datetime.now():return jsonify(error='Choose a future time'),400
  if Appointment.query.filter(Appointment.doctor_id==a.doctor_id,Appointment.date==b['date'],Appointment.time==b['time'],Appointment.status=='Confirmed',Appointment.id!=a.id).first():return jsonify(error='Time slot already booked'),409
  a.date=b['date'];a.time=b['time'];a.status='Confirmed'
 db.session.commit();audit('Updated appointment');return jsonify(appointment_json(a))
@app.get('/api/audit')
@roles('admin')
def audits(): return jsonify([{'actor':x.actor,'action':x.action,'created':x.created.isoformat()} for x in Audit.query.order_by(Audit.id.desc()).limit(30)])
SAFETY='For education only. This is not a diagnosis or treatment; consult a qualified clinician. For severe or rapidly worsening symptoms, seek urgent local care.'
@app.post('/api/assistant')
@jwt_required()
def assistant():
 b=request.get_json(silent=True) or {}; message=str(b.get('message','')).strip()
 if not message or len(message)>4000:return jsonify(error='Enter a message under 4,000 characters'),400
 key=os.getenv('GEMINI_API_KEY')
 if key:
  try:
   from google import genai
   client=genai.Client(api_key=key)
   result=client.models.generate_content(model=os.getenv('GEMINI_MODEL','gemini-2.5-flash'),contents='Give general health education only. Do not diagnose, prescribe, or claim certainty. Encourage clinician review and urgent care for emergencies. User: '+message)
   return jsonify(answer=(result.text or 'No response available')+'\n\n'+SAFETY,mode='Gemini')
  except Exception: pass
 return jsonify(answer='Demo mode: I cannot assess your condition or interpret individual results. Write down your symptoms, their duration, and any questions for a qualified clinician. If symptoms are severe or worsening, seek urgent care.\n\n'+SAFETY,mode='Demo')
@app.post('/api/report')
@jwt_required()
def report():
 f=request.files.get('file')
 if not f or not f.filename.lower().endswith('.pdf'):return jsonify(error='Upload a text-based PDF (maximum 5 MB). Image OCR is not available in this version.'),400
 try:
  if f.stream.read(5)!=b'%PDF-': return jsonify(error='Invalid PDF'),400
  f.stream.seek(0); reader=PdfReader(f.stream); content='\n'.join((p.extract_text() or '') for p in reader.pages[:15])[:12000]
 except Exception:return jsonify(error='Could not read this PDF'),400
 if not content.strip():return jsonify(error='No text found. Scanned PDFs require OCR, which is not included.'),400
 key=os.getenv('GEMINI_API_KEY')
 if key:
  try:
   from google import genai
   result=genai.Client(api_key=key).models.generate_content(model=os.getenv('GEMINI_MODEL','gemini-2.5-flash'),contents='Summarize this medical report in plain language. Only flag numerical values when the report explicitly provides a reference range, and quote that range. Never diagnose or prescribe. If unclear, say so.\n'+content)
   return jsonify(summary=(result.text or 'No summary available')+'\n\n'+SAFETY,mode='Gemini',extracted=content[:1500])
  except Exception: pass
 return jsonify(summary='Demo mode: text extracted. AI summarization and reliable reference-range interpretation require a configured Gemini API key. Please ask a clinician to review the report.\n\n'+SAFETY,mode='Demo',extracted=content[:1500])
with app.app_context():
 db.create_all()
 if not User.query.first():
  admin=User(name='Demo Administrator',email='admin@mediverse.demo',password=generate_password_hash(os.getenv('DEMO_ADMIN_PASSWORD', 'DemoAdmin123!')),role='admin'); db.session.add(admin);db.session.flush()
  db.session.add_all([Patient(name='Aarav Kumar',age=34,gender='Male',condition='Routine follow-up'),Patient(name='Maya Patel',age=28,gender='Female',condition='Wellness visit'),Patient(name='Rohan Shah',age=46,gender='Male',condition='Cardiology review'),Patient(name='Priya Rao',age=39,gender='Female',condition='General check-up')]);db.session.add_all([Doctor(name='Dr. Ananya Sharma',specialty='Cardiology',availability='Mon–Fri, 09:00–16:00'),Doctor(name='Dr. Arjun Mehta',specialty='General Medicine',availability='Mon–Sat, 10:00–17:00'),Doctor(name='Dr. Nisha Rao',specialty='Neurology',availability='Tue–Fri, 09:00–15:00')]);db.session.commit()
if __name__=='__main__': app.run(port=5000,debug=os.getenv('FLASK_DEBUG')=='1')
