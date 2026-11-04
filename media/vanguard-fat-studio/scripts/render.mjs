import { chromium } from 'playwright';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { once } from 'node:events';
import { mkdir, rename, rm, open, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { config } from '../config.mjs';
import { startServer, studioRoot } from './serve.mjs';

const exec = promisify(execFile);
const args = process.argv.slice(2);
if (args.some(arg => !['--master', '--draft'].includes(arg))) throw new Error('Use --draft or --master.');
const variant = args.includes('--master') ? 'master' : 'draft';
const exportName = config.exportName ?? 'film';
if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(exportName)) throw new Error('exportName must be a safe local filename stem.');
if (process.argv.includes('--master') && process.argv.includes('--draft')) throw new Error('Choose draft or master.');
if (!Number.isFinite(config.duration) || config.duration <= 0 ||
    !Number.isSafeInteger(config.width) || config.width <= 0 || config.width % 2 !== 0 ||
    !Number.isSafeInteger(config.height) || config.height <= 0 || config.height % 2 !== 0 ||
    !Number.isSafeInteger(config.fps) || config.fps <= 0) {
  throw new Error('Render config requires a positive duration, positive even pixel dimensions, and an integer frame rate.');
}
const gcd = (a, b) => b ? gcd(b, a % b) : a;
const unit = gcd(config.width, config.height);
const draftFactor = 180;
// Exact aspect ratio, even H.264 dimensions: half size where integer geometry permits it.
const width = variant === 'master' ? config.width : config.width / unit * draftFactor;
const height = variant === 'master' ? config.height : config.height / unit * draftFactor;
const fps = variant === 'master' ? config.fps : Math.min(15, config.fps);
const frames = config.duration * fps;
if (!Number.isSafeInteger(frames)) throw new Error('Duration × frame rate must produce an exact integer frame count.');
const exportsDir = join(studioRoot, 'exports');
await mkdir(exportsDir, { recursive: true });
const output = join(exportsDir, `${exportName}-${variant}.mp4`);
const silent = join(exportsDir, `${exportName}-${variant}-silent.mp4`);
const wav = join(exportsDir, 'soundtrack.wav');
const token = `${process.pid}-${Date.now()}`;
const tempSilent = join(exportsDir, `.render-${variant}-${token}-silent.tmp.mp4`);
const tempAudio = join(exportsDir, `.render-${variant}-${token}-audio.tmp.mp4`);
const lockPath = join(exportsDir, `.render-${variant}.lock`);
let lock, server, browser, encoder, stopping = false;
const errors = [];
let stderr = '';
const watchdog = setTimeout(() => {
  errors.push('Rendering exceeded the 30-minute watchdog.');
  stopping = true; encoder?.kill('SIGTERM'); browser?.close().catch(() => {});
}, 30 * 60 * 1000);
watchdog.unref();
const stop = () => {
  stopping = true; errors.push('Rendering interrupted explicitly.');
  encoder?.kill('SIGTERM'); browser?.close().catch(() => {});
};
process.once('SIGINT', stop); process.once('SIGTERM', stop);

async function probe(file, expectedAudio) {
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-count_frames', '-show_entries',
    'stream=codec_name,codec_type,width,height,pix_fmt,color_range,color_space,color_transfer,color_primaries,r_frame_rate,avg_frame_rate,nb_read_frames,duration,sample_rate:format=duration',
    '-of', 'json', file], { maxBuffer: 1024 * 1024, timeout: 60_000 });
  const result = JSON.parse(stdout);
  const video = result.streams.find(s => s.codec_type === 'video');
  const audio = result.streams.find(s => s.codec_type === 'audio');
  if (!video || video.codec_name !== 'h264' || video.width !== width || video.height !== height ||
      video.pix_fmt !== 'yuv420p' || video.r_frame_rate !== `${fps}/1` ||
      video.color_range !== 'tv' || video.color_space !== 'bt709' ||
      video.color_transfer !== 'bt709' || video.color_primaries !== 'bt709' ||
      Number(video.nb_read_frames) !== frames || Math.abs(Number(video.duration) - config.duration) > 0.0001 ||
      Math.abs(Number(result.format.duration) - config.duration) > 0.01 ||
      Boolean(audio) !== expectedAudio || (audio && audio.codec_name !== 'aac')) {
    throw new Error(`Export validation failed: ${JSON.stringify(result)}`);
  }
  return result;
}

async function command(program, args) {
  const { stderr: detail } = await exec(program, args, { timeout: 180_000, maxBuffer: 2 * 1024 * 1024 });
  return detail;
}

try {
  lock = await open(lockPath, 'wx');
  await lock.writeFile(JSON.stringify({ pid: process.pid, variant, started: new Date().toISOString() }));
  if ((await stat(wav)).size <= 44) throw new Error('Soundtrack missing or empty. Run npm run audio.');
  await command('ffmpeg', ['-version']);
  server = await startServer({ port: 0 });
  browser = await chromium.launch({ headless: true, args: ['--disable-background-timer-throttling'] });
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1,
    reducedMotion: 'no-preference', colorScheme: 'dark' });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(`JavaScript: ${error.message}`));
  page.on('console', message => { if (message.type() === 'error') errors.push(`Console: ${message.text()}`); });
  page.on('requestfailed', request => errors.push(`Resource: ${request.url()} — ${request.failure()?.errorText}`));
  page.on('response', response => { if (response.status() >= 400) errors.push(`HTTP ${response.status()}: ${response.url()}`); });
  await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1'
    ? route.continue() : route.abort('blockedbyclient'));
  await page.goto(`${server.url}/?render=1&width=${width}&height=${height}`, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.waitForFunction(() => Boolean(window.ready), { timeout: 15_000 });
  await page.evaluate(() => window.ready);
  const captures = await page.evaluate(() => window.captureManifest);
  if(captures.status!=='ui-frozen-real-demo'||!captures.transcript?.lines?.length||['pid','bool','analog','timed','guided','trends','report','archive'].some(id=>!captures.shots[id]?.length))throw Error('All actual demo captures and real CLI transcript are required before rendering.');
  const geometry = await page.evaluate(() => {
    const canvas = document.querySelector('canvas'); const bounds = canvas.getBoundingClientRect();
    return { width: canvas.width, height: canvas.height, x: bounds.x, y: bounds.y,
      boxWidth: bounds.width, boxHeight: bounds.height, visibility: document.visibilityState };
  });
  if (geometry.width !== width || geometry.height !== height || geometry.x !== 0 || geometry.y !== 0 ||
      geometry.boxWidth !== width || geometry.boxHeight !== height || geometry.visibility !== 'visible') {
    throw new Error(`Canvas/viewport mismatch: ${JSON.stringify(geometry)}`);
  }
  if (errors.length) throw new Error(errors.join('\n'));
  const ffmpegArgs = ['-hide_banner', '-loglevel', 'warning', '-n', '-f', 'image2pipe', '-vcodec', 'png',
    '-framerate', String(fps), '-i', 'pipe:0', '-an', '-frames:v', String(frames),
    '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709', '-c:v', 'libx264',
    '-preset', 'medium', '-crf', variant === 'master' ? '17' : '20', '-pix_fmt', 'yuv420p',
    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
    '-movflags', '+faststart', tempSilent];
  encoder = spawn('ffmpeg', ffmpegArgs, { stdio: ['pipe', 'ignore', 'pipe'] });
  encoder.stderr.setEncoding('utf8');
  encoder.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-16_384); });
  let encoderError;
  encoder.on('error', error => { encoderError = error; });
  encoder.stdin.on('error', error => { encoderError = error; });
  const exited = new Promise(resolve => encoder.once('close', (code, signal) => resolve({ code, signal })));
  const started = Date.now();
  console.log(`Rendering ${variant}: ${width}×${height}, ${fps} fps, ${frames} frames, CRF ${variant === 'master' ? 17 : 20}.`);
  for (let frame = 0; frame < frames; frame++) {
    if (stopping || encoderError || errors.length || encoder.exitCode !== null) {
      throw new Error([encoderError?.message, ...errors, stderr].filter(Boolean).join('\n') || 'FFmpeg exited before the final frame.');
    }
    await page.evaluate(t => window.seek(t), frame / fps);
    const png = await page.screenshot({ type: 'png', animations: 'disabled', timeout: 15_000 });
    if (!encoder.stdin.write(png)) await once(encoder.stdin, 'drain');
    if ((frame + 1) % fps === 0 || frame === frames - 1) {
      console.log(`${frame + 1}/${frames} frames — ${((frame + 1) / frames * 100).toFixed(0)}% — ${((Date.now() - started) / 1000).toFixed(1)} s elapsed`);
    }
  }
  encoder.stdin.end();
  const verdict = await exited;
  if (verdict.code !== 0 || encoderError || stopping || errors.length) {
    throw new Error(`FFmpeg failed (${verdict.code}, ${verdict.signal}): ${encoderError?.message ?? ''}\n${errors.join('\n')}\n${stderr}`);
  }
  const silentProbe = await probe(tempSilent, false);
  await command('ffmpeg', ['-hide_banner', '-loglevel', 'warning', '-n', '-i', tempSilent, '-i', wav,
    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
    '-t', String(config.duration), '-movflags', '+faststart', tempAudio]);
  const audioProbe = await probe(tempAudio, true);
  // These exact generated exports belong to this script. Replace them only after both files validate.
  await rename(tempSilent, silent);
  await rename(tempAudio, output);
  await writeFile(join(exportsDir, `render-${variant}.json`), JSON.stringify({
    variant, width, height, fps, frames, duration: config.duration, startedAt: new Date(started).toISOString(),
    elapsedSeconds: (Date.now() - started) / 1000, browser: await browser.version(),
    node: process.version, output, silent, codec: 'libx264', crf: variant === 'master' ? 17 : 20,
    screenshot: 'sequential compressed PNG, no accumulated frame buffer', ffmpegArgs,
    silentProbe, audioProbe, browserErrors: errors,
  }, null, 2) + '\n');
  console.log(`VERIFIED ${frames} frames / ${config.duration} s:\n${output}\n${silent}`);
} catch (error) {
  console.error(`Render stopped: ${error.message}`);
  process.exitCode = 1;
} finally {
  clearTimeout(watchdog);
  process.removeListener('SIGINT', stop); process.removeListener('SIGTERM', stop);
  if (encoder && encoder.exitCode === null) encoder.kill('SIGTERM');
  await browser?.close().catch(() => {});
  await server?.close().catch(() => {});
  await rm(tempSilent, { force: true }); await rm(tempAudio, { force: true });
  if (lock) { await lock.close(); await rm(lockPath, { force: true }); }
}
