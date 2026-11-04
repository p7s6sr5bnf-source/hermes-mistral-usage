import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, pluginSettingsHref } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useEffect, useState } from 'react'

const ID = 'hermes-mistral-usage'
const DEFAULTS = Object.freeze({
  display: 'used',
  units: 'percent',
  showVibe: true,
  showApi: true,
  thresholdVibe: 80,
  thresholdApi: 80,
  notifications: true,
  colors: true,
  pollMinutes: 5
})
const INTERVALS = [5, 10, 15, 30]
let runtime = null

function normalized(raw) {
  const s = { ...DEFAULTS, ...(raw && typeof raw === 'object' ? raw : {}) }
  if (!['used', 'remaining'].includes(s.display)) s.display = DEFAULTS.display
  if (!['percent', 'eur'].includes(s.units)) s.units = DEFAULTS.units
  for (const key of ['showVibe', 'showApi', 'notifications', 'colors']) s[key] = s[key] === true
  for (const key of ['thresholdVibe', 'thresholdApi']) {
    const n = Number(s[key])
    s[key] = Number.isFinite(n) ? Math.min(100, Math.max(1, n)) : DEFAULTS[key]
  }
  if (!INTERVALS.includes(Number(s.pollMinutes))) s.pollMinutes = 5
  s.pollMinutes = Number(s.pollMinutes)
  return s
}

function fmtNumber(n, digits = 1) {
  return typeof n === 'number' && Number.isFinite(n)
    ? n.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : '—'
}

function formatValue(metric, s) {
  if (!metric?.ok) return '—'
  if (s.units === 'eur') {
    const n = s.display === 'used' ? metric.spent : metric.remaining
    return fmtNumber(n, 2) + ' ' + (metric.currency || '€').replace('EUR', '€')
  }
  return fmtNumber(s.display === 'used' ? metric.used_percent : metric.remaining_percent) + ' %'
}

function tone(metric, threshold, colors) {
  if (!colors || !metric?.ok) return 'text-(--ui-text-tertiary)'
  const pct = Number(metric.used_percent)
  if (!Number.isFinite(pct)) return 'text-(--ui-text-tertiary)'
  if (pct >= threshold) return 'text-(--ui-danger)'
  if (pct >= threshold * 0.8) return 'text-(--ui-warning)'
  return 'text-(--ui-success)'
}

function makeRuntime(ctx) {
  const listeners = new Set()
  const state = {
    ctx,
    settings: normalized(ctx.storage.get('preferences', DEFAULTS)),
    data: null,
    error: '',
    loading: false,
    lastPoll: 0,
    listeners,
    inFlight: null,
    sentAlerts: ctx.storage.get('sentAlerts', {}),
    disposed: false
  }
  state.subscribe = (fn) => {
    listeners.add(fn)
    return () => listeners.delete(fn)
  }
  state.emit = () => {
    for (const fn of listeners) fn((n) => n + 1)
  }
  state.setSettings = (patch) => {
    state.settings = normalized({ ...state.settings, ...patch })
    ctx.storage.set('preferences', state.settings)
    state.emit()
    state.checkAlerts()
  }
  state.checkAlerts = () => {
    if (!state.data || !state.settings.notifications) return
    let changed = false
    for (const [id, label, threshold] of [
      ['vibe', 'Vibe Code', state.settings.thresholdVibe],
      ['api', 'Mistral API', state.settings.thresholdApi]
    ]) {
      const metric = state.data[id]
      if (!metric?.ok || typeof metric.used_percent !== 'number') continue
      const cycle = metric.reset_at || 'unknown-cycle'
      const key = id + ':' + cycle + ':' + threshold
      if (metric.used_percent < threshold) continue
      if (state.sentAlerts[key]) continue
      state.sentAlerts[key] = true
      changed = true
      const message = label + ' has reached ' + fmtNumber(metric.used_percent) + '% used (alert at ' + threshold + '%).'
      try {
        const pending = ctx.os.notify({ title: 'Mistral quota alert', body: message })
        if (pending && typeof pending.catch === 'function') pending.catch(() => {
          host.notify({ kind: 'warning', message })
        })
      } catch {
        host.notify({ kind: 'warning', message })
      }
    }
    if (changed) ctx.storage.set('sentAlerts', state.sentAlerts)
  }
  state.refresh = async (force = false) => {
    if (state.inFlight) return state.inFlight
    state.loading = true
    state.emit()
    const job = (async () => {
      try {
        const next = await ctx.rest('/usage' + (force ? '?refresh=true' : ''))
        if (state.disposed) return
        state.data = next
        state.error = ''
        state.lastPoll = Date.now()
        state.checkAlerts()
      } catch {
        if (!state.disposed) {
          state.error = 'Backend Hermes indisponible — vérifie le plugin et le profil courant.'
          state.lastPoll = Date.now()
        }
      } finally {
        state.loading = false
        state.inFlight = null
        if (!state.disposed) state.emit()
      }
    })()
    state.inFlight = job
    return job
  }
  ctx.setInterval(() => {
    if (Date.now() - state.lastPoll >= state.settings.pollMinutes * 60000) state.refresh()
  }, 30000)
  ctx.onDispose(() => { state.disposed = true; listeners.clear(); if (runtime === state) runtime = null })
  return state
}

function useMonitor() {
  const [, render] = useState(0)
  useEffect(() => runtime?.subscribe(render), [])
  return runtime
}

function Metric({ title, metric, threshold, s }) {
  const value = formatValue(metric, s)
  const used = metric?.ok ? metric.used_percent : 0
  const severity = tone(metric, threshold, s.colors)
  const pct = Math.max(0, Math.min(100, Number(used) || 0))
  const width = pct + '%'
  const reset = metric?.reset_at ? new Date(metric.reset_at).toLocaleString('fr-FR') : 'Non indiqué'
  return jsxs('section', {
    className: 'rounded-lg border border-(--ui-stroke-secondary) p-4 flex flex-col gap-2',
    children: [
      jsxs('div', { className: 'flex items-center justify-between gap-2', children: [
        jsx('strong', { className: 'text-sm', children: title }),
        jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Alerte : ' + threshold + '% consommé' })
      ] }),
      jsx('div', { className: 'text-xl font-semibold ' + severity, children: value }),
      metric?.ok ? jsxs('div', { className: 'flex flex-col gap-2', children: [
        jsx('div', { className: 'rounded-full h-2 bg-(--ui-stroke-secondary) overflow-hidden', children:
          jsx('div', { className: 'h-full rounded-full ' + (pct >= threshold ? 'bg-(--ui-danger)' : pct >= threshold * 0.8 ? 'bg-(--ui-warning)' : 'bg-(--ui-success)'),
            style: { width } }) }),
        jsx('p', { className: 'text-xs text-(--ui-text-tertiary)',
          children: fmtNumber(metric.used_percent, 2) + '% consommé · ' + fmtNumber(metric.spent, 2) + ' / ' +
            fmtNumber(metric.initial_budget, 2) + ' ' + metric.currency + ' · Reset : ' + reset })
      ] }) : jsx('p', { className: 'text-xs text-(--ui-danger)', children: metric?.error || 'Aucune donnée' })
    ]
  })
}

function UsagePage() {
  const m = useMonitor()
  if (!m) return null
  const s = m.settings
  const data = m.data
  const fetched = data?.fetched_at ? new Date(data.fetched_at).toLocaleString('fr-FR') : 'Jamais'
  return jsxs('div', {
    className: 'flex flex-col gap-4 h-full overflow-auto p-5 text-(--ui-text-primary)',
    children: [
      jsxs('div', { className: 'flex items-center justify-between gap-3', children: [
        jsx('h1', { className: 'text-lg font-semibold', children: 'Mistral Usage' }),
        jsxs('div', { className: 'flex gap-2', children: [
          jsx('button', { type: 'button', className: 'rounded border border-(--ui-stroke-secondary) px-3 py-1.5 text-xs',
            onClick: () => host.navigate(pluginSettingsHref(ID)), children: 'Réglages' }),
          jsx('button', { type: 'button', disabled: m.loading, onClick: () => m.refresh(true),
            className: 'rounded border border-(--ui-stroke-secondary) px-3 py-1.5 text-xs',
            children: m.loading ? 'Actualisation…' : 'Actualiser' })
        ] })
      ] }),
      jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Budgets inclus Mistral Vibe / API · Pay-as-you-go exclu · ' + (s.display === 'used' ? 'Consommé' : 'Restant') }),
      m.error ? jsx('p', { className: 'text-xs text-(--ui-danger)', children: m.error }) : null,
      s.showVibe ? jsx(Metric, { title: 'Vibe Code', metric: data?.vibe, threshold: s.thresholdVibe, s }) : null,
      s.showApi ? jsx(Metric, { title: 'Mistral API', metric: data?.api, threshold: s.thresholdApi, s }) : null,
      !s.showVibe && !s.showApi ? jsx('p', { className: 'text-sm', children: 'Active au moins un indicateur dans les réglages.' }) : null,
      jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Dernière lecture : ' + fetched + (data?.cached ? ' · cache' : '') }),
      data?.configured === false ? jsx('p', { className: 'text-sm', children: 'Configure le cookie local avec scripts/configure.py.' }) : null
    ]
  })
}

function UsageChip() {
  const m = useMonitor()
  if (!m) return null
  const s = m.settings
  const items = [
    s.showVibe && { id: 'vibe', label: 'Vibe', threshold: s.thresholdVibe },
    s.showApi && { id: 'api', label: 'API', threshold: s.thresholdApi }
  ].filter(Boolean)
  return jsxs('button', {
    type: 'button',
    title: 'Mistral · ' + (s.display === 'used' ? 'consommé' : 'restant') + ' · cliquer pour les détails',
    onClick: () => host.navigate('/mistral-usage'),
    className: 'inline-flex h-full items-center gap-1.5 px-2 text-xs hover:bg-(--chrome-action-hover) whitespace-nowrap',
    children: [
      jsx('span', { className: 'font-semibold text-(--ui-text-secondary)', children: 'Mistral' }),
      ...items.flatMap((item, i) => [
        jsx('span', { key: 'sep-' + item.id, className: 'text-(--ui-text-quaternary)', children: i === 0 ? '·' : '|' }),
        jsx('span', { key: item.id, className: 'font-medium ' + tone(m.data?.[item.id], item.threshold, s.colors),
          children: item.label + ' ' + formatValue(m.data?.[item.id], s) })
      ])
    ]
  })
}

function SelectSetting({ label, value, values, change, help }) {
  return jsxs('label', { className: 'flex flex-col gap-1.5 text-sm', children: [
    jsx('span', { className: 'font-medium', children: label }),
    jsx('select', {
      value, onChange: (e) => change(e.target.value),
      className: 'rounded border border-(--ui-stroke-secondary) bg-(--ui-bg) px-3 py-2 text-sm',
      children: values.map(([v, name]) => jsx('option', { value: v, children: name, key: v }))
    }),
    help ? jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: help }) : null
  ] })
}

function CheckSetting({ label, checked, change, help }) {
  return jsxs('label', { className: 'flex items-start gap-2 text-sm cursor-pointer', children: [
    jsx('input', { type: 'checkbox', checked, onChange: (e) => change(e.target.checked), className: 'mt-1' }),
    jsxs('span', { className: 'flex flex-col gap-1', children: [
      jsx('strong', { className: 'font-medium', children: label }),
      help ? jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: help }) : null
    ] })
  ] })
}

function SettingsPage() {
  const m = useMonitor()
  if (!m) return null
  const s = m.settings
  const set = (key, value) => m.setSettings({ [key]: value })
  return jsxs('div', { className: 'flex flex-col gap-5 p-4 max-w-xl text-(--ui-text-primary)', children: [
    jsx('p', { className: 'text-sm text-(--ui-text-tertiary)',
      children: 'Réglages locaux Hermes Desktop. Les seuils utilisent toujours le pourcentage consommé, indépendamment du format affiché.' }),
    jsx('h3', { className: 'font-semibold', children: 'Affichage' }),
    jsx(SelectSetting, { label: 'Valeur affichée', value: s.display,
      values: [['used', 'Consommé'], ['remaining', 'Restant']], change: v => set('display', v) }),
    jsx(SelectSetting, { label: 'Unité', value: s.units,
      values: [['percent', 'Pourcentage (%)'], ['eur', 'Crédits (monnaie du compte)']], change: v => set('units', v) }),
    jsx(CheckSetting, { label: 'Afficher Vibe Code', checked: s.showVibe, change: v => set('showVibe', v) }),
    jsx(CheckSetting, { label: 'Afficher API Mistral', checked: s.showApi, change: v => set('showApi', v) }),
    jsx(CheckSetting, { label: 'Activer les couleurs de statut', checked: s.colors,
      change: v => set('colors', v), help: 'Vert : normal, orange : proche du seuil, rouge : seuil atteint.' }),
    jsx('h3', { className: 'font-semibold pt-2', children: 'Alertes' }),
    jsx(CheckSetting, { label: 'Notifications système', checked: s.notifications,
      change: v => set('notifications', v), help: 'Une notification par quota, seuil et période de renouvellement ; pas de spam au rafraîchissement.' }),
    ...[['thresholdVibe', 'Vibe Code'], ['thresholdApi', 'Mistral API']].map(([key, label]) =>
      jsxs('label', { key, className: 'flex flex-col gap-1.5 text-sm', children: [
        jsx('span', { className: 'font-medium', children: label + ' — alerte à ' + s[key] + '% consommé' }),
        jsx('input', { type: 'range', min: 1, max: 100, step: 1, value: s[key],
          onChange: e => set(key, Number(e.target.value)), className: 'w-full' })
      ] })
    ),
    jsx(SelectSetting, { label: 'Actualisation', value: String(s.pollMinutes),
      values: INTERVALS.map(v => [String(v), v + ' min']), change: v => { set('pollMinutes', Number(v)) },
      help: 'Le backend met en cache les réponses pendant 5 minutes. Aucun nouveau compte Mistral n’est interrogé plus souvent.' }),
    jsx('button', { type: 'button', onClick: () => m.setSettings(DEFAULTS),
      className: 'self-start rounded border border-(--ui-stroke-secondary) px-3 py-2 text-sm',
      children: 'Restaurer les valeurs par défaut' })
  ] })
}

export default {
  id: ID,
  name: 'Mistral Usage',
  defaultEnabled: false,
  register(ctx) {
    runtime = makeRuntime(ctx)
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/mistral-usage' },
        render: () => jsx(UsagePage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA,
        data: { path: '/mistral-usage', label: 'Mistral Usage', codicon: 'graph' } },
      { id: 'chip', area: 'statusBar.right', order: 135, render: () => jsx(UsageChip, {}) }
    ])
    ctx.registerSettingsPage?.({ id: 'settings', title: 'Mistral Usage', icon: 'graph',
      render: () => jsx(SettingsPage, {}) })
    runtime.refresh()
  }
}
