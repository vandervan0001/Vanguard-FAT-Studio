// Capture only a disposable, disconnected demo. The film renderer never controls a PLC.
import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

const studio=resolve(fileURLToPath(new URL('..',import.meta.url)));
const repo=resolve(studio,'../..');
const privateDir=join(repo,'.local/vanguard-motion-2026-11-03');
const out=join(studio,'assets/captures');
const origin='http://127.0.0.1:8774';
const manifest={status:'capturing',capture_mode:'demo',connected_plc:false,source_bundle:['index-CDBs7U1H.js','index-6ra9f6L1.css'],shots:{},transcript:null};
const observations=[];const errors=[];
await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1600,height:1100},deviceScaleFactor:1.5,acceptDownloads:true});
await page.route('**/*',route=>{const u=new URL(route.request().url());return u.origin===origin?route.continue():route.abort();});
page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',async d=>d.accept());
const read=async path=>{const r=await page.request.get(origin+'/api/'+path);if(!r.ok())throw Error('Read failed '+path+' '+r.status());return r.json();};
const state=()=>read('state');
async function waitState(test,why,timeout=15000){const end=Date.now()+timeout;while(Date.now()<end){const s=await state();if(test(s))return s;await page.waitForTimeout(120);}throw Error('State timeout: '+why);}
async function snap(id,locator,{fit='cover',height,focus}={}){
  await locator.scrollIntoViewIfNeeded();await page.waitForTimeout(40);
  const n=(manifest.shots[id]??=[]).length;
  const file=`${id}-${String(n).padStart(3,'0')}.png`;
  if(height){const b=await locator.boundingBox();if(!b)throw Error('Missing '+id);await page.screenshot({path:join(out,file),clip:{x:b.x,y:b.y,width:b.width,height:Math.min(height,b.height)},animations:'disabled'});}
  else await locator.screenshot({path:join(out,file),animations:'disabled'});
  const bytes=await readFile(join(out,file));manifest.shots[id].push({file,fit,focus,sha256:createHash('sha256').update(bytes).digest('hex')});
}
async function stopReset(){
  if((await state()).status!=='idle'){
    const b=page.getByRole('button',{name:'Arrêter l’essai',exact:true});if(await b.isEnabled())await b.click();
  }
  await page.getByRole('button',{name:'Réinitialiser le modèle',exact:true}).click();
  await waitState(s=>s.status==='idle','reset to idle');
}
async function pidTab(){await page.getByRole('button',{name:'P&ID',exact:true}).click();await page.locator('#active-scenario').waitFor();}
async function start(scenario=''){await page.locator('#active-scenario').selectOption(scenario);await page.getByRole('button',{name:'Démarrer',exact:true}).click();await waitState(s=>s.status==='running','start');}
try{
  await page.goto(origin);await page.getByLabel('Nom du projet',{exact:true}).waitFor();
  await Promise.all(['health','schema','catalog','project'].map(read));
  const project=await read('project');if(project.plc.mode!=='demo'||project.tags.length!==75)throw Error('Expected disconnected75-tag demo');
  if((await state()).status!=='idle')throw Error('Fresh demo must be idle');
  console.log('Capture P&ID: real demo UI');
  await page.getByRole('button',{name:'Mode présentation',exact:true}).click();
  await page.getByRole('button',{name:'Vue complète',exact:true}).click();await page.waitForTimeout(500);
  await page.getByRole('button',{name:'Zoom arrière',exact:true}).click();
  await snap('pid',page.locator('.canvas-area'));
  await start('demo-fill-source');
  for(let i=0;i<12;i++){await snap('pid',page.locator('.canvas-area'));await page.waitForTimeout(180);}
  await waitState(s=>s.scenario.state==='completed','P&ID demo scenario');
  await page.getByRole('button',{name:'Quitter la présentation',exact:true}).click();
  await stopReset();
  console.log('Capture BOOL pulse');
  await start();
  await page.getByLabel('Filtrer les entrées digitales').fill('p101_request');
  const digital=page.locator('aside.digital-inputs');
  await snap('bool',digital,{fit:'contain',height:420});
  await page.getByRole('button',{name:'Commutateur P101_Request',exact:true}).click();
  for(let i=0;i<7;i++){await snap('bool',digital,{fit:'contain',height:420});await page.waitForTimeout(90);}
  observations.push({phase:'bool',snapshot:await state()});
  console.log('Capture analog 12mA');
  await page.getByLabel('Filtrer les entrées analogiques').fill('lt101');
  const analog=page.locator('.analog-control[data-tag="lt101_raw"]');
  await analog.getByLabel('Unité de stimulus LT101_Raw').selectOption('mA');
  await analog.getByLabel('Forçage LT101_Raw').fill('12');
  await snap('analog',analog,{fit:'contain'});
  await analog.getByTitle('Forcer LT101_Raw',{exact:true}).click();
  const a=await waitState(s=>s.tags.lt101_raw.value===13824&&Math.abs(s.tags.lt101_percent.value-50)<.1,'12mA=13824=50%');
  observations.push({phase:'analog',raw:a.tags.lt101_raw.value,engineering:a.tags.lt101_percent.value,quality:a.tags.lt101_raw.quality});
  for(let i=0;i<8;i++){await snap('analog',analog,{fit:'contain'});await page.waitForTimeout(100);}
  await stopReset();
  await page.getByLabel('Filtrer les entrées digitales').fill('');await page.getByLabel('Filtrer les entrées analogiques').fill('');
  console.log('Capture timed scenario');
  await start('demo-fill-source');
  const timed=page.locator('.fat-run:not(.guided-run)');
  for(let i=0;i<15;i++){await snap('timed',timed,{fit:'cover',height:850});await page.waitForTimeout(210);}
  const t=await waitState(s=>s.scenario.state==='completed','timed complete');
  if(t.scenario.assertions.length!==4||t.scenario.assertions.some(x=>!x.passed)||t.result.verdict!=='not_evaluated')throw Error('Timed demo controls or human verdict differ');
  observations.push({phase:'timed',assertions:t.scenario.assertions,human_verdict:t.result.verdict});
  console.log('Capture trends and report exports');
  await page.getByRole('button',{name:'Tendances & rapport',exact:true}).click();
  const panel=page.locator('.chart-panel');await panel.waitFor();
  for(let i=0;i<7;i++){await snap('trends',panel);await page.waitForTimeout(100);}
  const evidence=page.locator('.evidence-grid');
  await snap('report',evidence,{fit:'cover'});
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Rapport FAT',exact:true}).click();
  const saved=await download;await saved.saveAs(join(privateDir,'demo-report.html'));
  observations.push({phase:'report',download:'HTML actual demo report',human_verdict:t.result.verdict});
  for(let i=0;i<6;i++){await snap('report',evidence);await page.waitForTimeout(90);}
  await pidTab();await stopReset();
  console.log('Capture guided STEP1; no observation');
  await start('demo-guided-io');
  const guided=page.locator('.guided-run');
  await snap('guided',guided,{height:1040});
  await page.getByRole('button',{name:'Exécuter STEP 1',exact:true}).click();
  const g=await waitState(s=>s.guided_steps?.[0]?.state==='applied','STEP1 applied');
  if(g.guided_steps.some(x=>x.state==='reviewed')||g.tags.lt101_raw.value!==13824||Math.abs(g.tags.lt101_percent.value-50)>.1||g.result.verdict!=='not_evaluated')throw Error('Guided no-observe invariant');
  observations.push({phase:'guided',step:g.guided_steps[0],reviewed:0,human_verdict:g.result.verdict});
  for(let i=0;i<10;i++){await snap('guided',page.locator('.guided-current-step'),{height:1000});await page.waitForTimeout(100);}
  await stopReset();
  console.log('Capture archive/project dialog');
  await page.getByRole('button',{name:'Ouvrir',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  for(let i=0;i<6;i++){await snap('archive',page.locator('.archive-actions'));await page.waitForTimeout(80);}
  const archiveDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Exporter l’archive FAT',exact:true}).click();
  await (await archiveDownload).saveAs(join(privateDir,'movie-demo.fat.zip'));
  await page.getByRole('button',{name:'Fermer la fenêtre',exact:true}).click();
  console.log('Capture public external assistant CLI');
  const py=join(repo,'.venv/Scripts/python.exe');const ctx=join(privateDir,'movie-assistant-context.json');
  function cli(args){const stdout=execFileSync(py,['-m','fat_studio.assistant','--url',origin,'--context',ctx,...args],{cwd:repo,encoding:'utf8',timeout:20000});return JSON.parse(stdout);}
  cli(['context']);cli(['health']);cli(['schema']);cli(['catalog']);cli(['project']);cli(['start']);
  const stimulus=cli(['stimulus','--tag','lt101_raw','--value','12','--unit','mA']);
  await waitState(s=>s.tags.lt101_raw.value===13824&&Math.abs(s.tags.lt101_percent.value-50)<.1,'CLI wire values');
  const actual=cli(['state']);cli(['stop']);
  if(actual.tags.lt101_raw.value!==13824||actual.tags.lt101_percent.value!==50)throw Error('CLI actual stimulus');
  manifest.transcript={source:'python -m fat_studio.assistant, actual demo commands and selected response fields',mode:'demo',lines:[
    '$ python -m fat_studio.assistant',
    '  --url http://127.0.0.1:8774',
    '  stimulus --tag lt101_raw',
    '  --value 12 --unit mA',
    '',
    '  lt101_raw.value : '+actual.tags.lt101_raw.value,
    '  lt101_percent   : '+actual.tags.lt101_percent.value+' %',
    '  qualité         : '+actual.tags.lt101_raw.quality,
    '  mode            : démonstration',
  ]};
  observations.push({phase:'cli',command:'stimulus --tag lt101_raw --value12 --unit mA',actual_wire_value:actual.tags.lt101_raw.value,level_percent:actual.tags.lt101_percent.value,stop:await state(),stimulus});
  manifest.status='ui-frozen-real-demo';
  manifest.capture_date='2026-11-03';
  manifest.disclosure='Interface démonstration uniquement. Aucune connexion PLC dans ces captures. Le mapping DB public est observé, pas une preuve de connexion pendant le film.';
  if(errors.length)throw Error('Browser JS errors: '+errors.join('; '));
  await writeFile(join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  await writeFile(join(privateDir,'capture-observations.json'),JSON.stringify(observations,null,2)+'\n');
  console.log(JSON.stringify({status:manifest.status,frames:Object.fromEntries(Object.entries(manifest.shots).map(([k,v])=>[k,v.length])),browser_errors:errors}));
}catch(error){
  await writeFile(join(privateDir,'capture-failure.json'),JSON.stringify({error:String(error),errors,manifest,observations},null,2));
  await page.screenshot({path:join(privateDir,'capture-failure.png'),fullPage:false});throw error;
}finally{await browser.close();}
