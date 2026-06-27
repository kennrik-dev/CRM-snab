import { type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  getDashboard,
  type Meter,
  type FlowStage,
  type AttentionItem,
  type FeedItem,
} from '../api/dashboard'
import { relTime, targetRoute, feedRoute } from '../lib/dashView'
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

function AttentionPanel({
  data,
  onOpen,
}: {
  data: AttentionItem[]
  onOpen: (route: string) => void
}) {
  const shown = data.slice(0, 20)
  const rest = data.length - shown.length
  return (
    <div className="panel">
      <div className="phead">
        <h2>Требует внимания</h2>
        <span className="cnt">{data.length}</span>
        <span className="sp" />
      </div>
      {shown.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Всё под контролем
        </div>
      ) : (
        shown.map((a, i) => {
          const route = targetRoute(a.target)
          return (
            <div
              key={i}
              className="alert"
              style={{
                '--al': `var(${a.severity === 'error' ? 'late' : 'proc'})`,
              } as CSSProperties}
            >
              <span className="aid">{a.id_label}</span>
              <span className="at">{a.text}</span>
              <button
                className="ab"
                disabled={!route}
                onClick={() => route && onOpen(route)}
              >
                Открыть
              </button>
            </div>
          )
        })
      )}
      {rest > 0 && (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          и ещё {rest}
        </div>
      )}
    </div>
  )
}

function FeedPanel({
  data,
  onOpen,
}: {
  data: FeedItem[]
  onOpen: (route: string) => void
}) {
  return (
    <div className="panel">
      <div className="phead">
        <h2>Лента событий</h2>
        <span className="sp" />
      </div>
      {data.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Пока нет событий
        </div>
      ) : (
        data.map((f, i) => {
          const route = feedRoute(f.target)
          return (
            <div
              key={i}
              className="fitem"
              style={route ? { cursor: 'pointer' } : undefined}
              onClick={route ? () => onOpen(route) : undefined}
            >
              <span className="ft2">{relTime(f.created_at)}</span>
              <div>
                <b>{f.actor}</b>{' '}
                <span>
                  {f.action_label}
                  {f.entity_display ? ` ${f.entity_display}` : ''}
                </span>
              </div>
            </div>
          )
        })
      )}
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

      <div className="grid2">
        <AttentionPanel
          data={d.attention}
          onOpen={(route) => navigate(route)}
        />
        <FeedPanel data={d.feed} onOpen={(route) => navigate(route)} />
      </div>
      {/* Компактные таблицы — Task 5 */}
    </div>
  )
}
