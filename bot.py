from __future__ import annotations
import argparse,json,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from pypdf import PdfReader
from playwright.sync_api import sync_playwright,expect,TimeoutError as PlaywrightTimeout
from fake_portal import start,SCENARIOS

class VerificationError(RuntimeError):pass

def verify_mail(message_request,expected_request,sent,login_started,tolerance=5):
    if message_request!=expected_request or sent<login_started-tolerance or sent>time.time()+tolerance:
        raise VerificationError('OTP does not belong to current request/time window')

def verify_download(path:Path,order:str,year:int,amount:str):
    if not path.read_bytes().startswith(b'%PDF-'):raise VerificationError('download is not a PDF')
    text='\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
    lines={line.strip() for line in text.splitlines()}
    expected={f'Order: {order}',f'Year: {year}',f'Amount: {Decimal(amount):.2f} USD'}
    if not expected.issubset(lines):raise VerificationError('PDF order/year/amount mismatch')
    return {'order':order,'year':year,'amount':amount,'verified':True}

def run_demo(scenario='success',out=Path('artifacts/run'),headed=False):
    out.mkdir(parents=True,exist_ok=True)
    # Remove stale prior success files: a failed rerun must not leave an apparently verified result.
    for name in ('notice.pdf','result.json','failure.json'):(out/name).unlink(missing_ok=True)
    server=start(scenario);base=f'http://127.0.0.1:{server.server_port}';steps=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=not headed,timeout=12000)
            context=browser.new_context(accept_downloads=True)
            context.tracing.start(screenshots=True,snapshots=True,sources=True)
            page=context.new_page();page.set_default_timeout(6000)
            try:
                page.goto(base,timeout=10000);began=time.time()
                page.get_by_test_id('email').fill('demo@example.test');page.get_by_test_id('password').fill('demo-pass');page.get_by_test_id('login').click()
                mail=page.get_by_test_id('mailbox-code');mail.wait_for()
                rid=parse_qs(urlparse(page.url).query)['request'][0]
                verify_mail(mail.get_attribute('data-request'),rid,float(mail.get_attribute('data-sent')),began)
                page.get_by_test_id('otp').fill(mail.inner_text());page.get_by_test_id('verify').click()
                page.get_by_test_id('product').select_option('DEMO-SAVE');steps.append('logged_in_and_selected_stable_product')
                page.get_by_test_id('query').click()
                expect(page.get_by_test_id('status')).to_have_text(__import__('re').compile('Loaded|No results'))
                year=datetime.now(timezone.utc).year
                row=page.locator(f'[data-testid="notice"][data-year="{year}"][data-order="ORDER-DEMO-001"]')
                if row.count()!=1:raise VerificationError('exactly one current-year notice required; refuse old or empty results')
                steps.append('selected_current_year_instead_of_first_row')
                downloaded=None
                for attempt in range(1,3):
                    try:
                        with page.expect_download(timeout=1600) as pending:row.get_by_role('button',name='Download').click()
                        downloaded=pending.value;downloaded.save_as(out/'unverified.pdf');steps.append(f'download_attempt_{attempt}');break
                    except PlaywrightTimeout:
                        steps.append(f'download_attempt_{attempt}_timed_out')
                if downloaded is None:raise VerificationError('download failed after 2 attempts')
                result=verify_download(out/'unverified.pdf','ORDER-DEMO-001',year,'1000.00')
                (out/'unverified.pdf').replace(out/'notice.pdf')
                result.update({'scenario':scenario,'steps':steps,'downloadAttempts':server.download_attempts})
                (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                page.screenshot(path=str(out/'success.png'),full_page=True)
                return result
            except Exception as exc:
                (out/'unverified.pdf').unlink(missing_ok=True)
                (out/'failure.json').write_text(json.dumps({'scenario':scenario,'error':str(exc),'steps':steps},indent=2),encoding='utf-8')
                page.screenshot(path=str(out/'failure.png'),full_page=True)
                raise
            finally:
                context.tracing.stop(path=str(out/'trace.zip'));browser.close()
    finally:server.shutdown();server.server_close()

def main():
    p=argparse.ArgumentParser(description='Self-contained browser workflow and PDF verification demo')
    p.add_argument('--scenario',choices=SCENARIOS,default='success');p.add_argument('--out',type=Path,default=Path('artifacts/run'));p.add_argument('--headed',action='store_true');args=p.parse_args()
    try:print(json.dumps(run_demo(args.scenario,args.out,args.headed),indent=2));return 0
    except Exception as exc:print('FAILED:',exc);return 2
if __name__=='__main__':raise SystemExit(main())
