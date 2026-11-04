// Correct portrait framing using the actual demo UI; original captures remain on disk.
import {chromium} from 'playwright';
import {readFile,writeFile,mkdir,copyFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const studio=resolve(fileURLToPath(new URL('..',import.meta.url))),repo=resolve(studio,'../..');
const dir=join(studio,'assets/captures'),privateDir=join(repo,'.local/vanguard-motion-2026-11-03');
const manifest=JSON.parse(await readFile(join(dir,'manifest.json'),'utf8'));
await mkdir(join(privateDir,'draft-1'),{recursive:true});
for(const f of ['vanguard-fat-studio-draft.mp4','contact-sheet-draft.png','verification.json'])await copyFile(join(studio,'exports',f),join(privateDir,'draft-1',f));
await copyFile(join(dir,'manifest.json'),join(privateDir,'draft-1','capture-manifest.json'));
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1000,height:1200},deviceScaleFactor:1.5,acceptDownloads:true});
const origin='http://127.0.0.1:8774';
await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
page.on('dialog',d=>d.accept());
const state=async()=>{const r=await page.request.get(origin+'/api/state');if(!r.ok())throw Error(r.status());return r.json();};
async function wait(test){for(let n=0;n<150;n++){const s=await state();if(test(s))return s;await page.waitForTimeout(100);}throw Error('State timeout');}
async function reset(){const stop=page.getByRole('button',{name:'Arrêter l’essai',exact:true});if(await stop.isEnabled())await stop.click();await page.getByRole('button',{name:'Réinitialiser le modèle',exact:true}).click();await wait(s=>s.status==='idle');}
async function start(id){await page.locator('#active-scenario').selectOption(id);await page.getByRole('button',{name:'Démarrer',exact:true}).click();await wait(s=>s.status==='running');}
async function shot(id,locator,fit='cover'){
  await locator.scrollIntoViewIfNeeded();await page.waitForTimeout(70);const n=manifest.shots[id].length;const file=`${id}-portrait-${String(n).padStart(3,'0')}.png`;
  await locator.screenshot({path:join(dir,file),animations:'disabled'});const b=await readFile(join(dir,file));manifest.shots[id].push({file,fit,sha256:createHash('sha256').update(b).digest('hex')});
}
try{
  await page.goto(origin);await page.getByLabel('Nom du projet',{exact:true}).waitFor();
  const project=await (await page.request.get(origin+'/api/project')).json();if(project.plc.mode!=='demo'||project.id!=='public-io-lab'||project.tags.length!==75)throw Error('Only the disconnected75-tag demo may be captured');
  await reset();
  manifest.shots.timed=[];manifest.shots.trends=[];manifest.shots.report=[];manifest.shots.guided=[];
  await start('demo-fill-source');
  for(let i=0;i<12;i++){await shot('timed',page.locator('.fat-run:not(.guided-run)'));await page.waitForTimeout(180);}
  const timed=await wait(s=>s.scenario.state==='completed');if(timed.scenario.assertions.length!==4||timed.scenario.assertions.some(a=>!a.passed))throw Error('Timed demo4/4');
  await shot('timed',page.locator('.fat-run:not(.guided-run)'));
  await page.getByRole('button',{name:'Tendances & rapport',exact:true}).click();
  for(let i=0;i<5;i++)await shot('trends',page.locator('.chart-panel'),'contain');
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Rapport FAT',exact:true}).click();const html=join(privateDir,'demo-report-portrait.html');await (await download).saveAs(html);
  const paper=await browser.newPage({viewport:{width:1000,height:1000},deviceScaleFactor:1.5});
  await paper.route('**/*',r=>r.request().url().startsWith('file:')||r.request().url().startsWith('data:')?r.continue():r.abort());
  await paper.goto(pathToFileURL(html).href);await paper.evaluate(()=>document.fonts.ready);
  for(let i=0;i<6;i++){
    await paper.evaluate(y=>window.scrollTo(0,y),i*125);await paper.waitForTimeout(70);
    const file=`report-portrait-${String(i).padStart(3,'0')}.png`;await paper.screenshot({path:join(dir,file),animations:'disabled'});
    manifest.shots.report.push({file,fit:'cover',sha256:createHash('sha256').update(await readFile(join(dir,file))).digest('hex')});
  }
  await paper.close();
  await page.getByRole('button',{name:'P&ID',exact:true}).click();await reset();await start('demo-guided-io');
  await shot('guided',page.locator('.guided-run'),'contain');
  await page.getByRole('button',{name:'Exécuter STEP 1',exact:true}).click();
  const g=await wait(s=>s.guided_steps[0]?.state==='applied');if(g.guided_steps.some(s=>s.state==='reviewed')||g.result.verdict!=='not_evaluated')throw Error('No observation allowed');
  for(let i=0;i<8;i++)await shot('guided',page.locator('.guided-current-step'),'contain');
  await reset();
  for(const f of manifest.shots.archive)f.fit='contain';
  manifest.portrait_correction={viewport:[1000,1200],capture_mode:'demo',timed_controls:4,guided_observed_steps:0,human_verdict:'not_evaluated',report:'actual exported HTML, locally rendered'};
  await writeFile(join(dir,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  console.log(JSON.stringify({frames:Object.fromEntries(Object.entries(manifest.shots).map(([k,v])=>[k,v.length])),status:manifest.status}));
}finally{await browser.close();}
