from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from backend import globalVar
from backend.modules.messaging.providers.gupshup.whatsapp.service import (
    GupshupWhatsAppSendError,
    send_text_message as gupshup_send_text,
)
from backend.modules.vertice360_orquestador_demo import db, repo
from backend.telemetry.context import set_correlation_id

logger = logging.getLogger(__name__)

DOMAIN = "vertice360_orquestador_demo"
STAGE_PENDING_VISIT = "Pendiente de visita"
STAGE_WAITING_CONFIRMATION = "Esperando confirmación"
STAGE_VISIT_CONFIRMED = "Visita confirmada"
REQUIREMENTS_FIELDS = ("ambientes", "presupuesto", "moneda")

ALLOWED_SOURCES = {"whatsapp", "instagram", "web", "meta_ads", "other"}
PROJECT_ALIASES = {
    "BULNES_966_ALMAGRO": ("bulnes", "966", "almagro", "bulnes 966"),
    "GDR_3760_SAAVEDRA": ("gdr", "3760", "gdr 3760", "garcia del rio", "garcia del rio 3760"),
    "MANZANARES_3277": ("manzanares", "3277", "manzanares 3277", "nunez", "nuñez"),
}

VISIT_REQUEST_PATTERNS = (
    r"\bvisita(?:r)?\b",
    r"\bentrevista\b",
    r"\bcita\b",
    r"\bpuedo\s+visitarl[oa]s?\b",
    r"\bpuedo\s+verlo\b",
    r"\blo\s+puedo\s+ver\b",
    r"\bse\s+puede\s+visitar\b",
    r"\bse\s+puede\s+ver\b",
    r"\bse\s+puede\s+pasar\s+a\s+ver\b",
    r"\bquiero\s+visitarl[oa]s?\b",
    r"\bquiero\s+verlo\b",
    r"\bme\s+gustaria\s+visitarl[oa]s?\b",
    r"\bpodemos\s+verlo\b",
    r"\bpodemos\s+visitarl[oa]s?\b",
    r"\bcoordinar(?:mos)?\b.*\bvisita\b",
    r"\bcoordinar\b",
    r"\bcoordinamos\b",
    r"\bagendar(?:mos)?\b",
    r"\bir\s+a\s+ver\b",
    r"\bpodemos\s+agendar\b",
    r"\bver\s+el\s+depto\b",
    r"\bpasar\s+a\s+ver\b",
)

OUT_OF_SCOPE_PATTERNS = (
    r"\bgaranti[sz]a\b",
    r"\bpromete[snr]?\b",
    r"\blegal(?:es)?\b",
    r"\bcontrato\b",
    r"\bescriban[oa]\b",
    r"\bjuicio\b",
    r"\breclamo\b",
)

INTENT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "FINANCING",
        (r"\bfinanciaci[oó]n\b", r"\bcuotas?\b", r"\banticipo\b", r"\bplan(?:es)?\b"),
    ),
    (
        "DELIVERY",
        (r"\bentrega\b", r"\bposesi[oó]n\b", r"\bfecha\s+estimada\b", r"\bcu[aá]ndo\s+entregan\b"),
    ),
    (
        "AVAILABILITY",
        (
            r"\bdisponible(?:s)?\b",
            r"\bstock\b",
            r"\bquedan\b",
            r"\bcu[aá]ntas?\s+unidades\b",
            r"\bcu[aá]ntos?\s+hay\b",
            r"\bambientes?\s+disponibles\b",
            r"\bhay\s+disponibles\b",
            r"\breservad",
        ),
    ),
    (
        "PRICE",
        (
            r"\bprecio(?:s)?\b",
            r"\bvalor(?:es)?\b",
            r"\bcu[aá]nto\s+sale\b",
            r"\bcu[aá]nto\s+est[aá]\b",
            r"\busd\b",
            r"\bars\b",
            r"\bu\s*\$\s*s?\b",
            r"\bd[oó]lares?\b",
            r"\bpesos?\b",
            r"\bsus\s+precios\b",
            r"\bme\s+das\s+los\s+precios\b",
            r"\bpasame\s+precios\b",
            r"\by\s+los\s+precios\b",
        ),
    ),
    ("LOCATION", (r"\bd[oó]nde\b", r"\bubicaci[oó]n\b", r"\bbarrio\b", r"\bzona\b", r"\bdirecci[oó]n\b")),
    (
        "UNIT_TYPES",
        (
            r"\btipolog[ií]a(?:s)?\b",
            r"\bde\s+qu[eé]\s+tipo\b",
            r"\bqu[eé]\s+tipo\b",
            r"\btipos?\b",
            r"\bmono\b",
            r"\bmonoamb",
            r"\b2\s+ambientes?\b",
            r"\b3\s+ambientes?\b",
            r"\b4\s+ambientes?\b",
            r"\bqu[eé]\s+hay\b",
        ),
    ),
    ("FEATURES", (r"\bamenities\b", r"\bcaracter[ií]sticas?\b", r"\bservicios?\b", r"\bseguridad\b", r"\bdom[oó]tica\b", r"\bgym\b", r"\bpileta\b")),
)


def demo_db_ready() -> bool:
    return db.can_connect()


def _safe_demo_phone(raw_phone: str | None) -> str:
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if not digits:
        return ""
    if str(raw_phone or "").strip().startswith("+"):
        return f"+{digits}"
    return f"+{digits}"


def _normalize_phone_e164(raw_phone: str) -> str:
    text = str(raw_phone or "").strip()
    if not text:
        raise ValueError("phone is required")

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        raise ValueError("phone is invalid")

    if text.startswith("+"):
        return f"+{digits}"

    if digits.startswith("549"):
        return f"+{digits}"

    if digits.startswith("54"):
        return f"+549{digits[2:]}"

    if digits.startswith("9"):
        return f"+54{digits}"

    if digits.startswith("0"):
        return f"+549{digits.lstrip('0')}"

    return f"+549{digits}"


def _normalize_source(source: str | None) -> str:
    clean = str(source or "").strip().lower().replace(" ", "_")
    if clean in ALLOWED_SOURCES:
        return clean
    if clean in {"meta", "metaads", "meta_ad"}:
        return "meta_ads"
    return "whatsapp"


def _normalize_snippet(text: str, limit: int = 160) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _digits_only(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_optional_phone(value: Any) -> str | None:
    digits = _digits_only(value)
    if not digits:
        return None
    return f"+{digits}"


def _provider_line_prefix(provider_name: str | None) -> str:
    clean = str(provider_name or "").strip().lower()
    if "meta" in clean:
        return "meta"
    if "gupshup" in clean:
        return "gupshup"
    return "inbound"


def _default_gupshup_line_key() -> str:
    sender_digits = _digits_only(globalVar.GUPSHUP_SRC_NUMBER) or _digits_only(
        globalVar.get_gupshup_wa_sender_provider_value()
    )
    if sender_digits:
        return f"gupshup:{sender_digits}"
    return "gupshup:unknown"


def _derive_inbound_line(
    provider_name: str | None,
    provider_meta: dict[str, Any] | None,
) -> dict[str, str | None]:
    meta = provider_meta if isinstance(provider_meta, dict) else {}
    explicit_key = str(meta.get("inbound_line_key") or "").strip()
    explicit_phone = _normalize_optional_phone(meta.get("inbound_line_phone"))
    if explicit_key:
        return {
            "inbound_line_key": explicit_key,
            "inbound_line_phone": explicit_phone,
        }

    prefix = _provider_line_prefix(provider_name)
    phone_candidate = (
        meta.get("to")
        or meta.get("destination")
        or meta.get("receiver")
        or meta.get("recipient")
        or meta.get("line")
        or meta.get("connected_number")
        or meta.get("inbound_line_phone")
    )
    phone_digits = _digits_only(phone_candidate)

    if prefix == "meta":
        meta_phone_number_id = meta.get("phone_number_id") or meta.get("phoneNumberId")
        phone_number_id_digits = _digits_only(meta_phone_number_id)
        if phone_number_id_digits:
            return {
                "inbound_line_key": f"meta:{phone_number_id_digits}",
                "inbound_line_phone": _normalize_optional_phone(phone_candidate),
            }
        if phone_digits:
            return {
                "inbound_line_key": f"meta:{phone_digits}",
                "inbound_line_phone": _normalize_optional_phone(phone_candidate),
            }
        fallback_meta_id = _digits_only(globalVar.META_VERTICE360_PHONE_NUMBER_ID)
        if fallback_meta_id:
            return {
                "inbound_line_key": f"meta:{fallback_meta_id}",
                "inbound_line_phone": None,
            }
        return {
            "inbound_line_key": "meta:unknown",
            "inbound_line_phone": None,
        }

    if phone_digits:
        return {
            "inbound_line_key": f"{prefix}:{phone_digits}",
            "inbound_line_phone": _normalize_optional_phone(phone_candidate),
        }

    if prefix == "gupshup":
        return {
            "inbound_line_key": _default_gupshup_line_key(),
            "inbound_line_phone": _normalize_optional_phone(globalVar.GUPSHUP_SRC_NUMBER),
        }

    return {
        "inbound_line_key": f"{prefix}:unknown",
        "inbound_line_phone": None,
    }


def _resolve_dashboard_inbound_line(row: dict[str, Any]) -> dict[str, str | None]:
    ticket_key = str(row.get("ticket_inbound_line_key") or "").strip()
    message_key = str(row.get("message_inbound_line_key") or "").strip()
    inbound_line_key = ticket_key or message_key

    inbound_line_phone = _normalize_optional_phone(
        row.get("ticket_inbound_line_phone")
        or row.get("message_inbound_line_phone")
        or row.get("message_to_phone")
    )

    if not inbound_line_key:
        derived = _derive_inbound_line(
            str(row.get("message_provider") or "gupshup_whatsapp"),
            {
                "to": row.get("message_to_phone"),
                "phone_number_id": row.get("message_phone_number_id"),
                "inbound_line_phone": inbound_line_phone,
            },
        )
        inbound_line_key = str(derived.get("inbound_line_key") or "").strip()
        if not inbound_line_phone:
            inbound_line_phone = derived.get("inbound_line_phone")

    return {
        "inbound_line_key": inbound_line_key or _default_gupshup_line_key(),
        "inbound_line_phone": inbound_line_phone,
    }


def _contains_project_code(text: str, code: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Z0-9_]){re.escape(code.upper())}(?![A-Z0-9_])",
            text.upper(),
        )
    )


def _normalize_alias_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_accents.lower()
    lowered = re.sub(r"[_\-\/]+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(lowered.split())


def _compact_alias_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _normalize_alias_text(value))


def _match_project_alias(text: str) -> tuple[str | None, str | None]:
    normalized = _normalize_alias_text(text)
    compact = _compact_alias_text(text)
    if not normalized:
        return None, None

    best_code: str | None = None
    best_alias: str | None = None
    best_pos = -1
    for code, aliases in PROJECT_ALIASES.items():
        candidates = [code, code.replace("_", " "), *aliases]
        for raw_alias in candidates:
            alias = _normalize_alias_text(raw_alias)
            if not alias:
                continue
            alias_compact = _compact_alias_text(alias)
            position = normalized.rfind(alias)
            if position >= 0 and position >= best_pos:
                best_pos = position
                best_code = code
                best_alias = raw_alias
                continue
            compact_pos = compact.rfind(alias_compact) if alias_compact else -1
            if compact_pos >= 0 and compact_pos >= best_pos:
                best_pos = compact_pos
                best_code = code
                best_alias = raw_alias
    return best_code, best_alias


def _infer_project(
    conn: Any, project_code: str | None, text: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    metadata: dict[str, Any] = {"source": None, "matched_text": None}
    explicit = str(project_code or "").strip()
    if explicit:
        project = repo.get_project_by_code(conn, explicit)
        if project is not None:
            metadata["source"] = "explicit"
            metadata["matched_text"] = explicit
            return project, metadata

    alias_code, matched_alias = _match_project_alias(text)
    if alias_code:
        project = repo.get_project_by_code(conn, alias_code)
        if project is not None:
            metadata["source"] = "alias"
            metadata["matched_text"] = matched_alias
            return project, metadata

    codes = repo.list_project_codes(conn)
    for code in codes:
        if _contains_project_code(text, code):
            project = repo.get_project_by_code(conn, code)
            if project is not None:
                metadata["source"] = "code_in_text"
                metadata["matched_text"] = code
                return project, metadata
    return None, metadata


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().split())


def parse_ambientes(text: str) -> int | None:
    clean = _normalize_text(text)
    if not clean:
        return None

    if re.search(r"\bmono(?:ambiente)?s?\b", clean):
        return 1

    digit_match = re.search(r"\b([1-4])\s*amb(?:\.|ientes?)?\b", clean)
    if digit_match:
        return int(digit_match.group(1))

    word_map = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4}
    word_match = re.search(r"\b(un|uno|dos|tres|cuatro)\s+amb(?:\.|ientes?)?\b", clean)
    if word_match:
        return word_map.get(word_match.group(1))
    return None


def _parse_compact_number(token: str) -> Decimal | None:
    compact = str(token or "").strip().replace(" ", "")
    if not compact:
        return None

    if "." in compact and "," in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = compact.replace(".", "").replace(",", ".")
        else:
            normalized = compact.replace(",", "")
    elif re.match(r"^\d{1,3}(?:[.,]\d{3})+$", compact):
        normalized = compact.replace(".", "").replace(",", "")
    else:
        normalized = compact.replace(",", ".")

    try:
        return Decimal(normalized)
    except Exception:  # noqa: BLE001
        return None


def parse_budget_currency(text: str) -> dict[str, Any]:
    clean = _normalize_text(text)
    if not clean:
        return {"presupuesto": None, "moneda": None}

    currency = None
    if re.search(r"(?:\bu\s*\$\s*s?\b|\busd\b|\bdolares?\b|\bdolar(?:es)?\b)", clean):
        currency = "USD"
    elif re.search(r"(?:\bars\b|\bpeso(?:s)?\b|\bargentin(?:os|as)\b)", clean):
        currency = "ARS"

    amount_candidates: list[tuple[int, str]] = []
    for match in re.finditer(
        r"(?<!\w)(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*(k|m|mil))?(?!\w)",
        clean,
    ):
        value = _parse_compact_number(match.group(1))
        if value is None:
            continue
        suffix = str(match.group(2) or "").lower()
        multiplier = 1
        if suffix in {"k", "mil"}:
            multiplier = 1000
        elif suffix == "m":
            multiplier = 1_000_000
        computed = int(value * multiplier)
        amount_candidates.append((computed, suffix))

    if not amount_candidates:
        return {"presupuesto": None, "moneda": currency}

    presupuesto, suffix = max(amount_candidates, key=lambda item: item[0])
    has_budget_context = bool(
        re.search(
            r"\b(presupuesto|budget|inversion|invierto|tengo|dispongo|hasta|tope|maximo|max|usd|ars|dolar|peso)\b",
            clean,
        )
    )
    if currency is None and not suffix and not has_budget_context:
        return {"presupuesto": None, "moneda": None}
    if presupuesto < 1000 and not suffix and currency is None:
        return {"presupuesto": None, "moneda": currency}
    return {"presupuesto": presupuesto, "moneda": currency}


def _extract_ticket_requirements(detail: dict[str, Any] | None) -> dict[str, Any]:
    base_summary = detail.get("summary_jsonb") if isinstance(detail, dict) else {}
    requirements = {}
    if isinstance(base_summary, dict):
        raw = base_summary.get("requirements")
        if isinstance(raw, dict):
            requirements = dict(raw)

    if detail:
        if detail.get("req_ambientes") is not None:
            requirements["ambientes"] = int(detail.get("req_ambientes"))
        if detail.get("req_presupuesto") is not None:
            requirements["presupuesto"] = int(detail.get("req_presupuesto"))
        if detail.get("req_moneda"):
            requirements["moneda"] = str(detail.get("req_moneda")).upper()

    normalized: dict[str, Any] = {}
    if requirements.get("ambientes") is not None:
        normalized["ambientes"] = int(requirements["ambientes"])
    if requirements.get("presupuesto") is not None:
        normalized["presupuesto"] = int(requirements["presupuesto"])
    if requirements.get("moneda"):
        normalized["moneda"] = str(requirements["moneda"]).upper()
    return normalized


def _missing_requirements(requirements: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIREMENTS_FIELDS:
        value = requirements.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def _requirements_patch_from_text(text: str) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    ambientes = parse_ambientes(text)
    if ambientes is not None:
        patch["ambientes"] = ambientes

    budget_data = parse_budget_currency(text)
    if budget_data.get("presupuesto") is not None:
        patch["presupuesto"] = int(budget_data["presupuesto"])
    if budget_data.get("moneda"):
        patch["moneda"] = str(budget_data["moneda"]).upper()
    return patch


def _is_visit_request_intent(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    for pattern in VISIT_REQUEST_PATTERNS:
        if re.search(pattern, clean):
            return True
    return False


def _is_out_of_scope_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, clean):
            return True
    return False


def _looks_like_project_question(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if "?" in text:
        return True
    return bool(
        re.search(
            r"\b(amenities|caracteristicas|precio|valor|financiacion|financian|entrega|posesion|m2|metros|expensas|ubicacion)\b",
            clean,
        )
    )


def _is_confirmation_message(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(re.search(r"\b(si|dale|ok|perfecto|confirmo|de acuerdo|genial|listo)\b", clean))


def _message_mentions_schedule(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    has_day = bool(
        re.search(
            r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo|manana|tarde|noche)\b",
            clean,
        )
    )
    has_time = bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:hs|h)?\b", clean))
    return has_day or has_time


def _build_vera_project_selected_reply(project_name: str) -> str:
    return (
        f"Perfecto, tomamos {project_name}. "
        "¿Qué te gustaría saber primero: características, precio, financiación o entrega?"
    )


def _build_vera_visit_requested_reply() -> str:
    return (
        "Sí, claro 🙂. Ya lo dejo en 'Pendiente de visita' para que un asesor te proponga un horario por este chat. "
        "¿Preferís por la mañana o por la tarde?"
    )


def _build_vera_sensitive_reply(project_name: str) -> str:
    return (
        f"Sobre {project_name}, para ese punto prefiero confirmártelo con un asesor para darte información precisa. "
        "Si te parece, te lo gestiono ahora por este mismo chat."
    )


def _followup_intent_from_summary(
    text: str,
    summary: dict[str, Any] | None,
) -> tuple[str | None, str]:
    summary_obj = summary if isinstance(summary, dict) else {}
    last_intent = str(summary_obj.get("last_intent") or "").upper()
    clean = _normalize_text(text)
    asks_types = bool(
        re.search(r"\b(de\s+que\s+tipo|qu[eé]\s+tipo|tipolog[ií]a(?:s)?|tipos?|qu[eé]\s+hay)\b", clean)
    )
    asks_prices = bool(
        re.search(r"\b(sus\s+precios|los\s+precios|y\s+los\s+precios|precios?|valores?)\b", clean)
    )
    if last_intent == "AVAILABILITY" and asks_types:
        return "UNIT_TYPES", "followup_from_availability"
    if last_intent in {"AVAILABILITY", "UNIT_TYPES"} and asks_prices:
        return "PRICE", "followup_from_previous"
    return None, "none"


def _detect_project_intent(
    text: str,
    *,
    summary: dict[str, Any] | None = None,
) -> tuple[str, bool, str]:
    if _is_visit_request_intent(text):
        return "VISIT_REQUEST", False, "visit_pattern"
    followup_intent, followup_reason = _followup_intent_from_summary(text, summary)
    if followup_intent:
        return followup_intent, True, followup_reason
    clean = _normalize_text(text)
    if not clean:
        return "GENERAL", False, "empty"
    if re.search(r"\btipolog[ií]a", clean):
        return "UNIT_TYPES", False, "keyword_tipologia"
    if re.search(r"\bambientes?\b", clean) and re.search(r"\bdisponib|quedan|stock\b", clean):
        return "AVAILABILITY", False, "keyword_amb_disponible"
    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, clean):
                return intent, False, f"keyword:{pattern}"
    return "GENERAL", False, "default_general"


def _extract_currency_slot(text: str) -> str | None:
    parsed = parse_budget_currency(text)
    currency = str(parsed.get("moneda") or "").strip().upper()
    if currency in {"USD", "ARS"}:
        return currency
    clean = _normalize_text(text)
    if re.search(r"\b(u\s*\$\s*s?|usd|dolares?|dolar)\b", clean):
        return "USD"
    if re.search(r"\b(ars|pesos?)\b", clean):
        return "ARS"
    return None


def _extract_query_slots(text: str) -> dict[str, Any]:
    return {
        "ambientes": parse_ambientes(text),
        "currency": _extract_currency_slot(text),
    }


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        compact = [part.strip() for part in value.split(",")]
        return [part for part in compact if part]
    return [value]


def _dedupe_texts(values: list[Any], *, limit: int = 6) -> list[str]:
    deduped: list[str] = []
    for raw in values:
        clean = " ".join(str(raw or "").split()).strip()
        if not clean:
            continue
        if clean in deduped:
            continue
        deduped.append(clean)
        if len(deduped) >= limit:
            break
    return deduped


def _source_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for row in rows:
        source = str(row.get("_source_table") or "").strip()
        if source and source not in sources:
            sources.append(source)
    return sources


def _source_from_payload(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    source = str(payload.get("source_table") or "").strip()
    return [source] if source else []


def _overview_project_name(overview: dict[str, Any] | None, fallback: str = "") -> str:
    row = overview if isinstance(overview, dict) else {}
    return (
        str(row.get("name") or row.get("project_name") or fallback or "").strip()
        or "el proyecto"
    )


def _overview_description(overview: dict[str, Any] | None) -> str:
    row = overview if isinstance(overview, dict) else {}
    for key in ("description", "proposal", "propuesta_valor", "short_description"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _overview_location_text(overview: dict[str, Any] | None) -> str:
    row = overview if isinstance(overview, dict) else {}
    location_value = row.get("location_jsonb")
    location_data = location_value if isinstance(location_value, dict) else {}
    location_chunks: list[str] = []
    for key in ("address", "street", "direccion", "line1"):
        value = str(location_data.get(key) or row.get(key) or "").strip()
        if value:
            location_chunks.append(value)
            break
    for key in ("neighborhood", "barrio", "zone", "zona", "district"):
        value = str(location_data.get(key) or row.get(key) or "").strip()
        if value and value not in location_chunks:
            location_chunks.append(value)
    for key in ("city", "ciudad"):
        value = str(location_data.get(key) or row.get(key) or "").strip()
        if value and value not in location_chunks:
            location_chunks.append(value)
    return ", ".join(location_chunks)


def _extract_marketing_copies(assets: list[dict[str, Any]]) -> list[str]:
    values: list[Any] = []
    for row in assets:
        values.extend(
            [
                row.get("short_copy"),
                row.get("title"),
                row.get("text"),
                row.get("copy"),
                row.get("whatsapp_prefill"),
            ]
        )
    return _dedupe_texts(values, limit=4)


def _extract_marketing_chips(assets: list[dict[str, Any]]) -> list[str]:
    chips: list[Any] = []
    for row in assets:
        chips.extend(_as_list(row.get("chips")))
    return _dedupe_texts(chips, limit=6)


def _extract_overview_features(overview: dict[str, Any] | None) -> list[str]:
    row = overview if isinstance(overview, dict) else {}
    values: list[Any] = []
    values.extend(_as_list(row.get("tags")))
    values.extend(_as_list(row.get("amenities")))
    for key in ("features", "servicios", "domotica", "seguridad"):
        values.extend(_as_list(row.get(key)))
    return _dedupe_texts(values, limit=6)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _format_price(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".")


def _format_date_like(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return text


def _human_availability_status(value: Any) -> str:
    clean = _normalize_text(str(value or ""))
    if clean in {"available", "disponible", "activo", "active"}:
        return "disponibles"
    if clean in {"reserved", "reservada", "reservado"}:
        return "reservadas"
    if clean in {"sold", "vendida", "vendido"}:
        return "vendidas"
    if clean in {"unavailable", "no disponible", "no_disponible"}:
        return "no disponibles"
    return str(value or "sin estado")


def _ticket_selected_project(detail: dict[str, Any] | None) -> dict[str, Any]:
    local_detail = detail if isinstance(detail, dict) else {}
    summary = local_detail.get("summary_jsonb")
    summary_obj = summary if isinstance(summary, dict) else {}
    selected = summary_obj.get("selected_project")
    selected_obj = selected if isinstance(selected, dict) else {}
    return {
        "code": str(
            selected_obj.get("code")
            or local_detail.get("project_code")
            or ""
        ).strip(),
        "name": str(
            selected_obj.get("name")
            or local_detail.get("project_name")
            or ""
        ).strip(),
        "prompted_once": bool(summary_obj.get("project_prompted_once")),
    }


def _ticket_summary(detail: dict[str, Any] | None) -> dict[str, Any]:
    local_detail = detail if isinstance(detail, dict) else {}
    summary = local_detail.get("summary_jsonb")
    return summary if isinstance(summary, dict) else {}


def _is_available_status(value: Any) -> bool:
    clean = _normalize_text(str(value or ""))
    return clean in {"available", "disponible", "activo", "active"}


def _extract_available_by_rooms(
    conn: Any,
    project_code: str,
) -> dict[int, int]:
    list_units = getattr(repo, "list_demo_units", None)
    if callable(list_units):
        rows = list_units(conn, project_code, rooms=None, currency=None) or []
        grouped: dict[int, int] = {}
        for row in rows:
            if not _is_available_status(row.get("availability_status")):
                continue
            rooms_raw = row.get("rooms_count")
            try:
                rooms = int(rooms_raw)
            except Exception:  # noqa: BLE001
                continue
            grouped[rooms] = grouped.get(rooms, 0) + 1
        if grouped:
            return grouped

    types = repo.get_unit_types(conn, project_code)
    fallback: dict[int, int] = {}
    for row in types:
        rooms_raw = row.get("rooms")
        if rooms_raw in (None, "", "null"):
            continue
        try:
            rooms = int(str(rooms_raw))
        except Exception:  # noqa: BLE001
            continue
        count_raw = row.get("units_count")
        try:
            count = int(count_raw)
        except Exception:  # noqa: BLE001
            count = 0
        if count > 0:
            fallback[rooms] = fallback.get(rooms, 0) + count
    return fallback


def _price_ranges_by_rooms(
    conn: Any,
    project_code: str,
    *,
    rooms_list: list[int],
    currency: str | None = None,
) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for rooms in sorted(set(rooms_list)):
        prices = repo.get_prices_by_rooms(conn, project_code, rooms=rooms, currency=currency)
        numeric = [value for value in (_to_float(row.get("price")) for row in prices) if value is not None]
        if not numeric:
            continue
        currencies = _dedupe_texts([row.get("currency") for row in prices], limit=1)
        ranges.append(
            {
                "rooms": rooms,
                "currency": currency or (currencies[0] if currencies else ""),
                "low": min(numeric),
                "high": max(numeric),
                "source_table": "demo_units" if any(str(row.get("_source_table")) == "demo_units" for row in prices) else "prices",
            }
        )
    return ranges


def _list_projects_brief(conn: Any) -> str:
    rows = repo.list_projects(conn)
    labels = _dedupe_texts(
        [row.get("name") or row.get("code") for row in rows],
        limit=6,
    )
    if not labels:
        return _build_vera_project_fallback()
    return "Hoy tengo estos proyectos: " + ", ".join(labels) + ". ¿Sobre cuál querés que te pase detalle?"


def _build_missing_project_reply(prompted_once: bool) -> str:
    if not prompted_once:
        return "¿Sobre qué proyecto querés consultar: Bulnes 966, GDR 3760 o Manzanares 3277?"
    return (
        "Para darte datos exactos necesito el proyecto. "
        "Si preferís, te deriva un asesor y lo confirma por este chat."
    )


def _resolve_project_knowledge_reply(
    conn: Any,
    *,
    ticket_id: str,
    detail: dict[str, Any] | None,
    question: str,
) -> dict[str, Any]:
    summary_obj = _ticket_summary(detail)
    intent, is_followup, intent_reason = _detect_project_intent(
        question,
        summary=summary_obj,
    )
    slots = _extract_query_slots(question)
    selected_project = _ticket_selected_project(detail)
    project_code = selected_project["code"]
    project_name = selected_project["name"]
    summary_patch: dict[str, Any] = {}

    asks_project_catalog = bool(
        re.search(r"\b(que|cu[aá]les)\s+proyectos?\s+ten[eé]s\b", _normalize_text(question))
    )

    if not project_code:
        if intent == "GENERAL" and asks_project_catalog:
            return {
                "variant": "project_catalog",
                "intent": "GENERAL",
                "followup": False,
                "reason": "project_catalog",
                "answer": _list_projects_brief(conn),
                "found": True,
                "fields_used": ["projects.list"],
                "data_sources": ["projects"],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        alias_code, matched_alias = _match_project_alias(question)
        if alias_code:
            project_row = repo.get_project_by_code(conn, alias_code)
            if project_row:
                project_code = str(project_row.get("code") or "").strip()
                project_name = str(project_row.get("name") or "").strip()
                summary_patch["selected_project"] = {
                    "id": project_row.get("id"),
                    "code": project_code,
                    "name": project_name,
                    "matched_alias": matched_alias,
                }
                repo.update_ticket_activity(
                    conn,
                    ticket_id,
                    project_id=str(project_row.get("id") or "") or None,
                )

    if not project_code:
        reply = _build_missing_project_reply(selected_project["prompted_once"])
        summary_patch["project_prompted_once"] = True
        return {
            "variant": "choose_project_once" if not selected_project["prompted_once"] else "project_handoff",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": reply,
            "found": False,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": "",
            "project_name": "",
            "result_slots": {},
        }

    overview = repo.get_project_overview(conn, project_code)
    marketing_assets = repo.get_project_marketing_assets(conn, project_code)
    project_name = project_name or _overview_project_name(overview, fallback=project_code)
    data_sources = _source_from_rows(marketing_assets)
    fields_used: list[str] = []
    found = False

    if overview:
        source = str(overview.get("_source_table") or "").strip()
        if source and source not in data_sources:
            data_sources.append(source)

    if _is_out_of_scope_query(question):
        return {
            "variant": "project_sensitive",
            "intent": intent,
            "followup": is_followup,
            "reason": "out_of_scope",
            "answer": _build_vera_sensitive_reply(project_name),
            "found": False,
            "fields_used": [],
            "data_sources": data_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    answer = ""
    result_slots: dict[str, Any] = {}
    if intent == "FEATURES":
        copies = _extract_marketing_copies(marketing_assets)
        chips = _extract_marketing_chips(marketing_assets)
        description = _overview_description(overview)
        overview_features = _extract_overview_features(overview)
        if copies or chips:
            pieces: list[str] = []
            if copies:
                pieces.append(copies[0])
                fields_used.append("marketing_assets.short_copy")
            if chips:
                pieces.append(f"Amenities destacados: {', '.join(chips[:4])}.")
                fields_used.append("marketing_assets.chips")
            answer = " ".join(pieces)
            found = True
        elif description:
            answer = f"Sobre {project_name}: {description}"
            fields_used.append("projects.description")
            found = True
        elif overview_features:
            answer = f"En {project_name} se destaca: {', '.join(overview_features[:4])}."
            fields_used.append("projects.tags")
            found = True
        else:
            answer = _build_vera_sensitive_reply(project_name)

    elif intent == "LOCATION":
        location_text = _overview_location_text(overview)
        if location_text:
            answer = f"{project_name} está en {location_text}."
            fields_used.append("projects.location_jsonb")
            found = True
        else:
            answer = _build_vera_sensitive_reply(project_name)

    elif intent == "UNIT_TYPES":
        available_by_rooms = _extract_available_by_rooms(conn, project_code)
        if available_by_rooms:
            parts = [f"{rooms} amb ({count})" for rooms, count in sorted(available_by_rooms.items())]
            answer = f"Disponibles en {project_name}: {', '.join(parts)}."
            fields_used.append("demo_units.rooms_count")
            data_sources = _dedupe_texts([*data_sources, "demo_units"], limit=8)
            result_slots["available_by_rooms"] = {str(k): v for k, v in available_by_rooms.items()}
            found = True
        else:
            types = repo.get_unit_types(conn, project_code)
            data_sources.extend([src for src in _source_from_rows(types) if src not in data_sources])
            labels = _dedupe_texts(
                [
                    row.get("label")
                    or (
                        f"{row.get('rooms')} ambientes"
                        if row.get("rooms") not in (None, "", "null")
                        else ""
                    )
                    for row in types
                ],
                limit=5,
            )
            if labels:
                answer = f"En {project_name} hoy tengo tipologías: {', '.join(labels)}."
                fields_used.append("unit_types")
                found = True
            else:
                answer = "No veo tipologías publicadas ahora mismo. Si querés, lo confirmo con un asesor."

    elif intent == "PRICE":
        rooms = slots.get("ambientes")
        currency = slots.get("currency")
        last_slots = summary_obj.get("last_result_slots") if isinstance(summary_obj.get("last_result_slots"), dict) else {}
        last_available_raw = (
            last_slots.get("available_by_rooms")
            if isinstance(last_slots, dict) and isinstance(last_slots.get("available_by_rooms"), dict)
            else {}
        )
        last_available_by_rooms: dict[int, int] = {}
        for key, value in last_available_raw.items():
            try:
                last_available_by_rooms[int(key)] = int(value)
            except Exception:  # noqa: BLE001
                continue

        if rooms is None and (is_followup or last_available_by_rooms):
            room_candidates = sorted(last_available_by_rooms.keys())
            if not room_candidates:
                room_candidates = sorted(_extract_available_by_rooms(conn, project_code).keys())
            ranges = _price_ranges_by_rooms(
                conn,
                project_code,
                rooms_list=room_candidates,
                currency=currency,
            )
            if ranges:
                parts: list[str] = []
                for item in ranges:
                    low = float(item["low"])
                    high = float(item["high"])
                    curr = str(item.get("currency") or "USD")
                    if abs(high - low) < 1:
                        parts.append(f"{item['rooms']} amb desde {curr} {_format_price(low)}")
                    else:
                        parts.append(f"{item['rooms']} amb desde {curr} {_format_price(low)}–{_format_price(high)}")
                answer = (
                    f"Para {project_name}: {', '.join(parts)} (según disponibilidad). "
                    "¿Querés que te pase las opciones puntuales?"
                )
                fields_used.extend(["prices.price", "prices.currency"])
                data_sources = _dedupe_texts([*data_sources, "demo_units"], limit=8)
                result_slots["available_by_rooms"] = {str(k): v for k, v in last_available_by_rooms.items()}
                found = True
            else:
                answer = (
                    "No tengo precio publicado para esos tipos en este momento. "
                    "¿Lo querés en USD o ARS para pedirlo al asesor?"
                )
        if found:
            pass
        else:
            prices = repo.get_prices_by_rooms(conn, project_code, rooms=rooms, currency=currency)
            data_sources.extend([src for src in _source_from_rows(prices) if src not in data_sources])
            numeric_prices = [value for value in (_to_float(row.get("price")) for row in prices) if value is not None]
            currencies = _dedupe_texts([row.get("currency") for row in prices], limit=2)
            chosen_currency = currency or (currencies[0] if len(currencies) == 1 else "")
            if numeric_prices:
                low = min(numeric_prices)
                high = max(numeric_prices)
                currency_text = chosen_currency or "la moneda publicada"
                if rooms is not None:
                    if abs(high - low) < 1:
                        answer = (
                            f"Para {rooms} ambientes en {project_name}, el valor publicado es {currency_text} {_format_price(low)}."
                        )
                    else:
                        answer = (
                            f"Para {rooms} ambientes en {project_name}, hoy veo un rango de {currency_text} {_format_price(low)} a {_format_price(high)}."
                        )
                else:
                    by_room: dict[int, list[float]] = {}
                    for row in prices:
                        price_value = _to_float(row.get("price"))
                        rooms_value = row.get("rooms")
                        if price_value is None:
                            continue
                        try:
                            rooms_int = int(str(rooms_value))
                        except Exception:  # noqa: BLE001
                            rooms_int = 0
                        by_room.setdefault(rooms_int, []).append(price_value)
                    room_keys = [room for room in sorted(by_room.keys()) if room > 0]
                    if len(room_keys) > 1:
                        parts = []
                        for room in room_keys:
                            low_room = min(by_room[room])
                            high_room = max(by_room[room])
                            if abs(high_room - low_room) < 1:
                                parts.append(f"{room} amb desde {currency_text} {_format_price(low_room)}")
                            else:
                                parts.append(
                                    f"{room} amb desde {currency_text} {_format_price(low_room)}–{_format_price(high_room)}"
                                )
                        answer = (
                            f"Para {project_name}: {', '.join(parts)} (según disponibilidad). "
                            "¿Querés que te pase las opciones puntuales?"
                        )
                    else:
                        answer = (
                            f"En {project_name} hoy veo precios publicados desde {currency_text} {_format_price(low)} "
                            f"hasta {currency_text} {_format_price(high)}."
                        )
                        answer += " Si querés, te lo desgloso por ambientes."
                fields_used.extend(["prices.price", "prices.currency"])
                found = True
            else:
                capabilities = repo.get_project_capabilities(conn)
                prices_cap = bool((capabilities or {}).get("prices_by_rooms"))
                if not prices_cap:
                    answer = (
                        "No tengo precios publicados en sistema para ese proyecto. "
                        "Decime tipología y moneda (USD o ARS) y lo confirmo con un asesor."
                    )
                elif rooms is None:
                    answer = "Ese valor lo tengo por tipología. ¿Lo querés para mono, 1, 2, 3 o 4 ambientes?"
                elif currency is None:
                    answer = "Ese valor varía por moneda. ¿Lo querés en USD o ARS?"
                else:
                    answer = (
                        f"Ese valor lo tengo que confirmar con el asesor porque varía por disponibilidad. "
                        f"¿Querés que lo pida para {rooms} ambientes en {currency}?"
                    )

    elif intent == "AVAILABILITY":
        rooms = slots.get("ambientes")
        available_by_rooms = _extract_available_by_rooms(conn, project_code)
        if available_by_rooms:
            result_slots["available_by_rooms"] = {str(k): v for k, v in available_by_rooms.items()}
            data_sources = _dedupe_texts([*data_sources, "demo_units"], limit=8)
            if rooms is not None:
                count = int(available_by_rooms.get(int(rooms)) or 0)
                answer = f"Para {rooms} ambientes en {project_name} hay {count} disponibles."
            else:
                total = sum(available_by_rooms.values())
                answer = f"En total en {project_name} hay {total} disponibles."
            fields_used.append("demo_units.availability_status")
            found = True
        else:
            availability = repo.get_availability_by_rooms(conn, project_code, rooms=rooms)
            data_sources.extend([src for src in _source_from_rows(availability) if src not in data_sources])
            if availability:
                fragments: list[str] = []
                for row in availability[:3]:
                    status = _human_availability_status(row.get("status"))
                    count = int(row.get("units_count") or 0)
                    fragments.append(f"{count} {status}")
                scope = f"para {rooms} ambientes" if rooms is not None else "en total"
                answer = f"Disponibilidad {scope} en {project_name}: " + ", ".join(fragments) + "."
                fields_used.append("availability.status")
                found = True
            elif rooms is None:
                answer = "¿Para cuántos ambientes querés validar disponibilidad?"
            else:
                answer = (
                    f"No tengo disponibilidad publicada para {rooms} ambientes en este momento. "
                    "Si querés, lo confirmo con un asesor."
                )

    elif intent == "FINANCING":
        financing = repo.get_financing_terms(conn, project_code)
        data_sources.extend([src for src in _source_from_payload(financing) if src not in data_sources])
        items = financing.get("items") if isinstance(financing, dict) else []
        first_item = items[0] if isinstance(items, list) and items else {}
        detail_text = _dedupe_texts(
            [
                first_item.get("financing_data"),
                first_item.get("description"),
                first_item.get("detail"),
                first_item.get("terms"),
                first_item.get("payment_terms"),
            ],
            limit=1,
        )
        if detail_text:
            answer = f"Sí, en {project_name} figura esta financiación: {detail_text[0]}"
            fields_used.append("financing_terms")
            found = True
        elif items:
            answer = f"Sí, hay financiación cargada para {project_name}. Si querés te paso el detalle puntual con un asesor."
            fields_used.append("financing_terms")
            found = True
        else:
            answer = _build_vera_sensitive_reply(project_name)

    elif intent == "DELIVERY":
        delivery = repo.get_delivery_info(conn, project_code)
        data_sources.extend([src for src in _source_from_payload(delivery) if src not in data_sources])
        items = delivery.get("items") if isinstance(delivery, dict) else []
        first_item = items[0] if isinstance(items, list) and items else {}
        delivery_date = _format_date_like(
            first_item.get("delivery_date")
            or first_item.get("entrega_estimada")
            or first_item.get("estimated_delivery_date")
        )
        status = str(first_item.get("status") or "").strip()
        if delivery_date:
            answer = f"La entrega estimada de {project_name} figura para {delivery_date}."
            if status:
                answer += f" Estado actual: {status}."
            fields_used.append("projects.delivery_date")
            found = True
        elif status:
            answer = f"Hoy el estado de {project_name} figura como {status}."
            fields_used.append("projects.status")
            found = True
        else:
            answer = _build_vera_sensitive_reply(project_name)

    else:
        if asks_project_catalog:
            answer = _list_projects_brief(conn)
            fields_used.append("projects.list")
            data_sources = _dedupe_texts([*data_sources, "projects"], limit=8)
            found = True
        else:
            copies = _extract_marketing_copies(marketing_assets)
            description = _overview_description(overview)
            features = _extract_overview_features(overview)
            if copies:
                answer = copies[0]
                fields_used.append("marketing_assets.short_copy")
                found = True
            elif description:
                answer = f"{project_name}: {description}"
                fields_used.append("projects.description")
                found = True
            elif features:
                answer = f"{project_name} se destaca por {', '.join(features[:4])}."
                fields_used.append("projects.tags")
                found = True
            else:
                answer = _build_vera_sensitive_reply(project_name)

    return {
        "variant": "project_qa",
        "intent": intent,
        "followup": is_followup,
        "reason": intent_reason,
        "answer": _normalize_snippet(answer, limit=700),
        "found": found,
        "fields_used": fields_used,
        "data_sources": data_sources,
        "slots": slots,
        "summary_patch": summary_patch,
        "project_code": project_code,
        "project_name": project_name,
        "result_slots": result_slots,
    }


def _recent_human_schedule_sent(messages: list[dict[str, Any]]) -> bool:
    for msg in reversed(messages[-8:]):
        actor = str(msg.get("actor") or "").strip().lower()
        direction = str(msg.get("direction") or "").strip().lower()
        text = str(msg.get("text") or "")
        if direction != "out":
            continue
        if actor not in {"advisor", "supervisor"}:
            continue
        if _message_mentions_schedule(text):
            return True
    return False


def _format_amount(amount: Any) -> str:
    try:
        value = int(amount)
    except Exception:  # noqa: BLE001
        return str(amount or "-")
    return f"{value:,}".replace(",", ".")


def _build_vera_project_requirements_reply(project_name: str, missing_fields: list[str]) -> str:
    clean_project = str(project_name or "").strip() or "este proyecto"
    missing = set(missing_fields or [])

    if missing == {"ambientes"}:
        ask = "Contame cuántos ambientes buscás."
    elif missing == {"presupuesto"}:
        ask = "Contame tu presupuesto aproximado."
    elif missing == {"moneda"}:
        ask = "Decime si tu presupuesto es en USD o ARS."
    elif missing == {"presupuesto", "moneda"}:
        ask = "Contame tu presupuesto aproximado y la moneda (USD o ARS)."
    elif missing:
        ask = "Contame cuántos ambientes buscás y tu presupuesto aproximado (USD o ARS)."
    else:
        ask = "Contame cuántos ambientes buscás y tu presupuesto aproximado (USD o ARS)."

    return (
        f"Hola 👋 Soy Vera. Gracias por tu consulta por {clean_project}.\n"
        f"{ask}"
    )


def _build_vera_project_summary_reply(project_name: str, requirements: dict[str, Any]) -> str:
    ambientes = int(requirements.get("ambientes") or 0)
    presupuesto = _format_amount(requirements.get("presupuesto"))
    moneda = str(requirements.get("moneda") or "").upper() or "-"
    return (
        "Perfecto 🙌. Entonces:\n"
        f"• Proyecto: {project_name}\n"
        f"• Unidad: {ambientes} ambientes\n"
        f"• Presupuesto: {presupuesto} {moneda}\n"
        "Ya lo dejé listo para coordinar visita. Un asesor te va a proponer horarios por este chat en breve."
    )


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _event_payload(base: dict[str, Any], **extra: Any) -> dict[str, Any]:
    payload = dict(base)
    payload.update(extra)
    return payload


def build_board_url(phone_e164: str) -> str:
    base = str(globalVar.V360_DEMO_BOARD_BASE_URL or "").strip()
    if not base:
        base = "http://localhost:3062/demo/vertice360-orquestador/"
    digits = "".join(ch for ch in str(phone_e164 or "") if ch.isdigit())
    if "?" in base:
        separator = "&" if not base.endswith(("?", "&")) else ""
    else:
        separator = "?" if not base.endswith("?") else ""
    return f"{base}{separator}cliente={digits}"


def build_orquestador_board_url(phone_e164: str) -> str:
    # Backward-compatible alias used by existing tests/docs.
    return build_board_url(phone_e164)


def _safe_board_url_for_log(board_url: str) -> str:
    if str(globalVar.RUN_ENV).lower() == "dev":
        return board_url
    if not board_url:
        return "-"
    return board_url.split("?")[0] + "?cliente=***"


def _build_vera_onboarding_reply(board_url: str) -> str:
    return (
        "Hola 👋 Soy Vera. Gracias por querer probar nuestra solución.\n"
        "Te dejo el tablero para ver en vivo todo el flujo de mensajes y acciones:\n"
        f"{board_url}\n\n"
        "Tenés dos opciones para seguir:\n\n"
        "1) Desde el tablero: elegí un proyecto y tocá \"Enviar WhatsApp\" para simular una consulta "
        "que llega desde una publicidad.\n"
        "2) Desde este chat: empezá a conversar y te voy a preguntar qué proyecto querés "
        "(Bulnes 966, GDR 3760 o Manzanares 3277) para avanzar.\n\n"
        "Te acompaño en la forma que prefieras 🙂.\n"
        "Si querés, empezá por el tablero… o simplemente escribime por acá y seguimos."
    )


def _build_vera_project_reply(project_name: str) -> str:
    return (
        f"Perfecto, trabajamos sobre {project_name}. "
        "Contame qué te gustaría saber y avanzamos."
    )


def _build_vera_project_fallback() -> str:
    return "¿Sobre qué proyecto querés consultar: Bulnes 966, GDR 3760 o Manzanares 3277?"


def _build_qa_summary_patch(
    *,
    intent: str,
    query: str,
    answer: str,
    data_sources: list[str],
    last_result_slots: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_intent = str(intent or "").strip()
    stored_intent = "visit_request" if raw_intent.lower() == "visit_request" else (raw_intent.upper() or "GENERAL")
    patch = {
        "last_intent": stored_intent,
        "last_query": _normalize_snippet(query, limit=220),
        "last_answer_brief": _normalize_snippet(answer, limit=260),
        "last_data_sources": [str(item) for item in data_sources if str(item or "").strip()],
    }
    if isinstance(last_result_slots, dict):
        patch["last_result_slots"] = _jsonable(last_result_slots)
    if isinstance(extra, dict):
        patch.update(extra)
    return patch


def _insert_qa_trace_events(
    conn: Any,
    *,
    ticket_id: str,
    intent: str,
    project_code: str | None,
    query: str,
    slots: dict[str, Any] | None,
    followup: bool,
    reason: str,
    found: bool,
    fields_used: list[str],
    data_sources: list[str],
) -> None:
    repo.insert_event(
        conn,
        correlation_id=ticket_id,
        domain=DOMAIN,
        name="orq.qa.requested",
        actor="client",
        payload={
            "ticket_id": ticket_id,
            "intent": str(intent or "").upper() or "GENERAL",
            "project_code": project_code,
            "query": _normalize_snippet(query, limit=280),
            "slots": _jsonable(slots or {}),
            "followup": bool(followup),
            "reason": reason,
        },
    )
    repo.insert_event(
        conn,
        correlation_id=ticket_id,
        domain=DOMAIN,
        name="orq.qa.responded",
        actor="system",
        payload={
            "ticket_id": ticket_id,
            "intent": str(intent or "").upper() or "GENERAL",
            "project_code": project_code,
            "found": bool(found),
            "fields_used": [str(item) for item in fields_used],
            "data_sources": [str(item) for item in data_sources],
            "followup": bool(followup),
            "reason": reason,
        },
    )


async def _send_vera_whatsapp_reply(phone_e164: str, text: str) -> dict[str, Any]:
    if not globalVar.gupshup_whatsapp_enabled():
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": "GupshupConfigError",
                "message": "Gupshup WhatsApp is not configured",
            },
        }

    try:
        ack = await gupshup_send_text(phone_e164, text)
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": str(ack.provider_message_id or ""),
            "raw": ack.raw,
        }
    except GupshupWhatsAppSendError as exc:
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "upstream_status": exc.upstream_status,
                "upstream_body": exc.upstream_body,
                "url": exc.url,
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


def _missing_gupshup_config_keys() -> list[str]:
    missing: list[str] = []
    if not str(globalVar.GUPSHUP_APP_NAME or "").strip():
        missing.append("GUPSHUP_APP_NAME")
    if not str(globalVar.GUPSHUP_API_KEY or "").strip():
        missing.append("GUPSHUP_API_KEY")
    if not str(globalVar.get_gupshup_wa_sender_provider_value() or "").strip():
        missing.append("GUPSHUP_WA_SENDER")
    return missing


def _normalize_target_phone(raw_phone: str | None) -> str:
    clean = str(raw_phone or "").strip()
    if not clean:
        return ""
    try:
        return _normalize_phone_e164(clean)
    except ValueError:
        return ""


def _provider_response_json(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return _jsonable(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return _jsonable(parsed)
                return {"raw": _jsonable(parsed)}
            except Exception:  # noqa: BLE001
                return {"raw_text": text}
        return {}
    return {"raw": _jsonable(value)}


async def _send_supervisor_whatsapp_via_gupshup(phone_e164: str, text: str) -> dict[str, Any]:
    missing = _missing_gupshup_config_keys()
    if missing:
        return {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "error",
            "provider_message_id": None,
            "provider_response": {"missing": missing},
            "error": "missing_gupshup_config",
        }

    try:
        ack = await gupshup_send_text(phone_e164, text)
        provider_message_id = str(ack.provider_message_id or "").strip() or None
        return {
            "send_ok": True,
            "provider": "gupshup",
            "provider_status": "sent",
            "provider_message_id": provider_message_id,
            "provider_response": _provider_response_json(ack.raw),
            "error": None,
        }
    except GupshupWhatsAppSendError as exc:
        upstream_status = exc.upstream_status
        upstream_body = str(exc.upstream_body or "")
        lowered_body = upstream_body.lower()
        if upstream_status is not None:
            error_code = f"gupshup_http_{upstream_status}"
        elif "timeout" in lowered_body or "timed out" in lowered_body:
            error_code = "gupshup_timeout"
        else:
            error_code = "gupshup_send_error"
        return {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "error",
            "provider_message_id": None,
            "provider_response": _provider_response_json(
                {
                    "upstream_status": upstream_status,
                    "upstream_body": upstream_body or None,
                    "url": exc.url,
                }
            ),
            "error": error_code,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "error",
            "provider_message_id": None,
            "provider_response": _provider_response_json(str(exc)),
            "error": "gupshup_send_exception",
        }


def bootstrap() -> dict[str, Any]:
    def _tx(conn: Any) -> dict[str, Any]:
        knowledge = repo.get_project_schema_and_capabilities(conn, force_refresh=True)
        logger.info(
            "ORQ_PROJECT_KNOWLEDGE_DISCOVERY tables=%s capabilities=%s",
            sorted((knowledge.get("schema_map") or {}).keys()),
            knowledge.get("capabilities") or {},
        )
        return {
            "whatsapp_demo_phone": _safe_demo_phone(
                globalVar.get_gupshup_wa_sender_e164()
            ),
            "projects": repo.list_projects(conn),
            "marketing_assets": repo.list_marketing_assets(conn),
            "users": repo.list_users(conn),
            "project_knowledge": knowledge,
        }

    return _jsonable(db.run_in_transaction(_tx))


def project_knowledge_capabilities(*, force_refresh: bool = False) -> dict[str, Any]:
    def _tx(conn: Any) -> dict[str, Any]:
        knowledge = repo.get_project_schema_and_capabilities(
            conn,
            force_refresh=bool(force_refresh),
        )
        return {
            "schema_map": knowledge.get("schema_map") or {},
            "capabilities": knowledge.get("capabilities") or {},
        }

    return _jsonable(db.run_in_transaction(_tx))


def project_knowledge_debug_project(*, code: str) -> dict[str, Any]:
    clean_code = str(code or "").strip()
    if not clean_code:
        raise ValueError("code is required")

    def _tx(conn: Any) -> dict[str, Any]:
        overview = repo.get_project_overview(conn, clean_code)
        facts = getattr(repo, "get_demo_project_facts", lambda _c, _p: None)(conn, clean_code)
        units = getattr(repo, "list_demo_units", lambda _c, _p, **_k: [])(
            conn,
            clean_code,
            rooms=None,
            currency=None,
        )
        prices = repo.get_prices_by_rooms(conn, clean_code, rooms=None, currency=None)
        availability = repo.get_availability_by_rooms(conn, clean_code, rooms=None)
        financing = repo.get_financing_terms(conn, clean_code)
        delivery = repo.get_delivery_info(conn, clean_code)
        return {
            "project_code": clean_code,
            "overview": overview,
            "facts": facts,
            "sample_units": units[:10],
            "prices": prices[:10],
            "availability": availability,
            "financing": financing,
            "delivery": delivery,
        }

    return _jsonable(db.run_in_transaction(_tx))


def dashboard(cliente: str | None = None) -> dict[str, Any]:
    def _tx(conn: Any) -> dict[str, Any]:
        rows = repo.get_dashboard_ticket_rows(conn, cliente)
        kpis = repo.get_dashboard_kpis(conn)
        active = repo.find_cliente_activo(conn, str(cliente or "")) if cliente else None
        enriched_rows: list[dict[str, Any]] = []
        general_keys: set[str] = set()

        for row in rows:
            inbound_data = _resolve_dashboard_inbound_line(row)
            inbound_line_key = str(inbound_data.get("inbound_line_key") or "").strip()
            record = {**row, **inbound_data}
            enriched_rows.append(record)
            if not row.get("project_code") and inbound_line_key:
                general_keys.add(inbound_line_key)

        general_order = sorted(general_keys)
        general_label_index = {key: idx + 1 for idx, key in enumerate(general_order)}

        tickets = []
        for row in enriched_rows:
            inbound_line_key = str(row.get("inbound_line_key") or "").strip()
            project_code = str(row.get("project_code") or "").strip()
            if project_code:
                project_label = project_code
            else:
                project_name = str(row.get("project_name") or "").strip()
                if project_name:
                    project_label = project_name
                else:
                    general_idx = general_label_index.get(inbound_line_key)
                    project_label = f"General {general_idx}" if general_idx else "General"

            tickets.append(
                {
                    "ticket_id": row.get("ticket_id"),
                    "stage": row.get("stage"),
                    "project_id": row.get("project_id"),
                    "project_code": row.get("project_code"),
                    "project_name": row.get("project_name"),
                    "project_label": project_label,
                    "inbound_line_key": inbound_line_key,
                    "inbound_line_phone": row.get("inbound_line_phone"),
                    "requirements": {
                        "ambientes": row.get("req_ambientes"),
                        "presupuesto": row.get("req_presupuesto"),
                        "moneda": row.get("req_moneda"),
                    },
                    "lead_id": row.get("lead_id"),
                    "lead_name": row.get("lead_name"),
                    "phone_e164": row.get("phone_e164"),
                    "lead_phone": row.get("phone_e164"),
                    "conversation_id": row.get("conversation_id"),
                    "last_activity_at": row.get("last_activity_at"),
                    "last_message_snippet": _normalize_snippet(
                        str(row.get("last_message_text") or row.get("last_message_snippet") or "")
                    ),
                    "last_message_direction": row.get("last_message_direction"),
                    "last_message_actor": row.get("last_message_actor"),
                    "last_message_at": row.get("last_message_at"),
                    "visit_scheduled_at": row.get("visit_scheduled_at"),
                    "cliente_match": bool(row.get("cliente_match")),
                }
            )

        return {
            "kpis": kpis,
            "tickets": tickets,
            "cliente_activo": active,
        }

    return _jsonable(db.run_in_transaction(_tx))


def admin_reset_phone(*, phone: str) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(phone)

    def _tx(conn: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "phone": normalized_phone,
            "deleted": repo.reset_by_phone(conn, normalized_phone),
        }

    result = db.run_in_transaction(_tx)
    logger.warning(
        "ORQ_ADMIN_RESET_PHONE phone=%s deleted=%s",
        normalized_phone,
        result.get("deleted"),
    )
    return _jsonable(result)


def ingest_message(
    *,
    phone: str,
    text: str,
    project_code: str | None = None,
    source: str | None = None,
    provider_message_id: str | None = None,
    provider_meta: dict[str, Any] | None = None,
    inbound_line_key: str | None = None,
    inbound_line_phone: str | None = None,
) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(phone)
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")
    source_value = _normalize_source(source)

    def _tx(conn: Any) -> dict[str, Any]:
        repo.ensure_ticket_inbound_line_columns(conn)
        inferred_project, inference_meta = _infer_project(conn, project_code, clean_text)
        inferred_project_id = (
            str(inferred_project.get("id")) if inferred_project and inferred_project.get("id") else None
        )
        inbound_line = _derive_inbound_line(
            str((provider_meta or {}).get("provider") or "gupshup_whatsapp"),
            {
                **(provider_meta or {}),
                "inbound_line_key": inbound_line_key,
                "inbound_line_phone": inbound_line_phone,
            },
        )
        resolved_inbound_line_key = str(inbound_line.get("inbound_line_key") or "").strip()
        resolved_inbound_line_phone = _normalize_optional_phone(
            inbound_line_phone or inbound_line.get("inbound_line_phone")
        )

        lead = repo.get_lead_by_phone(conn, normalized_phone)
        lead_created = lead is None
        if lead is None:
            lead = repo.create_lead(conn, normalized_phone, source_value)
        else:
            lead = repo.touch_lead(conn, str(lead["id"]), source_value)

        lead_id = str(lead["id"])
        conversation = repo.get_open_conversation_for_lead(conn, lead_id)
        conversation_created = conversation is None
        if conversation is None:
            conversation = repo.create_conversation(conn, lead_id)

        conversation_id = str(conversation["id"])
        ticket = repo.get_ticket_by_conversation(conn, conversation_id)
        ticket_created = ticket is None
        previous_project_id = str(ticket.get("project_id") or "") if ticket else ""

        snippet = _normalize_snippet(clean_text)
        if ticket is None:
            ticket = repo.create_ticket(
                conn,
                conversation_id=conversation_id,
                lead_id=lead_id,
                project_id=inferred_project_id,
                last_message_snippet=snippet,
            )
        else:
            ticket_project = str(ticket.get("project_id") or "")
            project_to_set = inferred_project_id if inferred_project_id and ticket_project != inferred_project_id else None
            ticket = repo.update_ticket_activity(
                conn,
                str(ticket["id"]),
                project_id=project_to_set,
                last_message_snippet=snippet,
            )

        ticket_id = str(ticket["id"])
        current_inbound_key = str(ticket.get("inbound_line_key") or "").strip()
        current_inbound_phone = _normalize_optional_phone(ticket.get("inbound_line_phone"))
        if (resolved_inbound_line_key and not current_inbound_key) or (
            resolved_inbound_line_phone and not current_inbound_phone
        ):
            updated_line = repo.set_ticket_inbound_line(
                conn,
                ticket_id=ticket_id,
                inbound_line_key=resolved_inbound_line_key,
                inbound_line_phone=resolved_inbound_line_phone,
            )
            if updated_line:
                ticket = {**ticket, **updated_line}
        repo.touch_conversation_activity(conn, conversation_id)

        inbound_provider_meta = {"source": source_value}
        if isinstance(provider_meta, dict):
            inbound_provider_meta.update(
                {str(k): v for k, v in provider_meta.items() if v is not None}
            )
        if resolved_inbound_line_key:
            inbound_provider_meta["inbound_line_key"] = resolved_inbound_line_key
        if resolved_inbound_line_phone:
            inbound_provider_meta["inbound_line_phone"] = resolved_inbound_line_phone

        message = repo.insert_message(
            conn,
            conversation_id=conversation_id,
            lead_id=lead_id,
            direction="in",
            actor="client",
            text=clean_text,
            provider_message_id=str(provider_message_id or "").strip() or None,
            provider_meta=inbound_provider_meta,
        )

        if ticket_created:
            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name="ticket.created",
                actor="system",
                payload=_event_payload(
                    {
                        "ticket_id": ticket_id,
                        "conversation_id": conversation_id,
                        "lead_id": lead_id,
                        "project_id": ticket.get("project_id"),
                        "stage": ticket.get("stage"),
                    }
                ),
            )

        repo.insert_event(
            conn,
            correlation_id=ticket_id,
            domain=DOMAIN,
            name="message.ingested",
            actor="client",
            payload=_event_payload(
                {
                    "ticket_id": ticket_id,
                    "conversation_id": conversation_id,
                    "lead_id": lead_id,
                    "message_id": message.get("id"),
                    "direction": "in",
                    "actor": "client",
                    "text": clean_text,
                }
            ),
        )

        project_changed = bool(inferred_project_id and previous_project_id != inferred_project_id)
        project_selected = bool(project_changed and not previous_project_id)
        project_overridden = bool(project_changed and bool(previous_project_id))
        previous_project = (
            repo.get_project_by_id(conn, previous_project_id)
            if previous_project_id
            else None
        )
        explicit_project_mention = str(inference_meta.get("source") or "") in {
            "alias",
            "code_in_text",
            "explicit",
        }
        if project_changed:
            event_name = "orq.project.overridden" if project_overridden else "orq.project.selected"
            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name=event_name,
                actor="system",
                payload={
                    "ticket_id": ticket_id,
                    "project_id": inferred_project_id,
                    "project_code": inferred_project.get("code") if inferred_project else None,
                    "project_name": inferred_project.get("name") if inferred_project else None,
                    "previous_project_id": previous_project_id or None,
                    "previous_project_code": previous_project.get("code") if previous_project else None,
                    "matched_by": inference_meta.get("source"),
                    "matched_text": inference_meta.get("matched_text"),
                    "explicit_mention": explicit_project_mention,
                },
            )
            repo.merge_ticket_summary(
                conn,
                ticket_id,
                {
                    "project_prompted_once": False,
                    "selected_project": {
                        "id": inferred_project_id,
                        "code": inferred_project.get("code") if inferred_project else None,
                        "name": inferred_project.get("name") if inferred_project else None,
                    }
                },
            )

        detail = repo.get_ticket_detail(conn, ticket_id)
        requirements_patch = _requirements_patch_from_text(clean_text)
        if requirements_patch:
            repo.update_ticket_requirements(conn, ticket_id, requirements_patch)
            detail = repo.get_ticket_detail(conn, ticket_id) or detail
            requirements = _extract_ticket_requirements(detail)
            repo.merge_ticket_summary(
                conn,
                ticket_id,
                {
                    "captured_requirements": requirements,
                },
            )
            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name="orq.requirements.captured",
                actor="system",
                payload={
                    "ticket_id": ticket_id,
                    "project_code": detail.get("project_code") if detail else None,
                    "captured": requirements_patch,
                    "requirements": requirements,
                },
            )

        requirements = _extract_ticket_requirements(detail)
        requirements_missing = _missing_requirements(requirements)
        requirements_complete = bool(requirements and not requirements_missing)
        return {
            "ticket_id": ticket_id,
            "conversation_id": conversation_id,
            "lead_id": lead_id,
            "project_id": detail.get("project_id") if detail else ticket.get("project_id"),
            "project_code": detail.get("project_code") if detail else None,
            "project_name": detail.get("project_name") if detail else None,
            "inbound_line_key": (
                detail.get("inbound_line_key")
                if isinstance(detail, dict) and detail.get("inbound_line_key")
                else resolved_inbound_line_key
            ),
            "inbound_line_phone": (
                detail.get("inbound_line_phone")
                if isinstance(detail, dict) and detail.get("inbound_line_phone")
                else resolved_inbound_line_phone
            ),
            "stage": detail.get("stage") if detail else ticket.get("stage"),
            "requirements": requirements,
            "requirements_missing": requirements_missing,
            "requirements_complete": requirements_complete,
            "requirements_patch": requirements_patch,
            "message_id": message.get("id"),
            "normalized_phone": normalized_phone,
            "lead_created": lead_created,
            "conversation_created": conversation_created,
            "ticket_created": ticket_created,
            "project_selected": project_selected,
            "project_overridden": project_overridden,
            "project_previous_id": previous_project_id or None,
            "project_previous_code": previous_project.get("code") if previous_project else None,
            "explicit_project_mention": explicit_project_mention,
            "project_match_source": inference_meta.get("source"),
            "project_match_text": inference_meta.get("matched_text"),
        }

    result = db.run_in_transaction(_tx)
    ticket_id = str(result.get("ticket_id"))
    set_correlation_id(ticket_id)
    logger.info(
        "ORQ_INGEST_MESSAGE correlation_id=%s lead_created=%s conversation_created=%s ticket_created=%s phone=%s project_code=%s inbound_line_key=%s stage=%s requirements_complete=%s",
        ticket_id,
        result.get("lead_created"),
        result.get("conversation_created"),
        result.get("ticket_created"),
        normalized_phone,
        result.get("project_code") or "-",
        result.get("inbound_line_key") or "-",
        result.get("stage") or "-",
        bool(result.get("requirements_complete")),
    )
    if result.get("project_overridden"):
        logger.info(
            "PROJECT_OVERRIDE correlation_id=%s from=%s to=%s reason=explicit_mention",
            ticket_id,
            result.get("project_previous_code") or result.get("project_previous_id") or "-",
            result.get("project_code") or "-",
        )
    return _jsonable(result)


async def ingest_from_provider(
    *,
    user_phone: str,
    text: str,
    provider: str = "gupshup_whatsapp",
    provider_message_id: str | None = None,
    provider_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(user_phone)
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")

    provider_name = str(provider or "gupshup_whatsapp").strip().lower() or "gupshup_whatsapp"
    safe_provider_message_id = str(provider_message_id or "").strip() or None

    inbound_meta = dict(provider_meta or {})
    inbound_meta.setdefault("provider", provider_name)
    inbound_meta.setdefault("channel", "whatsapp")
    inbound_line = _derive_inbound_line(provider_name, inbound_meta)
    inbound_meta.setdefault("inbound_line_key", inbound_line.get("inbound_line_key"))
    inbound_meta.setdefault("inbound_line_phone", inbound_line.get("inbound_line_phone"))

    ingest_result = ingest_message(
        phone=normalized_phone,
        text=clean_text,
        source="whatsapp",
        provider_message_id=safe_provider_message_id,
        provider_meta=inbound_meta,
        inbound_line_key=str(inbound_line.get("inbound_line_key") or ""),
        inbound_line_phone=inbound_line.get("inbound_line_phone"),
    )

    is_first_contact = bool(
        ingest_result.get("lead_created")
        or ingest_result.get("conversation_created")
        or ingest_result.get("ticket_created")
    )
    ticket_id = str(ingest_result.get("ticket_id") or "")
    conversation_id = str(ingest_result.get("conversation_id") or "")
    project_selected = bool(ingest_result.get("project_selected"))
    visit_requested = _is_visit_request_intent(clean_text)
    board_url = ""
    context_messages: list[dict[str, Any]] = []
    detail: dict[str, Any] | None = None
    qa_resolution: dict[str, Any] | None = None

    def _tx_load_context(conn: Any) -> dict[str, Any]:
        capabilities = repo.get_project_capabilities(conn)
        local_detail = repo.get_ticket_detail(conn, ticket_id) if ticket_id else None
        local_messages = (
            repo.list_conversation_messages(conn, conversation_id, limit=40)
            if conversation_id
            else []
        )
        return {
            "detail": local_detail,
            "messages": local_messages,
            "capabilities": capabilities,
        }

    if ticket_id:
        loaded_context = db.run_in_transaction(_tx_load_context)
        detail = loaded_context.get("detail") if isinstance(loaded_context, dict) else None
        context_messages = (
            loaded_context.get("messages")
            if isinstance(loaded_context, dict) and isinstance(loaded_context.get("messages"), list)
            else []
        )

    project_name = str(
        (detail or {}).get("project_name")
        or ingest_result.get("project_name")
        or ingest_result.get("project_code")
        or ""
    ).strip()
    detail_summary = _ticket_summary(detail)
    detected_intent, detected_followup, detected_reason = _detect_project_intent(
        clean_text,
        summary=detail_summary,
    )
    qa_candidate = bool(
        project_name
        or detected_intent != "GENERAL"
        or _match_project_alias(clean_text)[0]
        or _looks_like_project_question(clean_text)
    )

    if visit_requested:
        variant = "visit_requested"
        reply_text = _build_vera_visit_requested_reply()
    elif project_name:
        if _is_confirmation_message(clean_text) and _recent_human_schedule_sent(context_messages):
            variant = "post_human_followup"
            reply_text = (
                "Perfecto, confirmado. Si querés te paso dirección exacta y qué necesitás traer para la visita."
            )
        elif (project_selected or ingest_result.get("project_overridden")) and detected_intent == "GENERAL":
            variant = "project_selected"
            reply_text = _build_vera_project_selected_reply(project_name)
        elif qa_candidate and ticket_id:
            def _tx_resolve_qa(conn: Any) -> dict[str, Any]:
                local_detail = repo.get_ticket_detail(conn, ticket_id)
                return _resolve_project_knowledge_reply(
                    conn,
                    ticket_id=ticket_id,
                    detail=local_detail,
                    question=clean_text,
                )

            qa_resolution = db.run_in_transaction(_tx_resolve_qa)
            variant = str(qa_resolution.get("variant") or "project_qa")
            reply_text = str(qa_resolution.get("answer") or _build_vera_project_fallback())
            if qa_resolution.get("project_code"):
                ingest_result["project_code"] = qa_resolution.get("project_code")
            if qa_resolution.get("project_name"):
                ingest_result["project_name"] = qa_resolution.get("project_name")
        else:
            variant = "project_qa"
            reply_text = _build_vera_project_fallback()
    elif qa_candidate and ticket_id:
        def _tx_resolve_qa(conn: Any) -> dict[str, Any]:
            local_detail = repo.get_ticket_detail(conn, ticket_id)
            return _resolve_project_knowledge_reply(
                conn,
                ticket_id=ticket_id,
                detail=local_detail,
                question=clean_text,
            )

        qa_resolution = db.run_in_transaction(_tx_resolve_qa)
        variant = str(qa_resolution.get("variant") or "project_qa")
        reply_text = str(qa_resolution.get("answer") or _build_vera_project_fallback())
        if qa_resolution.get("project_code"):
            ingest_result["project_code"] = qa_resolution.get("project_code")
        if qa_resolution.get("project_name"):
            ingest_result["project_name"] = qa_resolution.get("project_name")
    elif is_first_contact:
        variant = "onboarding"
        board_url = build_board_url(normalized_phone)
        reply_text = _build_vera_onboarding_reply(board_url)
    else:
        variant = "choose_project"
        reply_text = _build_vera_project_fallback()

    def _tx_apply_intent(conn: Any) -> dict[str, Any]:
        if not ticket_id:
            return {"stage": None}
        local_detail = repo.get_ticket_detail(conn, ticket_id)
        if local_detail is None:
            return {"stage": None}

        stage = str(local_detail.get("stage") or "")
        if visit_requested:
            if stage not in {STAGE_PENDING_VISIT, STAGE_WAITING_CONFIRMATION, STAGE_VISIT_CONFIRMED}:
                previous_stage = stage
                updated = repo.update_ticket_activity(conn, ticket_id, stage=STAGE_PENDING_VISIT)
                stage = str(updated.get("stage") or STAGE_PENDING_VISIT)
                repo.insert_event(
                    conn,
                    correlation_id=ticket_id,
                    domain=DOMAIN,
                    name="orq.stage.updated",
                    actor="system",
                    payload={
                        "ticket_id": ticket_id,
                        "from_stage": previous_stage,
                        "to_stage": STAGE_PENDING_VISIT,
                        "reason": "visit_requested",
                    },
                )

            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name="orq.visit.requested",
                actor="client",
                payload={
                    "ticket_id": ticket_id,
                    "text": clean_text,
                },
            )

        intent_for_trace = str(
            (qa_resolution or {}).get("intent")
            or ("VISIT_REQUEST" if visit_requested else detected_intent)
            or "GENERAL"
        ).upper()
        followup_for_trace = bool(
            (qa_resolution or {}).get("followup")
            if qa_resolution is not None
            else detected_followup
        )
        reason_for_trace = str(
            (qa_resolution or {}).get("reason")
            if qa_resolution is not None
            else detected_reason
        )
        project_for_trace = str(
            (qa_resolution or {}).get("project_code")
            or local_detail.get("project_code")
            or ""
        ).strip() or None
        slots_for_trace = (
            (qa_resolution or {}).get("slots")
            if isinstance((qa_resolution or {}).get("slots"), dict)
            else _extract_query_slots(clean_text)
        )
        fields_used = (
            (qa_resolution or {}).get("fields_used")
            if isinstance((qa_resolution or {}).get("fields_used"), list)
            else []
        )
        data_sources = (
            (qa_resolution or {}).get("data_sources")
            if isinstance((qa_resolution or {}).get("data_sources"), list)
            else []
        )
        result_slots = (
            (qa_resolution or {}).get("result_slots")
            if isinstance((qa_resolution or {}).get("result_slots"), dict)
            else None
        )
        found_flag = bool((qa_resolution or {}).get("found"))

        should_trace_qa = bool(
            visit_requested
            or qa_resolution is not None
            or _looks_like_project_question(clean_text)
        )
        if should_trace_qa:
            _insert_qa_trace_events(
                conn,
                ticket_id=ticket_id,
                intent=intent_for_trace,
                project_code=project_for_trace,
                query=clean_text,
                slots=slots_for_trace,
                followup=followup_for_trace,
                reason=reason_for_trace,
                found=found_flag or visit_requested,
                fields_used=[str(item) for item in fields_used],
                data_sources=[str(item) for item in data_sources],
            )

        qa_summary_extra = (
            (qa_resolution or {}).get("summary_patch")
            if isinstance((qa_resolution or {}).get("summary_patch"), dict)
            else {}
        )
        summary_patch = _build_qa_summary_patch(
            intent=intent_for_trace,
            query=clean_text,
            answer=reply_text,
            data_sources=[str(item) for item in data_sources],
            last_result_slots=result_slots,
            extra=qa_summary_extra,
        )
        repo.merge_ticket_summary(conn, ticket_id, summary_patch)
        return {"stage": stage}

    stage_result = db.run_in_transaction(_tx_apply_intent) if ticket_id else {"stage": None}
    if stage_result and stage_result.get("stage"):
        ingest_result["stage"] = stage_result.get("stage")

    send_result = await _send_vera_whatsapp_reply(normalized_phone, reply_text)
    vera_send_ok = bool(send_result.get("vera_send_ok"))
    lead_id = str(ingest_result.get("lead_id") or "")

    provider_error_payload = send_result.get("error") if isinstance(send_result.get("error"), dict) else {}
    provider_error_type = str(provider_error_payload.get("type") or "").strip()
    if vera_send_ok:
        provider_status = "sent"
    elif provider_error_type == "GupshupConfigError":
        provider_status = "skipped"
    else:
        provider_status = "error"

    provider_message_id = str(send_result.get("provider_message_id") or "").strip() or None
    provider_error = str(provider_error_payload.get("message") or "").strip() or None
    provider_response = send_result.get("raw") if isinstance(send_result.get("raw"), dict) else {}
    provider_persist_error: str | None = None
    vera_message_id: str | None = None

    def _tx_persist_vera_reply(conn: Any) -> None:
        nonlocal provider_persist_error
        nonlocal vera_message_id
        if not conversation_id or not lead_id or not ticket_id:
            return
        try:
            message = repo.insert_message(
                conn,
                conversation_id=conversation_id,
                lead_id=lead_id,
                direction="out",
                actor="system",
                text=reply_text,
                provider_message_id=provider_message_id,
                provider_meta={
                    "provider": "gupshup",
                    "channel": "whatsapp",
                    "variant": variant,
                    "to": normalized_phone,
                    "send_ok": vera_send_ok,
                },
            )
            vera_message_id = str(message.get("id") or "")
            repo.update_ticket_activity(
                conn,
                ticket_id,
                last_message_snippet=_normalize_snippet(reply_text),
            )
            ensure_columns = getattr(repo, "ensure_messages_provider_columns", None)
            update_provider = getattr(repo, "update_message_provider_result", None)
            if callable(ensure_columns):
                ensure_columns(conn)
            if callable(update_provider) and vera_message_id:
                update_provider(
                    conn,
                    message_id=vera_message_id,
                    provider_name="gupshup",
                    provider_status=provider_status,
                    provider_message_id=provider_message_id,
                    provider_response=provider_response,
                    provider_error=provider_error,
                    sent_at=datetime.now(timezone.utc) if provider_status == "sent" else None,
                )
            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name="vera.reply.sent" if vera_send_ok else "vera.reply.failed",
                actor="system",
                payload={
                    "ticket_id": ticket_id,
                    "message_id": vera_message_id,
                    "variant": variant,
                    "provider": "gupshup",
                    "provider_status": provider_status,
                    "provider_message_id": provider_message_id,
                    "provider_error": provider_error,
                    "send_ok": vera_send_ok,
                },
            )
        except Exception as exc:  # noqa: BLE001
            provider_persist_error = str(exc)

    db.run_in_transaction(_tx_persist_vera_reply)

    logger.info(
        "VERA_REPLY correlation_id=%s phone=%s provider=%s variant=%s send_ok=%s provider_status=%s provider_message_id=%s message_id=%s board_url=%s persist_error=%s",
        ticket_id or "-",
        normalized_phone,
        provider_name,
        variant,
        vera_send_ok,
        provider_status,
        provider_message_id or "-",
        vera_message_id or "-",
        _safe_board_url_for_log(board_url),
        provider_persist_error or "-",
    )
    logger.info(
        "INTENT_RESOLVED correlation_id=%s intent=%s project=%s followup=%s reason=%s",
        ticket_id or "-",
        str((qa_resolution or {}).get("intent") or detected_intent),
        str((qa_resolution or {}).get("project_code") or ingest_result.get("project_code") or "-"),
        bool((qa_resolution or {}).get("followup") if qa_resolution is not None else detected_followup),
        str((qa_resolution or {}).get("reason") if qa_resolution is not None else detected_reason),
    )

    payload = {
        **ingest_result,
        "ok": True,
        "routed": "orquestador",
        "vera_send_ok": vera_send_ok,
        "vera_provider_status": provider_status,
        "vera_provider_message_id": provider_message_id,
        "vera_provider_error": provider_error,
        "vera_message_id": vera_message_id,
        "vera_reply_variant": variant,
        "vera_reply_text": reply_text,
    }
    if not vera_send_ok:
        payload["error"] = send_result.get("error")
    return _jsonable(payload)


async def propose_visit(
    *,
    ticket_id: str,
    advisor_name: str | None,
    option1: datetime | None,
    option2: datetime | None,
    option3: datetime | None,
    message_out: str,
    mode: str,
) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    clean_mode = str(mode or "propose").strip().lower()
    if clean_mode not in {"propose", "reschedule"}:
        raise ValueError("mode must be propose or reschedule")

    clean_message_out = str(message_out or "").strip()
    if not clean_message_out:
        raise ValueError("message_out is required")

    def _tx_prepare(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        advisor = repo.find_advisor_by_name(conn, advisor_name)
        if advisor_name and advisor is None:
            raise ValueError("advisor_name not found")

        proposal = repo.create_visit_proposal(
            conn,
            ticket_id=clean_ticket_id,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            advisor_id=str(advisor["id"]) if advisor else None,
            mode=clean_mode,
            option1=option1,
            option2=option2,
            option3=option3,
            message_out=clean_message_out,
        )

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="advisor",
            text=clean_message_out,
            provider_meta={
                "mode": clean_mode,
                "proposal_id": str(proposal.get("id")),
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
            },
        )

        ticket = repo.update_ticket_activity(
            conn,
            clean_ticket_id,
            stage=STAGE_WAITING_CONFIRMATION,
            assigned_advisor_id=str(advisor["id"]) if advisor else None,
            last_message_snippet=_normalize_snippet(clean_message_out),
        )

        return {
            "ticket_id": clean_ticket_id,
            "proposal_id": proposal.get("id"),
            "mode": clean_mode,
            "stage": ticket.get("stage"),
            "advisor": advisor,
            "message_id": message.get("id"),
            "option1": proposal.get("option1"),
            "option2": proposal.get("option2"),
            "option3": proposal.get("option3"),
            "visit_scheduled_at": ticket.get("visit_scheduled_at"),
            "target_phone_e164": _normalize_target_phone(context.get("phone_e164")),
        }

    prepared = db.run_in_transaction(_tx_prepare)
    target_phone_e164 = str(prepared.get("target_phone_e164") or "").strip()

    provider_result: dict[str, Any]
    if not target_phone_e164:
        provider_result = {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "error",
            "provider_message_id": None,
            "provider_response": {},
            "error": "missing_target_phone",
        }
    elif not globalVar.gupshup_whatsapp_enabled():
        missing_keys = _missing_gupshup_config_keys()
        provider_result = {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "skipped",
            "provider_message_id": None,
            "provider_response": {"missing": missing_keys},
            "error": "missing_config",
        }
        logger.warning(
            "VISIT_PROPOSE_SEND skipped reason=missing_config correlation_id=%s proposal_id=%s mode=%s phone=%s missing=%s",
            clean_ticket_id,
            prepared.get("proposal_id") or "-",
            clean_mode,
            target_phone_e164 or "-",
            ",".join(missing_keys) if missing_keys else "-",
        )
    else:
        provider_result = await _send_supervisor_whatsapp_via_gupshup(
            target_phone_e164,
            clean_message_out,
        )

    provider_status = str(provider_result.get("provider_status") or "error")
    provider_message_id = str(provider_result.get("provider_message_id") or "").strip() or None
    provider_error = str(provider_result.get("error") or "").strip() or None
    provider_response = (
        provider_result.get("provider_response")
        if isinstance(provider_result.get("provider_response"), dict)
        else {}
    )
    sent_at = datetime.now(timezone.utc) if provider_status == "sent" else None
    provider_persist_error: str | None = None
    event_name = "visit.proposed" if clean_mode == "propose" else "visit.rescheduled"

    def _tx_finalize(conn: Any) -> None:
        nonlocal provider_persist_error
        try:
            repo.ensure_messages_provider_columns(conn)
            repo.update_message_provider_result(
                conn,
                message_id=str(prepared["message_id"]),
                provider_name="gupshup",
                provider_status=provider_status,
                provider_message_id=provider_message_id,
                provider_response=provider_response,
                provider_error=provider_error,
                sent_at=sent_at,
            )
        except Exception as exc:  # noqa: BLE001
            provider_persist_error = str(exc)
            repo.insert_event(
                conn,
                correlation_id=clean_ticket_id,
                domain=DOMAIN,
                name="visit.proposed.provider_persist_fallback",
                actor="system",
                payload={
                    "ticket_id": clean_ticket_id,
                    "proposal_id": prepared.get("proposal_id"),
                    "message_id": prepared.get("message_id"),
                    "provider": "gupshup",
                    "provider_status": provider_status,
                    "provider_message_id": provider_message_id,
                    "provider_error": provider_error,
                    "provider_response": provider_response,
                    "persist_error": str(exc),
                },
            )

        repo.insert_event(
            conn,
            correlation_id=clean_ticket_id,
            domain=DOMAIN,
            name=event_name,
            actor="advisor",
            payload={
                "ticket_id": clean_ticket_id,
                "proposal_id": prepared.get("proposal_id"),
                "mode": clean_mode,
                "advisor_id": (prepared.get("advisor") or {}).get("id")
                if isinstance(prepared.get("advisor"), dict)
                else None,
                "advisor_name": (prepared.get("advisor") or {}).get("full_name")
                if isinstance(prepared.get("advisor"), dict)
                else advisor_name,
                "message_id": prepared.get("message_id"),
                "option1": prepared.get("option1"),
                "option2": prepared.get("option2"),
                "option3": prepared.get("option3"),
                "provider": "gupshup",
                "provider_status": provider_status,
                "provider_message_id": provider_message_id,
                "provider_error": provider_error,
                "send_ok": bool(provider_result.get("send_ok")),
            },
        )

    db.run_in_transaction(_tx_finalize)

    result = {
        **prepared,
        "send_ok": bool(provider_result.get("send_ok")),
        "provider": "gupshup",
        "provider_status": provider_status,
        "provider_message_id": provider_message_id,
        "provider_error": provider_error,
    }
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_PROPOSE_VISIT correlation_id=%s proposal_id=%s mode=%s send_ok=%s provider_status=%s",
        clean_ticket_id,
        result.get("proposal_id"),
        clean_mode,
        bool(provider_result.get("send_ok")),
        provider_status,
    )
    logger.info(
        "VISIT_PROPOSE_SEND correlation_id=%s proposal_id=%s mode=%s send_ok=%s status=%s provider_message_id=%s phone=%s message_id=%s persist_error=%s",
        clean_ticket_id,
        result.get("proposal_id"),
        clean_mode,
        bool(provider_result.get("send_ok")),
        provider_status,
        provider_message_id or "-",
        target_phone_e164 or "-",
        result.get("message_id") or "-",
        provider_persist_error or "-",
    )
    return _jsonable(result)


def confirm_visit(
    *,
    proposal_id: str,
    confirmed_option: int,
    confirmed_by: str,
) -> dict[str, Any]:
    clean_proposal_id = str(proposal_id or "").strip()
    if not clean_proposal_id:
        raise ValueError("proposal_id is required")

    if confirmed_option not in {1, 2, 3}:
        raise ValueError("confirmed_option must be 1, 2 or 3")

    actor = str(confirmed_by or "").strip().lower()
    if actor not in {"client", "advisor", "supervisor"}:
        raise ValueError("confirmed_by must be client, advisor or supervisor")

    def _tx(conn: Any) -> dict[str, Any]:
        proposal = repo.get_visit_proposal(conn, clean_proposal_id)
        if proposal is None:
            raise KeyError("proposal not found")

        if str(proposal.get("status") or "") == "accepted":
            raise ValueError("proposal already accepted")

        option_key = f"option{confirmed_option}"
        confirmed_at = proposal.get(option_key)
        if confirmed_at is None:
            raise ValueError(f"proposal does not have {option_key}")

        ticket_id = str(proposal["ticket_id"])

        confirmation = repo.insert_visit_confirmation(
            conn,
            proposal_id=clean_proposal_id,
            ticket_id=ticket_id,
            confirmed_option=confirmed_option,
            confirmed_at=confirmed_at,
            confirmed_by=actor,
        )
        repo.mark_visit_proposal_accepted(conn, clean_proposal_id)
        repo.supersede_active_proposals(conn, ticket_id)

        ticket = repo.update_ticket_activity(
            conn,
            ticket_id,
            stage=STAGE_VISIT_CONFIRMED,
            visit_scheduled_at=confirmed_at,
            last_message_snippet=_normalize_snippet(
                f"Visita confirmada (opción {confirmed_option})"
            ),
        )

        repo.insert_event(
            conn,
            correlation_id=ticket_id,
            domain=DOMAIN,
            name="visit.confirmed",
            actor=actor,
            payload={
                "ticket_id": ticket_id,
                "proposal_id": clean_proposal_id,
                "confirmation_id": confirmation.get("id"),
                "confirmed_option": confirmed_option,
                "confirmed_by": actor,
                "confirmed_at": confirmed_at,
            },
        )

        return {
            "ticket_id": ticket_id,
            "proposal_id": clean_proposal_id,
            "confirmation_id": confirmation.get("id"),
            "confirmed_option": confirmed_option,
            "confirmed_by": actor,
            "visit_scheduled_at": confirmed_at,
            "stage": ticket.get("stage"),
        }

    result = db.run_in_transaction(_tx)
    ticket_id = str(result.get("ticket_id"))
    set_correlation_id(ticket_id)
    logger.info(
        "ORQ_CONFIRM_VISIT correlation_id=%s proposal_id=%s confirmation_id=%s option=%s by=%s",
        ticket_id,
        clean_proposal_id,
        result.get("confirmation_id"),
        confirmed_option,
        actor,
    )
    return _jsonable(result)


def reschedule_visit(
    *,
    ticket_id: str,
    advisor_name: str | None,
    option1: datetime | None,
    option2: datetime | None,
    option3: datetime | None,
    message_out: str,
) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    clean_message_out = str(message_out or "").strip()
    if not clean_message_out:
        raise ValueError("message_out is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        advisor = repo.find_advisor_by_name(conn, advisor_name)
        if advisor_name and advisor is None:
            raise ValueError("advisor_name not found")

        superseded_count = repo.supersede_active_proposals(conn, clean_ticket_id)

        proposal = repo.create_visit_proposal(
            conn,
            ticket_id=clean_ticket_id,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            advisor_id=str(advisor["id"]) if advisor else None,
            mode="reschedule",
            option1=option1,
            option2=option2,
            option3=option3,
            message_out=clean_message_out,
        )

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="advisor",
            text=clean_message_out,
            provider_meta={
                "mode": "reschedule",
                "proposal_id": str(proposal.get("id")),
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
            },
        )

        ticket = repo.update_ticket_activity(
            conn,
            clean_ticket_id,
            stage=STAGE_WAITING_CONFIRMATION,
            assigned_advisor_id=str(advisor["id"]) if advisor else None,
            last_message_snippet=_normalize_snippet(clean_message_out),
        )

        repo.insert_event(
            conn,
            correlation_id=clean_ticket_id,
            domain=DOMAIN,
            name="visit.rescheduled",
            actor="advisor",
            payload={
                "ticket_id": clean_ticket_id,
                "proposal_id": proposal.get("id"),
                "mode": "reschedule",
                "superseded_count": superseded_count,
                "advisor_id": advisor.get("id") if advisor else None,
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
                "message_id": message.get("id"),
                "option1": proposal.get("option1"),
                "option2": proposal.get("option2"),
                "option3": proposal.get("option3"),
            },
        )

        return {
            "ticket_id": clean_ticket_id,
            "proposal_id": proposal.get("id"),
            "mode": "reschedule",
            "stage": ticket.get("stage"),
            "superseded_count": superseded_count,
            "advisor": advisor,
            "message_id": message.get("id"),
            "option1": proposal.get("option1"),
            "option2": proposal.get("option2"),
            "option3": proposal.get("option3"),
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_RESCHEDULE_VISIT correlation_id=%s proposal_id=%s superseded_count=%s",
        clean_ticket_id,
        result.get("proposal_id"),
        result.get("superseded_count"),
    )
    return _jsonable(result)


async def supervisor_send(
    *,
    ticket_id: str | None,
    lead_phone: str | None = None,
    target: str | None = "client",
    text: str,
) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    clean_lead_phone = str(lead_phone or "").strip()
    if not clean_ticket_id and not clean_lead_phone:
        raise ValueError("ticket_id or lead_phone is required")

    clean_target = str(target or "client").strip().lower() or "client"
    if clean_target not in {"client", "advisor"}:
        raise ValueError("target must be client or advisor")

    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")

    def _tx_prepare(conn: Any) -> dict[str, Any]:
        resolved_ticket_id = clean_ticket_id
        context = None

        if resolved_ticket_id:
            context = repo.get_ticket_context(conn, resolved_ticket_id)
        else:
            normalized_lead_phone = _normalize_phone_e164(clean_lead_phone)
            lead = repo.get_lead_by_phone(conn, normalized_lead_phone)
            if lead is None:
                raise KeyError("lead not found")
            conversation = repo.get_open_conversation_for_lead(conn, str(lead["id"]))
            if conversation is None:
                raise KeyError("conversation not found")
            ticket = repo.get_ticket_by_conversation(conn, str(conversation["id"]))
            if ticket is None:
                raise KeyError("ticket not found")
            resolved_ticket_id = str(ticket["id"])
            context = repo.get_ticket_context(conn, resolved_ticket_id)

        if context is None:
            raise KeyError("ticket not found")

        if clean_target == "advisor":
            target_phone = _normalize_target_phone(context.get("assigned_advisor_phone_e164"))
        else:
            target_phone = _normalize_target_phone(context.get("phone_e164"))

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="supervisor",
            text=clean_text,
            provider_meta={
                "target": clean_target,
                "provider": "gupshup",
                "target_phone_e164": target_phone or None,
            },
        )

        ticket = repo.update_ticket_activity(
            conn,
            str(resolved_ticket_id),
            last_message_snippet=_normalize_snippet(clean_text),
        )

        return {
            "ticket_id": str(resolved_ticket_id),
            "target": clean_target,
            "target_phone_e164": target_phone,
            "message_id": str(message.get("id")),
            "stage": ticket.get("stage"),
            "last_activity_at": ticket.get("last_activity_at"),
        }

    prepared = db.run_in_transaction(_tx_prepare)

    target_phone_e164 = str(prepared.get("target_phone_e164") or "").strip()
    if not target_phone_e164:
        provider_result = {
            "send_ok": False,
            "provider": "gupshup",
            "provider_status": "error",
            "provider_message_id": None,
            "provider_response": {},
            "error": "missing_target_phone",
        }
    else:
        provider_result = await _send_supervisor_whatsapp_via_gupshup(target_phone_e164, clean_text)

    provider_status = str(provider_result.get("provider_status") or "error")
    provider_message_id = (
        str(provider_result.get("provider_message_id") or "").strip() or None
    )
    provider_error = str(provider_result.get("error") or "").strip() or None
    provider_response = (
        provider_result.get("provider_response")
        if isinstance(provider_result.get("provider_response"), dict)
        else {}
    )
    sent_at = datetime.now(timezone.utc) if provider_status == "sent" else None
    provider_persist_error: str | None = None

    def _tx_finalize(conn: Any) -> None:
        nonlocal provider_persist_error
        try:
            repo.ensure_messages_provider_columns(conn)
            repo.update_message_provider_result(
                conn,
                message_id=str(prepared["message_id"]),
                provider_name="gupshup",
                provider_status=provider_status,
                provider_message_id=provider_message_id,
                provider_response=provider_response,
                provider_error=provider_error,
                sent_at=sent_at,
            )
        except Exception as exc:  # noqa: BLE001
            provider_persist_error = str(exc)
            repo.insert_event(
                conn,
                correlation_id=str(prepared["ticket_id"]),
                domain=DOMAIN,
                name="supervisor.message.provider_persist_fallback",
                actor="system",
                payload={
                    "ticket_id": str(prepared["ticket_id"]),
                    "message_id": str(prepared["message_id"]),
                    "provider": "gupshup",
                    "provider_status": provider_status,
                    "provider_message_id": provider_message_id,
                    "provider_error": provider_error,
                    "provider_response": provider_response,
                    "persist_error": str(exc),
                },
            )

        repo.insert_event(
            conn,
            correlation_id=str(prepared["ticket_id"]),
            domain=DOMAIN,
            name="supervisor.message.sent",
            actor="supervisor",
            payload={
                "ticket_id": str(prepared["ticket_id"]),
                "target": str(prepared["target"]),
                "message_id": str(prepared["message_id"]),
                "text": clean_text,
                "provider": "gupshup",
                "provider_status": provider_status,
                "provider_message_id": provider_message_id,
                "provider_error": provider_error,
                "send_ok": bool(provider_result.get("send_ok")),
            },
        )

    db.run_in_transaction(_tx_finalize)

    set_correlation_id(str(prepared["ticket_id"]))
    if provider_status == "sent":
        logger.info(
            "ORQ_SUPERVISOR_SEND correlation_id=%s target=%s phone=%s provider=%s status=%s provider_message_id=%s message_id=%s",
            prepared["ticket_id"],
            prepared["target"],
            target_phone_e164 or "-",
            "gupshup",
            provider_status,
            provider_message_id or "-",
            prepared["message_id"],
        )
    else:
        logger.warning(
            "ORQ_SUPERVISOR_SEND correlation_id=%s target=%s phone=%s provider=%s status=%s error=%s message_id=%s persist_error=%s",
            prepared["ticket_id"],
            prepared["target"],
            target_phone_e164 or "-",
            "gupshup",
            provider_status,
            provider_error or "-",
            prepared["message_id"],
            provider_persist_error or "-",
        )

    return _jsonable(
        {
            "send_ok": bool(provider_result.get("send_ok")),
            "provider": "gupshup",
            "provider_message_id": provider_message_id,
            "error": provider_error,
            "message_id": str(prepared["message_id"]),
            "ticket_id": str(prepared["ticket_id"]),
        }
    )


def ticket_detail(*, ticket_id: str) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        ticket = repo.get_ticket_detail(conn, clean_ticket_id)
        messages = repo.list_conversation_messages(conn, str(context["conversation_id"]), limit=200)
        active_proposal = repo.get_active_visit_proposal_for_ticket(conn, clean_ticket_id)

        return {
            "ticket": ticket or context,
            "context": context,
            "active_proposal": active_proposal,
            "messages": messages,
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_TICKET_DETAIL correlation_id=%s messages=%s has_active_proposal=%s",
        clean_ticket_id,
        len(result.get("messages") or []),
        bool(result.get("active_proposal")),
    )
    return _jsonable(result)
