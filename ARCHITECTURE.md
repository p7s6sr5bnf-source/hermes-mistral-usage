# ARCHITECTURE.md — hermes-mistral-usage

Document de prise en main de ce dépôt : architecture, liaison des composants et
place du projet dans l'écosystème. Version du plugin : `plugin.yaml` → `0.4.2`,
licence MIT, `requires_hermes: ">=0.21.2"`.

## 1. Contexte global

Ce dépôt appartient à la **famille B — Hermes et agents IA** de l'écosystème
personnel `p7s6sr5bnf-source`. C'est un outillage pour l'agent Hermes lui-même :
il observe les budgets d'abonnement Mistral qui financent le reste de
l'écosystème, sans jamais consommer de modèle, de crédit ni modifier une
facturation.

- **Successeur direct de `ai-usage-monitor`** (génération précédente, quotas
  Codex/Scaleway). Ce dépôt reprend et simplifie les mécanismes de cette
  génération (lecture d'un backend authentifié, popover natif) mais ne partage
  aucun code avec elle.
- **Il ne dépend d'aucun autre dépôt** et **aucun autre dépôt ne dépend de lui**.
  Sa seule dépendance externe exécutable est **Hermes** (Desktop, Dashboard ou
  Agent selon le composant) et l'**endpoint navigateur non documenté de Mistral**.
- **Ce qui n'est PAS dans ce dépôt** : aucune CI (`.github/` absent, supprimé
  volontairement), aucun workflow, aucun modèle IA, aucun service réseau propre,
  aucune base de données distante, aucun réglage de facturation Mistral. Un seul
  fichier Makefile ou Docker n'existe pas non plus : tout est local.

## 2. Rôle et périmètre réel

Plugin **read-only** de suivi des quotas d'abonnement Mistral, exposé sous trois
formes indépendantes qui partagent un même module d'historique local :

- **Hermes Desktop** (`desktop/plugin.js`) : indicateur de barre d'état, popover
  natif cliquable, page complète, page de réglages, notifications OS.
- **Hermes Dashboard / clients mobiles supportés** (`dashboard/`) : page dédiée
  servie par le backend `dashboard/plugin_api.py`.
- **Hermes Agent (CLI)** (`__init__.py`) : un seul outil `mistral_usage_status`.

**Livré et vérifié en local** : lecture des budgets *Vibe Code* et *API*,
historique SQLite local, graphiques 7/30/90 jours, date de renouvellement,
budget quotidien restant, projection d'épuisement prudente, détection d'anomalie,
alertes seuil/notification, réglages d'affichage. Les 18 tests unitaires de
`tests/` passent via `bash scripts/check-local.sh`.

**Explicitement non livré / hors périmètre** : aucune consommation *pay-as-you-go*
(seuls les budgets d'abonnement globaux existent, pas de conso par clé) ; le
plugin **ne convertit ni n'appelle aucun modèle** ; il **ne renouvelle pas** le
cookie de session ; il **ne récupère pas** l'historique passé chez Mistral (le
sélecteur 7/30/90 jours borne la fenêtre *locale enregistrée*, pas une requête
d'historique) ; il ne modifie pas l'écran natif *Usage & Limits* des clients
mobiles et ne fournit aucune notification push iOS en arrière-plan. La
compatibilité macOS n'est **pas** certifiée localement (checks validés sous Linux).

## 3. Carte du dépôt

| Chemin | Rôle |
| --- | --- |
| `plugin.yaml` | Manifeste Hermes : nom, version, `requires_hermes`, `provides_tools: [mistral_usage_status]`. |
| `__init__.py` | Entrée **Agent** : `register(ctx)` déclare l'outil `mistral_usage_status` ; `_handle(args)` lit l'historique local, ne fait aucun réseau. |
| `usage_history.py` | Cœur **partagé** : schéma SQLite, `record()`, `_insight()`, `overview()`. Aucune credential. |
| `dashboard/plugin_api.py` | Backend **FastAPI** : lit le cookie, appelle Mistral, sert `/usage`, `/health`, `/insights`, écrit l'historique. |
| `dashboard/manifest.json` | Manifeste **Dashboard** : onglet `/mistral-usage`, `entry: dist/index.js`, `api: plugin_api.py`. |
| `dashboard/dist/index.js` | UI **Dashboard** navigateur (IIFE, SDK `window.__HERMES_PLUGIN_SDK__`). |
| `desktop/plugin.js` | Composant **Desktop** natif (SDK `@hermes/plugin-sdk`, React). |
| `scripts/configure.py` | Helper : écrit `~/.config/hermes-mistral-usage/session.cookie` en `0600`. |
| `scripts/check-local.sh` | **Porte locale unique** (tests + compile + node --check + manifest). |
| `tests/test_agent.py` | Contrat de l'outil Agent, données synthétiques. |
| `tests/test_backend.py` | Cookie (permissions, symlink), CSRF, schéma budget, URL fixe. |
| `tests/test_dashboard_assets.py` | Contrat des assets Dashboard (manifeste, bundle, absence de secret). |
| `tests/test_history.py` | Historique, projections, reset de cycle, anomalie. |
| `SECURITY.md` | Modèle de menace : le cookie est une session privilégiée, non un jeton scoped. |
| `THIRD_PARTY.md` | Attribution (UsageBar, endpoint DevTools). |
| `.gitignore` | Exclut `**/session.cookie`, `*.har`, `*.key`, `credentials.json`, `config.json`. |
| `LICENSE`, `README.md`, `AGENTS.md` | Licence MIT, doc utilisateur, règles agents. |

Répertoires : `dashboard/` (backend + UI Dashboard), `desktop/` (UI Desktop),
`scripts/` (outillage local), `tests/` (suite unitaire). Pas de `src/`, pas de
`docs/` : la documentation tient dans `README.md` et `SECURITY.md`.

## 4. Liaisons entre composants

Le module **`usage_history.py` est le point de jonction** : il est chargé par les
trois autres composants via `importlib.util.spec_from_file_location` (jamais par
`sys.path` ni comme package), pour éviter de polluer l'environnement Hermes.

- `__init__.py` : `_history()` charge `usage_history.py` et appelle `overview(days)`
  (1–90, défaut 30). L'outil renvoie le résultat après `pop("chart")` sur `api`
  et `vibe` (jamais de chemin local ni de cookie).
- `dashboard/plugin_api.py` : `_load_history()` charge le **même** fichier sous le
  nom `hermes_mistral_usage_history`, expose `history_store`. `_collect()` écrit
  via `history_store.record(snapshot)` ; `/insights` lit via `overview(days)`.
- `desktop/plugin.js` et `dashboard/dist/index.js` : purement clients ; ils
  appellent le backend Hermes par HTTP et **ne chargent jamais** `usage_history.py`.

**Flux de bout en bout (Desktop → Mistral → Desktop)** :
1. `desktop/plugin.js` → `ctx.rest('/usage' + (force?'?refresh=true':''))`.
2. `plugin_api.usage(refresh)` → `get_usage(force)` : cache 300 s (normale) ou
   30 s minimum (force), verrou `threading.Lock`.
3. `_collect()` → `_read_cookie()` (env `MISTRAL_USAGE_COOKIE` ou fichier `0600`).
4. `_subscription_budgets(cookie)` → `_get_json(_budget_url(), …)` : GET HTTPS
   vers `admin.mistral.ai`, redirections interdites (`NoRedirects`), réponse
   plafonnée à `MAX_RESPONSE_BYTES`.
5. `_budget_item()` normalise `api_budget` et `vibe_budget` en `{ok, used_percent,
   remaining_percent, initial_budget, spent, remaining, currency, reset_at, …}`.
6. `history_store.record(snapshot)` persiste (échec silencieux, jamais bloquant).
7. Le Desktop relit le snapshot, puis `ctx.rest('/insights?days='+historyDays)`
   pour `overview()` (historique + projection + anomalie) et déclenche ses alertes
   (`state.checkAlerts()`).

Le flux Dashboard (`dashboard/dist/index.js`) est identique via
`SDK.fetchJSON(API_ROOT + "/usage")` puis `"/insights?days=30"`, où
`API_ROOT = /api/plugins/hermes-mistral-usage`.

## 5. Entrées, sorties et commandes

Point d'entrée **unique** : `scripts/check-local.sh`. Il n'y a **aucune CI** ;
`.github/workflows/` ne doit jamais réapparaître.

```bash
# Porte locale (obligatoire avant push/PR), depuis la racine du dépôt :
bash scripts/check-local.sh

# Équivalent manuel (reprend exactement les mêmes étapes) :
python3 -m pip install fastapi
python3 -m unittest discover -s tests -v
python3 -m py_compile dashboard/plugin_api.py usage_history.py __init__.py scripts/configure.py
node --check desktop/plugin.js
node --check dashboard/dist/index.js
hermes plugins validate .

# Configurer la session Mistral (sur l'hôte de confiance) :
python3 scripts/configure.py      # écrit ~/.config/hermes-mistral-usage/session.cookie en 0600
```

Installation / mise à jour côté utilisateur :

```bash
hermes plugins install p7s6sr5bnf-source/hermes-mistral-usage --enable
hermes plugins update hermes-mistral-usage && hermes plugins enable hermes-mistral-usage
hermes plugins list && hermes plugins doctor hermes-mistral-usage
```

**Entrées (variables d'environnement du backend)** : `MISTRAL_USAGE_COOKIE`
(moins souhaitable), `MISTRAL_USAGE_COOKIE_FILE`, `HERMES_HOME`,
`HERMES_MISTRAL_DATA_DIR`. **Sorties** : JSON de `get_usage()`/`_collect()`,
JSON de `overview()`, base SQLite locale, notifications OS. L'outil Agent
`mistral_usage_status` (argument `days`, 1–90) ne fait **aucun** réseau.

## 6. Contrats et invariants

- **Schéma SQLite** (`usage_history.py`, table `observations`) : `observed_at`,
  `metric ∈ ('api','vibe')`, `cycle`, `used_pct` (0–100), `budget > 0`, `spent ≥ 0`,
  `currency` ∈ {EUR, USD, CHF, GBP}, `UNIQUE(observed_at, metric)`. Base
  `usage.sqlite3` en `0600`, répertoire en `0700`, hors arbre Git.
- **Aucun secret persisté** : la base ne contient **que** des pourcentages, montants
  agrégés, devises, timestamps. Ni cookie, ni jeton, ni prompt, ni identifiant de
  compte (garanti par `tests/test_history.py` et `tests/test_agent.py`).
- **Cookie traité comme secret** : jamais en argument de ligne de commande, en
  clair dans le dépôt, un log, un test ou un chat. Fichier régulier, `0600`,
  `st_nlink == 1`, propriétaire = utilisateur courant, `O_NOFOLLOW` ; refus des
  symlinks (`tests/test_backend.py`).
- **Réponse Mistral bornée** : `Content-Type` JSON exigé, taille ≤
  `MAX_RESPONSE_BYTES`, redirections interdites, erreurs HTTP mappées en messages
  neutres (jamais de corps de réponse ni d'en-tête renvoyé).
- **URL fixe et non paramétrable** : `_budget_url()` retourne toujours
  `https://admin.mistral.ai/api/local-trpc/billing.budget?...`, même si
  `MISTRAL_SUBSCRIPTION_BUDGET_URL` est définie (testé).
- **Rétention** : `MAX_AGE_DAYS = 400`, purge appliquée à chaque écriture.
- **Caches** : `CACHE_SECONDS = 300`, `MIN_REFRESH_SECONDS = 30` côté backend.
- **Contrat du bundle Dashboard** : contient `registry.register("hermes-mistral-usage", Page)`,
  `SDK.fetchJSON(API_ROOT + "/usage"`, `"/insights` ; et **ne contient pas**
  `admin.mistral.ai`, `MISTRAL_USAGE_COOKIE`, `document.cookie`, `window.localStorage`
  (`tests/test_dashboard_assets.py`).
- **Version** : `plugin.yaml` et `dashboard/manifest.json` doivent rester cohérents ;
  toute modification de comportement doit bumper la version et garder le tableau de
  fonctionnalités du README honnête.

## 7. Où intervenir selon la tâche

| Tâche | Ouvrir en premier |
| --- | --- |
| Changer l'appel Mistral / le schéma de budget | `dashboard/plugin_api.py` (`_budget_url`, `_budget_item`, `_subscription_budgets`) + `tests/test_backend.py` |
| Modifier lecture/permissions du cookie | `dashboard/plugin_api.py` (`_read_cookie`, `_validate_cookie`, `_csrf`) + `scripts/configure.py` |
| Historique, projection, anomalie, rétention | `usage_history.py` (`record`, `_insight`, `overview`) + `tests/test_history.py` |
| Outil Agent (schéma, validation `days`) | `__init__.py` + `tests/test_agent.py` |
| UI/réglages Desktop | `desktop/plugin.js` (`makeRuntime`, `SettingsPage`, `UsageChip`) |
| UI Dashboard / mobile | `dashboard/dist/index.js` + `dashboard/manifest.json` |
| Ajouter/retirer une vérification locale | `scripts/check-local.sh` (+ `tests/`) |
| Documentation / règles agents | `README.md`, `SECURITY.md`, `AGENTS.md` |

## 8. Pièges connus et dettes

- **Endpoint non documenté** : `billing.budget` est une API navigateur observée en
  DevTools ; elle peut changer sans préavis. Une panne côté Mistral n'est pas un bug
  du dépôt. Licence et conditions Mistral à respecter.
- **Session expirée** : le plugin ne renouvelle pas le cookie. Un `302`, `401` ou
  `403` signifie session/révocation/scope ; il faut relancer `scripts/configure.py`
  avec la valeur exacte de l'en-tête `Cookie` d'une requête `billing.budget`.
- **Graphique vide** : normal si une seule journée est enregistrée ; le sélecteur
  **ne rétro-remplit pas** les cycles précédents (test `test_cycle_reset_not_joined`
  garantit qu'un nouveau cycle n'est pas agrégé à l'ancien).
- **Projection exigeante** : épuisement calculé seulement si au moins 3 jours
  distincts et ≥ 24 h d'historique ; anomalie si ≥ 6 incréments valides, dernier
  ≥ 0,5 point et ≥ 3× la médiane. Un échantillonnage lent rate les pics courts.
- **Base illisible / permissions** : un échec d'écriture d'historique est **avalé**
  volontairement (`try/except` dans `_collect`) pour ne jamais casser les quotas
  live ; côté Agent, l'absence de base renvoie `no_history`.
- **`fastapi` requis** : le backend et `tests/test_backend.py` importent
  `fastapi`. Sans `uv` ni `fastapi`, `check-local.sh` marque l'étape **SKIP** — ne
  jamais présenter un test sauté comme un test réussi.
- **Pas de certification macOS** : les checks locaux passent sous Linux ; Desktop/Agent
  et macOS doivent être vérifiés sur l'installation cible.
- **Clients mobiles** : la page Dashboard n'existe que si le backend Hermes qui
  sert les assets a le plugin installé et activé ; installer le seul composant
  Desktop ne fournit **pas** la page Dashboard.
- **Vie privée Agent** : les chiffres agrégés renvoyés par `mistral_usage_status`
  peuvent être transmis au fournisseur de modèle de la conversation (le cookie,
  lui, n'est jamais lu).

## 9. Ordre de lecture conseillé

1. `README.md` — comportement produit, installation, réglages, dépannage.
2. `usage_history.py` — schéma et cœur partagé, source de vérité des invariants.
3. `dashboard/plugin_api.py` — seul composant qui touche au réseau et au cookie.
4. `desktop/plugin.js` — UI de référence (popover, réglages, alertes).
5. `AGENTS.md` + `scripts/check-local.sh` — règles de contribution et porte locale.
6. `tests/` — contrat exécutable de tout ce qui précède.
