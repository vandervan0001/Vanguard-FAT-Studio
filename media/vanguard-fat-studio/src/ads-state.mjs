import {config,shots} from '../config.mjs';
const clamp=x=>Math.max(0,Math.min(1,x));
export function adsState(seconds){
  const t=Math.max(0,Math.min(config.duration,Number(seconds)));
  const index=t===config.duration?shots.length-1:Math.max(0,shots.findIndex(s=>t>=s.start&&t<s.end));
  const shot=shots[index];
  return {time:t,index,shot,local:t-shot.start,p:clamp((t-shot.start)/(shot.end-shot.start)),entry:clamp((t-shot.start)/.26),exit:clamp((shot.end-t)/.20)};
}
