"""Dispatch real portal handlers without a socket; covers business responses offline."""
import io,json,secrets,threading,time,unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode,parse_qs,urlparse
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fake_portal import Handler,SCENARIOS
from bot import verify_download,VerificationError

class Harness:
 def __init__(self,scenario='success'):
  self.server=SimpleNamespace(scenario=scenario,requests={},sessions=set(),download_attempts=0,lock=threading.Lock())
 def request(self,method,path,params=None,cookie=None):
  h=Handler.__new__(Handler);h.server=self.server;h.path=path;h.headers=Message()
  if cookie:h.headers['Cookie']=cookie
  body=urlencode(params or {}).encode();h.headers['Content-Length']=str(len(body));h.rfile=io.BytesIO(body)
  captured={}
  def send(code,content,ctype='text/html; charset=utf-8',headers=None):captured.update(code=code,content=content,ctype=ctype,headers=headers or {})
  h.send=send
  (h.do_POST if method=='POST' else h.do_GET)()
  return captured
 def login(self):
  r=self.request('POST','/login',{'email':'demo@example.test','password':'demo-pass'})
  rid=parse_qs(urlparse(r['headers']['Location']).query)['request'][0]
  r=self.request('POST','/verify',{'request':rid,'code':'384620'})
  return r['headers']['Set-Cookie'].split(';')[0]

class PortalTests(unittest.TestCase):
 def test_auth_and_one_time_code(self):
  h=Harness();self.assertEqual(401,h.request('GET','/portal')['code'])
  self.assertEqual(403,h.request('POST','/login',{'email':'bad'})['code'])
  cookie=h.login();self.assertEqual(200,h.request('GET','/portal',cookie=cookie)['code'])
  self.assertEqual(403,h.request('POST','/verify',{'request':'already-used','code':'384620'})['code'])
 def test_all_scenarios_have_expected_business_responses(self):
  from datetime import datetime,timezone
  year=datetime.now(timezone.utc).year
  for scenario in SCENARIOS:
   with self.subTest(scenario=scenario):
    h=Harness(scenario);cookie=h.login();r=h.request('GET','/notices',cookie=cookie);rows=json.loads(r['content'])
    if scenario=='empty':self.assertEqual([],rows);continue
    if scenario=='stale-only':self.assertTrue(all(x['year']!=year for x in rows));continue
    self.assertEqual(year-1,rows[0]['year']);self.assertEqual(year,rows[1]['year'])
    download=h.request('GET',f'/download?year={year}',cookie=cookie)
    if scenario=='download-once':
     self.assertEqual(503,download['code']);download=h.request('GET',f'/download?year={year}',cookie=cookie)
    self.assertEqual(200,download['code'])
    with TemporaryDirectory() as tmp:
     path=Path(tmp)/'notice.pdf';path.write_bytes(download['content'])
     if scenario in ('wrong-order','wrong-amount'):
      with self.assertRaises(VerificationError):verify_download(path,'ORDER-DEMO-001',year,'1000.00')
     else:self.assertTrue(verify_download(path,'ORDER-DEMO-001',year,'1000.00')['verified'])
if __name__=='__main__':unittest.main()
