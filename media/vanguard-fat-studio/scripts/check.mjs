import { chromium } from 'playwright';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import {createHash} from 'node:crypto';
import { config } from '../config.mjs';
import { startServer, studioRoot } from './serve.mjs';

const exec = promisify(execFile);
const require = createRequire(import.meta.url);
const outputDir = join(studioRoot, 'exports');
const exportName = config.exportName ?? 'film';
const gcd = (a, b) => b ? gcd(b, a % b) : a;
const normalized = value => value * config.duration / 20;
function profile(variant) {
  if (!Number.isSafeInteger(config.width) || config.width <= 0 || !Number.isSafeInteger(config.height) || config.height <= 0) {
    throw new Error('Render dimensions must be positive integers.');
  }
  const unit = gcd(config.width, config.height);
  const factor = 180;
  const width = variant === 'master' ? config.width : config.width / unit * factor;
  const height = variant === 'master' ? config.height : config.height / unit * factor;
  const fps = variant === 'master' ? config.fps : Math.min(15, config.fps);
  return { width, height, fps, frames: config.duration * fps };
}
const draft = profile('draft');
const editorialTimes = [0.4, 1.5, 4.8, 5.3, 8.8, 11.85, 12.15, 12.6, 14.2, 16.3, 18.8, 19.95].map(normalized);
const reviewTimes = config.reviewTimes ?? editorialTimes;
function safeTime(t, fps = config.fps) { return Math.max(0, Math.min(config.duration - 1 / fps, t)); }
function eventTimes() {
  return Object.values(config.events ?? {}).map(value => typeof value === 'number' ? value : value?.time)
    .filter(value => Number.isFinite(value) && value >= 0 && value < config.duration);
}
const sourceOnly = process.argv.includes('--source-only');
const requestedVariant = process.argv.includes('--master') ? 'master' : process.argv.includes('--draft') ? 'draft' : null;
const args = process.argv.slice(2);
if (args.some(arg => !['--source-only', '--draft', '--master'].includes(arg)) || args.length > 1) {
  throw new Error('Use no argument, --source-only, --draft, or --master.');
}
await mkdir(outputDir, { recursive: true });
const report = { started: new Date().toISOString(), mode: sourceOnly ? 'source-only' : requestedVariant ?? 'full', checks: [], errors: [], exports: [],
  limits: ['Audio was measured numerically. This script does not prove human listening or aesthetic review.'] };
let server, browser;
const watchdog = setTimeout(() => {
  report.errors.push('Verification exceeded the five-minute watchdog.');
  browser?.close().catch(() => {});
}, 5 * 60 * 1000);
watchdog.unref();

function check(name, condition, detail) {
  report.checks.push({ name, passed: Boolean(condition), detail });
  if (!condition) throw new Error(`${name}: ${JSON.stringify(detail)}`);
  console.log(`PASS ${name}`);
}

async function exists(file) {
  try { return (await stat(file)).isFile(); } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

async function hashCanvas(page, time) {
  return page.evaluate(async t => {
    window.seek(t);
    const canvas = document.querySelector('canvas');
    const bytes = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    const colors = new Set();
    for (let i = 0; i < bytes.length; i += 4 * 97) colors.add(`${bytes[i]},${bytes[i + 1]},${bytes[i + 2]},${bytes[i + 3]}`);
    return { hash: Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, '0')).join(''),
      colors: colors.size, bytes: bytes.length };
  }, time);
}

function watchPage(page, requests) {
  page.on('pageerror', error => report.errors.push(`JavaScript: ${error.message}`));
  page.on('console', message => { if (message.type() === 'error') report.errors.push(`Console: ${message.text()}`); });
  page.on('requestfailed', request => report.errors.push(`Resource: ${request.url()} — ${request.failure()?.errorText}`));
  page.on('response', response => {
    requests.push({ path: new URL(response.url()).pathname, status: response.status() });
    if (response.status() >= 400) report.errors.push(`HTTP ${response.status()}: ${response.url()}`);
  });
}

async function openPage(context, url, requests) {
  const page = await context.newPage(); watchPage(page, requests);
  await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1'
    ? route.continue() : route.abort('blockedbyclient'));
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.waitForFunction(() => Boolean(window.ready), { timeout: 15_000 });
  await page.evaluate(() => window.ready);
  return page;
}

async function inspectVideo(file, variant, expectedAudio) {
  const { width, height, fps } = profile(variant);
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-count_frames', '-show_entries',
    'stream=codec_name,codec_type,width,height,pix_fmt,color_range,color_space,color_transfer,color_primaries,r_frame_rate,avg_frame_rate,nb_read_frames,duration,sample_rate:format=duration,size',
    '-of', 'json', file], { maxBuffer: 1024 * 1024, timeout: 60_000 });
  const probe = JSON.parse(stdout);
  const video = probe.streams.find(s => s.codec_type === 'video');
  const audio = probe.streams.find(s => s.codec_type === 'audio');
  check(`${variant} ${expectedAudio ? 'audio' : 'silent'} encoded metadata`,
    video?.codec_name === 'h264' && video.width === width && video.height === height &&
    video.pix_fmt === 'yuv420p' && video.color_range === 'tv' && video.color_space === 'bt709' &&
    video.color_transfer === 'bt709' && video.color_primaries === 'bt709' && video.r_frame_rate === `${fps}/1` &&
    video.avg_frame_rate === `${fps}/1` && Number(video.nb_read_frames) === config.duration * fps &&
    Math.abs(Number(video.duration) - config.duration) < 0.0001 &&
    Math.abs(Number(probe.format.duration) - config.duration) < 0.01 &&
    Boolean(audio) === expectedAudio && (!audio || audio.codec_name === 'aac'), probe);
  // Examine top-level MP4 atom ordering rather than searching for text inside compressed media.
  const bytes = await readFile(file);
  const atoms = []; let offset = 0;
  while (offset + 8 <= bytes.length) {
    let size = bytes.readUInt32BE(offset); const name = bytes.toString('ascii', offset + 4, offset + 8);
    if (size === 1) size = Number(bytes.readBigUInt64BE(offset + 8));
    if (size === 0) size = bytes.length - offset;
    if (size < 8 || offset + size > bytes.length) throw new Error(`Invalid MP4 atom ${name}.`);
    atoms.push(name); offset += size;
  }
  check(`${variant} ${expectedAudio ? 'audio' : 'silent'} faststart`,
    atoms.includes('moov') && atoms.includes('mdat') && atoms.indexOf('moov') < atoms.indexOf('mdat'), atoms);
  let loudness;
  if (expectedAudio) {
    const { stderr } = await exec('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-map', '0:a:0',
      '-af', 'ebur128=peak=true', '-f', 'null', '-'], { maxBuffer: 2 * 1024 * 1024, timeout: 60_000 });
    const peak = stderr.match(/True peak:\s*Peak:\s*(-?[\d.]+) dBFS/);
    const integrated = stderr.match(/Integrated loudness:\s*I:\s*(-?[\d.]+) LUFS/);
    loudness = { truePeakDbfs: peak ? Number(peak[1]) : null, integratedLufs: integrated ? Number(integrated[1]) : null };
    check(`${variant} final AAC true peak and audible signal`,
      Number.isFinite(loudness.truePeakDbfs) && loudness.truePeakDbfs < -0.5 && loudness.truePeakDbfs > -30 &&
      Number.isFinite(loudness.integratedLufs) && loudness.integratedLufs > -40, loudness);
  }
  report.exports.push({ file, probe, atoms, ...(loudness ? { loudness } : {}) });
  return { fps, width, height };
}

async function keyframes(file, variant, fps) {
  const times = reviewTimes;
  const frameNumbers = [...new Set(times.map(t => Math.round(safeTime(t, fps) * fps)))].sort((a, b) => a - b);
  const selection = frameNumbers.map(n => `eq(n,${n})`).join('+');
  const dir = join(outputDir, `keyframes-${variant}`); await mkdir(dir, { recursive: true });
  await exec('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', file,
    '-vf', `select='${selection}'`, '-fps_mode', 'vfr', join(dir, 'frame-%02d.png')],
    { timeout: 90_000, maxBuffer: 1024 * 1024 });
  const contactSheet = join(outputDir, `contact-sheet-${variant}.png`);
  await exec('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', file,
    '-vf', `select='${selection}',scale=480:480:force_original_aspect_ratio=decrease,pad=480:480:(ow-iw)/2:(oh-ih)/2:color=0x101419,tile=4x${Math.ceil(frameNumbers.length / 4)}`, '-frames:v', '1', contactSheet],
    { timeout: 90_000, maxBuffer: 1024 * 1024 });
  const allExist = await Promise.all(frameNumbers.map((_, i) => exists(join(dir, `frame-${String(i + 1).padStart(2, '0')}.png`))));
  check(`${variant} decoded final MP4 keyframes`, allExist.every(Boolean) && await exists(contactSheet),
    { count: allExist.filter(Boolean).length, times: frameNumbers.map(n => n / fps), contactSheet });
  const eventFrames = [...new Set(eventTimes().flatMap(time => [-1, 0, 1].map(offset =>
    Math.round(safeTime(time + offset / fps, fps) * fps))))].sort((a, b) => a - b);
  let transitionsDir;
  if (eventFrames.length) {
    transitionsDir = join(outputDir, `transitions-${variant}`); await mkdir(transitionsDir, { recursive: true });
    await exec('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', file,
      '-vf', `select='${eventFrames.map(n => `eq(n,${n})`).join('+')}'`, '-fps_mode', 'vfr', join(transitionsDir, 'frame-%03d.png')],
      { timeout: 90_000, maxBuffer: 1024 * 1024 });
    const present = await Promise.all(eventFrames.map((_, i) => exists(join(transitionsDir, `frame-${String(i + 1).padStart(3, '0')}.png`))));
    check(`${variant} decoded transition intermediates`, present.length > 0 && present.every(Boolean),
      { dir: transitionsDir, count: present.length, times: eventFrames.map(n => n / fps) });
  }
  return { dir, contactSheet, times: frameNumbers.map(n => n / fps), transitionsDir, transitionTimes: eventFrames.map(n => n / fps) };
}

async function inspectWave() {
  const file = join(outputDir, 'soundtrack.wav'); const wav = await readFile(file);
  check('soundtrack RIFF/WAVE', wav.toString('ascii', 0, 4) === 'RIFF' && wav.toString('ascii', 8, 12) === 'WAVE',
    { file, bytes: wav.length });
  let offset = 12, format, data;
  while (offset + 8 <= wav.length) {
    const name = wav.toString('ascii', offset, offset + 4), size = wav.readUInt32LE(offset + 4);
    if (name === 'fmt ') format = { encoding: wav.readUInt16LE(offset + 8), channels: wav.readUInt16LE(offset + 10),
      sampleRate: wav.readUInt32LE(offset + 12), bits: wav.readUInt16LE(offset + 22) };
    if (name === 'data') data = wav.subarray(offset + 8, offset + 8 + size);
    offset += 8 + size + size % 2;
  }
  check('soundtrack PCM16 samples exist', format?.encoding === 1 && format.bits === 16 && data?.length > 0,
    { format, dataBytes: data?.length });
  const sampleFrames = data.length / (format.channels * 2);
  let peak = 0, squared = 0, clipped = 0, head = 0, tail = 0;
  const edgeFrames = Math.round(format.sampleRate * 0.01);
  for (let i = 0; i < data.length / 2; i++) {
    const sample = data.readInt16LE(i * 2) / 32768; const amplitude = Math.abs(sample);
    peak = Math.max(peak, amplitude); squared += sample * sample;
    if (amplitude >= 0.999) clipped++;
    if (i < edgeFrames * format.channels) head = Math.max(head, amplitude);
    if (i >= (sampleFrames - edgeFrames) * format.channels) tail = Math.max(tail, amplitude);
  }
  const result = { ...format, sampleFrames, duration: sampleFrames / format.sampleRate,
    peak, peakDbfs: 20 * Math.log10(peak), rms: Math.sqrt(squared / (data.length / 2)), clipped,
    first10msPeak: head, last10msPeak: tail, humanListening: false };
  check('soundtrack exact duration, headroom, clean edges', Math.abs(result.duration - config.duration) < 1e-8 &&
    peak > 0.05 && peak < 0.98 && clipped === 0 && head < 0.01 && tail < 0.01, result);
  report.audio = result;
}

try {
  const captureManifest=JSON.parse(await readFile(join(studioRoot,'assets/captures/manifest.json'),'utf8'));
  const inputs=Object.values(captureManifest.shots).flat();
  const integrity=[];for(const frame of inputs){const bytes=await readFile(join(studioRoot,'assets/captures',frame.file));integrity.push(createHash('sha256').update(bytes).digest('hex')===frame.sha256);}
  check('actual demo capture inputs and SHA256 integrity',captureManifest.status==='ui-frozen-real-demo'&&captureManifest.capture_mode==='demo'&&captureManifest.connected_plc===false&&inputs.length>0&&integrity.every(Boolean)&&captureManifest.trend_selection.tags.length===3,{images:inputs.length,all_hashes_match:integrity.every(Boolean),connected_plc:captureManifest.connected_plc,trend_tags:captureManifest.trend_selection.tags});
  check('film delivery contract', Number.isFinite(config.duration) && config.duration > 0 &&
    Number.isSafeInteger(config.width) && config.width > 0 && config.width % 2 === 0 &&
    Number.isSafeInteger(config.height) && config.height > 0 && config.height % 2 === 0 &&
    Number.isSafeInteger(config.fps) && config.fps > 0 &&
    ['draft', 'master'].every(variant => Number.isSafeInteger(profile(variant).frames)) &&
    /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(exportName),
    { duration: config.duration, master: profile('master'), draft, exportName });
  check('editorial review times are bounded', Array.isArray(reviewTimes) && reviewTimes.length > 0 &&
    reviewTimes.every(time => Number.isFinite(time) && time >= 0 && time < config.duration), { reviewTimes });
  const declaredEvents = Object.entries(config.events ?? {});
  check('declared events stay inside the film', declaredEvents.every(([, value]) => {
    const time = typeof value === 'number' ? value : value?.time;
    return Number.isFinite(time) && time >= 0 && time < config.duration;
  }), { events: config.events ?? {} });
  const versions = await Promise.all([
    exec('ffmpeg', ['-version']), exec('ffprobe', ['-version']),
  ]);
  report.versions = { node: process.version, playwright: require('playwright/package.json').version,
    ffmpeg: versions[0].stdout.split('\n')[0], ffprobe: versions[1].stdout.split('\n')[0] };
  server = await startServer({ port: 0 });
  const forbidden = await fetch(`${server.url}/package.json`);
  check('local server responds', forbidden.ok && (await forbidden.json()).name === 'motion-design-studio', { url: server.url });
  const blocked = await fetch(`${server.url}/.env`);
  check('local server blocks hidden paths', blocked.status === 403, { status: blocked.status });
  browser = await chromium.launch({ headless: true, args: ['--disable-background-timer-throttling'] });
  report.versions.chromium = await browser.version();
  const context = await browser.newContext({ viewport: { width: draft.width, height: draft.height }, deviceScaleFactor: 1,
    reducedMotion: 'no-preference', colorScheme: 'dark' });
  const requests = [];
  const page = await openPage(context, `${server.url}/?render=1&width=${draft.width}&height=${draft.height}`, requests);
  const geometry = await page.evaluate(() => {
    const canvas = document.querySelector('canvas'); const box = canvas.getBoundingClientRect();
    return { width: canvas.width, height: canvas.height, box: { x: box.x, y: box.y, width: box.width, height: box.height },
      visibility: document.visibilityState, fontsStatus: document.fonts.status,
      fonts: [...document.fonts].map(f => ({ family: f.family, status: f.status })),
      controlsHidden: !document.querySelector('#play-pause') || document.querySelector('#play-pause').getBoundingClientRect().width === 0 };
  });
  check('render canvas, viewport, fonts, controls', geometry.width === draft.width && geometry.height === draft.height &&
    geometry.box.x === 0 && geometry.box.y === 0 && geometry.box.width === draft.width && geometry.box.height === draft.height &&
    geometry.visibility === 'visible' && geometry.fontsStatus === 'loaded' && geometry.controlsHidden &&
    geometry.fonts.length > 0 && geometry.fonts.every(f => f.status === 'loaded'), geometry);
  const target = safeTime(normalized(12.18), draft.fps);
  const reference = await hashCanvas(page, target);
  check('raw canvas positive visual control', reference.bytes === draft.width * draft.height * 4 && reference.colors > 100, reference);
  const traversals = [[0, 5.2, 18.9], [19.98, 13.4, 2.1, 8.3], [12.17, 12.19, 12.18]]
    .map(traversal => traversal.map(time => safeTime(normalized(time), draft.fps)));
  const hashes = [];
  for (const traversal of traversals) {
    for (const time of traversal) await page.evaluate(t => window.seek(t), time);
    hashes.push(await hashCanvas(page, target));
  }
  const otherTime = safeTime(normalized(6.1), draft.fps);
  const other = await hashCanvas(page, otherTime);
  check('determinism after three distinct time traversals', hashes.every(h => h.hash === reference.hash),
    { target, reference: reference.hash, hashes: hashes.map(h => h.hash), traversals });
  check('different-time positive control', other.hash !== reference.hash, { targetHash: reference.hash, otherTime, otherHash: other.hash });
  await page.evaluate(t => window.seek(t), target);
  await page.waitForTimeout(300);
  const held = await page.evaluate(async () => {
    const c = document.querySelector('canvas'); const data = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    const digest = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
  });
  check('render mode has no autonomous advancement', held === reference.hash, { held, expected: reference.hash, heldMilliseconds: 300 });
  const stateTimes = [...new Set([0, target, otherTime, ...eventTimes(), safeTime(config.duration - 1 / draft.fps)])];
  const genericStates = await page.evaluate(times => times.map(time => window.motionState(time)), stateTimes);
  check('absolute-time state contract', genericStates.length === stateTimes.length &&
    genericStates.every((state, index) => state && Number.isFinite(state.time) && Math.abs(state.time - stateTimes[index]) < 1e-8),
    { times: stateTimes, states: genericStates });
  report.motionStates = genericStates;
  if (config.mode === 'engineering') {
  const e = config.events;
  if (!e) throw new Error('Engineering mode needs physical event times.');
  const contactEarly = e.ejectContact + (e.ejectEnd - e.ejectContact) * 0.27;
  const contactLate = e.ejectContact + (e.ejectEnd - e.ejectContact) * 0.64;
  const landingTime = safeTime(e.retracted + normalized(0.95));
  const continueBefore = safeTime(e.retracted + normalized(1.75));
  const continueAfter = safeTime(e.retracted + normalized(2.25));
  const times = [0, e.inspection, e.detected, e.ejectStart, e.ejectContact, contactEarly, contactLate,
    e.ejectEnd, e.retracted, landingTime, continueBefore, continueAfter];
  const states = await page.evaluate(ts => ts.map(t => window.motionState(t)), times);
  report.motionStates = states;
  check('defective product identity throughout action', states.length === times.length &&
    states.every(s => s.defect?.id === 'P-04' && s.products.some(p => p.id === 'P-04' && p.defective)), { times, ids: states.map(s => s.defect?.id) });
  const at = t => states[times.indexOf(t)];
  check('inspection physically observes same product', Math.abs(at(e.inspection).defect.x - at(e.inspection).inspection.x) < 1 &&
    !at(e.inspection).inspection.detected && at(e.detected).inspection.detected &&
    Math.abs(at(e.detected).defect.x - at(e.detected).inspection.x) < 80,
    { inspection: at(e.inspection).inspection, atInspection: at(e.inspection).defect, detection: at(e.detected).defect });
  check('pusher moves perpendicular and remains in contact', at(contactEarly).pusher.x === at(contactLate).pusher.x &&
    Math.abs((at(contactEarly).defect.y - at(contactEarly).pusher.headY) - config.mechanics.productHalfY) < 0.01 &&
    Math.abs((at(contactLate).defect.y - at(contactLate).pusher.headY) - config.mechanics.productHalfY) < 0.01 &&
    at(contactLate).pusher.headY > at(contactEarly).pusher.headY && at(contactLate).defect.y > at(contactEarly).defect.y,
    { first: { defect: at(contactEarly).defect, pusher: at(contactEarly).pusher }, second: { defect: at(contactLate).defect, pusher: at(contactLate).pusher } });
  check('cylinder contains its full rod at maximum stroke',
    states.every(s => s.pusher.bodyLength > 0 && s.pusher.exposedRodLength >= 0 &&
      s.pusher.exposedRodLength <= s.pusher.bodyLength) && at(e.ejectEnd).pusher.exposedRodLength > config.mechanics.productHalfY,
    { rest: at(0).pusher, maximum: at(e.ejectEnd).pusher, retracted: at(e.retracted).pusher });
  const landing = at(landingTime); const bin = landing.bin;
  check('defective product lands inside opposite bin',
    landing.defect.x - config.mechanics.productHalfX > bin.xMin &&
    landing.defect.x + config.mechanics.productHalfX < bin.xMax &&
    landing.defect.y - config.mechanics.productHalfY > bin.yMin &&
    landing.defect.y + config.mechanics.productHalfY < bin.yMax &&
    landing.defect.y - config.mechanics.productHalfY > landing.belt.yMax &&
    landing.defect.z === bin.floorZ && landing.pusher.retracted && at(e.retracted).pusher.retracted,
    { defect: landing.defect, bin, pusher: landing.pusher });
  const before = at(continueBefore).products.filter(p => !p.defective), after = at(continueAfter).products.filter(p => !p.defective);
  check('conforming products continue straight after rejection', before.length >= 2 && before.every(p => {
    const next = after.find(q => q.id === p.id);
    return next && Math.abs(next.x - p.x - at(continueBefore).belt.speed * (continueAfter - continueBefore)) < 0.01 &&
      next.y === p.y && next.z === p.z && Math.abs(p.y) < at(continueBefore).belt.yMax;
  }), { count: before.length, expectedTravel: at(continueBefore).belt.speed * (continueAfter - continueBefore) });
  } else {
    report.limits.push('Creative mode: no mechanical simulation or industrial validation claimed.');
  }
  const previewDir = join(outputDir, 'preview-keyframes'); await mkdir(previewDir, { recursive: true });
  const previewTimes = reviewTimes.map(time => safeTime(time, draft.fps));
  for (let i = 0; i < previewTimes.length; i++) {
    await page.evaluate(t => window.seek(t), previewTimes[i]);
    await page.screenshot({ path: join(previewDir, `frame-${String(i + 1).padStart(2, '0')}.png`), type: 'png' });
  }
  report.previewKeyframes = { dir: previewDir, times: previewTimes };
  const previewContactSheet = join(outputDir, 'contact-sheet-preview.png');
  await exec('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', '1',
    '-i', join(previewDir, 'frame-%02d.png'), '-vf', `scale=480:480:force_original_aspect_ratio=decrease,pad=480:480:(ow-iw)/2:(oh-ih)/2:color=0x101419,tile=4x${Math.ceil(previewTimes.length / 4)}`, '-frames:v', '1', previewContactSheet],
    { timeout: 30_000, maxBuffer: 1024 * 1024 });
  report.previewKeyframes.contactSheet = previewContactSheet;
  const preview = await openPage(context, server.url, requests);
  await preview.evaluate(time => window.seek(time), normalized(2));
  const playback = await preview.evaluate(() => window.playbackState());
  if (playback.playing) await preview.locator('#play-pause').click();
  const paused = await preview.evaluate(() => window.playbackState());
  await preview.waitForTimeout(250);
  const pausedAfter = await preview.evaluate(() => window.playbackState());
  check('preview pause freezes its clock', !paused.playing && !pausedAfter.playing && Math.abs(pausedAfter.time - paused.time) < 0.001,
    { paused, pausedAfter });
  await preview.locator('#play-pause').click();
  await preview.waitForTimeout(300);
  const playing = await preview.evaluate(() => window.playbackState());
  check('preview play advances its clock', playing.playing && playing.time > pausedAfter.time + 0.1,
    { before: pausedAfter, after: playing });
  await preview.locator('#play-pause').click();
  const scrubTime = safeTime(normalized(12.2), draft.fps);
  await preview.locator('#scrubber').evaluate((input, time) => { input.value = String(time); input.dispatchEvent(new Event('input', { bubbles: true })); }, scrubTime);
  const scrubbed = await preview.evaluate(() => window.playbackState());
  check('preview timeline seeks requested instant', Math.abs(scrubbed.time - scrubTime) < 0.001 && !scrubbed.playing, scrubbed);
  const declaredAssets = Object.values(config.assets ?? {}).filter(value => typeof value === 'string' && !value.startsWith('data:'));
  const assetPaths = declaredAssets.map(value => new URL(value, server.url + '/').pathname);
  check('assets loaded and no browser errors', requests.length >= 3 && requests.some(r => /\.(woff2?|ttf|otf)$/.test(r.path)) &&
    assetPaths.every(path => requests.some(request => request.path === path && request.status < 400)) &&
    report.errors.length === 0, { requests, assetPaths, errors: report.errors });
  report.resources = requests;
  await inspectWave();
  const artifactChecks = [];
  const variants = sourceOnly ? [] : requestedVariant ? [requestedVariant] : ['draft', 'master'];
  for (const variant of variants) {
    const audio = join(outputDir, `${exportName}-${variant}.mp4`);
    const silent = join(outputDir, `${exportName}-${variant}-silent.mp4`);
    const present = await Promise.all([exists(audio), exists(silent)]);
    check(`${variant} both required exports really exist`, present.every(Boolean), { audio, silent, present });
    const info = await inspectVideo(audio, variant, true);
    await inspectVideo(silent, variant, false);
    artifactChecks.push({ variant, ...await keyframes(audio, variant, info.fps) });
  }
  report.decodedKeyframes = artifactChecks;
  if (!sourceOnly) check('all requested encoded exports were inspected',
    variants.length > 0 && report.exports.length === variants.length * 2,
    { expected: variants.length * 2, inspected: report.exports.length });
  if (sourceOnly) report.limits.push('Source-only check: no encoded video inspected. Run npm run check after producing the draft/master.');
  report.passed = true;
  console.log(`VERIFIED ${report.checks.length} meaningful checks; ${report.exports.length} encoded exports inspected.`);
} catch (error) {
  report.passed = false; report.failure = error.message; process.exitCode = 1;
  console.error(`Verification stopped: ${error.message}`);
} finally {
  clearTimeout(watchdog);
  await browser?.close().catch(() => {}); await server?.close().catch(() => {});
  report.finished = new Date().toISOString();
  await writeFile(join(outputDir, 'verification.json'), JSON.stringify(report, null, 2) + '\n');
}
