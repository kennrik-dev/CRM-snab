import { type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboard, type Meter, type FlowStage } from '../api/dashboard'
import { money } from '../lib/format'

function Meters({ data }: { data: Meter[] }) {
  return (
    <div className="meters">
      {data.map((m) => (
        <div key={m.key} className="meter" style={{ '--c': `var(${m.color})` } as CSSProperties}>
          <div className="ml">
            <i />
            {m.label}
          </div>
          <div className="mv">
            {m.value}
            {m.unit ? <em>{m.unit}</em> : null}
          </div>
          <div className="seg">
            {Array.from({ length: m.seg.total }, (_, i) => (
              <span key={i} className={i < m.seg.on ? 'on' : ''} />
            ))}
          </div>
          <div className="ms">{m.amount != null ? <b>{money(m.amount)}</b> : (m.sub ?? '')}</div>
        </div>
      ))}
    </div>
  )
}

function FlowRail({ data, onGo }: { data: FlowStage[]; onGo: (route: string) => void }) {
  return (
    <div className="flowrail">
      {data.map((s) => (
        <div
          key={s.key}
          className="fstage"
          style={{ '--c': `var(${s.color})` } as CSSProperties}
          onClick={() => onGo(s.route)}
        >
          <div className="ft">
            <i />
            <span>{s.label}</span>
          </div>
          <div className="fn">{s.count}</div>
          <div className="fs">{s.sub ?? ' '}</div>
        </div>
      ))}
    </div>
  )
}

export function Dashboard() {
  const navigate = useNavigate()
  const q = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    refetchInterval: 60000,
    refetchOnWindowFocus: true,
  })

  if (q.isError) {
    return (
      <div className="wrap">
        <div className="page-h">
          <h1>Дашборд</h1>
          <span className="desc">не удалось загрузить показатели</span>
          <span className="sp" />
        </div>
      </div>
    )
  }

  // Loading skeleton (full page) — keeps the layout from jumping and lets the
  // data branch below use `d` without null-checks.
  if (!q.data) {
    return (
      <div className="wrap">
        <div className="eyebrow" style={{ margin: '0 0 10px' }}>
          Показатели · реальное время
        </div>
        <div className="meters">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="meter" style={{ '--c': 'var(--line)' } as CSSProperties}>
              <div className="ml">…</div>
              <div className="mv">…</div>
              <div className="seg">
                {Array.from({ length: 14 }, (_, j) => (
                  <span key={j} />
                ))}
              </div>
              <div className="ms">…</div>
            </div>
          ))}
        </div>
        <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
          Поток по этапам
        </div>
        <div className="flowrail" />
      </div>
    )
  }

  const d = q.data
  return (
    <div className="wrap">
      <div className="eyebrow" style={{ margin: '0 0 10px' }}>
        Показатели · реальное время
      </div>
      <Meters data={d.meters} />

      <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
        Поток по этапам
      </div>
      <FlowRail data={d.flow} onGo={(route) => navigate(route)} />

      {/* Требует внимания / Лента событий — Task 4 */}
      {/* Компактные таблицы — Task 5 */}
    </div>
  )
}
