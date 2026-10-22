# Local fictional provider portal.
from __future__ import annotations
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse
from http.cookies import SimpleCookie
from pathlib import Path
import io,json,secrets,threading,time
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject

SCENARIOS=('success','delayed','empty','stale-only','download-once','wrong-amount','wrong-order')
def pdf_bytes(order,year,amount):
    writer=PdfWriter();page=writer.add_blank_page(width=595,height=842)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    lines=['SYNTHETIC PAYMENT NOTICE',f'Order: {order}',f'Year: {year}',f'Amount: {amount} USD','Local automation demo - no real policy.']
    content='BT /F1 16 Tf 50 770 Td 28 TL '+' T* '.join('('+line+') Tj' for line in lines)+' ET'
    stream=DecodedStreamObject();stream.set_data(content.encode('ascii'));page[NameObject('/Contents')]=writer._add_object(stream)
    out=io.BytesIO();writer.write(out);return out.getvalue()

STYLE='body{font:16px/1.6 system-ui;background:#eef2f6;color:#183046;margin:40px auto;max-width:980px;padding:20px}header{background:#142d45;color:white;padding:28px;border-radius:15px}section{background:white;padding:25px;margin-top:20px;border-radius:12px}input,select,button{font:inherit;padding:10px;margin:6px;border-radius:6px;border:1px solid #bdcbd5}button{background:#007f79;color:white;cursor:pointer}td,th{padding:15px;text-align:left;border-bottom:1px solid #ddd}table{width:100%}'
def shell(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+STYLE+'</style><header><small>PORTFOLIO / 04 · FICTIONAL PROVIDER</small><h1>'+title+'</h1></header><section>'+body+'</section></html>'

class Portal(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,scenario='success'):
        if scenario not in SCENARIOS:raise ValueError('unknown scenario')
        self.scenario=scenario;self.requests={};self.sessions=set();self.download_attempts=0;self.lock=threading.Lock()
        super().__init__(address,Handler)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,code,content,ctype='text/html; charset=utf-8',headers=None):
        content=content.encode('utf-8') if isinstance(content,str) else content
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(content)
    def auth(self):
        cookie=SimpleCookie(self.headers.get('Cookie',''));token=cookie.get('demo_session')
        return token is not None and token.value in self.server.sessions
    def redirect(self,url,headers=None):self.send(303,'',headers={'Location':url,**(headers or {})})
    def do_GET(self):
        url=urlparse(self.path);query=parse_qs(url.query)
        if url.path=='/':
            return self.send(200,shell('Provider portal','''<p>Local demo credentials: demo@example.test / demo-pass</p><form method="post" action="/login"><label>Email <input name="email" data-testid="email"></label><label>Password <input name="password" type="password" data-testid="password"></label><button data-testid="login">Sign in</button></form>'''))
        if url.path=='/verify':
            rid=query.get('request',[''])[0];record=self.server.requests.get(rid)
            if not record:return self.send(404,'request not found')
            # This is a synthetic mailbox, deliberately visible for a self-contained test.
            return self.send(200,shell('Synthetic mailbox',f'''<p>Only local test messages are shown.</p><div data-testid="mailbox-code" data-request="{rid}" data-sent="{record['mail_sent']}">{record['code']}</div><form method="post" action="/verify"><input type="hidden" name="request" value="{rid}"><label>Code <input name="code" data-testid="otp"></label><button data-testid="verify">Verify</button></form>'''))
        if not self.auth():return self.send(401,'login required')
        if url.path=='/portal':
            return self.send(200,shell('Payment notice download','''<p>Product labels may change. Automation uses stable semantic test ids.</p><label>Product <select data-testid="product"><option value="DEMO-SAVE">Future Savings 2026 (renamed)</option></select></label><button data-testid="query">Query notices</button><div data-testid="status">Ready</div><table><thead><tr><th>Order</th><th>Year</th><th>Amount</th><th>Download</th></tr></thead><tbody data-testid="rows"></tbody></table><p data-testid="download-error"></p><script>
const $=id=>document.querySelector('[data-testid="'+id+'"]');
$('query').onclick=async()=>{ $('status').textContent='Loading';$('rows').replaceChildren();const r=await fetch('/notices');const list=await r.json();for(const n of list){const row=document.createElement('tr');row.setAttribute('data-testid','notice');row.setAttribute('data-year',n.year);row.setAttribute('data-order',n.order);for(const v of [n.order,n.year,n.amount+' USD']){const td=document.createElement('td');td.textContent=v;row.append(td)}const td=document.createElement('td'),b=document.createElement('button');b.textContent='Download';b.onclick=async()=>{try{const r=await fetch('/download?year='+n.year);if(!r.ok)throw Error('Transient download failure');const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='notice-'+n.year+'.pdf';a.click();URL.revokeObjectURL(a.href);$('download-error').textContent=''}catch(e){$('download-error').textContent=e.message}};td.append(b);row.append(td);$('rows').append(row)}$('status').textContent=list.length?'Loaded':'No results'};
</script>'''))
        if url.path=='/notices':
            if self.server.scenario=='delayed':time.sleep(.6)
            year=datetime.now(timezone.utc).year
            rows=[{'order':'ORDER-DEMO-001','year':year-1,'amount':'900.00'}]
            if self.server.scenario!='stale-only':rows.append({'order':'ORDER-DEMO-001','year':year,'amount':'1000.00'})
            if self.server.scenario=='empty':rows=[]
            return self.send(200,json.dumps(rows),'application/json')
        if url.path=='/download':
            try:year=int(query['year'][0])
            except (KeyError,ValueError):return self.send(400,'year required')
            with self.server.lock:
                self.server.download_attempts+=1;attempt=self.server.download_attempts
            if self.server.scenario=='download-once' and attempt==1:return self.send(503,'synthetic failure')
            amount='777.00' if self.server.scenario=='wrong-amount' else '1000.00'
            order='WRONG-ORDER' if self.server.scenario=='wrong-order' else 'ORDER-DEMO-001'
            data=pdf_bytes(order,year,amount)
            return self.send(200,data,'application/pdf',{'Content-Disposition':'attachment; filename=notice.pdf'})
        self.send(404,'not found')
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>4096:return self.send(413,'payload too large')
        params=parse_qs(self.rfile.read(length).decode('utf-8'))
        get=lambda k:params.get(k,[''])[0]
        if self.path=='/login':
            if get('email')!='demo@example.test' or get('password')!='demo-pass':return self.send(403,'synthetic credentials required')
            rid=secrets.token_hex(16);now=time.time();self.server.requests[rid]={'code':'384620','issued':now,'mail_sent':now-3}
            return self.redirect('/verify?request='+rid)
        if self.path=='/verify':
            r=self.server.requests.pop(get('request'),None)
            if not r or r['code']!=get('code') or time.time()-r['issued']>120:return self.send(403,'invalid or expired code')
            token=secrets.token_hex(20);self.server.sessions.add(token)
            return self.redirect('/portal',{'Set-Cookie':f'demo_session={token}; HttpOnly; SameSite=Strict; Path=/'})
        self.send(404,'not found')

def start(scenario='success',port=0):
    server=Portal(('127.0.0.1',port),scenario)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start();return server
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8084);p.add_argument('--scenario',choices=SCENARIOS,default='success');args=p.parse_args()
    server=Portal(('127.0.0.1',args.port),args.scenario)
    print(f'Local fictional portal: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
