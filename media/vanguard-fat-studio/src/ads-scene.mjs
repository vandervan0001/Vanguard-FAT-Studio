import {config} from '../config.mjs';
const C=config.colors;
const ease=x=>1-Math.pow(1-Math.max(0,Math.min(1,x)),3);
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
function round(ctx,x,y,w,h,r=24,fill='#fff',stroke=null){ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke();}}
function text(ctx,value,x,y,size=48,weight=400,color=C.ink,align='left'){ctx.fillStyle=color;ctx.font=`${weight} ${size}px Geist`;ctx.textAlign=align;ctx.textBaseline='alphabetic';ctx.fillText(value,x,y);}
function lines(ctx,value,x,y,size=60,weight=700,color=C.ink,leading=1.15,align='left'){String(value).split('\n').forEach((line,i)=>text(ctx,line,x,y+i*size*leading,size,weight,color,align));}
function wrap(ctx,value,width,size=42){ctx.font=`400 ${size}px Geist`;const out=[];let row='';for(const word of value.split(' ')){const next=row?row+' '+word:word;if(ctx.measureText(next).width>width&&row){out.push(row);row=word;}else row=next;}if(row)out.push(row);return out;}
function mono(ctx,value,x,y,size=24,color=C.muted){ctx.font=`400 ${size}px GeistMono`;ctx.fillStyle=color;ctx.textAlign='left';ctx.fillText(value,x,y);}
function logo(ctx,img,x,y,w){if(img)ctx.drawImage(img,x,y,w,w*img.naturalHeight/img.naturalWidth);}
function motif(ctx,time,signature=false){
  ctx.save();ctx.strokeStyle=signature?'#ffffff20':'#0055DD10';ctx.lineWidth=2;
  for(let x=48;x<1080;x+=56){ctx.beginPath();ctx.moveTo(x,152);ctx.lineTo(x,1090);ctx.stroke();}
  for(let y=160;y<1090;y+=56){ctx.beginPath();ctx.moveTo(48,y);ctx.lineTo(1032,y);ctx.stroke();}
  ctx.strokeStyle=signature?'#ffffff88':'#0055DD30';ctx.lineWidth=9;ctx.lineCap='round';ctx.lineJoin='round';
  ctx.beginPath();ctx.moveTo(-40,1064);ctx.lineTo(94,1064);ctx.quadraticCurveTo(120,1064,120,1038);ctx.lineTo(120,992);ctx.quadraticCurveTo(120,966,146,966);ctx.lineTo(980,966);ctx.quadraticCurveTo(1008,966,1008,938);ctx.lineTo(1008,248);ctx.quadraticCurveTo(1008,220,1036,220);ctx.lineTo(1130,220);ctx.stroke();
  ctx.setLineDash([48,950]);ctx.lineDashOffset=-time*150;ctx.strokeStyle=signature?'#fff':C.blue;ctx.lineWidth=17;ctx.stroke();ctx.restore();
}
function disclosure(ctx){round(ctx,680,62,336,52,26,C.blue);mono(ctx,'INTERFACE EN MODE DÉMO',700,96,21,'#fff');}
function placeholder(ctx,x,y,w,h){
  round(ctx,x,y,w,h,24,'#fff',C.border);ctx.save();ctx.beginPath();ctx.roundRect(x,y,w,h,24);ctx.clip();
  for(let i=0;i<3;i++)round(ctx,x+80+i*(w-160)/3,y+h*.24,120,h*.40,28,C.background,C.border);
  mono(ctx,'PRÉPRODUCTION',x+44,y+76,26,C.blue);lines(ctx,'Captures de la nouvelle interface\nen attente du gel UI',x+44,y+h*.78,30,400,C.muted);ctx.restore();
}
function screenshot(ctx,state,assets,box){
  const series=assets.shots?.[state.shot.asset];if(!series?.length){placeholder(ctx,...box);return {placeholder:true};}
  const sample=series[Math.min(series.length-1,Math.floor(state.p*series.length))],img=sample.image;
  let [x,y,w,h]=box;const enter=ease(state.entry);if(state.shot.move==='slide')x+=56*(1-enter);if(state.shot.move==='paper')y+=35*(1-enter);
  if(sample.fit==='contain'){
    const factor=Math.min(w/img.naturalWidth,h/img.naturalHeight)*(1+.025*state.p),dw=img.naturalWidth*factor,dh=img.naturalHeight*factor;
    ctx.save();ctx.beginPath();ctx.roundRect(x,y,w,h,24);ctx.clip();ctx.fillStyle='#fff';ctx.fillRect(x,y,w,h);ctx.drawImage(img,x+(w-dw)/2,y+(h-dh)/2,dw,dh);ctx.restore();
    round(ctx,x,y,w,h,24,null,C.border);return {placeholder:false,image:sample.file,box:[x,y,w,h],fit:'contain'};
  }
  const base=Math.max(w/img.naturalWidth,h/img.naturalHeight),zoom=1+.07*state.p+(state.shot.move==='macro'?.06:0);
  const sw=w/(base*zoom),sh=h/(base*zoom),pan=state.shot.move==='panReverse'?1-state.p:state.p;
  const fx=clamp(sample.focus?.[0]??.5,.1,.9),fy=clamp(sample.focus?.[1]??.5,.1,.9);
  const sx=clamp((img.naturalWidth-sw)*fx+(pan-.5)*Math.min(42,img.naturalWidth*.04),0,img.naturalWidth-sw);
  const sy=clamp((img.naturalHeight-sh)*fy+(state.p-.5)*Math.min(20,img.naturalHeight*.03),0,img.naturalHeight-sh);
  ctx.save();ctx.shadowColor='#15335826';ctx.shadowBlur=28;ctx.shadowOffsetY=13;round(ctx,x,y,w,h,24,'#fff');ctx.restore();
  ctx.save();ctx.beginPath();ctx.roundRect(x,y,w,h,24);ctx.clip();ctx.drawImage(img,sx,sy,sw,sh,x,y,w,h);ctx.restore();round(ctx,x,y,w,h,24,null,C.border);
  return {placeholder:false,image:sample.file,box:[x,y,w,h]};
}
function subtitles(ctx,state){
  round(ctx,44,1138,992,156,24,state.shot.id==='signature'?'#FFFFFF17':'#FFFFFF');const rows=wrap(ctx,state.shot.subtitle,904,42);
  if(rows.length>2)throw new Error('Subtitle exceeds two lines: '+state.shot.id);
  rows.forEach((row,i)=>text(ctx,row,540,1197+i*51,42,400,state.shot.id==='signature'?'#fff':C.ink,'center'));
  ctx.fillStyle=state.shot.id==='signature'?'#fff':C.blue;ctx.fillRect(64,1324,952*state.time/45,4);
}
function terminal(ctx,state,assets){
  const transcript=assets.transcript?.lines??['$ python -m fat_studio.assistant …','  stimulus --tag lt101_raw','  --value 12 --unit mA','','  Extrait réel à capturer après gel UI'];
  round(ctx,64,370,952,660,24,'#102243');['#8CB4F8','#BCD4FF','#E9F1FF'].forEach((c,i)=>{ctx.fillStyle=c;ctx.beginPath();ctx.arc(103+i*28,411,7,0,Math.PI*2);ctx.fill();});
  mono(ctx,'CLIENT PUBLIC · API LOCALE',110,467,26,'#ADC9F8');const count=Math.ceil(clamp(state.p*1.7)*transcript.length);
  transcript.slice(0,count).forEach((line,i)=>mono(ctx,line,105,533+i*43,26,i<3?'#FFFFFF':'#B6D3FF'));
  round(ctx,705,932,260,56,28,C.blue);mono(ctx,'IA EXTERNE',742,968,25,'#fff');
}
function proof(ctx,state){
  const p=ease(state.entry);text(ctx,'31 / 31',540,563+30*(1-p),154,700,C.blue,'center');text(ctx,'attentes réussies',540,636,56,700,C.ink,'center');
  text(ctx,'TIA V21 + PLCSIM Advanced 8',540,730,40,400,C.ink,'center');round(ctx,233,789,614,73,36,'#fff',C.border);text(ctx,'3 novembre 2026',540,837,37,400,C.ink,'center');
  mono(ctx,'CAMPAGNE ANTÉRIEURE SUR CPU VIRTUELLE',182,936,28,C.muted);text(ctx,'Aucune réception FAT humaine déduite.',540,997,31,400,C.muted,'center');
}
export function drawAdsScene(ctx,state,assets){
  ctx.fillStyle=state.shot.id==='signature'?C.blue:C.background;ctx.fillRect(0,0,1080,1350);motif(ctx,state.time,state.shot.id==='signature');let imageLayout=null;
  if(state.shot.id==='signature'){
    logo(ctx,assets.logoWhite,160,220,760);lines(ctx,'Vanguard\nFAT Studio',540,612,100,700,'#fff',1.12,'center');text(ctx,'Version en préparation',540,881,43,400,'#fff','center');round(ctx,210,932,660,82,18,C.blue);text(ctx,'vanguard-systems.ch',540,986,49,700,'#fff','center');
  }else{
    logo(ctx,assets.logo,64,45,360);if(state.shot.asset)disclosure(ctx);mono(ctx,state.shot.label,64,216,27,C.blue);
    let size=state.shot.id==='hook'?85:64;ctx.font=`700 ${size}px Geist`;while(!state.shot.title.includes('\n')&&ctx.measureText(state.shot.title).width>920&&size>48){size--;ctx.font=`700 ${size}px Geist`;}
    const y=state.shot.id==='hook'?321:302;lines(ctx,state.shot.title,64,y+20*(1-ease(state.entry)),size,700,C.ink,1.12);
    if(state.shot.move==='proof')proof(ctx,state);else if(state.shot.move==='terminal')terminal(ctx,state,assets);else{
      const macro=['bool','analog'].includes(state.shot.id);
      imageLayout=screenshot(ctx,state,assets,state.shot.id==='hook'?[64,488,952,588]:macro?[64,362,490,720]:state.shot.id==='timed'?[64,362,952,660]:state.shot.id==='trends'?[64,500,952,400]:state.shot.id==='archive'?[64,470,952,490]:[64,362,952,720]);
      if(state.shot.id==='bool'){round(ctx,590,522,426,330,22,C.blue);text(ctx,'300',803,658,119,700,'#fff','center');text(ctx,'millisecondes',803,722,36,400,'#fff','center');mono(ctx,'IMPULSION',718,799,27,'#DDEAFF');}
      if(state.shot.id==='analog'){
        const switched=state.p>.36;round(ctx,590,398,426,638,22,C.blue);text(ctx,'12 mA',803,531,71,700,'#fff','center');
        ctx.strokeStyle='#96BFFF';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(803,574);ctx.lineTo(803,640);ctx.lineTo(787,624);ctx.moveTo(803,640);ctx.lineTo(819,624);ctx.stroke();
        ctx.save();ctx.globalAlpha=switched?1:.3;text(ctx,'13 824',803,738,74,700,'#fff','center');mono(ctx,'POINTS PLC',723,786,25,'#DDEAFF');text(ctx,'50 %',803,904,74,700,'#fff','center');mono(ctx,'NIVEAU',752,957,25,'#DDEAFF');ctx.restore();
      }
      if(state.shot.id==='guided'){round(ctx,382,976,594,74,22,C.blue);text(ctx,'Observation attendue',679,1026,37,700,'#fff','center');}
      if(state.shot.id==='timed'){const n=assets.shots.timed.length,finished=Math.floor(state.p*n)===n-1;round(ctx,654,890,322,142,22,C.blue);text(ctx,finished?'4 / 4':'4 attentes',815,979,finished?67:46,700,'#fff','center');}
      if(state.shot.id==='trends'){mono(ctx,'3 VARIABLES · TRACE ACQUISE',106,444,28,C.blue);text(ctx,'Niveau · consigne · retour vitesse',540,1006,38,700,C.ink,'center');}
      if(state.shot.id==='archive'){mono(ctx,'P&ID · SCÉNARIOS · HISTORIQUE',205,1040,29,C.blue);}
    }
  }
  subtitles(ctx,state);return {shot:state.shot.id,image:imageLayout,subtitle:state.shot.subtitle,captureReady:assets.captureReady??false};
}
