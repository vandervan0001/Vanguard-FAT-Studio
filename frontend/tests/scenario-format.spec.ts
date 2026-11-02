import { expect, test } from '@playwright/test';
import { parseScenarioSteps } from '../src/scenarioFormat';

test('refuse des objets à la place du texte avant de les exposer à React', () => {
  expect(() => parseScenarioSteps('[{"at_s":0,"action":"marker","message":{"html":"<script>"}}]', 10)).toThrow('message doit être du texte');
  expect(() => parseScenarioSteps('[{"at_s":0,"action":"force","target":[],"value":4}]', 10)).toThrow('target doit être un identifiant');
});

test('refuse un temps infini et une séquence hors ordre ou durée', () => {
  expect(() => parseScenarioSteps('[{"at_s":1e400,"action":"marker"}]', 10)).toThrow('temps fini');
  expect(() => parseScenarioSteps('[{"at_s":8,"action":"marker"},{"at_s":2,"action":"marker"}]', 10)).toThrow('temps croissant');
  expect(() => parseScenarioSteps('[{"at_s":12,"action":"marker"}]', 10)).toThrow('durée');
});

test('préserve les vrais booléens, les valeurs négatives et les étapes au même instant', () => {
  const result = parseScenarioSteps('[{"at_s":0,"action":"force","target":"level","value":-1.25},{"at_s":0,"action":"expect","target":"pump_cmd","value":false},{"at_s":3,"action":"fault","target":"P101","value":{"kind":"motor_trip"}}]', 10);
  expect(result[0].value).toBe(-1.25);
  expect(result[1].value).toBe(false);
  expect(result[2].value).toEqual({ kind: 'motor_trip' });
});

test('signale champs inconnus et mauvaises valeurs de défaut sans les supprimer', () => {
  expect(() => parseScenarioSteps('[{"at_s":0,"action":"marker","download":true}]', 10)).toThrow('champ(s) inconnu(s)');
  expect(() => parseScenarioSteps('[{"at_s":0,"action":"fault","target":"P101","value":{"kind":"motor_trip","value":[]}}]', 10)).toThrow('numérique ou booléenne');
});
