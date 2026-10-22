import io,time,unittest,os
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bot import run_demo,verify_download,verify_mail,VerificationError
from fake_portal import pdf_bytes

class AutomationTests(unittest.TestCase):
 def test_mail_request_and_five_second_tolerance(self):
  now=time.time();verify_mail('r','r',now-3,now)
  with self.assertRaises(VerificationError):verify_mail('old','r',now,now)
  with self.assertRaises(VerificationError):verify_mail('r','r',now-30,now)
 def test_pdf_exact_metadata(self):
  with TemporaryDirectory() as tmp:
   p=Path(tmp)/'file.pdf';p.write_bytes(pdf_bytes('ORDER',2026,'1000.00'))
   self.assertTrue(verify_download(p,'ORDER',2026,'1000.00')['verified'])
   with self.assertRaises(VerificationError):verify_download(p,'OTHER',2026,'1000.00')
 @unittest.skipIf(os.environ.get("SKIP_BROWSER_E2E")=="1","browser end-to-end explicitly disabled")
 def test_browser_success_delayed_and_retry(self):
  for scenario in ('success','delayed','download-once'):
   with self.subTest(scenario=scenario),TemporaryDirectory() as tmp:
    result=run_demo(scenario,Path(tmp));self.assertTrue(result['verified'])
    self.assertEqual(2 if scenario=='download-once' else 1,result['downloadAttempts'], result)
 @unittest.skipIf(os.environ.get("SKIP_BROWSER_E2E")=="1","browser end-to-end explicitly disabled")
 def test_browser_refuses_empty_stale_wrong_amount_and_wrong_order(self):
  for scenario in ('empty','stale-only','wrong-amount','wrong-order'):
   with self.subTest(scenario=scenario),TemporaryDirectory() as tmp:
    with self.assertRaises(VerificationError):run_demo(scenario,Path(tmp))
    self.assertFalse((Path(tmp)/'notice.pdf').exists());self.assertTrue((Path(tmp)/'failure.json').exists())
if __name__=='__main__':unittest.main()
