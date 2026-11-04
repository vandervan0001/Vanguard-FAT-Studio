import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const STUDIO = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TAU = Math.PI * 2;
const DEFAULT_EVENTS = Object.freeze({
  inspection: 4.8,
  detected: 5.12,
  signal: 7.25,
  ejectStart: 11.85,
  ejectContact: 12.05,
  ejectEnd: 12.6,
  retracted: 13.25,
  signature: 16.4,
});

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const smooth = (x) => {
  const y = clamp(x);
  return y * y * (3 - 2 * y);
};
const db = (x) => (x > 0 ? 20 * Math.log10(x) : null);
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);

/**
 * Original additive synthesis, deterministic seeded noise, no samples or services.
 * Mode-specific original synthesis: fast ads groove or restrained engineering bed.
 * Shared timing accents, seeded noise and stereo PCM at 48 kHz with quiet edges.
 */
export async function generateSoundtrack({
  duration = 20,
  sampleRate = 48000,
  events = {},
  mode = 'ads',
  bpm = mode === 'ads' ? 128 : 96,
  accents = [],
  outputPath = resolve(STUDIO, 'exports/soundtrack.wav'),
} = {}) {
  if (!Number.isFinite(duration) || duration < 1 || duration > 300) {
    throw new Error('Audio duration must be between 1 and 300 seconds.');
  }
  if (sampleRate !== 48000) throw new Error('This soundtrack uses 48 kHz.');
  if (!['ads', 'engineering'].includes(mode)) throw new Error('Audio mode must be ads or engineering.');
  if (!Number.isFinite(bpm) || bpm < 40 || bpm > 240) throw new Error('BPM must be between 40 and 240.');
  if (!Array.isArray(accents)) throw new Error('audio.accents must be an array.');
  const timing = Object.fromEntries(Object.entries(DEFAULT_EVENTS).map(([key, at]) => [key, at * duration / 20]));
  for (const key of Object.keys(timing)) if (events[key] !== undefined) timing[key] = events[key];
  for (const accent of accents) {
    if (!Number.isFinite(accent.time) || accent.time < 0 || accent.time >= duration ||
        !['impact', 'whoosh', 'transition', 'tick', 'rise', 'resolve'].includes(accent.type)) {
      throw new Error('Invalid audio accent: ' + JSON.stringify(accent));
    }
  }
  for (const [name, at] of Object.entries(timing)) {
    if (!Number.isFinite(at) || at < 0 || at >= duration) {
      throw new Error('Invalid audio event ' + name + ': ' + at);
    }
  }
  const frames = Math.round(duration * sampleRate);
  const left = new Float64Array(frames);
  const right = new Float64Array(frames);
  const noise = new Float64Array(frames);
  const lowNoise = new Float64Array(frames);
  const highNoise = new Float64Array(frames);
  let seed = 0x4d4f544e;
  let low = 0;
  let bright = 0;
  for (let i = 0; i < frames; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const white = (seed / 4294967296) * 2 - 1;
    low += 0.016 * (white - low);
    bright += 0.2 * (white - bright);
    noise[i] = white;
    lowNoise[i] = low;
    highNoise[i] = white - bright;
  }
  const soundEvents = [];

  function layer(start, length, pan, fn) {
    const a = Math.max(0, Math.floor(start * sampleRate));
    const b = Math.min(frames, Math.ceil((start + length) * sampleRate));
    const l = Math.cos(((clamp(pan, -1, 1) + 1) * Math.PI) / 4);
    const r = Math.sin(((clamp(pan, -1, 1) + 1) * Math.PI) / 4);
    for (let i = a; i < b; i++) {
      const t = i / sampleRate - start;
      const value = fn(t, i);
      left[i] += value * l;
      right[i] += value * r;
    }
  }

  function pad(start, length, notes, amplitude) {
    notes.forEach((note, j) => {
      const frequency = hz(note);
      const pan = [-0.55, 0.25, -0.12, 0.56][j % 4];
      layer(start, length, pan, (t) => {
        const envelope = smooth(t / 1.3) * smooth((length - t) / 1.5);
        const shimmer = 0.9 + 0.1 * Math.sin(TAU * 0.19 * t + j);
        const base = Math.sin(TAU * frequency * t + j * 0.8);
        const detune = Math.sin(TAU * frequency * 1.0018 * t + j * 1.9);
        const harmonic = Math.sin(TAU * frequency * 2 * t + 0.1 * Math.sin(TAU * 0.15 * t));
        return amplitude * envelope * shimmer * (base * 0.65 + detune * 0.25 + harmonic * 0.1);
      });
    });
  }

  function pluck(at, note, amplitude, pan = 0, decay = 0.45) {
    const frequency = hz(note);
    layer(at, decay * 6, pan, (t) => {
      const envelope = smooth(t / 0.011) * Math.exp(-t / decay);
      const tone = Math.sin(TAU * frequency * t) + 0.18 * Math.sin(TAU * frequency * 2 * t);
      return amplitude * envelope * tone;
    });
  }

  function metal(at, length, amplitude, pan, frequencies, label) {
    layer(at, length, pan, (t, i) => {
      const envelope = smooth(t / 0.002) * Math.exp(-t / (length * 0.19)) * smooth((length - t) / 0.03);
      let tone = 0;
      frequencies.forEach((f, j) => {
        tone += Math.sin(TAU * f * t + j * 0.4) * Math.exp(-t * j * 1.8) / (1 + j * 1.4);
      });
      return amplitude * envelope * (tone * 0.65 + noise[i] * Math.exp(-t / 0.012) * 0.16);
    });
    soundEvents.push({ name: label, seconds: at, lengthSeconds: length, pan });
  }

  function air(at, length, amplitude, pan, label) {
    layer(at, length, pan, (t, i) => {
      const envelope = smooth(t / 0.016) * smooth((length - t) / 0.08);
      const pressure = 0.72 + 0.28 * Math.exp(-t / 0.07);
      const body = 0.11 * Math.sin(TAU * (126 * t - 12 * t * t));
      return amplitude * envelope * pressure * (highNoise[i] * 0.4 + lowNoise[i] * 1.5 + body);
    });
    soundEvents.push({ name: label, seconds: at, lengthSeconds: length, pan });
  }

  if (mode === 'engineering') {
  // Warm, sparse harmony. Overlapping fades retain continuity across camera moves.
  pad(0, 7.5 * duration / 20, [50, 57, 64, 65], 0.038);
  pad(6.0 * duration / 20, 6.6 * duration / 20, [50, 55, 60, 64], 0.033);
  pad(11.2 * duration / 20, 6.2 * duration / 20, [50, 57, 62, 64], 0.034);
  pad(timing.signature - 0.6, duration - timing.signature + 0.6, [50, 57, 62, 66], 0.039);

  const beat = 60 / bpm;
  const bassPattern = [38, 45, 50, 45, 38, 45, 52, 45];
  for (let n = 0, at = 0.38; at < timing.signature - 0.5; n++, at += beat) {
    const note = bassPattern[n % bassPattern.length];
    pluck(at, note, n % 4 === 0 ? 0.087 : 0.049, Math.sin(n * 0.68) * 0.18, 0.36);
    if (n % 2 === 0 && at > 2.7) pluck(at + 0.3125, 69 + (n % 8 === 2 ? 2 : 0), 0.010, 0.3, 0.22);
  }

  // Conveyor low-frequency texture follows the process, fades before the signature.
  const machineEnd = Math.min(duration, timing.signature + 0.12);
  layer(0, machineEnd, 0.08, (t, i) => {
    const envelope = smooth(t / 0.4) * smooth((machineEnd - t) / 0.95);
    const motor = Math.sin(TAU * 81 * t + 0.035 * Math.sin(TAU * 1.7 * t));
    const bearings = 0.4 * Math.sin(TAU * 162 * t) + 0.18 * Math.sin(TAU * 486 * t);
    const speed = 0.87 + 0.13 * Math.sin(TAU * 5.8 * t);
    return envelope * (0.013 * (motor + bearings) * speed + lowNoise[i] * 0.035 + noise[i] * 0.0015);
  });
  soundEvents.push({ name: 'conveyor-bed', seconds: 0, lengthSeconds: machineEnd, pan: 0.08 });

  // Inspection sounds use two clean restrained tones, with no alarm or spoken cue.
  metal(timing.inspection, 0.35, 0.038, -0.18, [1174.66, 2349.32], 'inspection');
  metal(timing.detected, 0.55, 0.039, -0.1, [880, 1318.51, 1760], 'defect-confirmed');

  // Signal accents progress across the frame toward the command output.
  const signalOffsets = [0, 0.55, 1.1, 1.55];
  signalOffsets.forEach((offset, n) => {
    const at = timing.signal + offset;
    pluck(at, [76, 69, 74, 81][n], n === 3 ? 0.027 : 0.018, -0.4 + n * 0.27, 0.17);
    soundEvents.push({ name: 'signal-' + (n + 1), seconds: at, lengthSeconds: 1.02, pan: -0.4 + n * 0.27 });
  });

  // Piston extension, contact, collection bin, then retraction. No oversized impacts.
  air(timing.ejectStart, timing.ejectEnd - timing.ejectStart + 0.09, 0.085, -0.1, 'piston-extension');
  metal(timing.ejectContact, 0.23, 0.059, 0.02, [171, 513, 1026], 'pusher-contact');
  metal(timing.ejectEnd, 0.75, 0.052, 0.36, [225, 681, 1185, 2049], 'bin-impact');
  air(timing.retracted - 0.35, 0.38, 0.055, -0.1, 'piston-retraction');
  metal(timing.retracted, 0.2, 0.026, -0.1, [260, 780], 'piston-home');

  // Final restrained resolved chord, with enough decay to support a readable end frame.
  pluck(timing.signature + 0.1, 62, 0.040, -0.1, 0.82);
  pluck(timing.signature + 0.22, 69, 0.020, 0.25, 0.82);
  soundEvents.push({ name: 'signature-resolution', seconds: timing.signature + 0.1, lengthSeconds: duration - timing.signature - 0.1, pan: 0 });

  } else {
  // Ads: tight 128 BPM groove; visual transitions can accent the shared time grid.
  // All oscillators/noise are generated locally; no downloaded music or paid service.
  const beat = 60 / bpm;
  const signature = Math.min(duration - 0.3, Math.max(0.3, timing.signature));
  pad(0, duration * 0.38, [50, 57, 62, 64], 0.030);
  pad(duration * 0.30, duration * 0.40, [48, 55, 60, 64], 0.028);
  pad(duration * 0.62, duration * 0.38, [50, 57, 62, 66], 0.031);
  const bass = [38, 38, 45, 50, 38, 45, 48, 45];
  function kick(at, strength = 1) {
    layer(at, 0.30, 0, t => {
      const phase = TAU * (47 * t + 80 * 0.030 * (1 - Math.exp(-t / 0.030)));
      return 0.20 * strength * smooth(t / 0.0025) * Math.exp(-t / 0.11) * Math.sin(phase);
    });
  }
  for (let n = 0, at = 0; at < signature; n++, at = n * beat) {
    const phrase = Math.floor(n / 8);
    kick(at, n % 4 === 0 ? 1 : 0.82);
    pluck(at + 0.025, bass[n % bass.length], n % 4 === 0 ? 0.098 : 0.074, -0.1, 0.12);
    if (n % 4 === 1 || n % 4 === 3) {
      layer(at, 0.21, 0.08, (t, i) => 0.11 * smooth(t / 0.002) * Math.exp(-t / 0.047) *
        (highNoise[i] * 0.7 + 0.3 * Math.sin(TAU * 185 * t)));
    }
    for (let half = 0; half < 2; half++) {
      layer(at + half * beat / 2, 0.083, half ? 0.35 : -0.35, (t, i) =>
        0.038 * smooth(t / 0.0015) * Math.exp(-t / 0.020) * highNoise[i]);
    }
    if (phrase > 0 && n % 2 === 0) {
      pluck(at + beat / 2, [74, 69, 76, 81][n % 4], 0.023, 0.4, 0.13);
    }
    if (phrase % 3 === 2 && n % 4 === 3) {
      metal(at + beat * 0.75, 0.18, 0.023, -0.4, [1500, 2771, 4023], 'phrase-fill');
    }
  }
  const cueList = accents.length ? accents : [
    { time: duration * 0.08, type: 'impact' },
    { time: duration * 0.31, type: 'whoosh' },
    { time: duration * 0.55, type: 'impact' },
    { time: signature, type: 'resolve' },
  ];
  for (const cue of cueList) {
    const at = cue.time;
    const amplitude = Number.isFinite(cue.amplitude) ? clamp(cue.amplitude, 0, 0.25) : 0.10;
    if (cue.type === 'impact') {
      kick(at, 1.2);
      metal(at, 0.43, amplitude * 0.45, 0, [120, 360, 780], 'transition-impact');
    } else if (cue.type === 'whoosh' || cue.type === 'transition' || cue.type === 'rise') {
      const length = cue.type === 'rise' ? 0.75 : 0.34;
      layer(at - Math.min(at, length * 0.45), length, 0.13, (t, i) => {
        const envelope = Math.sin(Math.PI * clamp(t / length)) ** 2;
        return amplitude * envelope * (highNoise[i] * 0.55 + lowNoise[i] * 0.7);
      });
      soundEvents.push({ name: cue.type, seconds: at, lengthSeconds: length, pan: 0.13 });
    } else if (cue.type === 'tick') {
      metal(at, 0.16, amplitude * 0.36, 0.25, [1700, 3300], 'type-accent');
    } else if (cue.type === 'resolve') {
      [62, 66, 69, 74].forEach((note, j) => pluck(at + j * 0.022, note, 0.047 / (1 + j * 0.4), -0.35 + j * 0.23, 0.7));
      soundEvents.push({ name: 'brand-resolution', seconds: at, lengthSeconds: duration - at, pan: 0 });
    }
  }
  soundEvents.push({ name: 'ads-groove', seconds: 0, lengthSeconds: signature, pan: 0 });
  }

  // A fixed smooth edge envelope prevents initial/end clicks without shortening the file.
  let prePeak = 0;
  let preSquares = 0;
  for (let i = 0; i < frames; i++) {
    const t = i / sampleRate;
    const edge = smooth((t - 0.025) / 0.32) * smooth((duration - 0.04 - t) / 0.82);
    const compressionDrive = mode === 'ads' ? 5 : 1;
    left[i] = Math.tanh(left[i] * compressionDrive) * edge;
    right[i] = Math.tanh(right[i] * compressionDrive) * edge;
    prePeak = Math.max(prePeak, Math.abs(left[i]), Math.abs(right[i]));
    preSquares += left[i] ** 2 + right[i] ** 2;
  }
  const rawRms = Math.sqrt(preSquares / (frames * 2));
  const gain = Math.min((mode === 'ads' ? 0.15 : 0.112) / rawRms, (mode === 'ads' ? 0.60 : 0.69) / prePeak);
  const pcm = Buffer.alloc(frames * 4);
  let peak = 0;
  let squares = 0;
  let sum = 0;
  let clippedSamples = 0;
  let firstNonzeroFrame = -1;
  let lastNonzeroFrame = -1;
  let start25msPeak = 0;
  let end25msPeak = 0;
  for (let i = 0; i < frames; i++) {
    for (let channel = 0; channel < 2; channel++) {
      const value = (channel === 0 ? left[i] : right[i]) * gain;
      if (!Number.isFinite(value)) throw new Error('Non-finite synthesized sample.');
      if (Math.abs(value) >= 1) clippedSamples++;
      const integer = Math.round(clamp(value, -1, 1) * 32767);
      pcm.writeInt16LE(integer, i * 4 + channel * 2);
      const quantized = integer / 32768;
      peak = Math.max(peak, Math.abs(quantized));
      squares += quantized ** 2;
      sum += quantized;
      if (i < sampleRate * 0.025) start25msPeak = Math.max(start25msPeak, Math.abs(quantized));
      if (i >= frames - sampleRate * 0.025) end25msPeak = Math.max(end25msPeak, Math.abs(quantized));
      if (integer !== 0) {
        if (firstNonzeroFrame === -1) firstNonzeroFrame = i;
        lastNonzeroFrame = i;
      }
    }
  }
  const wavHeader = Buffer.alloc(44);
  wavHeader.write('RIFF', 0);
  wavHeader.writeUInt32LE(36 + pcm.length, 4);
  wavHeader.write('WAVEfmt ', 8);
  wavHeader.writeUInt32LE(16, 16);
  wavHeader.writeUInt16LE(1, 20);
  wavHeader.writeUInt16LE(2, 22);
  wavHeader.writeUInt32LE(sampleRate, 24);
  wavHeader.writeUInt32LE(sampleRate * 4, 28);
  wavHeader.writeUInt16LE(4, 32);
  wavHeader.writeUInt16LE(16, 34);
  wavHeader.write('data', 36);
  wavHeader.writeUInt32LE(pcm.length, 40);

  const rms = Math.sqrt(squares / (frames * 2));
  const report = {
    format: 'pcm_s16le',
    sampleRate,
    channels: 2,
    durationSeconds: frames / sampleRate,
    sampleFrames: frames,
    samplePeak: peak,
    samplePeakDbFS: db(peak),
    rms,
    rmsDbFS: db(rms),
    meanDc: sum / (frames * 2),
    clippedSamples,
    start25msPeak,
    end25msPeak,
    initialSilenceSeconds: firstNonzeroFrame / sampleRate,
    trailingSilenceSeconds: (frames - lastNonzeroFrame - 1) / sampleRate,
    gain,
    seed: '0x4d4f544e',
    mode,
    bpm,
    pcmSha256: createHash('sha256').update(pcm).digest('hex'),
    events: soundEvents.sort((a, b) => a.seconds - b.seconds),
    source: 'Original local additive synthesis and seeded noise; no samples, API or downloads.',
    listeningVerified: false,
    limitation: mode === 'engineering'
      ? 'Synthetic illustrative machine sounds; not recordings of specific equipment. Auditory review not performed.'
      : 'Original synthesized rhythmic music and accents. Auditory review not performed.',
  };
  if (clippedSamples !== 0 || start25msPeak !== 0 || end25msPeak !== 0 || rms < 0.01) {
    throw new Error('Audio safety/non-silence checks failed: ' + JSON.stringify(report));
  }
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, Buffer.concat([wavHeader, pcm]));
  const reportPath = resolve(dirname(outputPath), 'audio-report.json');
  await writeFile(reportPath, JSON.stringify(report, null, 2) + '\n');
  return { outputPath, reportPath, report };
}

export function inspectSoundtrack(outputPath, expectedDuration) {
  const probe = spawnSync('ffprobe', [
    '-v', 'error', '-show_entries', 'stream=codec_name,sample_rate,channels,duration',
    '-show_entries', 'format=duration', '-of', 'json', outputPath,
  ], { encoding: 'utf8', timeout: 30000 });
  if (probe.error || probe.status !== 0) throw new Error('ffprobe failed: ' + (probe.error?.message ?? probe.stderr));
  const metadata = JSON.parse(probe.stdout);
  const stream = metadata.streams?.[0];
  if (stream?.codec_name !== 'pcm_s16le' || Number(stream.sample_rate) !== 48000 || stream.channels !== 2) {
    throw new Error('Unexpected audio format: ' + JSON.stringify(metadata));
  }
  if (Math.abs(Number(metadata.format.duration) - expectedDuration) > 1 / 48000) {
    throw new Error('Incorrect audio duration: ' + metadata.format.duration);
  }
  const analysis = spawnSync('ffmpeg', [
    '-hide_banner', '-nostdin', '-nostats', '-i', outputPath,
    '-af', 'ebur128=peak=true:framelog=verbose', '-f', 'null', '-',
  ], { encoding: 'utf8', timeout: 30000, maxBuffer: 512 * 1024 });
  if (analysis.error || analysis.status !== 0) throw new Error('FFmpeg audio analysis failed: ' + (analysis.error?.message ?? analysis.stderr));
  const loudness = analysis.stderr.match(/Integrated loudness:\s*I:\s*(-?[\d.]+) LUFS/);
  const truePeak = analysis.stderr.match(/True peak:\s*Peak:\s*(-?[\d.]+) dBFS/);
  const range = analysis.stderr.match(/Loudness range:\s*LRA:\s*(-?[\d.]+) LU/);
  if (!loudness || !truePeak || !range) throw new Error('FFmpeg did not produce a complete loudness verdict.');
  const measured = {
    integratedLoudnessLUFS: Number(loudness[1]),
    truePeakDbFS: Number(truePeak[1]),
    loudnessRangeLU: Number(range[1]),
    probedDurationSeconds: Number(metadata.format.duration),
    probedCodec: stream.codec_name,
    probedSampleRate: Number(stream.sample_rate),
    probedChannels: stream.channels,
  };
  if (measured.truePeakDbFS >= -1 || measured.integratedLoudnessLUFS < -35) {
    throw new Error('Audio is clipped or unexpectedly quiet: ' + JSON.stringify(measured));
  }
  return measured;
}

async function main() {
  const argv = process.argv.slice(2);
  const flag = (name) => {
    const index = argv.indexOf(name);
    if (index === -1) return undefined;
    if (!argv[index + 1] || argv[index + 1].startsWith('--')) throw new Error('Missing value for ' + name);
    return argv[index + 1];
  };
  // The canonical editorial config is preferred; standalone use retains the same defaults.
  let config = {};
  const configPath = resolve(STUDIO, flag('--config') ?? 'config.mjs');
  try {
    await readFile(configPath);
    const module = await import(pathToFileURL(configPath).href);
    config = module.config ?? module.CONFIG ?? module.default ?? {};
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    if (flag('--config')) throw error;
  }
  const result = await generateSoundtrack({
    duration: flag('--duration') ? Number(flag('--duration')) : (config.duration ?? 20),
    events: config.events ?? {},
    mode: config.mode ?? 'ads',
    bpm: config.bpm ?? config.audio?.bpm ?? (config.mode === 'engineering' ? 96 : 128),
    accents: config.audio?.accents ?? [],
    outputPath: flag('--out') ? resolve(flag('--out')) : resolve(STUDIO, 'exports/soundtrack.wav'),
  });
  result.report.ffmpegVerification = inspectSoundtrack(result.outputPath, result.report.durationSeconds);
  await writeFile(result.reportPath, JSON.stringify(result.report, null, 2) + '\n');
  console.log(JSON.stringify({
    audio: result.outputPath,
    report: result.reportPath,
    duration: result.report.durationSeconds,
    peakDbFS: result.report.samplePeakDbFS,
    rmsDbFS: result.report.rmsDbFS,
    clippedSamples: result.report.clippedSamples,
    pcmSha256: result.report.pcmSha256,
    ...result.report.ffmpegVerification,
  }, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => {
    console.error(error.stack ?? error.message);
    process.exitCode = 1;
  });
}
