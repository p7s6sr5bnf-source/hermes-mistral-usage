/**
 * Hermes Dashboard / Hermes HQ client UI.
 * No Node dependencies, browser credentials or Mistral requests.
 * Data comes ONLY from the authenticated Hermes plugin backend.
 * The native Hermes Desktop UI lives separately in desktop/plugin.js.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  var registry = window.__HERMES_PLUGINS__;
  if (!SDK || !registry || !SDK.React || !SDK.hooks) {
    // The host must initialize the Dashboard SDK before loading plugins.
    return;
  }
  var R = SDK.React;
  var h = R.createElement;
  var useState = SDK.hooks.useState;
  var useEffect = SDK.hooks.useEffect;
  var API_ROOT = "/api/plugins/hermes-mistral-usage";

  function number(value, digits) {
    return typeof value === "number" && Number.isFinite(value)
      ? value.toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits })
      : "—";
  }
  function currency(value, code) {
    return number(value, 2) + " " + (code === "EUR" ? "€" : (code || ""));
  }
  function date(value) {
    if (!value) return "Indisponible";
    var d = new Date(value);
    return Number.isNaN(d.getTime()) ? "Indisponible" : d.toLocaleString("fr-FR");
  }
  function daysUntil(value) {
    if (!value) return null;
    var ts = new Date(value).getTime();
    if (!Number.isFinite(ts)) return null;
    return Math.max(0, Math.ceil((ts - Date.now()) / 86400000));
  }
  function pctClass(value) {
    if (value >= 80) return "text-red-500";
    if (value >= 65) return "text-amber-500";
    return "text-green-500";
  }
  function panel(title, children) {
    return h("section", {
      className: "rounded-xl border border-border bg-card p-4 space-y-3"
    }, h("h2", { className: "text-base font-semibold" }, title), children);
  }
  function Progress(props) {
    return h("div", {
      className: "w-full h-2 rounded-full bg-muted overflow-hidden",
      role: "progressbar", "aria-valuenow": props.value,
      "aria-valuemin": 0, "aria-valuemax": 100
    }, h("div", {
      className: "h-full rounded-full " +
        (props.value >= 80 ? "bg-red-500" : props.value >= 65 ? "bg-amber-500" : "bg-green-500"),
      style: { width: Math.max(0, Math.min(100, props.value)) + "%" }
    }));
  }
  function MetricCard(props) {
    var m = props.metric;
    if (!m || !m.ok) {
      return panel(props.name, h("p", { className: "text-sm text-muted-foreground" },
        m && m.error ? m.error : "Aucune donnée pour ce budget."));
    }
    var percent = Math.max(0, Math.min(100, m.used_percent || 0));
    return panel(props.name, h("div", { className: "space-y-2" },
      h("div", { className: "flex items-baseline justify-between gap-3 flex-wrap" },
        h("span", { className: "text-2xl font-bold " + pctClass(percent) },
          number(percent, 1) + " %"),
        h("span", { className: "text-sm text-muted-foreground" }, "consommé")
      ),
      h(Progress, { value: percent }),
      h("div", { className: "grid grid-cols-2 gap-2 text-xs sm:text-sm" },
        h("div", null,
          h("div", { className: "text-muted-foreground" }, "Utilisé"),
          h("strong", null, currency(m.spent, m.currency))
        ),
        h("div", null,
          h("div", { className: "text-muted-foreground" }, "Disponible"),
          h("strong", null, currency(m.remaining, m.currency))
        )
      ),
      h("p", { className: "text-xs text-muted-foreground" },
        "Budget : " + currency(m.initial_budget, m.currency)),
      h("p", { className: "text-xs text-muted-foreground" },
        "Renouvellement : " + date(m.reset_at) +
        (daysUntil(m.reset_at) != null ? " (" + daysUntil(m.reset_at) + " j)" : ""))
    ));
  }
  function HistoryChart(props) {
    var items = Array.isArray(props.points) ? props.points : [];
    if (items.length < 2) {
      return h("p", { className: "text-xs text-muted-foreground" },
        "Le graphique apparaîtra après plusieurs relevés.");
    }
    var points = items.slice(-90);
    var width = 540, height = 120, pad = 12;
    var max = Math.max(1, ...points.map(function (p) { return Number(p.used_percent) || 0; }));
    var line = points.map(function (p, i) {
      var x = pad + i * (width - 2 * pad) / (points.length - 1);
      var y = height - pad - (Number(p.used_percent) || 0) * (height - 2 * pad) / max;
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    return h("div", { className: "space-y-1" },
      h("svg", {
        viewBox: "0 0 540 120", role: "img", className: "w-full h-auto max-h-40",
        "aria-label": "Évolution de la consommation en pourcentage"
      },
        h("line", { x1: 12, y1: 108, x2: 528, y2: 108, stroke: "currentColor", opacity: 0.25 }),
        h("polyline", { points: line, fill: "none", stroke: "#22c55e",
          strokeWidth: 3, strokeLinecap: "round", strokeLinejoin: "round" })
      ),
      h("p", { className: "text-xs text-muted-foreground" },
        points[0].day + " → " + points[points.length - 1].day)
    );
  }
  function InsightCard(props) {
    var insight = props.insight;
    if (!insight || !insight.latest) {
      return panel(props.title + " · historique",
        h("p", { className: "text-sm text-muted-foreground" },
          "Pas encore de relevés locaux. Les données historiques ne sont pas récupérées rétroactivement."));
    }
    var latest = insight.latest;
    var exhaustion = insight.projected_exhaustion;
    return panel(props.title + " · historique",
      h("div", { className: "space-y-3" },
        h(HistoryChart, { points: insight.chart }),
        h("p", { className: "text-sm" },
          "Budget quotidien disponible : ",
          h("strong", null, insight.daily_remaining_budget == null ? "—" :
            currency(insight.daily_remaining_budget, latest.currency) + " / jour")),
        h("p", { className: "text-sm" },
          "Épuisement prévu : ",
          h("strong", null, exhaustion ? date(exhaustion) : "Pas de prévision fiable")),
        h("p", { className: "text-xs text-muted-foreground" },
          insight.forecast_note || "Une période d'observation plus longue est nécessaire."),
        insight.anomaly ? h("p", { className: "text-xs text-amber-500" },
          "Hausse inhabituelle : +" + number(insight.anomaly.delta_percent_points, 2) + " points.")
          : null
      )
    );
  }
  function Page() {
    var usageState = useState(null);
    var usage = usageState[0], setUsage = usageState[1];
    var historyState = useState(null);
    var insights = historyState[0], setInsights = historyState[1];
    var loadingState = useState(false);
    var loading = loadingState[0], setLoading = loadingState[1];
    var errorState = useState("");
    var error = errorState[0], setError = errorState[1];

    function load(force) {
      setLoading(true);
      setError("");
      return SDK.fetchJSON(API_ROOT + "/usage" + (force ? "?refresh=true" : ""))
        .then(function (latest) {
          setUsage(latest);
          // Historical insights are optional: a history error must not hide live quotas.
          return SDK.fetchJSON(API_ROOT + "/insights?days=30")
            .then(function (history) { setInsights(history); })
            .catch(function () { setInsights(null); });
        })
        .catch(function () {
          setError("Données indisponibles. Vérifiez le backend Hermes et l'activation du plugin.");
        })
        .finally(function () { setLoading(false); });
    }

    useEffect(function () {
      load(false);
      var timer = setInterval(function () { load(false); }, 300000);
      return function () { clearInterval(timer); };
    }, []);

    return h("main", { className: "mx-auto w-full max-w-4xl space-y-4 p-3 sm:p-6" },
      h("div", { className: "flex flex-wrap gap-2 items-center justify-between" },
        h("div", null,
          h("h1", { className: "text-xl font-bold" }, "Mistral Usage"),
          h("p", { className: "text-xs text-muted-foreground" },
            "Quotas d'abonnement API et Vibe Code · hors pay-as-you-go")
        ),
        h("button", { type: "button", disabled: loading,
          onClick: function () { load(true); },
          className: "rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50" },
          loading ? "Actualisation…" : "Actualiser")
      ),
      error ? h("p", { role: "alert", className: "rounded-md border border-red-500 p-3 text-sm" }, error) : null,
      !usage && loading ? h("p", { role: "status", className: "text-sm text-muted-foreground" },
        "Chargement des quotas…") : null,
      h("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3" },
        h(MetricCard, { name: "Vibe Code", metric: usage && usage.vibe }),
        h(MetricCard, { name: "Mistral API", metric: usage && usage.api })
      ),
      h("h2", { className: "font-semibold pt-2" }, "Historique et projections"),
      h("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3" },
        h(InsightCard, { title: "Vibe Code", insight: insights && insights.vibe }),
        h(InsightCard, { title: "Mistral API", insight: insights && insights.api })
      ),
      h("p", { className: "text-xs text-muted-foreground" },
        "Dernier relevé : " + date(usage && usage.fetched_at) +
          (usage && usage.cached ? " · cache" : "")),
      h("p", { className: "text-xs text-muted-foreground" },
        "Les graphiques utilisent uniquement les observations locales du cycle actuel. " +
        "Les réglages d'affichage de Hermes Desktop ne sont pas partagés avec ce client.")
    );
  }

  registry.register("hermes-mistral-usage", Page);
})();
