import { Field } from '../ui/Field'
import { StaticRuleCard } from './StaticRuleCard'

const inputClassName = 'tt-input'
const textareaClassName = 'tt-input leading-5'
const watchlistPlaceholder = '每行一个，支持“代码 | 备注”\n例如：\nTSLA | 财报后只看回踩确认\nNVDA | 只看放量延续'

export interface ReferenceInputsFormState {
  capitalUsed: string
  hkWatchlist: string
  lowerSupport: string
  pivotLevel: string
  profitTargetPct: string
  upperPressure: string
  usWatchlist: string
}

export function ReferenceInputsPanel({
  form,
  isUsMode,
  noTradeRules,
  onNormalizeWatchlist,
  onUpdateField,
  stopRules,
  compact = false,
  showRules = true,
}: {
  form: ReferenceInputsFormState
  isUsMode: boolean
  noTradeRules: string[]
  onNormalizeWatchlist: (key: 'hkWatchlist' | 'usWatchlist') => void
  onUpdateField: <K extends keyof ReferenceInputsFormState>(key: K, value: ReferenceInputsFormState[K]) => void
  stopRules: string[]
  compact?: boolean
  showRules?: boolean
}) {
  return (
    <section className={compact ? '' : 'tt-bento-panel'}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-bold tracking-tight text-toptrader-accent">观察池与高级项</h3>
          <p className="mt-1.5 text-xs leading-5 text-toptrader-muted">把观察池、关键位、资金目标和停手规则收进盘前作战台，作为同一套盘前输入的一部分。</p>
        </div>
      </div>

      <div className={['mt-3 grid gap-3', showRules ? 'xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]' : 'xl:grid-cols-[minmax(0,0.92fr)_minmax(0,0.92fr)]'].join(' ')}>
        <section className="rounded-lg border border-toptrader-line bg-toptrader-panel/90 px-3 py-3">
          <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">观察池与资金目标</div>
          <div className="mt-3 grid gap-3">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="港股关注池">
                <textarea
                  className={textareaClassName}
                  onChange={(event) => onUpdateField('hkWatchlist', event.target.value)}
                  placeholder={watchlistPlaceholder.replace('TSLA', '腾讯控股 0700').replace('NVDA', '美团 3690')}
                  rows={5}
                  value={form.hkWatchlist}
                />
                <div className="flex flex-wrap items-center justify-between gap-2.5 text-[11px]">
                  <span className="text-toptrader-muted">支持粘贴一串代码，保存前可一键整理成逐行清单。</span>
                  <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => onNormalizeWatchlist('hkWatchlist')} type="button">
                    清洗整理
                  </button>
                </div>
              </Field>
              <Field label="美股关注池">
                <textarea
                  className={textareaClassName}
                  onChange={(event) => onUpdateField('usWatchlist', event.target.value)}
                  placeholder={watchlistPlaceholder}
                  rows={5}
                  value={form.usWatchlist}
                />
                <div className="flex flex-wrap items-center justify-between gap-2.5 text-[11px]">
                  <span className="text-toptrader-muted">每行都可以带备注，例如 `TSLA | 只看回踩`。</span>
                  <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => onNormalizeWatchlist('usWatchlist')} type="button">
                    清洗整理
                  </button>
                </div>
              </Field>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <Field label="当日使用本金">
                <input className={inputClassName} onChange={(event) => onUpdateField('capitalUsed', event.target.value)} value={form.capitalUsed} />
              </Field>
              <Field label="盈利目标%">
                <input className={inputClassName} onChange={(event) => onUpdateField('profitTargetPct', event.target.value)} value={form.profitTargetPct} />
              </Field>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-toptrader-line bg-toptrader-panel/90 px-3 py-3">
          <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">{showRules ? '关键位与停手规则' : '关键位补充'}</div>
          <div className="mt-3 grid gap-3">
            {!isUsMode ? (
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="上方压力">
                  <input className={inputClassName} onChange={(event) => onUpdateField('upperPressure', event.target.value)} value={form.upperPressure} />
                </Field>
                <Field label="下方支撑">
                  <input className={inputClassName} onChange={(event) => onUpdateField('lowerSupport', event.target.value)} value={form.lowerSupport} />
                </Field>
                <Field className="md:col-span-2" label="枢轴位">
                  <input className={inputClassName} onChange={(event) => onUpdateField('pivotLevel', event.target.value)} value={form.pivotLevel} />
                </Field>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-toptrader-line bg-toptrader-soft/30 px-3 py-3 text-xs leading-5 text-toptrader-muted">
                当前是美股期权模式，恒指关键位先不作为主输入项保留。
              </div>
            )}

            {showRules ? (
              <div className="grid gap-3 md:grid-cols-2">
                <StaticRuleCard
                  accentClassName="from-toptrader-panel via-amber-900/15 to-toptrader-panel"
                  helper="出现以下情况时，不开新仓，先退回观察。"
                  items={noTradeRules}
                  title="禁做场景"
                />
                <StaticRuleCard
                  accentClassName="from-toptrader-panel via-toptrader-rose/10 to-toptrader-panel"
                  helper="触发以下条件时，直接暂停或结束当天交易。"
                  items={stopRules}
                  title="应停止条件"
                />
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </section>
  )
}
