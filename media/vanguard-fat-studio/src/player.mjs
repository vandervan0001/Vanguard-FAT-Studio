import {config} from '../config.mjs';
import {adsState} from './ads-state.mjs';
import {drawAdsScene} from './ads-scene.mjs';
import {clamp} from './math.mjs';

const query=new URLSearchParams(location.search),renderMode=query.get('render')==='1';
if(renderMode)document.documentElement.classList.add('render');
const canvas=document.querySelector('#film');
canvas.width=Number(query.get('width'))||config.width;canvas.height=Number(query.get('height'))||config.height;
document.querySelector('.stage').style.aspectRatio=`${config.width}/${config.height}`;
document.querySelector('#brand-name').textContent=config.brand.name;
document.querySelector('#film-info').textContent=`${config.mode==='ads'?'Publicité':'Démonstration technique'} · ${config.duration} secondes`;
const ctx=canvas.getContext('2d',{alpha:false}),assets={},audio=document.querySelector('#soundtrack');
const button=document.querySelector('#play-pause'),slider=document.querySelector('#scrubber');
const state=adsState;
let time=0,playing=false,frameRequest=0,startTime=0,startWall=0,lastLayout=null;
slider.max=String(config.duration);

function seek(seconds) {
  time=clamp(Number(seconds),0,config.duration);
  ctx.setTransform(canvas.width/config.width,0,0,canvas.height/config.height,0,0);
  ctx.globalAlpha=1;ctx.shadowBlur=0;ctx.lineWidth=1;ctx.setLineDash([]);
  const current=state(time);
  lastLayout=drawAdsScene(ctx,current,assets);
  slider.value=String(time);
  document.querySelector('#time').textContent=`${time.toFixed(2).replace('.',',')} / ${config.duration.toFixed(2).replace('.',',')} s`;
  return current;
}
function pause(){playing=false;cancelAnimationFrame(frameRequest);audio.pause();button.textContent='Lire';}
function tick(now){if(!playing)return;seek(startTime+(now-startWall)/1000);if(time>=config.duration){pause();return;}frameRequest=requestAnimationFrame(tick);}
function play(){
  if(renderMode)return;
  if(time>=config.duration)seek(0);
  playing=true;startTime=time;startWall=performance.now();button.textContent='Pause';
  if(document.querySelector('#audio-enabled').checked){audio.currentTime=time;audio.play().catch(e=>{document.querySelector('#status').textContent=`Lecture audio indisponible : ${e.message}`;});}
  frameRequest=requestAnimationFrame(tick);
}
window.motionState=state;window.playbackState=()=>({time,playing,renderMode});
window.motionDiagnostics=()=>({canvas:[canvas.width,canvas.height],renderMode,
  fonts:[...document.fonts].map(f=>({family:f.family,status:f.status,weight:f.weight})),
  logo:{width:assets.logo?.naturalWidth||assets.logo?.width,height:assets.logo?.naturalHeight||assets.logo?.height,fallback:assets.brandFallback},
  layout:lastLayout,state:state(time)});
window.ready=(async()=>{
  await Promise.all([document.fonts.load('400 24px Geist'),document.fonts.load('700 24px Geist'),document.fonts.load('400 13px GeistMono')]);await document.fonts.ready;
  if(config.assets.logo){const logo=new Image();logo.src=config.assets.logo;try{await logo.decode();}catch(e){throw Error('Logo decode failed: '+logo.src+' '+e.message);}assets.logo=logo;assets.brandFallback=false;}
  else {
    // Plain typeset name, explicitly a fallback. No invented logo symbol.
    const fallback=document.createElement('canvas');fallback.width=1180;fallback.height=300;
    const fctx=fallback.getContext('2d');let size=112;fctx.font=`700 ${size}px Geist`;
    while(fctx.measureText(config.brand.name).width>1100&&size>28){size-=2;fctx.font=`700 ${size}px Geist`;}
    fctx.fillStyle=config.colors.ink;fctx.textAlign='center';fctx.textBaseline='middle';fctx.fillText(config.brand.name,590,150);
    assets.logo=fallback;assets.brandFallback=true;
  }
  if(config.assets.logoWhite){const white=new Image();white.src=config.assets.logoWhite;try{await white.decode();}catch(e){throw Error('Logo decode failed: '+white.src+' '+e.message);}assets.logoWhite=white;}
  const manifest=await fetch('./assets/captures/manifest.json').then(r=>{if(!r.ok)throw new Error('Capture manifest missing');return r.json();});
  assets.shots={};assets.captureReady=manifest.status==='ui-frozen-real-demo';
  for(const [id,frames] of Object.entries(manifest.shots)){
    assets.shots[id]=[];for(const frame of frames){const image=new Image();image.src='./assets/captures/'+frame.file;try{await image.decode();}catch(e){throw Error('Capture decode failed: '+image.src+' '+e.message);}assets.shots[id].push({...frame,image});}
  }
  assets.transcript=manifest.transcript??null;window.captureManifest=manifest;
  window.seek=seek;seek(0);for(const el of document.querySelectorAll('button,input'))el.disabled=false;
  document.querySelector('#status').textContent=assets.brandFallback?'Ressources chargées. Nom composé en texte ; logo non fourni.':'Ressources locales chargées.';
  return window.motionDiagnostics();
})();
window.ready.catch(e=>{document.querySelector('#status').textContent=`Erreur : ${e.message}`;console.error(e);});
button.addEventListener('click',()=>playing?pause():play());
slider.addEventListener('input',()=>{pause();seek(Number(slider.value));audio.currentTime=time;});
document.querySelector('#restart').addEventListener('click',()=>{pause();seek(0);});
document.querySelector('#audio-enabled').addEventListener('change',()=>{audio.pause();if(playing&&document.querySelector('#audio-enabled').checked){audio.currentTime=time;audio.play().catch(console.error);}});
