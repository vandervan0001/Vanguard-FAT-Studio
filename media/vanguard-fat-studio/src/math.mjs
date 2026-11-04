export const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
export const mix = (a, b, t) => a + (b - a) * t;
export const smooth = (v) => { const t = clamp(v); return t * t * (3 - 2 * t); };
export const smoother = (v) => { const t = clamp(v); return t*t*t*(t*(t*6-15)+10); };
export const ease = (t, a, b) => smoother((t - a) / (b - a));
export const envelope = (t,a,b,c,d) => ease(t,a,b) * (1-ease(t,c,d));
export const radians = (v) => v * Math.PI / 180;
export function keyed(t, keys) {
  if (t <= keys[0].t) return {...keys[0]};
  for (let i=1;i<keys.length;i++) {
    if (t<=keys[i].t) {
      const v = ease(t,keys[i-1].t,keys[i].t), out={};
      for (const key of Object.keys(keys[i])) out[key]=mix(keys[i-1][key],keys[i][key],v);
      return out;
    }
  }
  return {...keys.at(-1)};
}
