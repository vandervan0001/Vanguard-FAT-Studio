import { expect, test } from '@playwright/test';
import { actionPreview, diagnosticProfile, displayValue, nativeValue } from '../src/signal';
import type { Tag } from '../src/types';

const input: Tag = { id: 'ai', name: 'Transmetteur', direction: 'input', writable: true, data_type: 'INT', unit: 'counts', initial_value: 0, min: 0, max: 27648, node_id: '', signal: { kind: '4-20mA', raw_min: 0, raw_max: 27648, engineering_min: 10, engineering_max: 30, engineering_unit: '°C', underflow_raw: -32768, overflow_raw: 32767 } };

test('la saisie en °C, % et mA donne le même stimulus brut et préserve l’unité affichée', () => {
  expect(nativeValue(input, 20, 'engineering')).toBe(13824);
  expect(nativeValue(input, 50, 'percent')).toBe(13824);
  expect(nativeValue(input, 12, 'mA')).toBe(13824);
  expect(displayValue(input, 13824, 'engineering')).toBe(20);
  expect(displayValue(input, 13824, 'percent')).toBe(50);
});

test('les diagnostics utilisent les deux codes déclarés et refusent tout dépassement de stockage', () => {
  expect(() => nativeValue(input, 0, 'mA')).toThrow('entre 4 et 20');
  expect(nativeValue(input, 0, 'mA', true)).toBe(-32768);
  expect(nativeValue(input, 24, 'mA', true)).toBe(32767);
  expect(() => nativeValue(input, 30, 'mA', true)).toThrow('plage INT');
  expect(() => nativeValue({ ...input, signal: { ...input.signal!, overflow_raw: null } }, 24, 'mA', true)).toThrow('plage INT');
  expect(actionPreview(input, { action: 'force', target: 'ai', value: 24, unit: 'mA', diagnostic: true })).toContain('code du profil');
  expect(diagnosticProfile(input, { value: -32768, quality: 'out_of_range' })).toBe('low');
  expect(diagnosticProfile(input, { value: -32768, quality: 'bad' })).toBe(null);
  expect(diagnosticProfile({ ...input, signal: { ...input.signal!, underflow_raw: 32767 } }, { value: 32767, quality: 'out_of_range' })).toBe('profile');
});

test('la prévisualisation conserve les frontières INT et REAL du protocole', () => {
  const integer = { ...input, signal: { ...input.signal!, raw_max: 5 } };
  expect(nativeValue(integer, 50, 'percent')).toBe(2);
  expect(() => nativeValue(input, 1.5)).toThrow('entière');
  const real = { ...input, data_type: 'REAL' as const };
  expect(nativeValue(real, .1)).toBe(Math.fround(.1));
  expect(() => nativeValue({ ...input, signal: null }, 50, 'percent')).toThrow('conversion analogique');
});
