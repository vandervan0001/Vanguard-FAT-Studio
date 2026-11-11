import type { PidRotation, PidSymbolDefinition, PidSymbolPort, PidSymbolShape } from './types';

// Definitions are data, never markup. Unknown SVG attributes and URLs are not forwarded.
const paint = (value: string | undefined, fallback: string) => value && /^(?:none|currentColor|#[\da-f]{3,8})$/i.test(value) ? value : fallback;
const number = (value: number | undefined, fallback = 0) => typeof value === 'number' && Number.isFinite(value) ? value : fallback;

function Shape({ shape }: { shape: PidSymbolShape }) {
  const style = { stroke: paint(shape.stroke, 'currentColor'), fill: paint(shape.fill, 'none'), strokeWidth: number(shape.stroke_width, shape.kind !== 'rect' ? number(shape.width, 2) : 2), strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const };
  if (shape.kind === 'rect') return <rect x={number(shape.x)} y={number(shape.y)} width={number(shape.width)} height={number(shape.height)} rx={number(shape.rx)} {...style} />;
  if (shape.kind === 'circle') return <circle cx={number(shape.x)} cy={number(shape.y)} r={number(shape.radius)} {...style} />;
  if (shape.kind === 'ellipse') return <ellipse cx={number(shape.x)} cy={number(shape.y)} rx={number(shape.rx)} ry={number(shape.ry)} {...style} />;
  const points = shape.points?.filter(point => point.length >= 2 && point.every(Number.isFinite)).map(point => `${point[0]},${point[1]}`).join(' ') ?? '';
  if (shape.kind === 'polyline') return <polyline points={points} {...style} />;
  if (shape.kind === 'polygon') return <polygon points={points} {...style} />;
  return null;
}

export function rotatedPort(port: PidSymbolPort, rotation: PidRotation = 0): PidSymbolPort {
  const turns = (((rotation / 90) % 4) + 4) % 4;
  let { x, y } = port;
  for (let turn = 0; turn < turns; turn++) [x, y] = [100 - y, x];
  return { ...port, x, y };
}

export function symbolDefinition(symbols: PidSymbolDefinition[], id: string | undefined): PidSymbolDefinition | undefined {
  return symbols.find(symbol => symbol.id === id) ?? symbols.find(symbol => symbol.id === 'generic');
}

export default function PidSymbolSvg({ definition, rotation = 0, compact = false }: { definition?: PidSymbolDefinition; rotation?: PidRotation; compact?: boolean }) {
  return <svg className={`process-symbol pid-library-symbol ${compact ? 'compact' : ''}`} viewBox="0 0 100 100" fill="none" aria-hidden="true" data-symbol-kind={definition?.id ?? 'generic'}>
    <g transform={`rotate(${rotation} 50 50)`}>
      {definition?.shapes.length ? definition.shapes.map((shape, index) => <Shape key={index} shape={shape} />) : <rect x="20" y="20" width="60" height="60" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />}
    </g>
    {definition?.instrument_code && <text x="50" y="55" textAnchor="middle" fill="currentColor" stroke="none" fontFamily="Geist, sans-serif" fontSize="16" data-instrument-code={definition.instrument_code}>{definition.instrument_code}</text>}
  </svg>;
}
