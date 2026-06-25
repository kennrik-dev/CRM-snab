import { overdueMod } from '../../lib/supportView'

/** Пилюля просрочки: `.ovd` (зелёный 0%) / `.w` (оранжевый 1–49%) / `.b` (красный ≥50%). */
export function OverduePct({ overduePct }: { overduePct: number }) {
  const pct = Math.round(overduePct)
  return <span className={`ovd${overdueMod(overduePct)}`}>{pct}%</span>
}
