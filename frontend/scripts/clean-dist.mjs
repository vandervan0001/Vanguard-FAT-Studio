import { existsSync, lstatSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// This directory contains only generated output. Never retain obsolete hashed bundles.
const dist = resolve(dirname(fileURLToPath(import.meta.url)), '../dist');
if (existsSync(dist)) {
  if (lstatSync(dist).isSymbolicLink()) throw new Error('Refus de nettoyer un lien symbolique frontend/dist.');
  rmSync(dist, { recursive: true, force: true });
}
if (existsSync(dist)) throw new Error('Le nettoyage de frontend/dist a échoué.');
