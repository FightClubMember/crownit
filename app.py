import os, sys, json, time, random, string, uuid, logging, html
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Random Data ──
CITIES = ["Mumbai","Delhi","Bangalore","Hyderabad","Ahmedabad","Chennai","Kolkata","Pune","Jaipur","Lucknow","Nagpur","Indore","Bhopal","Surat","Patna","Agra","Nashik","Faridabad","Meerut","Varanasi","Srinagar","Amritsar","Visakhapatnam","Thane","Aurangabad","Ranchi","Guwahati","Chandigarh","Coimbatore","Mysore","Mangalore","Dehradun","Panaji"]
FIRST_M = ["Aarav","Vihaan","Vivaan","Advik","Kabir","Aarush","Ayaan","Arjun","Reyansh","Aryan","Ishaan","Siddharth","Rahul","Amit","Vikram","Ravi","Suresh","Raj","Rohit","Aniket"]
FIRST_F = ["Ananya","Diya","Priya","Neha","Pooja","Sneha","Anjali","Kavita","Sunita","Riya","Isha","Nandini","Meera","Kiran","Shreya","Tanvi","Aishwarya","Divya","Shweta","Kriti"]
LAST = ["Sharma","Verma","Patel","Singh","Kumar","Gupta","Reddy","Joshi","Pandey","Mishra","Yadav","Agarwal","Nair","Menon","Deshmukh","Choudhury","Saxena","Mehta","Shah","Kapoor","Malhotra"]
SURVEY_ANS = ["Yes","No","Good","Daily","Weekly","Monthly","Very Satisfied","Satisfied","Neutral","Online","Store","Quality","Price","Morning","Evening","1-2 times","3-5 times","Never","Under ₹500","₹500-₹1000","₹1000+","Facebook","Instagram","YouTube","WhatsApp"]

def random_person():
    g = random.choice(["Male","Female"])
    p = FIRST_M if g=="Male" else FIRST_F
    return {"name":f"{random.choice(p)} {random.choice(LAST)}","dob":f"{random.randint(1970,2005)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}","gender":g,"city":random.choice(CITIES)}

# ── Crownit API ──
class CrownitAPI:
    def __init__(self, phone):
        self.phone = phone
        self.profile = random_person()
        self.s = requests.Session()
        self.did = f"crownit-web-{uuid.uuid4().hex[:16]}"
        self.token = None
        self.s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36","Accept":"application/json","Content-Type":"application/json","Origin":"https://feedback.crownit.in","Referer":"https://feedback.crownit.in/lite/"})
    
    def _r(self, m, p, **kw):
        url = p if p.startswith("http") else f"https://feedback.crownit.in/api{p}"
        kw.setdefault("timeout",25)
        r = self.s.request(m, url, **kw)
        logger.info(f"{m} {p} → {r.status_code}")
        return r
    
    def send_otp(self): return self._r("PUT",f"/users/{self.phone}/otp").status_code in (200,201,204)
    
    def register(self):
        r = self._r("POST","/users",json={"name":self.profile["name"],"mobile":self.phone,"email":f"{''.join(random.choices(string.ascii_lowercase,k=6))}{random.randint(1,999)}@gmail.com","dob":self.profile["dob"],"gender":self.profile["gender"],"city":self.profile["city"],"deviceId":self.did})
        if r.status_code in (200,201):
            d = r.json()
            self.token = d.get("token") or d.get("data",{}).get("token")
            if self.token: self.s.headers.update({"Authorization":f"Bearer {self.token}"})
            return True
        return False
    
    def accept_terms(self):
        self._r("POST","/get/term-and-cond-status",json={"mobile":self.phone})
        self._r("POST","/save/term-and-cond-status",json={"mobile":self.phone,"termAndCond":True})
    
    def get_survey(self):
        r = self._r("POST","/survey/smart/question/",json={"mobile":self.phone,"deviceId":self.did,"surveyType":"onboarding"})
        if r.status_code==200:
            d = r.json()
            return d.get("data",{}).get("questions",[]) or d.get("questions",[])
        return []
    
    def submit_survey(self, qs):
        if not qs: return False
        ans = []
        for q in qs:
            opts = q.get("options",q.get("answers",[]))
            if opts: v = random.choice(opts).get("value") or random.choice(opts).get("id") or random.choice(opts).get("text","")
            else: v = random.choice(SURVEY_ANS)
            ans.append({"questionId":q.get("id") or q.get("questionId"),"answer":v,"type":q.get("type","singleChoice")})
        r = self._r("POST","/survey/smart/question/",json={"mobile":self.phone,"deviceId":self.did,"answers":ans})
        return r.status_code in (200,201)
    
    def check_rewards(self):
        for url in ["https://feedback.crownit.in/v2/rewards","https://feedback.crownit.in/api/rewards"]:
            try:
                r = self.s.get(url, timeout=10)
                if r.status_code==200 and ("gift" in r.text.lower() or "voucher" in r.text.lower()):
                    return r.text[:2000]
            except: pass
        return None
    
    def run(self, otp):
        result = {"status":"error","profile":self.profile,"gift_card":None,"logs":[]}
        def log(m): result["logs"].append(m); logger.info(m)
        try:
            log("📤 Sending OTP...")
            if not self.send_otp(): result["error"]="Send OTP failed"; return result
            log("✅ OTP sent! Verifying...")
            time.sleep(2)
            log("🔐 Verifying OTP...")
            self._r("POST",f"/users/{self.phone}/verify-otp",json={"otp":otp,"mobile":self.phone})
            log("📝 Registering user...")
            if not self.register(): result["error"]="Registration failed"; return result
            log("✅ Registered!")
            log("📋 Accepting terms...")
            self.accept_terms()
            log("✅ Terms accepted!")
            log("📊 Fetching survey...")
            time.sleep(1)
            qs = self.get_survey()
            if qs:
                log(f"📝 Submitting {len(qs)} answers...")
                self.submit_survey(qs)
                log("✅ Survey done!")
            else: log("ℹ️ No survey available")
            log("⏳ Waiting 20s before rewards check...")
            for i in range(20,0,-1):
                if i%5==0: log(f"  {i}s...")
                time.sleep(1)
            log("🎁 Checking rewards...")
            gc = self.check_rewards()
            if gc: result["gift_card"]=gc; log("🎉 GIFT CARD FOUND!")
            else: log("ℹ️ No gift card")
            result["status"]="ok"
            log("✅ Done!")
        except Exception as e:
            result["error"]=str(e)
            log(f"❌ {e}")
        return result

# ── HTML Page ──
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Crownit Auto Bot</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{background:#fff;border-radius:20px;padding:40px;width:100%;max-width:500px;box-shadow:0 20px 60px rgba(0,0,0,.3)}
h1{font-size:24px;color:#333;margin-bottom:5px;display:flex;align-items:center;gap:10px}
.sub{color:#888;font-size:14px;margin-bottom:25px}
.form-group{margin-bottom:15px}
label{display:block;font-size:14px;font-weight:600;color:#555;margin-bottom:5px}
input{width:100%;padding:12px 16px;border:2px solid #e0e0e0;border-radius:12px;font-size:16px;transition:.2s}
input:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.15)}
.btn{width:100%;padding:14px;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;transition:.2s;margin-top:5px}
.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.btn-primary:hover{opacity:.9;transform:translateY(-1px)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn-secondary{background:#f0f0f0;color:#555}
.btn-secondary:hover{background:#e0e0e0}
.row{display:flex;gap:10px}
.row .btn{flex:1}
.profile-box{background:#f8f9ff;border-radius:12px;padding:16px;margin:15px 0;font-size:14px;line-height:1.8}
.profile-box b{color:#667eea}
.logs{background:#1a1a2e;color:#00ff88;border-radius:12px;padding:16px;font-family:monospace;font-size:13px;max-height:300px;overflow-y:auto;margin:15px 0;display:none;line-height:1.6}
.logs div{margin:2px 0}
.result{display:none}
.gift-card{background:#fff3cd;border:2px solid #ffc107;border-radius:12px;padding:16px;margin:15px 0;font-size:13px;word-break:break-all;max-height:300px;overflow-y:auto}
.gift-card b{color:#d39e00}
.error{background:#f8d7da;border:2px solid #f5c6cb;border-radius:12px;padding:16px;margin:15px 0;color:#721c24}
.step{display:none}
.step.active{display:block}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.status-dot.green{background:#00c853}
.status-dot.yellow{background:#ffc107}
</style>
</head>
<body>
<div class="card" id="app">
  <h1>🤖 Crownit Auto Bot</h1>
  <div class="sub">Automated registration + survey + rewards</div>
  
  <!-- Step 1: Phone -->
  <div id="step1" class="step active">
    <div class="form-group">
      <label>📱 Indian Mobile Number</label>
      <input type="tel" id="phone" placeholder="9876543210" maxlength="10" inputmode="numeric">
    </div>
    <button class="btn btn-primary" onclick="step1()">🚀 Start</button>
  </div>
  
  <!-- Step 2: Confirm Profile -->
  <div id="step2" class="step">
    <div class="profile-box" id="profileBox"></div>
    <div class="row">
      <button class="btn btn-secondary" onclick="regenerate()">🔄 New</button>
      <button class="btn btn-primary" onclick="step2()">✅ Confirm & Send OTP</button>
    </div>
  </div>
  
  <!-- Step 3: OTP -->
  <div id="step3" class="step">
    <div class="form-group">
      <label>🔑 Enter OTP from SMS</label>
      <input type="text" id="otp" placeholder="482916" maxlength="6" inputmode="numeric">
    </div>
    <button class="btn btn-primary" onclick="step3()">✅ Submit OTP</button>
  </div>
  
  <!-- Step 4: Running -->
  <div id="step4" class="step">
    <div style="text-align:center;margin:20px 0">
      <div style="display:inline-block;width:60px;height:60px;border:4px solid #e0e0e0;border-top-color:#667eea;border-radius:50%;animation:spin .8s linear infinite"></div>
      <p style="margin-top:15px;color:#888">Working on it... this takes ~1 minute</p>
    </div>
    <div class="logs" id="logs"></div>
  </div>
  
  <!-- Step 5: Result -->
  <div id="step5" class="step result">
    <div id="resultBox"></div>
    <button class="btn btn-primary" onclick="reset()">🔄 Do Another</button>
  </div>
</div>

<style>
@keyframes spin{to{transform:rotate(360deg)}}
</style>

<script>
let currentData = {};

function api(path, data){
  return fetch(path, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data)
  }).then(r=>r.json());
}

function show(id){
  document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function addLog(msg){
  const l = document.getElementById('logs');
  l.style.display='block';
  const d = document.createElement('div');
  d.textContent = '> ' + msg;
  l.appendChild(d);
  l.scrollTop = l.scrollHeight;
}

// Step 1: Send phone
function step1(){
  const phone = document.getElementById('phone').value.trim();
  if(!phone||phone.length!=10||!/^[6789]/.test(phone)){
    alert('Enter valid 10-digit Indian mobile number (starts with 6/7/8/9)');
    return;
  }
  document.querySelector('#step1 .btn').disabled=true;
  document.querySelector('#step1 .btn').textContent='⏳ Generating...';
  
  api('/init', {phone}).then(data=>{
    document.querySelector('#step1 .btn').disabled=false;
    document.querySelector('#step1 .btn').textContent='🚀 Start';
    if(data.status=='ok'){
      currentData = data;
      document.getElementById('profileBox').innerHTML = `
        <b>👤 Name:</b> ${data.profile.name}<br>
        <b>🎂 DOB:</b> ${data.profile.dob}<br>
        <b>⚧️ Gender:</b> ${data.profile.gender}<br>
        <b>🏙 City:</b> ${data.profile.city}<br>
        <b>📱 Phone:</b> ${phone}
      `;
      show('step2');
    } else {
      alert('Error: '+data.error);
    }
  });
}

// Regenerate profile
function regenerate(){
  currentData.profile = null;
  api('/init', {phone: document.getElementById('phone').value.trim()}).then(data=>{
    if(data.status=='ok'){
      currentData = data;
      document.getElementById('profileBox').innerHTML = `
        <b>👤 Name:</b> ${data.profile.name}<br>
        <b>🎂 DOB:</b> ${data.profile.dob}<br>
        <b>⚧️ Gender:</b> ${data.profile.gender}<br>
        <b>🏙 City:</b> ${data.profile.city}<br>
        <b>📱 Phone:</b> ${document.getElementById('phone').value.trim()}
      `;
    }
  });
}

// Step 2: Confirm & send OTP
function step2(){
  show('step4');
  addLog('📤 Sending OTP...');
  
  api('/send-otp', {phone: document.getElementById('phone').value.trim()}).then(data=>{
    if(data.status=='ok'){
      addLog('✅ OTP sent! Check SMS.');
      show('step3');
    } else {
      addLog('❌ '+data.error);
      document.getElementById('logs').innerHTML += '<div style="color:#ff6b6b">❌ Failed. Try again.</div>';
    }
  });
}

// Step 3: Submit OTP
function step3(){
  const otp = document.getElementById('otp').value.trim();
  if(!otp||otp.length<4){
    alert('Enter the OTP code from SMS');
    return;
  }
  show('step4');
  addLog('🔐 Verifying OTP and running workflow...');
  
  api('/run', {
    phone: document.getElementById('phone').value.trim(),
    otp: otp,
    profile: currentData.profile
  }).then(data=>{
    // Show all logs
    if(data.logs) data.logs.forEach(l=>addLog(l));
    
    if(data.status=='ok'){
      let html = '<div style="text-align:center;margin:10px 0"><span style="font-size:48px">✅</span></div>';
      html += '<div class="profile-box">';
      html += `<b>👤</b> ${data.profile.name}<br>`;
      html += `<b>📱</b> ${document.getElementById('phone').value.trim()}<br>`;
      html += `<b>🎂</b> ${data.profile.dob} | <b>⚧️</b> ${data.profile.gender} | <b>🏙</b> ${data.profile.city}`;
      html += '</div>';
      
      if(data.gift_card){
        html += '<div style="text-align:center;margin:15px 0"><span style="font-size:48px">🎁</span></div>';
        html += '<div class="gift-card"><b>🎉 GIFT CARD FOUND!</b><br><br>'+data.gift_card+'</div>';
      } else {
        html += '<div style="background:#e8f5e9;border-radius:12px;padding:16px;margin:15px 0;color:#2e7d32;text-align:center">✅ Workflow completed! No gift card found right now. Check the Crownit app later.</div>';
      }
      
      document.getElementById('resultBox').innerHTML = html;
      show('step5');
    } else {
      addLog('❌ Failed: '+data.error);
      document.getElementById('resultBox').innerHTML = `
        <div style="text-align:center;margin:10px 0"><span style="font-size:48px">❌</span></div>
        <div class="error">${data.error || 'Unknown error'}</div>
      `;
      show('step5');
    }
  });
}

function reset(){
  currentData = {};
  document.getElementById('phone').value='';
  document.getElementById('otp').value='';
  document.getElementById('logs').innerHTML='';
  document.getElementById('logs').style.display='none';
  show('step1');
}
</script>
</body>
</html>"""

# ── HTTP Server ──
sessions = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length',0))
        body = self.rfile.read(length).decode() if length else '{}'
        data = json.loads(body) if body else {}
        
        if self.path == '/init':
            phone = data.get('phone','')
            profile = random_person()
            sessions[phone] = {'profile': profile}
            self._json({'status':'ok','profile':profile})
        
        elif self.path == '/send-otp':
            phone = data.get('phone','')
            try:
                api = CrownitAPI(phone)
                if phone in sessions and sessions[phone].get('profile'):
                    api.profile = sessions[phone]['profile']
                ok = api.send_otp()
                if ok:
                    sessions[phone] = sessions.get(phone,{})
                    sessions[phone]['api'] = api
                    self._json({'status':'ok'})
                else:
                    self._json({'status':'error','error':'Failed to send OTP'})
            except Exception as e:
                self._json({'status':'error','error':str(e)})
        
        elif self.path == '/run':
            phone = data.get('phone','')
            otp = data.get('otp','')
            profile = data.get('profile')
            try:
                api = sessions.get(phone,{}).get('api')
                if not api:
                    api = CrownitAPI(phone)
                if profile:
                    api.profile = profile
                result = api.run(otp)
                self._json(result)
            except Exception as e:
                self._json({'status':'error','error':str(e),'logs':[]})
        
        else:
            self._json({'error':'not found'}, 404)
    
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

def main():
    port = int(os.environ.get('PORT', 7860))
    server = HTTPServer(('0.0.0.0', port), Handler)
    logger.info(f"Server running on http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == '__main__':
    main()
