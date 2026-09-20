"""MAAN v6: branded local chat with automatic live lookups."""
import getpass, json, os, re, secrets, sqlite3, sys, threading, time
from collections import deque
from datetime import timedelta
from urllib.parse import urlsplit
from pathlib import Path
import requests
from live_tools import route, lookup
from vision_tools import VISION_MODEL, LANGUAGES, MODES, IMAGE_MODES, MAX_IMAGE_CHARS, normalize_image, task_payload
from remote_stream import stream_remote
from flask import Flask, Response, jsonify, render_template, request, session
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('MAAN_DATA', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
KEY = DATA / 'secret.key'
if not KEY.exists():
    KEY.write_text(secrets.token_hex(32))
PUBLIC_ORIGIN = os.environ.get('MAAN_PUBLIC_ORIGIN','').rstrip('/')
PUBLIC = '--public' in sys.argv
if PUBLIC:
    parsed = urlsplit(PUBLIC_ORIGIN)
    if parsed.scheme != 'https' or not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', parsed.netloc) or parsed.path:
        raise SystemExit('Start public mode using START_ONLINE.bat.')
app = Flask(__name__)
app.config.update(SECRET_KEY=KEY.read_text(), MAX_CONTENT_LENGTH=4*1024*1024+16000,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                  SESSION_COOKIE_SECURE=PUBLIC, SESSION_COOKIE_NAME='maan_v2',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                  SESSION_REFRESH_EACH_REQUEST=False)
MODEL = 'qwen3:1.7b'
OLLAMA = 'http://127.0.0.1:11434'
queue = deque()
condition = threading.Condition()
busy_users = set()
DUMMY_HASH = generate_password_hash(secrets.token_hex(32))

def db():
    c = sqlite3.connect(DATA / 'chats.sqlite3', timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,user TEXT NOT NULL,title TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,chat TEXT REFERENCES chats(id) ON DELETE CASCADE,role TEXT,content TEXT);
        CREATE TABLE IF NOT EXISTS login_attempts(name TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS usage(user TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS login_time ON login_attempts(created);
        CREATE INDEX IF NOT EXISTS usage_time ON usage(created);
        ''')
        columns = {row[1] for row in c.execute('PRAGMA table_info(users)')}
        if 'version' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
        if 'enabled' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1')
init()

@app.before_request
def protect():
    if PUBLIC and request.host not in (urlsplit(PUBLIC_ORIGIN).netloc, '127.0.0.1:8080', 'localhost:8080'):
        return jsonify(error='Host rejected.'), 400
    if request.method == 'POST':
        if request.path != '/api/chat' and (request.content_length or 0)>16000:
            return jsonify(error='Request is too large.'),413
        if request.headers.get('X-MAAN') != '1':
            return jsonify(error='Request rejected. Reload the page.'), 403
        origin = request.headers.get('Origin')
        expected = PUBLIC_ORIGIN if PUBLIC else request.host_url.rstrip('/')
        if (PUBLIC and origin != expected) or (origin and origin != expected):
            return jsonify(error='Origin rejected. Open MAAN using its HTTPS link.'), 403
        if not isinstance(request.get_json(silent=True), dict):
            return jsonify(error='Expected a JSON object.'), 400
    if session.get('user'):
        with db() as c:
            row=c.execute('SELECT version,enabled FROM users WHERE name=?',(session['user'],)).fetchone()
        if not row or not row['enabled'] or row['version'] != session.get('version'):
            session.clear()
    if request.path.startswith('/api/') and request.path not in ('/api/login','/api/me','/api/health'):
        if not session.get('user'):
            return jsonify(error='Please sign in.'), 401

@app.after_request
def headers(r):
    r.headers['Cache-Control'] = 'no-store'
    r.headers['Referrer-Policy'] = 'no-referrer'
    r.headers['X-Robots-Tag'] = 'noindex, nofollow'
    if PUBLIC:
        r.headers['Strict-Transport-Security'] = 'max-age=86400'
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return r

@app.get('/api/health')
def health():
    return jsonify(version=6, public=PUBLIC)

@app.errorhandler(413)
def too_large(e):
    return jsonify(error='Request is too large.'),413

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/api/me')
def me():
    return jsonify(user=session.get('user'))

@app.post('/api/login')
def login():
    body = request.get_json(silent=True) or {}
    name, password = str(body.get('name','')).lower().strip(), str(body.get('password',''))
    if not re.fullmatch(r'[a-z0-9_]{2,24}',name) or len(password)>256:
        return jsonify(error='Incorrect username or password.'), 401
    now=time.time()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM login_attempts WHERE created<?',(now-900,))
        total=c.execute('SELECT COUNT(*) FROM login_attempts WHERE created>?',(now-60,)).fetchone()[0]
        own=c.execute('SELECT COUNT(*) FROM login_attempts WHERE name=?',(name,)).fetchone()[0]
        if total>=30 or own>=8:
            return jsonify(error='Too many sign-in attempts. Wait 15 minutes before retrying.'),429
        c.execute('INSERT INTO login_attempts VALUES(?,?)',(name,now))
        row=c.execute('SELECT password,version,enabled FROM users WHERE name=?',(name,)).fetchone()
    valid=check_password_hash(row['password'] if row else DUMMY_HASH,password)
    if not valid or not row or not row['enabled']:
        return jsonify(error='Incorrect username or password.'),401
    session.clear()
    session.permanent=True
    session['user']=name
    session['version']=row['version']
    return jsonify(user=name)

@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get('/api/status')
def status():
    try:
        r = requests.get(OLLAMA+'/api/tags', timeout=3)
        r.raise_for_status()
        ready = any(m.get('name') == MODEL for m in r.json().get('models',[]))
        return jsonify(ready=ready, vision_ready=any(m.get('name')==VISION_MODEL for m in r.json().get('models',[])), message='Ready to chat' if ready else 'Download qwen3:1.7b in Ollama first')
    except (requests.RequestException, ValueError):
        return jsonify(ready=False,message='Open Ollama on the laptop')

@app.get('/api/chats')
def chats():
    with db() as c:
        rows = c.execute('SELECT id,title FROM chats WHERE user=? ORDER BY created DESC',(session['user'],)).fetchall()
    return jsonify(chats=[dict(r) for r in rows])

@app.get('/api/chats/<cid>')
def history(cid):
    with db() as c:
        if not c.execute('SELECT 1 FROM chats WHERE id=? AND user=?',(cid,session['user'])).fetchone():
            return jsonify(error='Chat not found'),404
        rows=c.execute('SELECT role,content FROM messages WHERE chat=? ORDER BY id',(cid,)).fetchall()
    return jsonify(messages=[dict(r) for r in rows])

@app.post('/api/chat')
def chat():
    body=request.get_json(silent=True) or {}
    prompt=body.get('message','')
    mode=body.get('mode','auto')
    if not isinstance(mode,str) or mode not in ('auto','chat','weather','web')+MODES:
        return jsonify(error='Invalid mode'),400
    image_data=body.get('image')
    target=body.get('target','English')
    if target not in LANGUAGES:
        return jsonify(error='Choose a supported target language.'),400
    if image_data is not None and (not isinstance(image_data,str) or not image_data or len(image_data)>MAX_IMAGE_CHARS):
        return jsonify(error='Invalid image or image too large.'),400
    if mode in IMAGE_MODES and not image_data:
        return jsonify(error='Attach a photo first.'),400
    if image_data and mode not in IMAGE_MODES+('auto',):
        return jsonify(error='Choose Ask image, Read image text, Translate image or Camera search.'),400
    if image_data and mode=='auto':mode='vision'
    cid=body.get('chat_id')
    user=session['user']
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:
        return jsonify(error='Enter a message of 1–2,000 characters.'),400
    if cid is not None and not isinstance(cid,str):
        return jsonify(error='Invalid chat'),400
    with db() as c:
        if cid and not c.execute('SELECT 1 FROM chats WHERE id=? AND user=?',(cid,user)).fetchone():
            return jsonify(error='Chat not found'),404
    worker_active=threading.Event()
    cleanup_requested=threading.Event()
    ticket=secrets.token_hex(16)
    with condition:
        if user in busy_users:
            return jsonify(error='Your previous response is still running.'),409
        if len(queue)>=4:
            return jsonify(error='Queue is full. Try again shortly.'),429
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            now=time.time()
            c.execute('DELETE FROM usage WHERE created<?',(now-3600,))
            count=c.execute('SELECT COUNT(*) FROM usage WHERE user=?',(user,)).fetchone()[0]
            if count>=60:
                return jsonify(error='Hourly limit reached (60 requests). Please try later.'),429
            c.execute('INSERT INTO usage VALUES(?,?)',(user,now))
        busy_users.add(user)
        queue.append(ticket)
    def event(**kwargs):
        return json.dumps(kwargs,ensure_ascii=False)+'\n'
    def release():
        cleanup_requested.set()
        maybe_release()
    def maybe_release():
        if worker_active.is_set() or not cleanup_requested.is_set():return
        with condition:
            if ticket in queue:
                queue.remove(ticket)
                busy_users.discard(user)
                condition.notify_all()
    def generate():
        nonlocal cid
        response=None
        try:
            start=time.monotonic()
            while True:
                with condition:
                    position=list(queue).index(ticket)
                if position==0: break
                if time.monotonic()-start > 300:
                    yield event(error='Queue timed out. Please try again.')
                    return
                yield event(status=f'Waiting for the laptop · {position} ahead')
                with condition: condition.wait(timeout=1)
            yield event(status='Preparing your reply…')
            with db() as c:
                if not cid:
                    cid=secrets.token_hex(16)
                    c.execute('INSERT INTO chats VALUES(?,?,?,?)',(cid,user,prompt.strip()[:48],time.time()))
                old=c.execute('SELECT role,content FROM messages WHERE chat=? ORDER BY id DESC LIMIT 6',(cid,)).fetchall()
            if mode in MODES:
                yield event(chat_id=cid, route={'translate':'Translation','vision':'Image question','ocr':'Read image text','image_translate':'Image translation','camera_search':'Camera search'}[mode],status='Checking local image / translation model…')
                normalized=normalize_image(image_data) if image_data else None
                tags=requests.get(OLLAMA+'/api/tags',timeout=5);tags.raise_for_status()
                if not any(m.get('name')==VISION_MODEL for m in tags.json().get('models',[])):
                    yield event(error='Image and translation setup is needed on the host laptop. Run SETUP_IMAGE_TRANSLATION.bat once, then retry.')
                    return
                # One model at a time on the 16 GB host. Normal chat reloads on demand.
                if any(m.get('name')==MODEL for m in tags.json().get('models',[])):
                    unloaded=requests.post(OLLAMA+'/api/generate',json={'model':MODEL,'keep_alive':0},timeout=15)
                    unloaded.raise_for_status()
                answer=''
                for packet in stream_remote(OLLAMA+'/api/chat',task_payload(mode,prompt,target,normalized),worker_active,maybe_release):
                    if packet.get('delta'):
                        answer+=packet['delta']
                        if mode!='camera_search':yield event(delta=packet['delta'])
                    elif packet.get('status'):yield event(status=packet['status'])
                if not answer.strip():raise ValueError('No text returned. Try a clearer photo or shorter text.')
                if mode=='camera_search':
                    search_query=' '.join(answer.split()).strip('"')[:200]
                    if 'NO_QUERY' in search_query or len(search_query)<3:
                        answer='I could not identify a clear object to search. Try a close-up of the object or type a search in Web search mode.'
                    else:
                        yield event(status='Searching the web using the image description…')
                        answer='Search description (AI estimate): '+search_query+'\n\n'+lookup('web',search_query)
                    yield event(delta=answer)
                saved_prompt=('['+mode.replace('_',' ').title()+(' → '+target if mode in ('translate','vision','image_translate') else '')+'] '+prompt)
                if normalized:saved_prompt+='\n[Photo used for this answer; photo not stored. Attach it again to ask another image question.]'
                with db() as c:
                    c.executemany('INSERT INTO messages(chat,role,content) VALUES(?,?,?)',[(cid,'user',saved_prompt),(cid,'assistant',answer)])
                yield event(done=True)
                return
            selected, query = route(prompt, mode, [dict(row) for row in reversed(old)])
            if selected in ('weather','web'):
                yield event(chat_id=cid, route='Weather' if selected=='weather' else 'Web search', status='Checking weather…' if selected=='weather' else 'Searching the web…')
                answer=lookup(selected, query)
                yield event(delta=answer)
                with db() as c:
                    c.executemany('INSERT INTO messages(chat,role,content) VALUES(?,?,?)',[(cid,'user',prompt),(cid,'assistant',answer)])
                yield event(done=True)
                return
            context=[]
            budget=4000
            for row in old:
                if len(row['content'])>budget: break
                context.insert(0,dict(row)); budget-=len(row['content'])
            payload={'model':MODEL,'think':False,'stream':True,'keep_alive':'15m',
                     'options':{'num_ctx':4096,'num_predict':384},
                     'messages':[{'role':'system','content':'You are MAAN, a helpful assistant. Reply concisely in the user\'s language. Be honest about uncertainty. Use Markdown for structure. Write inline maths with $...$ and display maths with $$...$$. For live facts ask the user to select Weather or Web search. Do not invent current facts. You cannot create images or perform external actions.'}]+context+[{'role':'user','content':prompt}]}
            yield event(chat_id=cid, route='Local chat')
            response=requests.post(OLLAMA+'/api/chat',json=payload,stream=True,timeout=(5,120))
            response.raise_for_status()
            answer=''; finished=False; began=time.monotonic()
            for line in response.iter_lines(chunk_size=1):
                if time.monotonic()-began>180:
                    raise TimeoutError('Response timeout')
                if not line: continue
                packet=json.loads(line)
                if packet.get('error'): raise ValueError('Model error')
                delta=packet.get('message',{}).get('content','')
                if delta:
                    answer+=delta
                    yield event(delta=delta)
                if packet.get('done'):
                    finished=True
                    break
            if not finished or not answer.strip():
                raise ValueError('Incomplete model response')
            with db() as c:
                c.executemany('INSERT INTO messages(chat,role,content) VALUES(?,?,?)',[(cid,'user',prompt),(cid,'assistant',answer)])
            yield event(done=True)
        except (requests.RequestException,ValueError,TimeoutError) as e:
            message=str(e) if isinstance(e,(ValueError,TimeoutError)) and mode in MODES else 'Reply failed. Check Ollama on the host laptop and retry.'
            yield event(error=message+' This turn was not saved.')
        finally:
            if response is not None: response.close()
            release()
    result=Response(generate(),mimetype='application/x-ndjson')
    result.call_on_close(release)
    return result

def add_user():
    name=input('Choose a username (letters, numbers, underscore): ').strip().lower()
    if not re.fullmatch(r'[a-z0-9_]{2,24}',name):
        print('Use 2–24 letters, numbers or underscores.'); return
    password=getpass.getpass('Choose a password (minimum 10 characters; typing is hidden): ')
    if len(password)<10 or len(password)>256 or password!=getpass.getpass('Repeat password: '):
        print('Passwords must match and contain at least 10 characters.'); return
    with db() as c:
        if c.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone():
            print('Username already exists.'); return
        c.execute('INSERT INTO users(name,password) VALUES(?,?)',(name,generate_password_hash(password)))
    print('Account created:',name)

def manage_user():
    with db() as c:
        for row in c.execute('SELECT name,enabled FROM users'):
            print(row['name'], '(enabled)' if row['enabled'] else '(disabled)')
    name=input('Username to manage: ').strip().lower()
    action=input('Type reset, disable, or enable: ').strip().lower()
    with db() as c:
        if not c.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone():
            print('Username not found.'); return
        if action=='reset':
            password=getpass.getpass('New password (10 or more characters): ')
            if len(password)<10 or len(password)>256 or password!=getpass.getpass('Repeat: '):
                print('Passwords must match and contain 10–256 characters.'); return
            c.execute('UPDATE users SET password=?,version=version+1 WHERE name=?',(generate_password_hash(password),name))
        elif action in ('disable','enable'):
            c.execute('UPDATE users SET enabled=?,version=version+1 WHERE name=?',(int(action=='enable'),name))
        else:
            print('Unknown action.'); return
    print('Updated. Existing logins for this account have been revoked.')

def ensure_user():
    with db() as c:
        exists=c.execute('SELECT 1 FROM users WHERE enabled=1').fetchone()
    if not exists:
        print('Create your first login.'); add_user()
        with db() as c:
            if not c.execute('SELECT 1 FROM users WHERE enabled=1').fetchone():
                raise SystemExit('No enabled account exists.')

if __name__=='__main__':
    if '--add-user' in sys.argv: add_user()
    elif '--manage-user' in sys.argv: manage_user()
    elif '--ensure-user' in sys.argv: ensure_user()
    else:
        from waitress import serve
        ensure_user()
        lan='--lan' in sys.argv and not PUBLIC
        if PUBLIC: print('MAAN HTTPS backend ready. Use the public link shown by the launcher.',flush=True)
        else: print('Open http://localhost:8080. Keep this window and Ollama running.',flush=True)
        serve(app,host='0.0.0.0' if lan else '127.0.0.1',port=8080,threads=8,
              connection_limit=50,channel_timeout=60,max_request_body_size=4*1024*1024+16000,
              max_request_header_size=8192)
