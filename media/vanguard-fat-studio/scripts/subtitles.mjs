import {writeFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {config,shots} from '../config.mjs';
import {studioRoot} from './serve.mjs';
const stamp=t=>{const ms=Math.round(t*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`;};
await mkdir(join(studioRoot,'exports'),{recursive:true});
const file=join(studioRoot,'exports',config.exportName+'-fr.srt');
await writeFile(file,shots.map((s,i)=>`${i+1}\n${stamp(s.start)} --> ${stamp(s.end)}\n${s.subtitle}\n`).join('\n'),'utf8');
console.log(file);
