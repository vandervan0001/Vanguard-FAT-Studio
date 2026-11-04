import {chromium} from 'playwright';
import {readFile,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const studio=resolve(fileURLToPath(new URL('..',import.meta.url))),dir=join(studio,'assets/captures');
const manifest=JSON.parse(await readFile(join(dir,'manifest.json'),'utf8'));
const browser=await chromium.launch({headless:true});
try{
  const page=await browser.newPage({viewport:{width:1000,height:1100},deviceScaleFactor:1.5});
  await page.route('**/*',r=>new URL(r.request().url()).origin==='http://127.0.0.1:8774'?r.continue():r.abort());
  page.on('dialog',d=>d.accept());await page.goto('http://127.0.0.1:8774');await page.getByLabel('Nom du projet',{exact:true}).waitFor();
  const project=await (await page.request.get('http://127.0.0.1:8774/api/project')).json();if(project.plc.mode!=='demo'||project.id!=='public-io-lab'||project.tags.length!==75)throw Error('Only the disconnected75-tag demo may be captured');
  const state=async()=>{const r=await page.request.get('http://127.0.0.1:8774/api/state');if(!r.ok())throw Error(r.status());return r.json();};
  if((await state()).status==='stopped')await page.getByRole('button',{name:'Réinitialiser le modèle',exact:true}).click();
  if((await state()).status!=='idle')throw Error('Expected portrait-capture idle');
  await page.getByRole('button',{name:'Tendances & rapport',exact:true}).click();
  const labels=page.locator('.trend-tag-picker label');const count=await labels.count();
  for(let i=0;i<count;i++)if(await labels.nth(i).locator('input').isChecked())await labels.nth(i).locator('input').uncheck();
  const names=[];
  for(let i=0;i<count;i++){const label=labels.nth(i),name=(await label.innerText()).trim();if(/^(LT101_Percent|P101_SpeedCommand|P101_SpeedFeedback)(\s|%|$)/.test(name)){await label.locator('input').check();names.push(name);}}
  if(names.length!==3)throw Error('Need3actualtags: '+names);
  await page.getByRole('button',{name:'P&ID',exact:true}).click();await page.locator('#active-scenario').selectOption('demo-fill-source');await page.getByRole('button',{name:'Démarrer',exact:true}).click();
  await page.getByRole('button',{name:'Tendances & rapport',exact:true}).click();
  for(let i=0;i<count;i++)if(await labels.nth(i).locator('input').isChecked())await labels.nth(i).locator('input').uncheck();
  for(let i=0;i<count;i++){const label=labels.nth(i),name=(await label.innerText()).trim();if(names.includes(name))await label.locator('input').check();}
  if(await page.locator('.trend-tag-picker input:checked').count()!==3)throw Error('Exactly3 checked tags required after tab mount');
  const chart=page.locator('.chart-container');await chart.waitFor();manifest.shots.trends=[];
  for(let i=0;i<16;i++){
    const file=`trends-chart-${String(i).padStart(3,'0')}.png`;await chart.screenshot({path:join(dir,file),animations:'disabled'});
    const s=await state();manifest.shots.trends.push({file,fit:'contain',sim_time_s:s.sim_time_s,sha256:createHash('sha256').update(await readFile(join(dir,file))).digest('hex')});
    await page.waitForTimeout(300);
  }
  for(let i=0;i<100&&(await state()).scenario.state!=='completed';i++)await page.waitForTimeout(100);
  const s=await state();if(s.scenario.state!=='completed'||s.scenario.assertions.some(a=>!a.passed)||s.result.verdict!=='not_evaluated')throw Error('Trace demo not finished as expected');
  manifest.trend_selection={tags:names,source:'actual chart-container screenshot, 3 UI-selected tags, model demo',final_time_s:s.sim_time_s};
  await page.getByRole('button',{name:'Arrêter l’essai',exact:true}).click();
  await writeFile(join(dir,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  console.log(JSON.stringify(manifest.trend_selection));
}finally{await browser.close();}
