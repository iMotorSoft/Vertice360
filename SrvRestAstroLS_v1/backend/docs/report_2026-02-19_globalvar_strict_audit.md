# GlobalVar Strict Audit - 2026-02-19

## Scope and rule
Rule audited: no direct environment reads outside `backend/globalVar.py`.
Forbidden patterns: `os.getenv(...)`, `os.environ.get(...)`, `os.environ[...]`.

## 1) Canonical config available in `globalVar.py`
### DB v360 and demo-related config
- `DB_PG_V360_URL` (`globalVar.py:99`)
- `ALLOW_FALLBACK_V360_DB` (`globalVar.py:100`)
- `get_v360_db_url()` strict validator/fallback helper (`globalVar.py:268`)
- `_validate_v360_db_url()` validation helper (`globalVar.py:257`)

### Canonical env access helpers (added/used)
- `get_env_str(name, default)` (`globalVar.py:199`)
- `get_env_int(name, default, minimum=...)` (`globalVar.py:204`)
- `get_env_bool(name, default)` (`globalVar.py:216`)

## 2) Findings (initial scan before normalization)
### Runtime findings
- `modules/vertice360_orquestador_demo/db.py:57`
  - Snippet: `os.environ.get("V360_DB_POOL_MIN_SIZE", "1")`
- `modules/vertice360_orquestador_demo/db.py:58`
  - Snippet: `os.environ.get("V360_DB_POOL_MAX_SIZE", "4")`
- `modules/messaging/providers/meta/whatsapp/client.py:22`
  - Snippet: `os.environ.get("DEMO_DISABLE_META_SEND") == "1"`

### Snippet/tooling findings
- `modules/messaging/providers/bird/snippets/bird_verify_api.py:7-9`
- `modules/messaging/providers/bird/snippets/bird_verify_whatsapp.py:8-10`
- `modules/messaging/providers/gupshup/snippets/send_text.py:18,21,22`
- `modules/messaging/providers/gupshup/snippets/test_webhook_post_local.py:17,21`
- `modules/messaging/providers/gupshup/snippets/send_test_to_541130946950.py:10`
- `modules/messaging/providers/meta/snippets/send_text.py:26-28`
- `modules/messaging/providers/meta/snippets/send_template.py:23-25`
- `modules/messaging/providers/meta/snippets/send_template_vars.py:36-38`

### Test finding
- `tests/test_gupshup_globalvar_defaults.py:10,11,25,30`

## 3) Impact and risk
- Configuration drift: each module could parse defaults differently.
- Hidden runtime coupling: behavior depends on local env reads not visible in canonical config.
- Security/ops risk: harder auditing and change control for configuration usage.
- Test fragility: env mutation spread across files increases side effects.

## 4) Replacement applied
- Replaced direct env reads with `globalVar` constants/helpers.
- Kept business logic unchanged; only config access path was normalized.

### Runtime replacements
- `modules/vertice360_orquestador_demo/db.py:56-57`
  - now uses `globalVar.get_env_int("V360_DB_POOL_MIN_SIZE"...)` and `globalVar.get_env_int("V360_DB_POOL_MAX_SIZE"...)`.
- `modules/messaging/providers/meta/whatsapp/client.py:21`
  - now uses `globalVar.get_env_bool("DEMO_DISABLE_META_SEND", False)`.

### Snippet replacements
- All snippet files listed above now consume env through `globalVar.get_env_str(...)` or existing canonical constants in `globalVar`.

### Test cleanup
- `tests/test_gupshup_globalvar_defaults.py` rewritten to use `monkeypatch` context instead of direct `os.environ[...]` / `.get(...)`.

## 5) Post-normalization verification
Command run:
- `rg -n "os\.getenv\(|os\.environ\.get\(|os\.environ\[" . --glob '!.venv/**' --glob '!docs/**' --glob '!globalVar.py' --glob '!tests/test_no_direct_env_reads.py'`

Result:
- No matches.

Command run:
- `rg -n "DB_PG_V360_URL|ALLOW_FALLBACK_V360_DB" . --glob '!globalVar.py'`

Result:
- Only docs/tests textual references, no direct env access logic outside `globalVar.py`.

## 6) Anti-regression guard
- Added `tests/test_no_direct_env_reads.py`.
- The test scans backend `.py` files and fails on forbidden patterns outside `globalVar.py`.
- It excludes non-project/runtime artifacts (`.venv`, caches, and itself) to avoid false positives.
