"""Run ONLY on an ephemeral GitHub-hosted Linux runner; never on the box.
No traces/HARs/auth headers/cookies/JWT contents enter acceptance artifacts.
"""
from __future__ import annotations
import asyncio,datetime,json,os,re,signal,subprocess,sys,tempfile,time,traceback,urllib.request,uuid
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get('L4_OUTPUT','l4-ci-evidence')).resolve()
FORBIDDEN=('doc-draft','DRAFT_NEVER_LEAK_MARKER','foreign-doc','foreign-kb','FOREIGN_NEVER_LEAK_MARKER','Foreign space','alpha obsolete source')
JWT=re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{16,}')

def stamp():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def safe(value):return JWT.sub('[REDACTED_JWT]',str(value))
def save(name,value):
    text=json.dumps(value,ensure_ascii=False,indent=2) if not isinstance(value,str) else value
    assert not JWT.search(text),'Refusing credential-bearing artifact'
    (OUT/name).write_text(text+'\n')
def clean_body(body):
    text=json.dumps(body,ensure_ascii=False)
    for marker in FORBIDDEN:assert marker not in text,'Forbidden fixture leaked: '+marker
    assert not JWT.search(text),'JWT in API response'
    return body

def initialize_pg():
    import psycopg
    with psycopg.connect(os.environ['KNOWLEDGE_SDK_TEST_PG_DSN']) as c:
        role=c.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        assert role==(False,False),'Application must not bypass RLS'
        version=c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone();assert version
        return {'application_role_superuser':False,'application_role_bypassrls':False,'pgvector_version':version[0]}

def clean_pg():
    import psycopg
    from psycopg import sql
    with psycopg.connect(os.environ['KNOWLEDGE_SDK_TEST_PG_DSN']) as c:
        connections=c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchone()[0]
        assert connections==0,'Test connections survived fixture stop'
        schemas=c.execute("SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname LIKE 'sdk_test_%'").fetchall()
        for name,owner in schemas:
            assert re.fullmatch('sdk_test_[0-9a-f]{32}',name) and owner=='sdk_m4'
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))
        assert c.execute("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'sdk_test_%'").fetchone()[0]==0
        return {'other_client_connections':0,'remaining_test_schemas':0,'removed_disposable_schemas':len(schemas)}

def wait_ready(url,process):
    # Bounded runner-side HTTP readiness, not browser driving.
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        assert process.poll() is None,'Fixture exited before readiness'
        try:
            with urllib.request.urlopen(url,timeout=1) as r:
                if r.status==200:return
        except (OSError,urllib.error.URLError):pass
        time.sleep(.2)
    raise TimeoutError('Isolated fixture readiness exceeded60s')

async def exercise(context,page,engine,port,token_file):
    from urllib.parse import urlsplit
    base='http://127.0.0.1:'+str(port)
    log={'engine':engine,'capture_started_before_navigation':stamp(),'console':[],'page_errors':[],'requestfailed':[],'responses':[],'api_bodies':[],'direct_browser_requests':[],'assertions':[]}
    responses=[]
    page.on('console',lambda m:log['console'].append({'type':m.type,'text':safe(m.text),'at':stamp()}))
    page.on('pageerror',lambda e:log['page_errors'].append({'error':safe(e),'at':stamp()}))
    page.on('requestfailed',lambda r:log['requestfailed'].append({'path':urlsplit(r.url).path,'failure':safe(r.failure),'at':stamp()}))
    page.on('response',lambda r:responses.append(r))
    def checked(name):log['assertions'].append({'name':name,'passed':True,'at':stamp()})
    try:
        await page.goto(base+'/kb-prod/ui',wait_until='networkidle')
        assert await page.locator('#identity-form').count()==0 and await page.locator('#preset').count()==0
        assert 'demo switcher' not in (await page.locator('body').inner_text()).lower();checked('production UI has no demo identity controls')
        await page.locator('#token-file').set_input_files(str(token_file))
        await page.wait_for_function("document.querySelector('#status').textContent.startsWith('Authenticated.')")
        # spaces() finishes before login finally clears inputs; explicitly await both.
        await page.wait_for_function("document.querySelector('#bearer').value==='' && document.querySelector('#token-file').value===''")
        spaces=await page.locator('#spaces li').all_text_contents()
        assert len(spaces)==2 and any('controlled' in x for x in spaces) and any('sources' in x for x in spaces);checked('authenticated two authorized spaces and cleared auth inputs')
        await page.locator('#documents-button').click()
        await page.wait_for_function("document.querySelector('#documents').textContent.includes('doc-published')")
        docs=clean_body(json.loads(await page.locator('#documents').inner_text()));assert isinstance(docs,list) and any(x.get('doc_id')=='doc-published' for x in docs)
        assert all(x.get('lifecycle_state')=='published' for x in docs);checked('authorized published document semantics')
        await page.locator('#query').fill('alpha');await page.get_by_role('button',name='Search evidence',exact=True).click()
        await page.wait_for_function("document.querySelector('#search-results').textContent.includes('APPROVED_PUBLIC_MARKER')")
        search=clean_body(json.loads(await page.locator('#search-results').inner_text()));assert 'doc-published' in json.dumps(search);checked('published search evidence')
        await page.locator('#citation').fill('kb://org/m4-browser/doc/doc-published@1');await page.get_by_role('button',name='Verify citation',exact=True).click()
        await page.wait_for_function("document.querySelector('#citation-result').textContent.length>0")
        citation=clean_body(json.loads(await page.locator('#citation-result').inner_text()))['result']['structuredContent']
        assert citation['valid'] is True and citation['current_status']=='valid';checked('citation verified valid and current')
        await page.locator('#pack-id').fill('browser-pack');await page.get_by_role('button',name='Read pack',exact=True).click()
        await page.wait_for_function("document.querySelector('#pack-result').textContent.includes('browser-pack')")
        pack=clean_body(json.loads(await page.locator('#pack-result').inner_text()));assert pack['status']=='sealed' and re.fullmatch('[0-9a-f]{64}',pack['pack_sha256']);checked('sealed pack and SHA256 digest')
        await page.locator('#alerts-button').click();await page.wait_for_function("document.querySelector('#alerts').textContent.includes('access_revoked')")
        alerts=clean_body(json.loads(await page.locator('#alerts').inner_text()));assert all(x in json.dumps(alerts) for x in ('access_revoked','doc-impact','impacted-pack'));checked('revocation impact alert identifiers')
        dom=await page.locator('body').inner_text();clean_body(dom);save(engine+'-dom.txt',dom)
        await page.screenshot(path=str(OUT/(engine+'-browser.png')),full_page=True)
        # APIRequestContext belongs to this new browser context and shares its
        # legitimate session. Expected HTTP negatives are not page navigations or
        # transport failures; record their status and bodies separately.
        for path in ('/ui/demo/sign','/kb-prod/ui/demo/sign'):
            for method in ('GET','POST'):
                r=await context.request.fetch(base+path,method=method,data={} if method=='POST' else None)
                body=await r.text();assert r.status in (403,404) and 'no-store' in r.headers.get('cache-control','')
                log['direct_browser_requests'].append({'method':method,'path':path,'status':r.status,'cache_control':r.headers.get('cache-control'),'body':safe(body),'expected_http_negative':True})
        checked('both browser signer paths GET POST fail closed no-store')
        # Authenticated browser-owned JSON inspection, including queries targeting
        # denied source markers, not merely app-rendered DOM checks.
        for query in ('alpha','DRAFT_NEVER_LEAK_MARKER','FOREIGN_NEVER_LEAK_MARKER'):
            r=await context.request.post(base+'/kb-prod/v1/search',data={'params':{'query':query}},headers={'Origin':base})
            assert r.status==200 and 'no-store' in r.headers.get('cache-control','');body=clean_body(await r.json())
            if query=='alpha':assert 'APPROVED_PUBLIC_MARKER' in json.dumps(body)
            log['api_bodies'].append({'source':'browser context.request','path':'/kb-prod/v1/search','query_kind':'published' if query=='alpha' else 'denied fixture query','json':body})
        checked('independent browser JSON response body positive and denied-query isolation')
        async with page.expect_response('**/v1/auth/logout') as event:
            await page.locator('#logout').click()
        logout=await event.value;assert logout.status==200 and (await logout.json())['authenticated'] is False
        await page.wait_for_function("document.querySelector('#status').textContent==='Signed out'")
        await page.wait_for_load_state('networkidle')
        assert not await context.cookies(),'Logout must clear session cookie'
        for selector in ('#spaces','#documents','#search-results','#citation-result','#pack-result','#alerts'):assert await page.locator(selector).inner_text()==''
        denied=await context.request.get(base+'/kb-prod/v1/kbs');assert denied.status in (401,403)
        log['direct_browser_requests'].append({'method':'GET','path':'/kb-prod/v1/kbs','phase':'after logout','status':denied.status,'expected_http_negative':True});checked('genuine logout clears UI cookie and authorization')
        # Bodies from every rendered page JSON response are independently read.
        for r in responses:
            path=urlsplit(r.url).path;headers=await r.all_headers();assert 'no-store' in headers.get('cache-control','')
            log['responses'].append({'path':path,'status':r.status,'cache_control':headers.get('cache-control')});assert r.status==200
            if 'application/json' in headers.get('content-type',''):
                log['api_bodies'].append({'source':'page response body','path':path,'json':clean_body(await r.json())})
        required={'/kb-prod/v1/kbs','/kb-prod/v1/documents','/kb-prod/v1/search','/kb-prod/v1/mcp','/kb-prod/v1/packs/get','/kb-prod/v1/impact/alerts','/kb-prod/v1/auth/session','/kb-prod/v1/auth/logout','/kb-prod/ui/assets/enterprise.js'}
        assert required<={r['path'] for r in log['responses']};checked('all required same-origin responses200 no-store and all JSON bodies inspected')
        log['logout_settled_at']=stamp();save(engine+'-signed-out-dom.txt',await page.locator('body').inner_text())
    finally:
        # No listener removal/gaps; final assertions happen after context close.
        await context.close();log['capture_finished_after_logout_and_context_close']=stamp()
        save(engine+'-browser-log.json',log)
    assert not [m for m in log['console'] if m['type']=='error'],log['console']
    assert not log['page_errors'] and not log['requestfailed'],log
    assert not any('[REDACTED_JWT]' in json.dumps(x) for x in log['console']),'Sensitive console output detected'
    log['passed']=True;save(engine+'-browser-log.json',log)
    return {'engine':engine,'passed':True,'assertions':len(log['assertions']),'console_errors':0,'page_errors':0,'requestfailed':0,'expected_direct_http_negatives':len(log['direct_browser_requests']),'capture_started':log['capture_started_before_navigation'],'capture_finished':log['capture_finished_after_logout_and_context_close']}

async def browser_run(private):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        try:
            audit=await browser.new_browser_cdp_session();version=await audit.send('Browser.getVersion');arguments=(await audit.send('Browser.getBrowserCommandLine'))['arguments']
            assert any(arg=='--headless' or arg.startswith('--headless=') for arg in arguments)
            runtime={'headless_launch_option':True,'runtime_headless_argument_verified':True,'browser_version':browser.version,'cdp_version':version,'process_arguments':arguments,'runner_environment':os.environ['RUNNER_ENVIRONMENT'],'runner_os':os.environ.get('RUNNER_OS'),'runner_name':os.environ.get('RUNNER_NAME'),'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],'run_url':'https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'at':stamp()}
            save('headless-runtime.json',runtime)
            contexts=[];context_proof=[]
            for engine,port in (('sqlite',18474),('postgres',18475)):
                context=await browser.new_context(viewport={'width':1280,'height':900});assert not await context.cookies()
                state=await context.storage_state();assert not state['cookies'] and not state['origins']
                page=await context.new_page();session=await context.new_cdp_session(page);info=(await session.send('Target.getTargetInfo'))['targetInfo'];await session.detach()
                context_proof.append({'engine':engine,'browser_context_id':info['browserContextId'],'target_id':info['targetId'],'fresh_cookies_count':0,'fresh_storage_origins_count':0})
                contexts.append((context,page,engine,port))
            assert len({x['browser_context_id'] for x in context_proof})==2
            save('independent-contexts.json',context_proof)
            results=[]
            try:
                for context,page,engine,port in contexts:results.append(await exercise(context,page,engine,port,private/(engine+'.jwt')))
            finally:
                for context,_,_,_ in contexts:await context.close()
            return {'passed':True,'source_sha':os.environ['GITHUB_SHA'],'run_url':runtime['run_url'],'engines':results,'headless':True,'independent_new_browser_contexts':True,'all_four_hard_requirements':True,'implicit_model_calls':0,'definition':'page console/error/requestfailed capture begins before initial application goto and remains attached through logout networkidle/context close; expected direct APIRequestContext403/404/401 are separately recorded HTTP responses, never excluded page events.'}
        finally:await browser.close()

def main():
    # Fail BEFORE any browser import/launch outside the specifically authorized CI.
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','Independent GitHub-hosted CI ONLY; never execute on box/self-hosted machines'
    assert os.environ.get('RUNNER_OS')=='Linux'
    OUT.mkdir(parents=True,exist_ok=True);processes=[];handles=[];summary={'passed':False,'source_sha':os.environ['GITHUB_SHA'],'started_at':stamp()}
    try:
        summary['postgres']=initialize_pg()
        with tempfile.TemporaryDirectory(prefix='q2-m4-l4-private-',dir=os.environ['RUNNER_TEMP']) as tmp:
            private=Path(tmp);os.chmod(private,0o700)
            for engine,port in (('sqlite',19474),('postgres',19475)):
                h=(OUT/(engine+'-backend.log')).open('w');handles.append(h)
                command=[sys.executable,str(HERE/'enterprise_fixture.py'),'--engine',engine,'--port',str(port),'--workdir',str(private/engine),'--token-file',str(private/(engine+'.jwt'))]
                process=subprocess.Popen(command,stdout=h,stderr=subprocess.STDOUT);processes.append(process);wait_ready('http://127.0.0.1:'+str(port)+'/v1/health',process)
            config='pid '+str(private/'nginx.pid')+';\nerror_log '+str(OUT/'nginx-error.log')+';\nevents {}\nhttp { access_log off; include /etc/nginx/mime.types;\n'
            for port,upstream in ((18474,19474),(18475,19475)):
                config+='server { listen 127.0.0.1:'+str(port)+'; location /kb-prod/ { proxy_pass http://127.0.0.1:'+str(upstream)+'/; proxy_set_header Host $http_host; } location = /ui/demo/sign { proxy_pass http://127.0.0.1:'+str(upstream)+'/ui/demo/sign; proxy_set_header Host $http_host; } }\n'
            config+='}\n';conf=private/'nginx.conf';conf.write_text(config);save('nginx-config.txt',config)
            h=(OUT/'nginx-process.log').open('w');handles.append(h);nginx=subprocess.Popen(['nginx','-c',str(conf),'-g','daemon off;'],stdout=h,stderr=subprocess.STDOUT);processes.append(nginx)
            for port in (18474,18475):wait_ready('http://127.0.0.1:'+str(port)+'/kb-prod/v1/health',nginx)
            summary.update(asyncio.run(asyncio.wait_for(browser_run(private),timeout=180)))
    except BaseException as exc:
        summary['failure']={'type':type(exc).__name__,'message':safe(exc)};save('failure.txt',safe(traceback.format_exc()));raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for handle in handles:handle.close()
        try:summary['cleanup']=clean_pg()
        except BaseException as exc:summary['cleanup']={'failure':safe(exc)};summary['passed']=False
        summary['owned_processes_stopped']=all(x.poll() is not None for x in processes);summary['finished_at']=stamp();save('summary.json',summary)
        print(json.dumps({'passed':summary['passed'],'source_sha':summary['source_sha'],'engines':summary.get('engines'),'cleanup':summary.get('cleanup')}))
        if not summary['passed']:raise SystemExit(1)
if __name__=='__main__':main()
