import { type CSSProperties, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  getDashboard,
  type Meter,
  type FlowStage,
  type AttentionItem,
  type FeedItem,
  type DashboardTables,
  type AwaitingRow,
  type ProcurementRow,
  type SupportRow,
} from '../api/dashboard'
import { relTime, targetRoute, feedRoute } from '../lib/dashView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { Chip } from '../components/Chip'
import { postavkiStatusChip, procStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'

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

function CompactTables({
  data,
  onRow,
  onSection,
}: {
  data: DashboardTables
  onRow: (route: string) => void
  onSection: (route: string) => void
}) {
  const awaitingCols: DataTableColumn<AwaitingRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'mtr', header: 'Тип МТР', render: (r) => r.mtr ?? '—' },
    { key: 'srok', header: 'Срок', render: (r) => dateRu(r.srok) },
    { key: 'position_count', header: 'Поз.', align: 'center', width: '10%' },
    { key: 'status', header: 'Статус', width: '18%' },
  ]

  const procurementCols: DataTableColumn<ProcurementRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'num', header: '№ заявки', render: (r) => r.num ?? '—' },
    { key: 'supplier', header: 'Поставщик', render: (r) => r.supplier ?? '—' },
    { key: 'position_count', header: 'Поз.', align: 'center', width: '10%' },
    {
      key: 'status_zakup',
      header: 'Статус',
      width: '18%',
      render: (r) => <Chip {...procStatusChip(r.status_zakup)} mini />,
    },
  ]

  const supportCols: DataTableColumn<SupportRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'num', header: '№ заявки', render: (r) => r.num ?? '—' },
    { key: 'supplier', header: 'Поставщик', render: (r) => r.supplier ?? '—' },
    {
      key: 'contract_sum',
      header: 'Сумма договора',
      align: 'right',
      render: (r) => <span className="dt">{money(r.contract_sum)}</span>,
    },
    {
      key: 'status_postavki',
      header: 'Статус поставки',
      width: '16%',
      render: (r) => <Chip {...postavkiStatusChip(r.status_postavki)} mini />,
    },
    {
      key: 'overdue_pct',
      header: 'Просроч.',
      align: 'center',
      width: '10%',
      render: (r) => {
        const v = Math.round(r.overdue_pct)
        const cls = v >= 50 ? 'b' : v > 0 ? 'w' : ''
        return <span className={`ovd ${cls}`}>{v}%</span>
      },
    },
    {
      key: 'progress',
      header: 'Прогресс',
      align: 'center',
      width: '14%',
      render: (r) => {
        const pct = r.total ? Math.round((r.delivered / r.total) * 100) : 0
        return (
          <div className="prog">
            <div className="bar">
              <i style={{ width: `${pct}%` }} />
            </div>
            <span className="pn">
              <b>{r.delivered}</b>/{r.total}
            </span>
          </div>
        )
      },
    },
  ]

  const block = (
    num: string,
    color: string,
    title: string,
    eng: string,
    total: number,
    route: string,
    inner: ReactNode,
  ) => (
    <div className="block" style={{ '--bc': `var(${color})` } as CSSProperties}>
      <div className="block-h">
        <span className="bnum">{num}</span>
        <div>
          <div className="btitle">{title}</div>
          <div className="beng">{eng}</div>
        </div>
        <span className="bcount">{total}</span>
        <span className="sp" />
        <button className="blink" onClick={() => onSection(route)}>
          Открыть раздел →
        </button>
      </div>
      <div className="tbl-scroll">{inner}</div>
    </div>
  )

  return (
    <>
      <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
        Заявки по этапам
      </div>
      {block('1', 'wait', 'Ожидают закупки', 'Awaiting', data.awaiting.total, '/komplektaciya',
        <DataTable<AwaitingRow>
          className="fit"
          columns={awaitingCols}
          rows={data.awaiting.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/komplektaciya/${r.id}`)}
          empty={<span className="empty-state">Нет заявок</span>}
        />,
      )}
      {block('2', 'proc', 'В закупке', 'In procurement', data.procurement.total, '/zakupka',
        <DataTable<ProcurementRow>
          className="fit"
          columns={procurementCols}
          rows={data.procurement.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/zakupka/${r.id}`)}
          empty={<span className="empty-state">Нет процедур</span>}
        />,
      )}
      {block('3', 'supp', 'В сопровождении', 'In support', data.support.total, '/soprovozhdenie',
        <DataTable<SupportRow>
          className="fit"
          columns={supportCols}
          rows={data.support.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/soprovozhdenie/${r.id}`)}
          empty={<span className="empty-state">Нет процедур</span>}
        />,
      )}
    </>
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
      <CompactTables
        data={d.tables}
        onRow={(route) => navigate(route)}
        onSection={(route) => navigate(route)}
      />
    </div>
  )
}
