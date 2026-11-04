import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useCallback, useEffect, useState } from 'react'

const ID = 'hermes-mistral-usage'
let rest = null
const POLL_MS = 300000

function readUsage(refresh = false) {
  if (!rest) return Promise.reject(new Error('Backend unavailable'))
  return rest('/usage' + (refresh ? '?refresh=true' : ''))
}

function useUsage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const refresh = useCallback(async (force = false) => {
    setLoading(true)
    try {
      const next = await readUsage(force)
      setData(next)
      setError('')
    } catch {
      setError('Backend inaccessible — verify Hermes Dashboard and plugin installation.')
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    refresh()
    const t = setInterval(() => refresh(), POLL_MS)
    return () => clearInterval(t)
  }, [refresh])
  return { data, error, loading, refresh }
}

function Metric({ title, value, subtitle, error }) {
  return jsxs('section', {
    className: 'rounded-lg border border-(--ui-stroke-secondary) p-4',
    children: [
      jsx('div', { className: 'font-semibold text-sm mb-2', children: title }),
      jsx('div', { className: 'text-xl font-semibold', children: error ? 'Unavailable' : value }),
      jsx('div', { className: 'text-xs mt-1 text-(--ui-text-tertiary)', children: error || subtitle })
    ]
  })
}

function UsagePage() {
  const { data, error, loading, refresh } = useUsage()
  const vibe = data?.vibe
  const api = data?.api
  const reset = vibe?.reset_at ? 'Reset: ' + new Date(vibe.reset_at).toLocaleString() : 'Reset date unavailable'
  const fetched = data?.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'Never'
  return jsxs('div', {
    className: 'flex flex-col gap-4 h-full overflow-auto p-5 text-(--ui-text-primary)',
    children: [
      jsxs('div', { className: 'flex items-center justify-between gap-3', children: [
        jsx('h1', { className: 'text-lg font-semibold', children: 'Mistral Usage' }),
        jsx('button', { type: 'button', disabled: loading, onClick: () => refresh(true),
          className: 'rounded border border-(--ui-stroke-secondary) px-3 py-1.5 text-xs',
          children: loading ? 'Refreshing…' : 'Refresh' })
      ] }),
      jsx('p', { className: 'text-xs text-(--ui-text-tertiary)',
        children: 'Read-only subscription Vibe Code and API budget data from Mistral Admin. Not Pay-as-you-go.' }),
      error ? jsx('div', { className: 'text-sm text-red-400', children: error }) : null,
      jsx(Metric, { title: 'Vibe Code — included quota', value: vibe?.ok ? vibe.remaining_percent.toFixed(2) + '% remaining' : '—',
        subtitle: vibe?.ok ? vibe.spent.toFixed(2) + ' / ' + vibe.initial_budget.toFixed(2) + ' ' + vibe.currency + ' · ' + vibe.used_percent.toFixed(2) + '% used · ' + reset : '',
        error: vibe && !vibe.ok ? vibe.error : '' }),
      jsx(Metric, { title: 'Mistral API — included quota', value: api?.ok ? api.remaining_percent.toFixed(2) + '% remaining' : '—',
        subtitle: api?.ok ? api.spent.toFixed(2) + ' / ' + api.initial_budget.toFixed(2) + ' ' + api.currency + ' · ' + api.used_percent.toFixed(2) + '% used' : '',
        error: api && !api.ok ? api.error : '' }),
      jsx('div', { className: 'text-xs text-(--ui-text-tertiary)',
        children: 'Last read: ' + fetched + (data?.cached ? ' · cached' : '') }),
      jsx('div', { className: 'text-xs text-(--ui-text-tertiary)',
        children: data?.configured === false ? 'Configure a session cookie using scripts/configure.py (see README).' : '' })
    ]
  })
}

function formatPercentUsed(metric) {
  return metric?.ok && Number.isFinite(metric.used_percent)
    ? metric.used_percent.toFixed(1) + '%'
    : '—'
}

function UsageChip() {
  const { data } = useUsage()
  const vibe = data?.vibe
  const api = data?.api
  const vibeText = formatPercentUsed(vibe)
  const apiText = formatPercentUsed(api)
  const label = `Vibe ${vibeText} · API ${apiText}`
  const title = `Mistral subscription quota used — Vibe: ${vibeText}, API: ${apiText}. Click for details.`
  return jsx('button', {
    type: 'button',
    title,
    onClick: () => host.navigate('/mistral-usage'),
    className: 'inline-flex items-center gap-1.5 px-2 text-xs text-(--ui-text-tertiary) hover:text-foreground whitespace-nowrap',
    children: [
      jsx('span', { className: 'font-medium', children: 'Mistral' }),
      jsx('span', { children: '·' }),
      jsx('span', { children: label })
    ]
  })
}

export default {
  id: ID,
  name: 'Mistral Usage',
  defaultEnabled: false,
  register(ctx) {
    rest = ctx.rest
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/mistral-usage' },
        render: () => jsx(UsagePage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA,
        data: { path: '/mistral-usage', label: 'Mistral Usage', codicon: 'graph' } },
      { id: 'chip', area: 'statusBar.right', order: 135,
        render: () => jsx(UsageChip, {}) }
    ])
    ctx.onDispose(() => { rest = null })
  }
}
