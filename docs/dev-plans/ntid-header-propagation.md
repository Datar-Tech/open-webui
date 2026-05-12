# NTID `user` Header Propagation — Dev Plan

| Field | Value |
|---|---|
| **Status** | ✅ **Implemented** in PRs [open-webui#44](https://github.com/Datar-Tech/open-webui/pull/44) + [pipeline#96](https://github.com/Datar-Tech/pipeline/pull/96) — pending merge + dev verification |
| **Owner** | TBD (deployer) |
| **IT Deadline** | 2026-05-02 (past — P0) |
| **Source of Truth** | [Confluence: User Header Modification](https://amd.atlassian.net/wiki/spaces/SI/pages/1655519770/User+Header+Modification) |
| **Repos Affected** | `Datar-Tech/open-webui` (4 files + 1 manual DDL) + `Datar-Tech/pipeline` (3 files) |
| **Created** | 2026-05-06 |
| **Last updated** | 2026-05-12 (post-implementation sync) |

> **Implementation chose Path C (Microsoft Graph fetch).** Originally drafted as Path A (capture NTID from an Entra ID **optional claim**), but inspection of the live ID token + the Entra app manifest revealed:
> - The token currently has no NTID-bearing claim and adding one requires a claim-mapping policy (admin-only Graph API config; not in the manifest UI).
> - The app already has `User.Read` Microsoft Graph permission consented, so OWUI can call `GET /v1.0/me?$select=onPremisesSamAccountName` after login at zero IT cost.
>
> **Path B (pipeline-side AD lookup)** is documented in §12 as a fallback if Graph proves unreliable; the pipeline contract (`body.user.ntid`) is identical so switching later requires no pipeline changes.

> **Storage decision:** NTID lives in a **new dedicated `ntid` column** on the `user` table — not in the `info` JSONField. Rationale: this is a fork of Open WebUI (the team already maintains schema divergence — see `Datar-Tech/open-webui` history); NTID is a first-class business identifier (compliance, billing attribution, IT audit); a real column gives type safety, B-tree indexability for reverse lookups, and clean ORM access (`user.ntid` instead of `(user.info or {}).get("ntid")`).

---

## 1. Background

AMD IT mandates that **every** outbound request to `https://llm-api.amd.com/*` made with a **shared application API key** must carry a `user: <NTID>` HTTP header. The header value is the human user's AMD network login ID (e.g. `jdoe1`); for CI/automation it is the service account's NTID.

Our Open WebUI deployment authenticates users via Microsoft OIDC (Entra ID) and proxies chat completions through an external pipeline (`llamaindex_pipeline_v6.1_SPA_Chief_Planner_modularized.py`) that finally calls `https://llm-api.amd.com/*`. The NTID currently does **not** flow end-to-end. This plan closes that gap.

**Out of scope** (per IT, SLAI/IT-managed tools are exempt):
- NABU / TIP calls — uses `intelligence.amd.com/nabu/prod`, not the LLM Gateway
- Personal API key users (Claude Code, Codex CLI) — handled separately

---

## 2. End-to-End Flow (Target State)

```
┌──────────────┐  OIDC   ┌──────────────┐               ┌──────────────────┐
│  Microsoft   │ ──────► │  Open WebUI  │ ──Graph API──►│  graph.microsoft │
│  Entra ID    │ id_tok  │   backend    │ ◄── ntid ─────│  /me?$select=... │
└──────────────┘         └──────┬───────┘               └──────────────────┘
                                │
                            user.ntid                  ┌────────────────┐    HTTPS    ┌──────────────┐
                       (dedicated column,              │   Pipeline     │ ──────────► │  LLM Gateway │
                        persisted in MSSQL)            │   server       │  user:NTID  │  llm-api.amd │
                                │                      └────────────────┘             └──────────────┘
                                │                            ▲
                          payload.user.ntid                  │
                          (POST /chat/completions)           │
                                ▼                            │
                        ────► Pipeline ◄──── ntid_context (ContextVar) ──┘
                                              (per-request propagation)
```

**Four handoffs**, each requires code change:

1. **Microsoft Entra ID → Open WebUI**: standard OIDC code-flow login (existing; no change beyond adding `User.Read` to `OAUTH_SCOPES`).
2. **Open WebUI → Microsoft Graph**: after OIDC sub validation, call `GET /v1.0/me?$select=onPremisesSamAccountName` with the access_token; persist result to `user.ntid` (new dedicated column).
3. **Open WebUI → Pipeline**: inject `payload["user"]["ntid"]` when calling pipeline-flagged models (registered as OpenAI-compatible URLs).
4. **Pipeline → LLM Gateway**: read `body["user"]["ntid"]` in `orchestrator_agent_workflow`, propagate via `ContextVar` to `CustomHTTPLLM._get_headers()`, emit `user: <NTID>` header on every outbound to `llm-api.amd.com`.

---

## 3. Architectural Decision: Why ContextVar (not instance attr)

`CustomHTTPLLM` is instantiated **once** in `Pipeline.__init__()` (entrypoint line 170) and registered as the global `Settings.llm`. All agents (`orchestrator`, `react`, `powerbi`, etc.) share this singleton.

NTID is **per-request** data. Three options were considered:

| Approach | Verdict | Why |
|---|---|---|
| Instance attribute (`self.ntid = ntid`) | ❌ Reject | Cross-user leak under concurrent requests |
| Thread through every call's `kwargs` | ❌ Reject | Touches ~10 call sites, breaks LlamaIndex's `LLM` interface |
| **`ContextVar`** | ✅ **Adopt** | Per-request isolation, codebase already uses this pattern (`user_id_context` in `orchestrator_agent_workflow.py:782`), single choke point at `_get_headers()` |

---

## 4. Change Inventory

### 4.1 `open-webui` repo — 1 manual DDL + 4 code files (as shipped in PR #44)

#### Step 0 — Deployment DDL (must run BEFORE deploying code)

> No migration file is created. This deployment runs against a single SQL Server instance with no fresh-install requirement, so the column is added directly via DDL.

```sql
-- Run as DB admin on [openwebui]
ALTER TABLE [openwebui].[dbo].[user]
    ADD [ntid] NVARCHAR(64) NULL;

-- Optional but recommended for fast reverse lookup (NTID → user)
CREATE INDEX [IX_user_ntid] ON [openwebui].[dbo].[user]([ntid])
    WHERE [ntid] IS NOT NULL;
```

**Caveats**:
- DDL must run **before** the new code deploys, otherwise the SQLAlchemy model declaration will fail on first read with `column user.ntid does not exist`.
- No UNIQUE constraint — defer until backfill confirms there are no duplicate NTIDs in AD (rare but possible: contractor rejoin, account merge).
- A future re-deploy from scratch (new env, DR rebuild) requires re-running this DDL — keep it in your runbook / infra-as-code repo.

#### File A: `backend/open_webui/config.py`

| Location | Change (as shipped) |
|---|---|
| After `ENABLE_OAUTH_GROUP_MANAGEMENT` (~line 515) | Added `ENABLE_OAUTH_NTID_FROM_GRAPH` `PersistentConfig` (default `False`). Primary opt-in gate for the Graph fetch — enabling this is required for the feature to activate. |

#### File B: `backend/open_webui/models/users.py`

| Location | Change (as shipped) |
|---|---|
| `User` ORM class (after `oauth_sub`) | Added `ntid = Column(String(64), nullable=True, index=True)` |
| `UserModel` Pydantic class (after `oauth_sub`) | Added `ntid: Optional[str] = None` |
| `insert_new_user(...)` signature + builder dict | Added `ntid: Optional[str] = None` kwarg and threaded it into the `UserModel` build |

#### File C: `backend/open_webui/models/auths.py`

| Location | Change (as shipped) |
|---|---|
| `insert_new_auth(...)` signature + call to `Users.insert_new_user` | Added `ntid: Optional[str] = None` kwarg and forwarded it. Removes the need for a follow-up `update_user_by_id` after signup (single-transaction insert). |

#### File D: `backend/open_webui/utils/oauth.py` (the heavy lift)

| Location | Change (as shipped) |
|---|---|
| Imports + `auth_manager_config` setup | Pull in `ENABLE_OAUTH_NTID_FROM_GRAPH` |
| After OIDC `sub` validation | New Graph-fetch block, **two-stage gated**: (1) `ENABLE_OAUTH_NTID_FROM_GRAPH` env opt-in; (2) ID-token `iss` claim must contain `login.microsoftonline.com` or `sts.windows.net`. Any failure (skip / network / non-200) is logged and never blocks login. |
| Result tracking | Local `ntid` (string value) + `ntid_fetched` (bool: True iff Graph returned 200). The bool drives DB writes so a failed Graph call leaves existing data alone, while a successful 200-with-null-value purges stale rows. |
| Existing-user branch | `if ntid_fetched and user.ntid != ntid: Users.update_user_by_id(user.id, {"ntid": ntid or None})` — write-through including purge on null. |
| New-user branch | Pass `ntid=(ntid or None) if ntid_fetched else None` into `Auths.insert_new_auth(...)`. No follow-up update. |

**Two-stage Graph gating (security):**
1. `ENABLE_OAUTH_NTID_FROM_GRAPH` (default `False`) is the **kill switch** — generic OIDC deployments using Keycloak/Okta/Auth0 that copy this fork stay safe by default.
2. Even with the env on, the runtime validates the ID token's `iss` before issuing the call. Without this guard, a misconfigured generic OIDC provider would leak its access_token to `graph.microsoft.com` and add a 5s timeout penalty per login.

#### File E: `backend/open_webui/routers/openai.py`

| Location | Change (as shipped) |
|---|---|
| `if "pipeline" in model and model.get("pipeline"):` block (~line 660) | Added `"ntid": user.ntid or ""` to `payload["user"]`. |

**Why body channel, not the header block at 705–726:**
The header block is gated by `ENABLE_FORWARD_USER_INFO_HEADERS` and applies to **all** OpenAI-compatible URLs (Azure OpenAI, OpenAI direct, etc.). Putting NTID there would leak our internal identifier to non-AMD endpoints. The body channel (line 660) only fires when the model is flagged as `pipeline=True` — exactly the right scope.

---

### 4.2 `pipeline` repo (`C:\Github\pipeline`) — 3 files (as shipped in PR #96)

> **Entrypoint `pipe()` is unchanged.** `body` is forwarded as-is from open-webui through `_async_pipe_logic` to `run_orchestrator_workflow`, which reads `body["user"]["ntid"]` directly. Initially the plan was to modify `pipe()` to extract and pass `user_ntid` as a kwarg, but that turned out to be redundant — the body channel already carries everything.

#### File F: `pipeline_modules/utils.py`

| Location | Change (as shipped) |
|---|---|
| After existing `user_id_context` declaration (~line 18) | Added module-level `ntid_context = contextvars.ContextVar('ntid', default='')`. Mirrors the existing `user_id_context` pattern so all consumers import from one place. |

#### File G: `pipeline_modules/llm_clients.py` ⭐ **Core choke point**

| Location | Change (as shipped) |
|---|---|
| Top of file (imports) | Added `from pipeline_modules.utils import ntid_context` |
| `_get_headers()` (~line 118) | Read `ntid = ntid_context.get("")`; if non-empty, set `headers["user"] = ntid`. Empty NTID → header omitted entirely (per IT FAQ, gateway monitors non-compliance separately). |
| All other call sites | **No change** — `requests.post(..., headers=self._get_headers(), ...)` and any streaming variant funnel through this single choke point, so every existing agent (orchestrator/react/powerbi/etc.) inherits the change for free. |

#### File H: `pipeline_modules/agents/orchestrator_agent_workflow.py`

| Location | Change (as shipped) |
|---|---|
| Imports | Added `ntid_context` to the existing `from pipeline_modules.utils import ...` line |
| Top of `run_orchestrator_workflow` (next to `user_id_token = None`) | Added `ntid_token = None` |
| Inside try, after `user_id_context.set(...)` (~line 782) | Added `ntid_token = ntid_context.set(user_info.get("ntid", "") or "")` |
| Bottom finally clause | Added a third nested `try/finally` so a stream-handler-cleanup or user_id-reset failure cannot leak NTID across requests. |

> ⚠️ **Header name is the literal lowercase string `user`** — IT specified this verbatim in their cURL example. Do NOT use `X-NTID`, `X-User-NTID`, or any variant.

---

### 4.3 Files explicitly NOT changing

| File | Why skip |
|---|---|
| `pipeline_modules/nabu_client.py` | NABU is SLAI/IT-managed (per IT FAQ); not in NTID enforcement scope |
| `pipeline_modules/azure_search_client.py` | Azure Search is not the LLM Gateway |
| `react_agent_workflow.py`, `powerbi_agent_workflow.py`, etc. | All consume `Settings.llm` → routed through `CustomHTTPLLM._get_headers()`, automatically covered |
| `agent_registry.py` | No outbound HTTP |

---

## 5. Prerequisites & Deployment Configuration

### 5.1 Azure / IT (verified — no work needed)

The implementation chose Path C (Microsoft Graph), which means **no Entra app registration changes are required**. This was confirmed by:

| Verification | Source | Result |
|---|---|---|
| App `pdase-cepm-wapp` (`appId 17ed0bbb-...`) `requiredResourceAccess` includes Microsoft Graph `User.Read` | Manifest JSON read via Chrome DevTools (2026-05-11) | ✅ Already requested |
| ID token's `iss` is `login.microsoftonline.com` | jwt.io decode of live login token | ✅ Confirmed |
| Federation flow Okta → Entra → OWUI is invisible to OWUI | HAR capture of full login (2026-05-11) | ✅ OWUI sees only Entra; Okta is server-side |

**Operator action**: confirm "Grant admin consent" is granted for the `User.Read` permission on the dev/prod app (`9e1ebe94-...` for dev). If not, users will see a one-time consent prompt on first login after the OAUTH_SCOPES change.

### 5.2 Required env vars (must set at deploy time)

| Variable | Value | Purpose |
|---|---|---|
| `ENABLE_OAUTH_NTID_FROM_GRAPH` | `true` | Primary feature gate. Without this the Graph call is skipped entirely (silent miss). |
| `OAUTH_SCOPES` | `openid email profile User.Read` | Adds `User.Read` to the OIDC scope request so the access_token returned can call Graph. The existing `openid email profile` value is **not** sufficient. |

Without **both**: `ntid` stays NULL → no `user` header is emitted → gateway will 401 once enforcement kicks in.

### 5.3 Database (must run BEFORE deploying code)

See §4.1 Step 0 — `ALTER TABLE [user] ADD ntid NVARCHAR(64) NULL;` on the `dvse-cepm-sqlmi/openwebui` (dev) and `pdase-cepm-sqlmi/openwebui` (prod) databases.

---

## 6. Backfill Strategy (Existing Users) — Dual Track

Existing users' `user.ntid` is NULL until they re-login. We adopt **both** approaches:

| Track | When | Purpose |
|---|---|---|
| **A. Lazy backfill on OIDC re-login** (built-in, primary) | Continuous, every login | The implementation calls Graph on every successful OIDC login and write-throughs the result (including purging stale rows on null returns). Self-healing forever. **Sufficient by itself** if you can tolerate the 7-day session window during which old sessions emit no `user` header. |
| **B. One-shot SQL backfill** (optional warm-up) | Deployment day | Eliminate the empty-header window for users whose session won't expire soon. Useful if the gateway enforcement starts before all users naturally re-login. |

### 6.1 Backfill SQL (Track B)

**Backend confirmed**: SQL Server. Target column is the new dedicated `[ntid]` column added in §4.1 Step 0 — plain `UPDATE`, no JSON path required.

**AD source**: `PKG_ENG.[dbo].[ACTIVEDIRECTORY_USERS]` — `mail` column joins to `[user].email`; `NTName` column carries the identifier in `DOMAIN\username` format (e.g. `amd\agriffin`).

#### Step 1 — Sanity check (run first, fix issues before UPDATE)

```sql
-- 6.1.a Match rate
SELECT
    SUM(CASE WHEN ad.[NTName] IS NOT NULL THEN 1 ELSE 0 END) AS matched,
    SUM(CASE WHEN ad.[NTName] IS NULL     THEN 1 ELSE 0 END) AS unmatched,
    COUNT(*) AS total
FROM [openwebui].[dbo].[user] u
LEFT JOIN PKG_ENG.[dbo].[ACTIVEDIRECTORY_USERS] ad
    ON u.[email] COLLATE Latin1_General_100_CI_AS_SC_UTF8 = ad.[mail];

-- 6.1.b Duplicate-email check (must be empty before UPDATE; otherwise pick a tiebreaker)
SELECT u.[email], COUNT(*) AS ad_match_count
FROM [openwebui].[dbo].[user] u
JOIN PKG_ENG.[dbo].[ACTIVEDIRECTORY_USERS] ad
    ON u.[email] COLLATE Latin1_General_100_CI_AS_SC_UTF8 = ad.[mail]
GROUP BY u.[email]
HAVING COUNT(*) > 1;
```

#### Step 2 — Backfill UPDATE (transactional, idempotent)

```sql
BEGIN TRAN;

UPDATE u
SET u.[ntid] =
    -- Strip "amd\" (or any DOMAIN\) prefix; IT requires bare NTID, e.g. "agriffin" not "amd\agriffin"
    CASE
        WHEN ad.[NTName] LIKE '%\%'
            THEN RIGHT(ad.[NTName], LEN(ad.[NTName]) - CHARINDEX('\', ad.[NTName]))
        ELSE ad.[NTName]
    END
FROM [openwebui].[dbo].[user] u
INNER JOIN PKG_ENG.[dbo].[ACTIVEDIRECTORY_USERS] ad
    ON u.[email] COLLATE Latin1_General_100_CI_AS_SC_UTF8 = ad.[mail]
WHERE ad.[NTName] IS NOT NULL
  AND u.[oauth_sub] IS NOT NULL    -- only OIDC-provisioned users; excludes bootstrap admin / local-auth accounts
  AND (u.[ntid] IS NULL OR u.[ntid] = '');   -- idempotent: skip rows already backfilled

-- Verify before commit
SELECT TOP 20 u.[email], u.[ntid] AS backfilled_ntid
FROM [openwebui].[dbo].[user] u
WHERE u.[ntid] IS NOT NULL;

-- COMMIT;   -- uncomment after sanity check
-- ROLLBACK; -- if numbers look wrong
```

#### Critical correctness gotchas (do not skip)

| # | Gotcha | Mitigation |
|---|---|---|
| 1 | **`NTName` is `DOMAIN\username` format** (e.g. `amd\agriffin`). Loading the raw string sends `user: amd\agriffin` to gateway, which is invalid NTID — calls misattributed or rejected | The `RIGHT(... CHARINDEX('\\', ...))` slice in the UPDATE strips the prefix |
| 2 | **Email-side `COLLATE` defeats index** — query plan goes to scan. OK for one-shot; document as known cost | If `[user]` is large (>50k rows), pre-stage to a temp table or add a persisted computed column on the AD side |
| 3 | **Duplicate AD rows per email** (contractor offboarding lag, test accounts) → `UPDATE` may pick a non-canonical NTID | Run 6.1.b first; if duplicates exist, refine join with `WHERE ad.[active] = 1` or `MAX(ad.[lastLogon])` tiebreaker |
| 4 | **Idempotency** — re-running must not regress users who logged-in post-backfill and got fresher data | `WHERE u.[ntid] IS NULL OR u.[ntid] = ''` skips already-set rows |
| 5 | **Non-OIDC users** (bootstrap admin, local-auth accounts) have `oauth_sub IS NULL` and may not have a valid AD email match; populating their `ntid` would send a wrong/stale NTID to the gateway | `AND u.[oauth_sub] IS NOT NULL` guard limits backfill to users provisioned through OIDC. Non-OIDC accounts must be handled separately (typically via a service-account NTID per IT FAQ). |

### 6.2 Lazy backfill (Track A)

Already covered by §4.1 File B (`oauth.py`) — OIDC callback writes `user.ntid` on every login (insert and update branches). This is the long-term mechanism; SQL backfill is a one-shot warm-up.

---

## 7. Test Plan

### 7.1 Unit / Component
- [ ] `oauth.py`: with `ENABLE_OAUTH_NTID_FROM_GRAPH=true` and a Microsoft `iss`, mock Graph 200 + value → `user.ntid` is persisted on both new-user and existing-user branches
- [ ] `oauth.py`: with `ENABLE_OAUTH_NTID_FROM_GRAPH=true` and a non-Microsoft `iss` (e.g. `iss="https://keycloak.example/realms/x"`), Graph is **never called** — verify by mocking and asserting zero invocations
- [ ] `oauth.py`: with `ENABLE_OAUTH_NTID_FROM_GRAPH=false`, Graph is **never called** even with a Microsoft `iss`
- [ ] `oauth.py`: Graph 200 with `onPremisesSamAccountName == null` → `user.ntid` is set to `None` (purge), not left untouched
- [ ] `oauth.py`: Graph 5xx / network exception → `user.ntid` remains unchanged (no overwrite on failure)
- [ ] `openai.py`: pipeline-flagged model receives `payload["user"]["ntid"]` matching `user.ntid`; non-pipeline models do **not** carry it
- [ ] `llm_clients.py`: `ntid_context.set("foo")` → `_get_headers()` returns `{"user": "foo", ...}`
- [ ] `llm_clients.py`: empty `ntid_context` → `user` header is **omitted entirely** (not present as empty string)
- [ ] `orchestrator_agent_workflow.py`: `ContextVar` reset is reached even when workflow raises (the 3-deep finally)

### 7.2 Integration
- [ ] End-to-end on dev VM (`https://dev.cepm.amd.com:3443`): login → chat → confirm `user: <ntid>` header on outbound POST to `https://llm-api.amd.com` (pipeline log or `tcpdump`/mitmproxy)
- [ ] Concurrent test: 2 users login + chat in parallel → each request's outbound `user` header matches the calling user's NTID (verifies no ContextVar leak)
- [ ] Empty-NTID path: a user with `ntid IS NULL` → outbound has the `user` header **omitted**, not present as `""`

### 7.3 Manual Acceptance
- [ ] Re-login → `docker compose logs openwebui | grep '\[NTID\]'` should show `[NTID] fetched ...: <value>` (or `set on new user`)
- [ ] `SELECT email, ntid FROM [user] WHERE email = '<your-email>'` → `ntid` populated
- [ ] Send chat with a pipeline model → pipeline log shows `LLM_REQUEST` with `user:` header to `llm-api.amd.com`
- [ ] (Optional) `tcpdump -A -i any 'host llm-api.amd.com'` confirms wire-level header presence

---

## 8. Rollout Sequence

> **Critical constraint**: PRs cross repos. If pipeline ships without open-webui, `body.user.ntid` is always missing → gateway 401. If open-webui ships without pipeline, body field is set but never read → silent miss. **DDL must precede the open-webui code deploy** or SQLAlchemy will crash on the missing column.

### Dev VM iteration (current state — both PRs open)

```
[1]  Run DDL on dvse-cepm-sqlmi/openwebui:
     ALTER TABLE [user] ADD ntid NVARCHAR(64) NULL;
     CREATE INDEX IX_user_ntid ON [user](ntid) WHERE ntid IS NOT NULL;

[2]  Update docker-compose.yml openwebui service env:
     - OAUTH_SCOPES=openid email profile User.Read
     - ENABLE_OAUTH_NTID_FROM_GRAPH=true

[3]  Pull both PR branches into the dev VM:
     git checkout feat/ntid-user-header-propagation       (open-webui)
     git -C ../pipeline checkout feat/ntid-user-header-injection

[4]  docker compose down
     docker compose build openwebui pipelines
     docker compose up -d

[5]  Open https://dev.cepm.amd.com:3443/ → log in (accept consent on first time)
     Send a chat using a pipeline-flagged model

[6]  Verify per §7.3: log lines, DB row, outbound header
```

### Prod rollout (after dev signs off)

```
Day 0:  Both PRs reviewed, ready to merge
Day 1:  Run DDL on prod (pdase-cepm-sqlmi/openwebui)
Day 1:  Update prod env: OAUTH_SCOPES + ENABLE_OAUTH_NTID_FROM_GRAPH
Day 1:  Merge & deploy open-webui PR #44 — body field now appears (no-op until pipeline ships)
Day 1:  Merge & deploy pipeline PR #96 — outbound header now flows
Day 1:  (Optional) Run §6.1 backfill SQL to pre-populate users who haven't logged in lately
Day 2+: Monitor gateway 401 rate + [NTID] log lines
```

---

## 9. Rollback

| PR | Rollback impact | Mitigation |
|---|---|---|
| pipeline PR #96 | `user` header stops being sent → gateway 401 (post-enforcement) | Coordinate temporary enforcement skip with `dl.LLM-Gateway-Ops@amd.com` |
| open-webui PR #44 | Body field disappears; pipeline reads `""` → header omitted → gateway 401 | Same as above |
| Env flip `ENABLE_OAUTH_NTID_FROM_GRAPH=false` | Graph stops being called; existing `user.ntid` values are stale-but-functional until rows naturally update | Cheapest possible "off switch" without code revert |

Both PRs are **additive** (new column, new field, new header). `git revert` is clean. No destructive schema changes.

---

## 10. Resolved Questions

All originally open questions are now answered by the implementation:

| # | Question | Resolution |
|---|---|---|
| 1 | Body field name | `ntid` (lowercase string, single key in `payload["user"]`) — implemented |
| 2 | Behavior on missing NTID | Header omitted entirely (not empty string) — implemented in `llm_clients.py._get_headers` |
| 3 | Failure logging | Implemented at WARN/INFO via `[NTID]` log prefix in `oauth.py`; ContextVar value visible in Langfuse traces via `user_id_context` |
| 4 | Service account NTID for batch/CI | Out of scope for this plan; per IT FAQ, allocate a dedicated service account separately and inject via env or per-request override (future work) |
| 5 | Graph fetch security | Resolved by two-stage gating (env flag + `iss` validation); see §4.1 File D |
| 6 | Stale NTID purge on AD removal | Resolved by `ntid_fetched` flag distinguishing failure vs successful-empty fetch; see §4.1 File D |
| 7 | Single-transaction signup | Resolved by threading `ntid` through `Auths.insert_new_auth`; see §4.1 File C |

---

## 11. References

### Pull requests
- **open-webui**: [Datar-Tech/open-webui#44](https://github.com/Datar-Tech/open-webui/pull/44) — `feat(ntid): propagate AMD NTID to LLM Gateway via user HTTP header` (commits `b9744300a` initial impl + `5526b3eb9` review fixes)
- **pipeline**: [Datar-Tech/pipeline#96](https://github.com/Datar-Tech/pipeline/pull/96) — `feat(ntid): inject AMD NTID into LLM Gateway user HTTP header` (commit `77d4d45`)

### IT documentation
- [Confluence: User Header Modification](https://amd.atlassian.net/wiki/spaces/SI/pages/1655519770/User+Header+Modification) — primary spec
- [Confluence: Mandatory User Identification Policy and Enforcement Strategy](https://amd.atlassian.net/wiki/spaces/SI/pages/1655519770) (deadline 2026-05-02)

### IT contacts
- Gateway implementation: `dl.LLM-Gateway-Ops@amd.com`
- SLAI Suite / personal keys: `dl.SLAI-Suite-Ops@amd.com`

### Code reference (post-merge)
- Open WebUI feature config: `backend/open_webui/config.py` (`ENABLE_OAUTH_NTID_FROM_GRAPH`)
- Open WebUI OIDC + Graph fetch: `backend/open_webui/utils/oauth.py` (after `provider_sub` resolution)
- Open WebUI body injection: `backend/open_webui/routers/openai.py` (~line 660)
- Pipeline ContextVar declaration: `pipeline_modules/utils.py` (`ntid_context`)
- Pipeline header injection (single choke point): `pipeline_modules/llm_clients.py:_get_headers`
- Pipeline ContextVar set/reset: `pipeline_modules/agents/orchestrator_agent_workflow.py` (`run_orchestrator_workflow`)

---

## 12. Fallback: Plan B — Pipeline-Side AD Lookup

> **Status: not implemented.** Plan A (Microsoft Graph fetch) shipped in PRs #44/#96 and is the active path. Plan B is documented here as a **fallback** if Graph proves unreliable in production (e.g., persistent rate limiting, long timeouts, or `onPremisesSamAccountName` returning null for too many users). Switching is non-disruptive on the pipeline side because the body contract (`body.user.ntid`) is the same — open-webui would simply stop populating it and pipeline would resolve it itself.

### 12.1 Idea

Instead of teaching Open WebUI to capture and store NTID, let the **pipeline** look it up itself at request time. The pipeline already receives `body["user"]["email"]` (Open WebUI sends this today, no code change). The pipeline queries `PKG_ENG.[dbo].[ACTIVEDIRECTORY_USERS]` directly to translate `email → NTID`, caches the result, and emits the `user: <NTID>` header.

### 12.2 Why Plan B exists

The user table already has `email`. AD has `email → NTID`. Plan A (shipped) does the lookup at OIDC login via Microsoft Graph; Plan B would do it on demand at chat time. **Same data flow, different cache point.**

### 12.3 Comparison

| Dimension | Plan A (current §1–§10) | Plan B |
|---|---|---|
| Repos changed | `open-webui` + `pipeline` (1 DDL + 6 files) | `pipeline` only (4 files: 3 from §4.2 + 1 new `ad_client.py`) |
| Open WebUI schema | Adds dedicated `ntid` column (manual DDL) | Untouched |
| Open WebUI DB writes | Yes (`user.ntid` updated on OIDC login) | None |
| Backfill SQL needed | Yes (§6) | No |
| External blocker | Azure Entra ID optional claim config (IT) | None |
| Runtime cost per request | Zero (NTID already in body) | One DB lookup (cached LRU; ~0ms warm, ~10–50ms cold) |
| Pipeline infra needs | Existing | New: network access from pipeline host → `PKG_ENG` DB + read-only credential |
| Failure mode if AD is down | Pipeline still works (uses cached `user.info`) | Pipeline degrades — must decide: 503, fall back to cached, or send empty header |
| AD identity drift (rename/rejoin) | Stale until user re-logs in | Stale until cache TTL expires (configurable, e.g. 1h) |
| Schema coupling | Pipeline ignorant of AD schema | Pipeline directly depends on `ACTIVEDIRECTORY_USERS` table shape |

### 12.4 What Plan B keeps from Plan A

The entire **pipeline-side** half is unchanged:

- §4.2 File C (`llamaindex_pipeline_v6.1_..._modularized.py`) — same `pipe()` change, but reads `body["user"]["email"]` instead of `body["user"]["ntid"]`
- §4.2 File D (`orchestrator_agent_workflow.py`) — same `ContextVar` plumbing
- §4.2 File E (`pipeline_modules/llm_clients.py`) — same `_get_headers()` injection of `user: <NTID>`

### 12.5 New code Plan B requires

#### `pipeline_modules/ad_client.py` (new file)

Responsibilities:
1. Hold a connection (or pool) to MSSQL `PKG_ENG`
2. Expose `lookup_ntid(email: str) -> str | None`
3. In-memory LRU cache with TTL (recommend `cachetools.TTLCache(maxsize=10000, ttl=3600)`)
4. Strip `DOMAIN\` prefix from `NTName` (same gotcha as Plan A §6.1)
5. Log cache hit/miss metrics for ops visibility

Pseudocode skeleton:

```python
# pipeline_modules/ad_client.py
import pyodbc
from cachetools import TTLCache
from threading import Lock

_cache: TTLCache[str, str] = TTLCache(maxsize=10000, ttl=3600)
_lock = Lock()

def lookup_ntid(email: str) -> str | None:
    if not email:
        return None
    if email in _cache:
        return _cache[email]
    with _lock:  # avoid stampede on cold key
        if email in _cache:
            return _cache[email]
        with pyodbc.connect(AD_CONN_STR, readonly=True) as conn:
            row = conn.execute(
                "SELECT TOP 1 NTName FROM PKG_ENG.dbo.ACTIVEDIRECTORY_USERS "
                "WHERE mail COLLATE Latin1_General_100_CI_AS_SC_UTF8 = ? "
                "ORDER BY <tiebreaker>",
                email,
            ).fetchone()
        if not row:
            _cache[email] = ""        # negative cache, prevents repeated lookups
            return None
        ntid = row.NTName.split("\\")[-1]   # strip "amd\"
        _cache[email] = ntid
        return ntid
```

#### Changes to existing pipeline files (replace email-keyed flow for NTID)

- `llamaindex_pipeline_v6.1_..._modularized.py:228-230`: read `email = user.get("email", "")`; immediately call `ad_client.lookup_ntid(email)`; pass result down as `user_ntid`
- `orchestrator_agent_workflow.py` and `llm_clients.py`: identical to Plan A §4.2 D & E

### 12.6 New configuration (Pipeline `.env` / Valves)

| Var | Purpose |
|---|---|
| `AD_DB_CONN_STR` | MSSQL connection string for `PKG_ENG` (read-only credential) |
| `AD_CACHE_TTL_SEC` | Default 3600 |
| `AD_CACHE_MAX` | Default 10000 |

### 12.7 Test Plan delta vs §7

Add:
- [ ] `ad_client.lookup_ntid` returns correct stripped NTID for sample emails
- [ ] Cache hit on second call (no second DB query) — verify via mock or query counter
- [ ] Negative cache: missing email returns `None` and doesn't re-query within TTL
- [ ] Stampede: 100 concurrent calls for a cold key result in 1 DB query (lock works)
- [ ] AD unreachable: failure mode behaves per chosen policy (503 / empty header / cached)

### 12.8 Rollout delta vs §8

```
Day 0:  DBA grants pipeline service account read on PKG_ENG.dbo.ACTIVEDIRECTORY_USERS
Day 0:  Pipeline host network: confirm reachability to PKG_ENG
Day 1:  PR-1 (pipeline only, includes ad_client.py)
Day 2:  Stage; load test (verify cache effectiveness, p99 latency unchanged)
Day 3:  Prod
```

No Open WebUI deployment, no SQL backfill, no IT/Azure claim work.

### 12.9 When to switch to Plan B (post-implementation triggers)

Switch only if ≥1 of these is observed in production:

- Microsoft Graph rate-limited beyond what 1 retry can absorb (429s in `[NTID]` log)
- Graph timeout (>5s) for >5% of logins, slowing user perception of login
- `onPremisesSamAccountName` returns `null` for users we know have AD identities (suggests Entra hybrid sync issues we can't fix from our side)
- IT moves to deprecate the Graph optional permissions and forces a different lookup path

If switching:

1. Set `ENABLE_OAUTH_NTID_FROM_GRAPH=false` (off switch — no code revert)
2. Drop the `User.Read` scope from `OAUTH_SCOPES`
3. Build & deploy the `ad_client.py` per §12.5
4. In open-webui, change `payload["user"]["ntid"] = user.ntid or ""` to omit the key (or leave it; pipeline will prefer its own lookup)

The `user.ntid` column can stay on the schema — harmless, and useful as a per-user cache that the pipeline can prime if desired.
