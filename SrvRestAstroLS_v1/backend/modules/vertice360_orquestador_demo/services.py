from __future__ import annotations

import difflib
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
    r"\bir\s+a\s+ver\b",
    r"\bver\s+el\s+depto\b",
    r"\bpasar\s+a\s+ver\b",
)

HUMAN_CONTACT_PATTERNS = (
    r"\bhablar\s+con\s+un\s+asesor\b",
    r"\bhablar\s+con\s+alguien\b",
    r"\bque\s+me\s+contacte\b",
    r"\bque\s+me\s+llamen\b",
    r"\bllamada\b",
    r"\bvideo\s*llamada\b",
    r"\bvideollamada\b",
    r"\bcontact(?:ame|arme|enme|en)\b",
    r"\bllam(?:ame|arme|enme|en)\b",
    r"\basesor(?:a)?\b",
    r"\bhumano\b",
)

AMBIGUOUS_MEETING_PATTERNS = (
    r"\breunion(?:es)?\b",
    r"\bcita\b",
    r"\bentrevista\b",
    r"\bcoordinar\b",
    r"\bcoordinamos\b",
    r"\bagendar(?:mos)?\b",
    r"\bpodemos\s+reunirnos\b",
)

LIST_PROJECT_PATTERNS = (
    r"\bque\s+proyectos?\s+ten(?:es|eis|en)\b",
    r"\bcuales?\s+proyectos?\s+ten(?:es|eis|en)\b",
    r"\bcuales?\s+son\s+los?\s+proyectos?\b",
    r"\bque\s+proyectos?\s+son\b",
    r"\bque\s+obras?\s+ten(?:es|eis|en)\b",
    r"\bcuales?\s+obras?\s+ten(?:es|eis|en)\b",
    r"\bcuales?\s+son\s+las?\s+otras?\s+obras?\b",
    r"\bque\s+obra\s+ten(?:es|eis|en)\b",
    r"\bque\s+proyecto\s+ten(?:es|eis|en)\b",
    r"\bcual\s+otro\b",
)

PROJECT_OVERVIEW_PATTERNS = (
    r"\bcontame\b",
    r"\bdecime\b",
    r"\binfo\b",
    r"\binformacion\b",
    r"\bdetalle\b",
    r"\bdetalles\b",
    r"\bcomo\s+es\b",
    r"\bde\s+que\s+se\s+trata\b",
)

GLOBAL_PRICE_HIGHEST_PATTERNS = (
    r"\b(precio|valor)\s+m[aá]s\s+alto\b",
    r"\bunidad\s+m[aá]s\s+car[ao]\b",
    r"\bproyecto\s+.*unidad\s+m[aá]s\s+car[ao]\b",
    r"\bvalor\s+m[aá]ximo\b",
    r"\bprecio\s+m[aá]ximo\b",
    r"\bm[aá]ximo\b",
)

AFFIRM_PATTERNS = (
    r"\bs[ií]\b",
    r"\bdale\b",
    r"\bok\b",
    r"\bperfecto\b",
    r"\bde\s+una\b",
    r"\bclaro\b",
    r"\bbuen[ií]sim[oa]\b",
    r"\bgenial\b",
    r"\blisto\b",
)

GREETING_PATTERNS = (
    r"hola",
    r"buenas",
    r"buen dia",
    r"hi",
    r"hello",
    r"que tal",
)

ACKNOWLEDGEMENT_PATTERNS = (
    r"gracias",
    r"muchas gracias",
    r"ok",
    r"dale",
    r"perfecto",
    r"buenisimo",
    r"genial",
    r"de una",
    r"claro",
    r"listo",
    r"👍",
)

UNIT_FEATURE_ALIASES: dict[str, tuple[str, ...]] = {
    "balcon": ("balcon", "balcones"),
    "cochera": ("cochera", "parking", "garage"),
    "jardin": ("jardin", "garden"),
    "parrilla": ("parrilla",),
    "patio": ("patio",),
    "baulera": ("baulera", "storage"),
    "en_suite": ("en suite", "suite"),
    "walk_in_closet": ("walk in closet", "vestidor"),
    "mascotas": ("mascotas", "pet friendly", "pets allowed"),
    "lavadero": ("lavadero", "laundry"),
    "jacuzzi": ("jacuzzi", "hidromasaje"),
    "pileta": ("pileta", "piscina"),
    "terraza": ("terraza", "terrazas"),
    "toilette": ("toilette",),
}

GLOBAL_SEARCH_SIGNALS = (
    r"\ben\s+todos\s+los\s+proyectos\b",
    r"\ben\s+todos\b",
    r"\bde\s+todos\s+los\s+proyectos\b",
    r"\bno\s+importa\s+(?:el\s+)?proyecto\b",
    r"\bsin\s+importar\s+(?:el\s+)?proyecto\b",
    r"\bcualquiera\b",
    r"\bcualquier\s+proyecto\b",
    r"\bde\s+cualquier\s+proyecto\b",
    r"\bde\s+todos\b",
    r"\btomando\s+todos\b",
    r"\btomando\s+todos\s+los\s+proyectos\b",
    r"\bno\s+importa\s+cual\b",
    r"\bme\s+da\s+igual\s+el\s+proyecto\b",
    r"\ben\s+cualquier\s+proyecto\b",
)

PROJECT_SCOPE_OVERRIDE_PATTERNS = (
    *GLOBAL_SEARCH_SIGNALS,
    r"\bentre\s+todos\s+los\s+proyectos\b",
    r"\bentre\s+todos\b",
    r"\bglobalmente\b",
)

SURFACE_QUERY_PATTERNS = (
    r"\bmetros?\b",
    r"\bmetros?\s+cuadrados?\b",
    r"\bm2\b",
    r"\bm²\b",
    r"\bmts?\b",
    r"\bmts?\s+cuadrados?\b",
    r"\b\d+(?:[.,]\d+)?\s*mts?\b",
    r"\b\d+(?:[.,]\d+)?\s*m2\b",
    r"\bsuperficie(?:s)?\b",
    r"\bsuperficie\s+(?:cubierta|total)\b",
    r"\bmedidas?\b",
)

PROJECT_COMPARISON_METRIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reserved_units", (r"\breservas?\b",)),
    ("units_total", (r"\bunidades?\b", r"\bdepartamentos?\b", r"\bdeptos?\b")),
    ("available_units", (r"\bdisponibilid(?:ad|ades)\b", r"\bdisponibles?\b", r"\bstock\b")),
    ("average_price", (r"\bprecio\s+promedio\b", r"\bvalor\s+promedio\b", r"\bticket\s+promedio\b")),
    ("visits", (r"\bvisitas?\b",)),
    ("leads", (r"\bleads?\b",)),
    ("closures", (r"\bcierres?\b",)),
)

PROJECT_COMPARISON_METRIC_CONFIG: dict[str, dict[str, Any]] = {
    "reserved_units": {
        "label": "reservas",
        "missing_answer": "No tengo reservas cargadas por proyecto para comparar.",
        "answer_template": "Tomando el inventario que tengo cargado hoy, el proyecto con más reservas es {project_name}, con {value} reservas.",
        "fields": ["demo_project_profile.reserved_units", "demo_units.availability_status"],
    },
    "units_total": {
        "label": "total de unidades",
        "missing_answer": "No tengo total de unidades cargado por proyecto para comparar.",
        "answer_template": "Tomando el inventario que tengo cargado hoy, el proyecto con más unidades es {project_name}, con {value} unidades.",
        "fields": ["demo_project_profile.units_total", "demo_project_facts.units_total", "demo_units.availability_status"],
    },
    "available_units": {
        "label": "disponibilidad",
        "missing_answer": "No tengo disponibilidad cargada por proyecto para comparar.",
        "answer_template": "Tomando el inventario que tengo cargado hoy, el proyecto con más disponibilidad es {project_name}, con {value} unidades disponibles.",
        "fields": ["demo_project_profile.available_units", "demo_units.availability_status"],
    },
    "average_price": {
        "label": "precio promedio",
        "missing_answer": "No tengo precio promedio por proyecto para comparar.",
        "fields": ["demo_units.list_price"],
    },
    "visits": {
        "label": "visitas",
        "missing_answer": "No tengo visitas cargadas por proyecto para comparar.",
        "fields": [],
    },
    "leads": {
        "label": "leads",
        "missing_answer": "No tengo leads cargados por proyecto para comparar.",
        "fields": [],
    },
    "closures": {
        "label": "cierres",
        "missing_answer": "No tengo cierres cargados por proyecto para comparar.",
        "fields": [],
    },
}

OUT_OF_SCOPE_PATTERNS = (
    r"\bexpensas?\b",
    r"\breglamento\b",
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
        "AVAILABLE_UNITS",
        (
            r"\bdisponible(?:s)?\b",
            r"\bstock\b",
            r"\bquedan\b",
            r"\bcu[aá]ntas?\s+quedan\b",
            r"\bcu[aá]ntos?\s+hay\b.*\bdisponible",
            r"\bambientes?\s+disponibles\b",
            r"\bhay\s+disponibles\b",
        ),
    ),
    (
        "PRICE",
        (
            r"\bprecio(?:s)?\b",
            r"\bvalor(?:es)?\b",
            r"\bcu[aá]nto\s+sale\b",
            r"\bcu[aá]nto\s+vale\b",
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

FUZZY_INTENT_ALIASES: dict[str, tuple[str, ...]] = {
    "FEATURES": ("caracteristicas", "caracteristica", "amenities", "servicios", "carac"),
    "PRICE": ("precio", "precios", "valor", "valores", "cuanto sale"),
    "DELIVERY": ("entrega", "entregan", "posesion", "fecha estimada"),
    "FINANCING": ("financiacion", "financia", "cuotas", "anticipo", "plan de pago"),
    "AVAILABLE_UNITS": ("disponibles", "disponible", "stock", "cuantas hay", "cuantas quedan"),
    "UNIT_TYPES": ("tipologias", "tipologia", "tipos", "ambientes", "que hay"),
    "VISIT_REQUEST": ("visita", "visitar", "agendar visita", "quiero visitar"),
    "HUMAN_CONTACT_REQUEST": ("asesor", "contactame", "contacto", "llamame", "hablar con alguien"),
}

REAL_AMENITY_HINTS = (
    "sum",
    "piscina",
    "pileta",
    "gym",
    "gim",
    "cowork",
    "club house",
    "cancha",
    "parrilla",
    "solarium",
    "bike",
    "bicicletero",
    "bike rack",
    "terraza",
    "quincho",
    "laundry",
    "sauna",
    "jacuzzi",
    "playroom",
    "camara",
    "camaras",
    "acceso",
    "biometr",
    "portero",
    "wifi",
    "panel",
    "solar",
)

GENERIC_OVERVIEW_TERMS = {
    "seguridad",
    "domotica",
    "eficiencia",
    "premium",
    "inversion",
    "familia",
    "en construccion",
    "confort",
    "detalles premium",
    "espacios inteligentes",
    "diseno flexible",
    "smartwifi",
}


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


def _compact_normalized_text(value: str) -> str:
    return _normalize_text(value).replace(" ", "")


def _fuzzy_basic_intent(
    text: str,
    *,
    selected_project_code: str | None,
) -> tuple[str | None, float, str]:
    clean = _normalize_text(text)
    compact = _compact_normalized_text(text)
    if not clean or len(compact) < 4:
        return None, 0.0, ""

    selected_context = bool(str(selected_project_code or "").strip())
    best_intent: str | None = None
    best_score = 0.0
    best_alias = ""

    for intent, aliases in FUZZY_INTENT_ALIASES.items():
        for alias in aliases:
            alias_clean = _normalize_text(alias)
            alias_compact = alias_clean.replace(" ", "")
            if not alias_clean:
                continue
            if clean == alias_clean or compact == alias_compact:
                return intent, 0.99, alias_clean
            if len(compact) >= 4 and (alias_clean.startswith(clean) or alias_compact.startswith(compact)):
                score = 0.96 if len(clean) >= 5 else 0.91
                if score > best_score:
                    best_intent = intent
                    best_score = score
                    best_alias = alias_clean
                continue
            ratio = max(
                difflib.SequenceMatcher(None, clean, alias_clean).ratio(),
                difflib.SequenceMatcher(None, compact, alias_compact).ratio(),
            )
            threshold = 0.88
            if selected_context:
                threshold = 0.78 if len(compact) >= 6 else 0.84
            if ratio >= threshold and ratio > best_score:
                best_intent = intent
                best_score = ratio
                best_alias = alias_clean

    return best_intent, best_score, best_alias


def parse_ambientes(text: str) -> int | None:
    clean = _normalize_text(text)
    if not clean:
        return None

    if re.search(r"\bmono(?:ambiente)?s?\b", clean):
        return 1

    digit_match = re.search(r"\b([1-4])\s*amb(?:\.|iente|ientes)?\b", clean)
    if digit_match:
        return int(digit_match.group(1))

    word_map = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4}
    word_match = re.search(r"\b(un|uno|dos|tres|cuatro)\s+amb(?:\.|iente|ientes)?\b", clean)
    if word_match:
        return word_map.get(word_match.group(1))
    return None


def _rooms_label_from_count(rooms_count: int | None) -> str:
    if rooms_count is None:
        return ""
    rooms_int = int(rooms_count)
    return "1 ambiente" if rooms_int == 1 else f"{rooms_int} ambientes"


def _last_rooms_query(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary_obj = summary if isinstance(summary, dict) else {}
    raw = summary_obj.get("last_rooms_query")
    data = raw if isinstance(raw, dict) else {}
    rooms_count = data.get("rooms_count")
    try:
        normalized_rooms = int(rooms_count) if rooms_count is not None else None
    except Exception:  # noqa: BLE001
        normalized_rooms = None
    return {
        "rooms_count": normalized_rooms,
        "rooms_label": str(data.get("rooms_label") or _rooms_label_from_count(normalized_rooms)).strip(),
        "intent": str(data.get("intent") or "").strip().upper(),
        "search_scope": str(data.get("search_scope") or "").strip().lower(),
    }


def _normalize_active_filter_payload(filter_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    raw_payload = payload if isinstance(payload, dict) else {}
    normalized: dict[str, Any] = {}
    clean_type = str(filter_type or "").strip().lower()
    if clean_type in {"rooms", "feature", "surface"}:
        rooms_count = raw_payload.get("rooms_count")
        try:
            normalized["rooms_count"] = int(rooms_count) if rooms_count is not None else None
        except Exception:  # noqa: BLE001
            normalized["rooms_count"] = None
    if clean_type == "feature":
        normalized["feature_key"] = str(raw_payload.get("feature_key") or "").strip().lower() or None
    if clean_type == "surface":
        min_surface = _to_float(raw_payload.get("min_surface_total_m2"))
        max_surface = _to_float(raw_payload.get("max_surface_total_m2"))
        if min_surface is not None:
            normalized["min_surface_total_m2"] = float(min_surface)
        if max_surface is not None:
            normalized["max_surface_total_m2"] = float(max_surface)
    facets = [
        str(item or "").strip().lower()
        for item in (raw_payload.get("facets_applied") or [])
        if str(item or "").strip()
    ]
    if facets:
        normalized["facets_applied"] = _dedupe_texts(facets, limit=8)
    return {key: value for key, value in normalized.items() if value is not None}


def _active_filter_summary_text(filter_type: str, payload: dict[str, Any] | None) -> str:
    clean_type = str(filter_type or "").strip().lower()
    normalized_payload = _normalize_active_filter_payload(clean_type, payload)
    rooms_count = normalized_payload.get("rooms_count")
    rooms_text = f" de {_rooms_label_from_count(int(rooms_count))}" if rooms_count is not None else ""
    facets = [str(item or "").strip().lower() for item in (normalized_payload.get("facets_applied") or []) if str(item or "").strip()]
    facet_labels = [_feature_label(item) for item in facets]
    if clean_type == "rooms" and rooms_count is not None:
        summary = f"unidades de {_rooms_label_from_count(int(rooms_count))}"
        if facet_labels:
            summary += f" con {' y '.join(facet_labels)}"
        return summary
    if clean_type == "feature":
        feature_key = str(normalized_payload.get("feature_key") or "").strip()
        if feature_key:
            labels = [_feature_label(feature_key), *facet_labels]
            return f"unidades{rooms_text} con {' y '.join(labels)}"
    if clean_type == "surface":
        min_surface = normalized_payload.get("min_surface_total_m2")
        max_surface = normalized_payload.get("max_surface_total_m2")
        if min_surface is not None and max_surface is not None:
            summary = f"unidades{rooms_text} entre {_format_surface(min_surface)} y {_format_surface(max_surface)} m²"
            if facet_labels:
                summary += f" con {' y '.join(facet_labels)}"
            return summary
        if min_surface is not None:
            summary = f"unidades{rooms_text} de más de {_format_surface(min_surface)} m²"
            if facet_labels:
                summary += f" con {' y '.join(facet_labels)}"
            return summary
        if max_surface is not None:
            summary = f"unidades{rooms_text} de hasta {_format_surface(max_surface)} m²"
            if facet_labels:
                summary += f" con {' y '.join(facet_labels)}"
            return summary
    return "unidades que cumplen el filtro actual"


def _last_active_filter(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary_obj = summary if isinstance(summary, dict) else {}
    raw = summary_obj.get("active_filter")
    data = raw if isinstance(raw, dict) else {}
    filter_type = str(data.get("type") or "").strip().lower()
    payload = _normalize_active_filter_payload(filter_type, data.get("payload") if isinstance(data.get("payload"), dict) else {})
    return {
        "type": filter_type,
        "payload": payload,
        "scope": str(data.get("scope") or "").strip().lower(),
        "origin_intent": str(data.get("origin_intent") or "").strip().upper(),
        "project_code": str(data.get("project_code") or "").strip().upper(),
        "project_name": str(data.get("project_name") or "").strip(),
        "summary": str(data.get("summary") or _active_filter_summary_text(filter_type, payload)).strip(),
    }


def _build_active_filter_summary_patch(
    *,
    filter_type: str,
    filter_payload: dict[str, Any] | None,
    scope: str,
    origin_intent: str,
    project_code: str | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    clean_type = str(filter_type or "").strip().lower()
    payload = _normalize_active_filter_payload(clean_type, filter_payload)
    return {
        "active_filter": {
            "type": clean_type or None,
            "payload": payload,
            "scope": str(scope or "").strip().lower() or None,
            "origin_intent": str(origin_intent or "").strip().upper() or None,
            "project_code": str(project_code or "").strip().upper() or None,
            "project_name": str(project_name or "").strip() or None,
            "summary": _active_filter_summary_text(clean_type, payload),
        }
    }


def _build_rooms_query_summary_patch(
    *,
    rooms_count: int,
    query_intent: str,
    search_scope: str,
) -> dict[str, Any]:
    return {
        "last_rooms_query": {
            "rooms_count": int(rooms_count),
            "rooms_label": _rooms_label_from_count(int(rooms_count)),
            "intent": str(query_intent or "").strip().upper(),
            "search_scope": str(search_scope or "").strip().lower(),
        }
    }


def _is_count_units_by_rooms_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean or parse_ambientes(clean) is None:
        return False
    if re.search(r"\bcantidad\s+de\s+unidades?\b", clean):
        return True
    if re.search(r"\bcu[aá]ntas?\s+unidades?\s+de\b", clean):
        return True
    if re.search(r"\bcu[aá]ntos?\s+(?:mono(?:ambiente)?s?|[1-4]\s+ambientes?)\s+ten(?:e|es|en)\b", clean):
        return True
    if re.search(r"\bcu[aá]ntas?\s+hay\b", clean) and re.search(r"\bambientes?\b", clean):
        return True
    return False


def _is_list_units_by_rooms_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean or parse_ambientes(clean) is None:
        return False
    if re.search(r"\b(precio(?:s)?|valor(?:es)?|cu[aá]nto\s+sale|cu[aá]nto\s+vale|usd|ars|dolares?|pesos?)\b", clean):
        return False
    patterns = (
        r"\bquiero\s+todas?\s+las?\s+unidades?\b",
        r"\bmostra(?:me|r)?\b",
        r"\blista(?:me|r)?\b",
        r"\bcu[aá]les?\s+son\b",
        r"\bdame\b",
        r"\bpasame\b",
        r"\bver\b.*\bunidades?\b",
        r"\btodas?\s+las?\s+unidades?\s+de\b",
    )
    return any(re.search(pattern, clean) for pattern in patterns)


def _is_global_scope_override_followup(text: str, summary: dict[str, Any] | None) -> bool:
    if not _has_global_scope_override(text):
        return False
    clean = _normalize_text(text)
    if parse_ambientes(clean) is not None:
        return False
    if _extract_feature_key(text) or _extract_surface_filter(text):
        return False
    active_filter = _last_active_filter(summary)
    if active_filter.get("type"):
        return True
    last_rooms = _last_rooms_query(summary)
    return last_rooms.get("rooms_count") is not None and last_rooms.get("intent") in {
        "COUNT_UNITS_BY_ROOMS",
        "LIST_UNITS_BY_ROOMS",
    }


def _is_projects_matching_active_filter_question(text: str, summary: dict[str, Any] | None) -> bool:
    active_filter = _last_active_filter(summary)
    if active_filter.get("type") not in {"rooms", "feature", "surface"}:
        return False
    if str(active_filter.get("scope") or "").strip().lower() not in {"global", "transversal"}:
        return False
    clean = _normalize_text(text)
    if not clean:
        return False
    patterns = (
        r"\bcuales?\s+son\s+los\s+proyectos\b",
        r"\bque\s+proyectos?\s+son\b",
        r"\bque\s+proyectos?\s+tienen\b",
        r"\ben\s+que\s+proyectos?\b",
        r"\ben\s+cuales?\b",
        r"^cuales?$",
        r"^en\s+cuales?$",
    )
    return any(re.search(pattern, clean) for pattern in patterns)


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


def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return any(re.search(pattern, clean) for pattern in patterns)


def _normalize_short_social_text(text: str) -> str:
    clean = _normalize_text(text)
    return re.sub(r"[!¡?¿.,;:]+", "", clean).strip()


def _is_human_contact_request(text: str) -> bool:
    return _matches_any_pattern(text, HUMAN_CONTACT_PATTERNS)


def _is_ambiguous_meeting_request(text: str) -> bool:
    return _matches_any_pattern(text, AMBIGUOUS_MEETING_PATTERNS)


def _is_list_projects_request(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if any(re.search(pattern, clean) for pattern in LIST_PROJECT_PATTERNS):
        return True
    asks_projects = bool(re.search(r"\b(proyectos?|obras?)\b", clean))
    asks_other = bool(re.search(r"\botr[oa]s?\b", clean))
    rejects_project = bool(re.search(r"\bno\b", clean))
    return asks_projects and (asks_other or rejects_project)


def _is_project_overview_request(text: str) -> bool:
    return _matches_any_pattern(text, PROJECT_OVERVIEW_PATTERNS)


def _is_affirm_message(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if len(clean.split()) > 3:
        return False
    return any(re.fullmatch(pattern, clean) for pattern in AFFIRM_PATTERNS)


def _is_greeting_message(text: str) -> bool:
    clean = _normalize_short_social_text(text)
    if not clean or len(clean.split()) > 4:
        return False
    return clean in GREETING_PATTERNS


def _is_acknowledgement_message(text: str) -> bool:
    clean = _normalize_short_social_text(text)
    if not clean or len(clean.split()) > 4:
        return False
    if clean in ACKNOWLEDGEMENT_PATTERNS:
        return True
    if clean.startswith("gracias"):
        return True
    return False


def _is_global_scope_ack_message(text: str, summary: dict[str, Any] | None = None) -> bool:
    clean = _normalize_short_social_text(text)
    if clean != "cualquiera":
        return False
    summary_obj = summary if isinstance(summary, dict) else {}
    last_intent = str(summary_obj.get("last_intent") or "").strip().upper()
    last_search_scope = str(summary_obj.get("last_search_scope") or "").strip().lower()
    return last_search_scope == "global" or last_intent in {
        "GLOBAL_UNIT_FILTER_SEARCH",
        "GLOBAL_UNIT_SEARCH_BY_FEATURE",
        "LIST_PROJECTS",
    }


def _detect_global_price_extreme(text: str) -> str | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    if any(re.search(pattern, clean) for pattern in GLOBAL_PRICE_HIGHEST_PATTERNS):
        return "highest"
    return None


def _is_surface_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if any(re.search(pattern, clean) for pattern in SURFACE_QUERY_PATTERNS):
        return True
    asks_largest = bool(re.search(r"\b(m[aá]s\s+grande|mayor(?:\s+superficie)?|m[aá]xima?\s+superficie)\b", clean))
    asks_units = bool(re.search(r"\b(unidad(?:es)?|depto(?:s)?|departamento(?:s)?)\b", clean))
    return asks_largest and asks_units


def _is_surface_extreme_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(re.search(r"\b(m[aá]s\s+grande|mayor(?:\s+superficie)?|m[aá]xima?\s+superficie)\b", clean))


def _is_surface_filter_list_query(text: str, surface_filter: dict[str, Any] | None = None) -> bool:
    clean = _normalize_text(text)
    if not clean or not surface_filter:
        return False
    if re.search(r"\b(cu[aá]l\s+es|el\s+departamento|la\s+unidad)\b", clean) and _is_surface_extreme_query(clean):
        return False
    return bool(
        re.search(
            r"\b(departamentos?|deptos?|unidades?|los\s+que|las\s+que|listad[oa]s?|mostra(?:me)?|dame|me\s+das?)\b",
            clean,
        )
    )


def _mentions_explicit_project_entity(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(re.search(r"\bproyectos?\b", clean))


def _asks_project_comparison_identity(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean or not _mentions_explicit_project_entity(clean):
        return False
    patterns = (
        r"\bcu[aá]l\s+es\s+(?:el\s+)?proyecto\b",
        r"\bcu[aá]l\s+proyecto\b",
        r"\bqu[eé]\s+proyecto\b",
    )
    return any(re.search(pattern, clean) for pattern in patterns)


def _has_explicit_project_entity_override(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean or not _mentions_explicit_project_entity(clean):
        return False
    patterns = (
        r"\bde\s+todos\s+los\s+proyectos\b",
        r"\bentre\s+todos\s+los\s+proyectos\b",
        r"\bqu[eé]\s+proyecto\s+tiene\b",
        r"\bqu[eé]\s+proyecto\s+es\s+el\s+(?:que\s+)?m[aá]s\b",
        r"\bqu[eé]\s+proyecto\s+es\s+el\s+mayor\b",
        r"\bproyecto\s+con\s+m[aá]s\b",
        r"\bproyecto\s+m[aá]s\s+grande\b",
    )
    return _asks_project_comparison_identity(clean) or any(re.search(pattern, clean) for pattern in patterns)


def _has_project_scope_override(text: str) -> bool:
    return _matches_any_pattern(text, PROJECT_SCOPE_OVERRIDE_PATTERNS)


def _extract_project_comparison_metric(text: str) -> str | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    if _is_surface_query(clean) or re.search(r"\b(construid\w*|construcci[oó]n|superficie\s+construid\w*)\b", clean):
        return "surface_total_m2"
    for metric, patterns in PROJECT_COMPARISON_METRIC_PATTERNS:
        if any(re.search(pattern, clean) for pattern in patterns):
            return metric
    return None


def _extract_project_comparison_request(text: str) -> dict[str, Any] | None:
    clean = _normalize_text(text)
    if not clean or not _mentions_explicit_project_entity(clean):
        return None
    metric = _extract_project_comparison_metric(clean)
    if not metric:
        return None
    explicit_project_entity_override = _has_explicit_project_entity_override(clean)
    if not explicit_project_entity_override and re.search(r"\b(unidad(?:es)?|depto(?:s)?|departamento(?:s)?)\b", clean):
        return None
    has_comparison_signal = bool(re.search(r"\b(m[aá]s|menos|mayor|menor|promedio)\b", clean))
    if not (explicit_project_entity_override or (has_comparison_signal and _asks_project_comparison_identity(clean))):
        return None
    return {
        "metric": metric,
        "search_scope": "global",
        "entity_override": "project",
        "scope_override": _has_project_scope_override(clean),
    }


def _has_project_comparison_override(text: str) -> bool:
    return _extract_project_comparison_request(text) is not None


def _project_metric_patterns(metric: str) -> tuple[str, ...]:
    if metric == "surface_total_m2":
        return (
            *SURFACE_QUERY_PATTERNS,
            r"\bmetros?\b",
            r"\bm2\b",
            r"\bm²\b",
            r"\bsuperficie\b",
            r"\bconstruid\w*\b",
        )
    for metric_key, patterns in PROJECT_COMPARISON_METRIC_PATTERNS:
        if metric_key == metric:
            return tuple(patterns)
    return ()


def _mentions_project_metric(text: str, metric: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return any(re.search(pattern, clean) for pattern in _project_metric_patterns(metric))


def _extract_project_metric_followup_request(
    text: str,
    summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    summary_obj = summary if isinstance(summary, dict) else {}
    last_intent = str(summary_obj.get("last_intent") or "").strip().upper()
    last_search_scope = str(summary_obj.get("last_search_scope") or "").strip().lower()
    last_slots = summary_obj.get("last_result_slots") if isinstance(summary_obj.get("last_result_slots"), dict) else {}
    metric = str(last_slots.get("comparison_metric") or "").strip()
    clean = _normalize_text(text)
    if last_intent != "PROJECT_COMPARISON_BY_METRIC" or last_search_scope != "global" or not metric or not clean:
        return None
    if _extract_project_comparison_request(clean):
        return None
    if _match_project_alias(text)[0]:
        return None
    if not _mentions_project_metric(clean, metric):
        return None
    asks_breakdown = bool(re.search(r"\b(cantidad|detalle|desglose|cu[aá]nt[ao]s?|hay|listado)\b", clean))
    if not asks_breakdown:
        return None
    return {
        "metric": metric,
        "search_scope": "global",
        "comparison_mode": "breakdown",
        "entity_override": "project",
        "scope_override": True,
    }


def _extract_project_metric_value_request(
    text: str,
    *,
    selected_project_code: str | None,
    chosen_project_code: str | None,
) -> dict[str, Any] | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    if _extract_project_comparison_request(clean):
        return None
    if (
        _is_count_units_by_rooms_query(clean)
        or _is_list_units_by_rooms_query(clean)
        or _is_total_units_query(clean)
        or _is_unit_status_breakdown_query(clean)
        or _is_available_units_query(clean)
    ):
        return None
    target_project_code = str(chosen_project_code or selected_project_code or "").strip().upper()
    if not target_project_code:
        return None
    metric = _extract_project_comparison_metric(clean)
    if not metric or metric == "surface_total_m2":
        return None
    if not _mentions_project_metric(clean, metric):
        return None
    asks_metric_value = bool(re.search(r"\b(cantidad|detalle|desglose|cu[aá]nt[ao]s?|tiene|hay|quiero\s+saber)\b", clean))
    if not asks_metric_value and clean not in {"reservas", "reserva"}:
        return None
    return {
        "metric": metric,
        "project_code": target_project_code,
        "search_scope": "project",
    }


def _is_project_surface_comparison_query(text: str) -> bool:
    request = _extract_project_comparison_request(text)
    return bool(request and str(request.get("metric") or "").strip() == "surface_total_m2")


def _extract_feature_key(text: str) -> str | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    for feature_key, aliases in UNIT_FEATURE_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_text(alias)
            if normalized_alias and normalized_alias in clean:
                return feature_key
    return None


def _feature_label(feature_key: str) -> str:
    labels = {
        "balcon": "balcón",
        "cochera": "cochera",
        "jardin": "jardín",
        "parrilla": "parrilla",
        "patio": "patio",
        "baulera": "baulera",
        "en_suite": "en suite",
        "walk_in_closet": "walk-in closet",
        "mascotas": "mascotas",
        "lavadero": "lavadero",
        "jacuzzi": "jacuzzi",
        "pileta": "pileta",
        "terraza": "terraza",
        "toilette": "toilette",
    }
    return labels.get(feature_key, feature_key.replace("_", " "))


def _feature_fields_used(feature_key: str) -> list[str]:
    mapping = {
        "balcon": ["demo_unit_profile.balcony_protection", "demo_units.features_jsonb"],
        "cochera": ["demo_unit_profile.has_garage"],
        "jardin": ["demo_unit_profile.has_garden"],
        "patio": ["demo_unit_profile.has_patio"],
        "baulera": ["demo_unit_profile.has_storage"],
        "mascotas": ["demo_unit_profile.pets_allowed", "demo_unit_profile.recommended_profiles_jsonb"],
        "jacuzzi": ["demo_units.features_jsonb"],
        "pileta": ["demo_units.features_jsonb"],
        "terraza": ["demo_units.features_jsonb"],
        "toilette": ["demo_units.features_jsonb"],
        "en_suite": ["demo_units.features_jsonb"],
    }
    return mapping.get(feature_key, ["demo_units.features_jsonb"])


def _has_global_scope_override(text: str) -> bool:
    return _matches_any_pattern(text, GLOBAL_SEARCH_SIGNALS)


def _is_global_feature_search_signal(text: str) -> bool:
    return _has_global_scope_override(text)


def _extract_surface_filter(text: str) -> dict[str, Any] | None:
    clean = _normalize_text(text).replace("m²", "m2")
    if not clean:
        return None
    patterns = (
        r"\b(?:mas\s+grandes?\s+que|mas\s+de|mayores?\s+a|superiores?\s+a|arriba\s+de)\s*(\d+(?:[.,]\d+)?)\s*(?:m2|mts?|metros?(?:\s+cuadrados?)?)?\b",
        r"\bde\s+mas\s+de\s*(\d+(?:[.,]\d+)?)\s*(?:m2|mts?|metros?(?:\s+cuadrados?)?)?\b",
    )
    has_surface_context = bool(
        re.search(r"\b(m2|mts?|metros?(?:\s+cuadrados?)?|superficie|grandes?|grande)\b", clean)
    )
    if not has_surface_context:
        return None
    for pattern in patterns:
        match = re.search(pattern, clean)
        if not match:
            continue
        try:
            value = float(str(match.group(1)).replace(",", "."))
        except Exception:  # noqa: BLE001
            continue
        return {
            "field": "surface_total_m2",
            "operator": ">",
            "value": value,
        }
    return None


def _is_global_unit_filter_followup(
    *,
    summary: dict[str, Any] | None,
    text: str,
    feature_key: str | None,
    surface_filter: dict[str, Any] | None,
) -> bool:
    summary_obj = summary if isinstance(summary, dict) else {}
    if str(summary_obj.get("last_search_scope") or "").strip().lower() != "global":
        return False
    last_intent = str(summary_obj.get("last_intent") or "").strip().upper()
    if last_intent not in {"GLOBAL_UNIT_FILTER_SEARCH", "GLOBAL_UNIT_SEARCH_BY_FEATURE"}:
        return False
    if feature_key:
        return True
    if surface_filter:
        return True
    clean = _normalize_text(text)
    return bool(re.search(r"\b(departamentos?|unidades?|los\s+que|las\s+que)\b", clean) and _is_surface_query(text))


def _extract_candidate_unit_code(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    match = re.search(r"\bunidad\s+([A-Za-z0-9-]+)\b", raw, re.IGNORECASE)
    if match:
        return str(match.group(1)).strip().upper()
    match = re.search(r"\b(?:la|el|depto|departamento|dto)\s+([0-9]+[A-Za-z](?:-[A-Za-z0-9]+)?)\b", raw, re.IGNORECASE)
    if match:
        return str(match.group(1)).strip().upper()
    return None


def _last_unit_subject(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary_obj = summary if isinstance(summary, dict) else {}
    if str(summary_obj.get("last_subject_type") or "").strip().lower() != "unit":
        return {}
    unit_code = str(summary_obj.get("last_subject_unit_code") or "").strip().upper()
    if not unit_code:
        return {}
    return {
        "unit_code": unit_code,
        "unit_id": str(summary_obj.get("last_subject_unit_id") or "").strip(),
        "project_code": str(summary_obj.get("last_subject_project_code") or "").strip().upper(),
        "project_name": str(summary_obj.get("last_subject_project_name") or "").strip(),
        "summary": str(summary_obj.get("last_subject_summary") or "").strip(),
    }


def _is_unit_reference_followup(text: str, summary: dict[str, Any] | None) -> bool:
    if not _last_unit_subject(summary):
        return False
    if _has_project_comparison_override(text):
        return False
    if _extract_candidate_unit_code(text):
        return False
    if _is_count_units_by_rooms_query(text) or _is_list_units_by_rooms_query(text):
        return False
    if _is_active_set_feature_followup(text, summary, _extract_feature_key(text)):
        return False
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(
        r"\b((que|qué)\s+precio\s+tiene|cu[aá]nto\s+vale|esa?\s+cu[aá]nto\s+vale|est[aá]\s+disponible|sigue\s+disponible|cu[aá]ntos?\s+ambientes?\s+tiene)\b",
        clean,
    ):
        return True
    if re.search(r"\b(y\s+)?los\s+metros\b", clean):
        return True
    if re.search(r"\btiene\s+(balcon|jardin|patio|cochera|baulera|parrilla|lavadero)\b", clean):
        return True
    if len(clean.split()) <= 5 and re.search(
        r"\b(precio|vale|metros?|m2|m²|disponible|ambientes?|balcon|jardin|patio|cochera|baulera)\b",
        clean,
    ):
        return True
    return False


def _is_unit_rooms_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(re.search(r"\bcu[aá]ntos?\s+ambientes?\s+tiene\b", clean))


def _last_result_units(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    summary_obj = summary if isinstance(summary, dict) else {}
    rows = summary_obj.get("last_result_units")
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(dict(row))
    return normalized


def _extract_result_set_sort_request(text: str) -> dict[str, Any] | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    field = ""
    label = ""
    default_direction = "asc"
    if re.search(r"\b(precio|valor)\b", clean):
        field = "price"
        label = "precio"
        default_direction = "asc"
    elif re.search(r"\b(metros?|m2|m²|mt|mts?|tamano|tamaño)\b", clean):
        field = "surface_total_m2"
        label = "metros"
        default_direction = "desc"
    elif re.search(r"\bambientes?\b", clean):
        field = "rooms_count"
        label = "ambientes"
        default_direction = "asc"
    if not field and re.search(r"\bde\s+menor\s+a\s+mayor\b", clean):
        field = "surface_total_m2"
        label = "metros"
        default_direction = "asc"
    if not field and re.search(r"\bde\s+mayor\s+a\s+menor\b", clean):
        field = "surface_total_m2"
        label = "metros"
        default_direction = "desc"
    if not field:
        return None
    if not (
        re.fullmatch(r"(y\s+)?por\s+[a-z0-9²\s]+", clean)
        or re.search(r"\bordena(?:lo|los|las)?\s+por\b", clean)
        or re.search(r"\bde\s+menor\s+a\s+mayor\b", clean)
        or re.search(r"\bde\s+mayor\s+a\s+menor\b", clean)
        or re.search(r"\b(?:ascendiente|ascendente|descendiente|descendente)\b", clean)
        or re.search(r"\ben\s+forma\s+(?:ascendiente|ascendente|descendiente|descendente)\b", clean)
    ):
        return None
    direction = default_direction
    if re.search(r"\bde\s+menor\s+a\s+mayor\b", clean):
        direction = "asc"
    elif re.search(r"\bde\s+mayor\s+a\s+menor\b", clean):
        direction = "desc"
    elif re.search(r"\b(?:ascendiente|ascendente)\b", clean):
        direction = "asc"
    elif re.search(r"\b(?:descendiente|descendente)\b", clean):
        direction = "desc"
    return {"field": field, "direction": direction, "label": label}


def _extract_result_set_extreme_request(text: str) -> dict[str, Any] | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    mapping: tuple[tuple[str, str, str, str], ...] = (
        (r"\bmas\s+grande\b", "surface_total_m2", "max", "más grande"),
        (r"\bmas\s+chic[ao]\b", "surface_total_m2", "min", "más chica"),
        (r"\bmas\s+barat[ao]\b", "price", "min", "más barata"),
        (r"\bmas\s+car[ao]\b", "price", "max", "más cara"),
    )
    for pattern, field, mode, label in mapping:
        if re.search(pattern, clean):
            return {"field": field, "mode": mode, "label": label}
    return None


def _parse_small_cardinal(token: str) -> int | None:
    compact = _normalize_text(token)
    if not compact:
        return None
    if compact.isdigit():
        return int(compact)
    word_map = {
        "un": 1,
        "uno": 1,
        "una": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
    }
    return word_map.get(compact)


def _extract_result_set_ranking_request(text: str) -> dict[str, Any] | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    if re.search(r"\bcual(?:es)?\s+es\b", clean):
        return None
    if _extract_surface_filter(text):
        return None

    field = ""
    direction = ""
    label = ""
    if re.search(r"\bmas\s+grandes?\b", clean) or re.search(r"\bmayores?\b", clean):
        field = "surface_total_m2"
        direction = "desc"
        label = "más grandes por m²"
    elif re.search(r"\bmas\s+chic[ao]s?\b", clean) or re.search(r"\bmenores?\b", clean):
        field = "surface_total_m2"
        direction = "asc"
        label = "más chicas por m²"
    elif re.search(r"\bmas\s+barat[ao]s?\b", clean):
        field = "price"
        direction = "asc"
        label = "más baratas"
    elif re.search(r"\bmas\s+car[ao]s?\b", clean):
        field = "price"
        direction = "desc"
        label = "más caras"

    if re.search(r"\b(precio|valor)\b", clean):
        field = field or "price"
        label = "por precio"
        direction = direction or "asc"
    elif re.search(r"\b(metros?|m2|m²|mt|mts?|tamano|tamaño|superficie)\b", clean):
        field = field or "surface_total_m2"
        label = label or "por m²"
        direction = direction or "desc"
    elif re.search(r"\bambientes?\b", clean):
        field = field or "rooms_count"
        label = label or "por ambientes"
        direction = direction or "desc"

    if re.search(r"\bde\s+menor\s+a\s+mayor\b", clean) or re.search(r"\b(?:ascendiente|ascendente)\b", clean):
        direction = "asc"
    elif re.search(r"\bde\s+mayor\s+a\s+menor\b", clean) or re.search(r"\b(?:descendiente|descendente)\b", clean):
        direction = "desc"

    limit: int | None = None
    for pattern in (
        r"\btop\s+(\d+|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
        r"\blos\s+primeros?\s+(\d+|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
        r"\blos\s+(\d+|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+(?:mas|m[aá]s)\b",
        r"\b(?:dame|pasame|mostrame|me\s+das)\s+los\s+(\d+|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
    ):
        match = re.search(pattern, clean)
        if match:
            limit = _parse_small_cardinal(match.group(1))
            break

    has_ranking_signal = bool(
        limit
        or re.search(r"\btop\b", clean)
        or re.search(r"\bprimeros?\b", clean)
        or re.search(r"\bordena(?:lo|los|las)?\b", clean)
        or re.search(r"\bordenad[oa]s?\b", clean)
        or re.search(r"\ben\s+forma\s+(?:ascendiente|ascendente|descendiente|descendente)\b", clean)
        or re.search(r"\bmas\s+grandes?\b", clean)
        or re.search(r"\bmas\s+barat[ao]s?\b", clean)
        or re.search(r"\bmas\s+car[ao]s?\b", clean)
        or re.search(r"\bmayores?\s+por\b", clean)
        or re.search(r"\bde\s+menor\s+a\s+mayor\b", clean)
        or re.search(r"\bde\s+mayor\s+a\s+menor\b", clean)
    )
    if not has_ranking_signal or not field:
        return None
    return {
        "field": field,
        "direction": direction or "desc",
        "label": label or "ordenadas",
        "limit": limit,
    }


def _result_set_sort_value(unit_row: dict[str, Any], field: str) -> float | str:
    if field == "price":
        return float(_to_float(unit_row.get("list_price")) or -1.0)
    if field == "surface_total_m2":
        return float(_to_float(unit_row.get("surface_total_m2")) or -1.0)
    if field == "rooms_count":
        return float(_to_float(unit_row.get("rooms_count")) or -1.0)
    return str(unit_row.get(field) or "")


def _sort_units_result_set(
    rows: list[dict[str, Any]],
    *,
    field: str,
    direction: str,
) -> list[dict[str, Any]]:
    reverse = str(direction or "").strip().lower() == "desc"
    valued_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for row in rows:
        value = _result_set_sort_value(row, field)
        if isinstance(value, float) and value < 0:
            missing_rows.append(row)
            continue
        valued_rows.append(row)
    if field in {"price", "surface_total_m2", "rooms_count"}:
        ranked = sorted(
            valued_rows,
            key=lambda row: (
                -float(_result_set_sort_value(row, field)) if reverse else float(_result_set_sort_value(row, field)),
                str(row.get("unit_code") or ""),
            ),
        )
    else:
        ranked = sorted(
            valued_rows,
            key=lambda row: (
                _result_set_sort_value(row, field),
                str(row.get("unit_code") or ""),
            ),
            reverse=reverse,
        )
    return [*ranked, *missing_rows]


def _rank_units_result_set(
    rows: list[dict[str, Any]],
    *,
    field: str,
    direction: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    ordered = _sort_units_result_set(rows, field=field, direction=direction)
    if limit is not None and limit >= 0:
        return ordered[:limit]
    return ordered


def _select_extreme_from_result_set(
    rows: list[dict[str, Any]],
    *,
    field: str,
    mode: str,
) -> dict[str, Any] | None:
    if not rows:
        return None
    ordered = _sort_units_result_set(rows, field=field, direction="desc" if mode == "max" else "asc")
    return ordered[0] if ordered else None


def _result_set_entry(unit_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_code": str(unit_row.get("project_code") or "").strip().upper(),
        "project_name": str(unit_row.get("project_name") or "").strip(),
        "unit_id": str(unit_row.get("unit_id") or "").strip(),
        "unit_code": str(unit_row.get("unit_code") or unit_row.get("unit_id") or "").strip().upper(),
        "surface_total_m2": _to_float(unit_row.get("surface_total_m2")),
        "list_price": _to_float(unit_row.get("list_price")),
        "currency": str(unit_row.get("currency") or "").strip().upper() or "USD",
        "availability_status": str(unit_row.get("availability_status") or "").strip(),
        "rooms_label": str(unit_row.get("rooms_label") or unit_row.get("typology") or "").strip(),
        "rooms_count": _to_float(unit_row.get("rooms_count")),
        "features_jsonb": list(_as_list(unit_row.get("features_jsonb"))),
        "commercial_features_jsonb": dict(unit_row.get("commercial_features_jsonb") or {})
        if isinstance(unit_row.get("commercial_features_jsonb"), dict)
        else {},
        "has_garage": unit_row.get("has_garage"),
        "has_storage": unit_row.get("has_storage"),
        "has_patio": unit_row.get("has_patio"),
        "has_garden": unit_row.get("has_garden"),
        "pets_allowed": unit_row.get("pets_allowed"),
        "balcony_protection": unit_row.get("balcony_protection"),
    }


def _result_set_summary_patch(
    rows: list[dict[str, Any]],
    *,
    origin_intent: str,
) -> dict[str, Any]:
    normalized_rows = [_result_set_entry(row) for row in rows]
    project_codes = {
        str(row.get("project_code") or "").strip().upper()
        for row in normalized_rows
        if str(row.get("project_code") or "").strip()
    }
    project_names = {
        str(row.get("project_name") or "").strip()
        for row in normalized_rows
        if str(row.get("project_name") or "").strip()
    }
    examples = [_format_unit_example(row, include_project=len(project_codes) > 1) for row in rows[:3]]
    examples = [item for item in examples if item]
    return {
        "last_subject_type": "unit_list",
        "last_result_units": normalized_rows[:12],
        "last_result_project_code": next(iter(project_codes), None) if len(project_codes) == 1 else None,
        "last_result_project_name": next(iter(project_names), None) if len(project_names) == 1 else None,
        "last_result_sortable_fields": ["price", "surface_total_m2", "rooms_count"],
        "last_result_origin_intent": origin_intent,
        "last_result_summary": _normalize_snippet("; ".join(examples), limit=260),
        "last_subject_unit_id": None,
        "last_subject_unit_code": None,
        "last_subject_project_code": None,
        "last_subject_project_name": None,
        "last_subject_summary": None,
    }


def _clear_unit_result_context_patch(*, last_subject_type: str = "project_comparison") -> dict[str, Any]:
    return {
        "last_subject_type": last_subject_type,
        "last_result_units": [],
        "last_result_project_code": None,
        "last_result_project_name": None,
        "last_result_sortable_fields": [],
        "last_result_origin_intent": None,
        "last_result_summary": None,
        "last_subject_unit_id": None,
        "last_subject_unit_code": None,
        "last_subject_project_code": None,
        "last_subject_project_name": None,
        "last_subject_summary": None,
        "active_filter": None,
    }


def _format_result_set_reply(rows: list[dict[str, Any]], *, lead_text: str) -> str:
    include_project = len(
        {
            str(row.get("project_code") or "").strip().upper()
            for row in rows
            if str(row.get("project_code") or "").strip()
        }
    ) > 1
    lines = [f"- {_format_unit_example(row, include_project=include_project)}" for row in rows[:6]]
    return lead_text + "\n" + "\n".join(line for line in lines if line)


def _format_ranked_result_set_reply(
    rows: list[dict[str, Any]],
    *,
    ranking: dict[str, Any],
    active_filter_summary: str = "",
) -> str:
    include_project = len(
        {
            str(row.get("project_code") or "").strip().upper()
            for row in rows
            if str(row.get("project_code") or "").strip()
        }
    ) > 1
    field = str(ranking.get("field") or "").strip()
    limit = ranking.get("limit")
    label = str(ranking.get("label") or "ordenadas").strip()
    if limit:
        limit_text = f"las {min(int(limit), len(rows))} {label}"
    else:
        limit_text = f"las unidades {label}"
    if active_filter_summary:
        lead_text = f"Sí. Tomando {active_filter_summary} que tengo cargadas hoy, {limit_text} son:"
    elif field == "price":
        lead_text = f"Sí. Tomando el grupo activo, {limit_text} son:"
    else:
        lead_text = f"Sí. Tomando el grupo activo, {limit_text} son:"

    lines: list[str] = []
    for index, row in enumerate(rows[:10], start=1):
        parts = [str(row.get("unit_code") or row.get("unit_id") or "").strip().upper()]
        if include_project:
            project_name = str(row.get("project_name") or row.get("project_code") or "").strip()
            if project_name:
                parts.append(project_name)
        surface = _format_surface(row.get("surface_total_m2"))
        if surface:
            parts.append(f"{surface} m²")
        price_value = _to_float(row.get("list_price"))
        currency = str(row.get("currency") or "").strip().upper() or "USD"
        if price_value is not None:
            parts.append(f"{currency} {_format_price(price_value)}")
        lines.append(f"{index}. " + " - ".join(part for part in parts if part))
    return lead_text + "\n" + "\n".join(lines)


def _result_set_feature_reply(
    rows: list[dict[str, Any]],
    *,
    feature_key: str,
) -> str:
    if not rows:
        return f"Dentro de ese grupo no veo unidades con {_feature_label(feature_key)}."
    return _format_result_set_reply(
        rows,
        lead_text=f"De las unidades que veníamos viendo, hoy figura con {_feature_label(feature_key)}:",
    )


def _result_set_feature_extreme_reply(
    unit_row: dict[str, Any],
    *,
    feature_key: str,
    label: str,
    field: str,
) -> str:
    unit_code = str(unit_row.get("unit_code") or unit_row.get("unit_id") or "").strip().upper()
    project_name = str(unit_row.get("project_name") or unit_row.get("project_code") or "").strip()
    if field == "price":
        price_value = _to_float(unit_row.get("list_price"))
        currency = str(unit_row.get("currency") or "").strip().upper() or "USD"
        if price_value is not None:
            return (
                f"La unidad {label} con {_feature_label(feature_key)} que tengo cargada hoy es {unit_code} "
                f"en {project_name}, publicada en {currency} {_format_price(price_value)}."
            )
        return f"La unidad {label} con {_feature_label(feature_key)} que tengo cargada hoy es {unit_code} en {project_name}."
    surface_value = _format_surface(unit_row.get("surface_total_m2"))
    price_value = _to_float(unit_row.get("list_price"))
    currency = str(unit_row.get("currency") or "").strip().upper() or "USD"
    answer = f"La unidad {label} con {_feature_label(feature_key)} que tengo cargada hoy es {unit_code} en {project_name}"
    if surface_value:
        answer += f", con {surface_value} m² totales"
    if price_value is not None:
        answer += f" y {currency} {_format_price(price_value)}"
    return answer + "."


def _apply_feature_to_active_filter(active_filter: dict[str, Any], feature_key: str) -> dict[str, Any]:
    clean_feature = str(feature_key or "").strip().lower()
    normalized = {
        "type": str(active_filter.get("type") or "").strip().lower(),
        "payload": dict(active_filter.get("payload") or {}),
        "scope": str(active_filter.get("scope") or "").strip().lower(),
        "origin_intent": str(active_filter.get("origin_intent") or "").strip().upper(),
        "project_code": str(active_filter.get("project_code") or "").strip().upper(),
        "project_name": str(active_filter.get("project_name") or "").strip(),
    }
    payload = _normalize_active_filter_payload(normalized["type"], normalized["payload"])
    facets = [str(item or "").strip().lower() for item in (payload.get("facets_applied") or []) if str(item or "").strip()]
    if normalized["type"] == "feature":
        base_feature = str(payload.get("feature_key") or "").strip().lower()
        if clean_feature and clean_feature != base_feature and clean_feature not in facets:
            facets.append(clean_feature)
    elif clean_feature and clean_feature not in facets:
        facets.append(clean_feature)
    if facets:
        payload["facets_applied"] = _dedupe_texts(facets, limit=8)
    normalized["payload"] = payload
    return normalized


def _looks_like_unit_feature_query(text: str, feature_key: str | None) -> bool:
    clean = _normalize_text(text)
    if not clean or not feature_key:
        return False
    return bool(
        re.search(r"\b(unidad(?:es)?|depto(?:s)?|departamento(?:s)?|tiene[n]?|hay|con|lista|listas|mostra|mostrame|que\s+hay)\b", clean)
    )


def _active_context_units(conn: Any, summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = _last_result_units(summary)
    if rows:
        return rows
    active_filter = _last_active_filter(summary)
    if not active_filter.get("type"):
        return []
    return getattr(repo, "list_units_matching_active_filter")(
        conn,
        filter_type=active_filter.get("type") or "",
        filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
        scope=active_filter.get("scope") or "global",
        project_code=active_filter.get("project_code") or None,
        limit=None,
    ) or []


def _is_active_set_feature_followup(text: str, summary: dict[str, Any] | None, feature_key: str | None) -> bool:
    clean = _normalize_text(text)
    if not clean or not feature_key:
        return False
    if _has_project_comparison_override(clean):
        return False
    if _extract_candidate_unit_code(text):
        return False
    has_active_context = bool(_last_result_units(summary) or _last_active_filter(summary).get("type"))
    if not has_active_context:
        return False
    if re.search(r"\b(de\s+estos?|de\s+esos?|de\s+estas?|de\s+esas?)\b", clean):
        return True
    if re.search(r"\by\s+con\b", clean):
        return True
    if re.fullmatch(r"(y\s+)?con\s+[a-z0-9\s]+", clean):
        return True
    if _extract_result_set_extreme_request(text) and re.search(r"\bcon\b", clean):
        return True
    if re.search(r"\b(cuales?|cu[aá]l|dame|mostra(?:me|r)?|lista(?:me|r)?)\b", clean) and re.search(r"\bcon\b", clean):
        return True
    return False


def _feature_data_available_for_result_set(rows: list[dict[str, Any]], feature_key: str) -> bool:
    structured_flags = {
        "cochera": "has_garage",
        "baulera": "has_storage",
        "patio": "has_patio",
        "jardin": "has_garden",
        "mascotas": "pets_allowed",
    }
    flag = structured_flags.get(feature_key)
    for row in rows:
        if flag and row.get(flag) is not None:
            return True
        if feature_key == "balcon" and row.get("balcony_protection") is not None:
            return True
        if _as_list(row.get("features_jsonb")):
            return True
        if isinstance(row.get("commercial_features_jsonb"), dict) and row.get("commercial_features_jsonb"):
            return True
    return False


def _feature_query_prefers_selected_project(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(r"\b(este\s+proyecto|en\s+este|aca|aqui|ahi|del\s+proyecto)\b", clean):
        return True
    if re.search(r"\b(hay|tiene)\b", clean) and not re.search(r"\b(que\s+unidades?|lista\w*|mostra\w*)\b", clean):
        return True
    if re.search(r"\b(tenes?\s+algo|hay\s+algo)\b", clean):
        return True
    return False


def _is_children_suitability_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(r"\b(apto|sirve|ideal|recomend|mejor|familiar)\b", clean) and re.search(
        r"\b(ninos?|ninas?|chicos?|familia(?:s)?|familiar)\b",
        clean,
    ):
        return True
    return bool(
        re.search(
            r"\b(es\s+apto\s+para\s+ninos?|sirve\s+para\s+familia(?:s)?\s+con\s+chicos?|hay\s+algo\s+para\s+ninos?|tenes\s+algo\s+familiar|cual\s+es\s+mas\s+comod[oa]\s+para\s+chicos?)\b",
            clean,
        )
    )


def _is_pets_suitability_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(r"\b(mascotas?|perros?|gatos?|pet\s*friendly|pets?)\b", clean) and re.search(
        r"\b(acept\w*|permit\w*|sirve|apto|ideal|recomend\w*|mejor|hay|tenes?)\b",
        clean,
    ):
        return True
    return bool(
        re.search(
            r"\b(aceptan\s+mascotas?|sirve\s+para\s+mascotas?|algo\s+mejor\s+para\s+mascotas?|cual\s+me\s+recomendas?\s+para\s+mascotas?)\b",
            clean,
        )
    )


def _asks_balcony_protection(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(re.search(r"\bbalcon\b", clean) and re.search(r"\b(proteg\w*|segur\w*|baranda\w*)\b", clean))


def _is_warning_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if _asks_balcony_protection(clean):
        return True
    return bool(
        re.search(
            r"\b(hay\s+alguna\s+contra|algo\s+a\s+tener\s+en\s+cuenta|alguna\s+restriccion|algun\s+warning|es\s+seguro\s+para\s+chicos)\b",
            clean,
        )
    )


def _is_light_orientation_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    return bool(
        re.search(
            r"\b(luz|luminos[oa]|orientacion|sol|manana|tarde|ventilacion|exposicion|habitabilidad|como\s+da)\b",
            clean,
        )
    )


def _clarification_context_active(
    summary: dict[str, Any] | None,
    recent_messages: list[dict[str, Any]] | None,
) -> bool:
    summary_obj = summary if isinstance(summary, dict) else {}
    last_intent = str(summary_obj.get("last_intent") or "").strip().upper()
    last_answer = _normalize_text(str(summary_obj.get("last_answer_brief") or ""))
    if last_intent == "CLARIFY" and "visita al proyecto" in last_answer and "asesor" in last_answer:
        return True

    for row in reversed((recent_messages or [])[-5:]):
        if str(row.get("direction") or "").strip().lower() != "out":
            continue
        text = _normalize_text(str(row.get("text") or ""))
        if "visita al proyecto" in text and "asesor" in text:
            return True
    return False


def _project_exclusions_for_list(
    text: str,
    *,
    selected_project_code: str | None,
) -> list[str]:
    clean = _normalize_text(text)
    exclusions: list[str] = []
    alias_code, _matched_alias = _match_project_alias(text)
    if alias_code and re.search(r"\bno\b", clean):
        exclusions.append(alias_code)
    if selected_project_code and (
        re.search(r"\botr[oa]s?\b", clean) or re.search(r"\bno\b", clean)
    ):
        exclusions.append(str(selected_project_code).strip().upper())
    return _dedupe_texts(exclusions, limit=4)


def _semantic_intent_resolver(
    text: str,
    *,
    detail: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean = _normalize_text(text)
    summary_obj = summary if isinstance(summary, dict) else {}
    selected_project = _ticket_selected_project(detail)
    selected_project_code = str(selected_project.get("code") or "").strip().upper()
    chosen_project_code, matched_alias = _match_project_alias(text)
    clarification_active = _clarification_context_active(summary_obj, recent_messages)
    pending_offer_type = str(summary_obj.get("pending_offer_type") or "").strip().upper()
    pending_question_type = str(summary_obj.get("pending_question_type") or "").strip().upper()
    project_comparison_request = _extract_project_comparison_request(text) or {}
    project_metric_followup_request = _extract_project_metric_followup_request(text, summary_obj) or {}
    project_metric_value_request = _extract_project_metric_value_request(
        text,
        selected_project_code=selected_project_code,
        chosen_project_code=chosen_project_code,
    ) or {}
    feature_key = _extract_feature_key(text)
    project_comparison_override = bool(project_comparison_request or project_metric_followup_request)
    candidate_unit_code = _extract_candidate_unit_code(text)
    last_unit_subject = _last_unit_subject(summary_obj)
    if not candidate_unit_code and not project_comparison_override and _is_unit_reference_followup(text, summary_obj):
        candidate_unit_code = str(last_unit_subject.get("unit_code") or "").strip().upper() or None
    last_result_units = _last_result_units(summary_obj)
    surface_filter = _extract_surface_filter(text)
    active_filter = _last_active_filter(summary_obj)
    has_active_result_context = bool(last_result_units or active_filter.get("type")) and not project_comparison_override
    result_set_ranking = _extract_result_set_ranking_request(text) if has_active_result_context else None
    result_set_extreme = _extract_result_set_extreme_request(text) if has_active_result_context else None
    result_set_sort = _extract_result_set_sort_request(text) if has_active_result_context and not result_set_extreme and not result_set_ranking else None
    explicit_global_scope = _has_global_scope_override(text)
    inherited_global_scope = _is_global_unit_filter_followup(
        summary=summary_obj,
        text=text,
        feature_key=feature_key,
        surface_filter=surface_filter,
    )
    effective_global_scope = bool(explicit_global_scope or inherited_global_scope)
    global_feature_search = bool(_is_global_feature_search_signal(text) or inherited_global_scope)
    feature_query_like = _looks_like_unit_feature_query(text, feature_key)
    time_preference = _extract_time_preference(text) if pending_question_type == "TIME_PREFERENCE" else None
    last_rooms_query = _last_rooms_query(summary_obj)
    rooms_count_query = _is_count_units_by_rooms_query(text)
    rooms_list_query = _is_list_units_by_rooms_query(text)

    if time_preference:
        return {
            "intent": "TIME_PREFERENCE",
            "confidence": 0.98,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "pending_time_preference",
            "time_preference": time_preference,
        }

    if _is_affirm_message(text):
        if _normalize_short_social_text(text) in {"si", "sí"} and not pending_offer_type and not pending_question_type:
            return {
                "intent": "AFFIRM",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": False,
                "reason": "affirm_without_pending_offer",
                "resolution_source": "social",
            }
        if pending_offer_type or pending_question_type:
            return {
                "intent": "AFFIRM",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": bool(pending_offer_type or pending_question_type),
                "reason": "affirm_with_pending_offer" if pending_offer_type else "affirm_with_pending_question",
                "resolution_source": "social",
            }
        return {
            "intent": "ACKNOWLEDGEMENT",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "social_ack_from_affirm",
            "resolution_source": "social",
        }

    if not chosen_project_code and _is_greeting_message(text):
        return {
            "intent": "GREETING",
            "confidence": 0.98,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "social_greeting",
            "resolution_source": "social",
        }

    if _is_acknowledgement_message(text):
        return {
            "intent": "ACKNOWLEDGEMENT",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "social_ack",
            "resolution_source": "social",
        }

    if _is_global_scope_ack_message(text, summary_obj):
        return {
            "intent": "ACKNOWLEDGEMENT",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "global_scope_ack",
            "resolution_source": "social",
            "search_scope": "global",
        }

    if project_comparison_request:
        comparison_metric = str(project_comparison_request.get("metric") or "").strip()
        if comparison_metric == "surface_total_m2":
            return {
                "intent": "PROJECT_COMPARISON_BY_SURFACE",
                "confidence": 0.98,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": False,
                "reason": "semantic_project_comparison_by_surface",
                "resolution_source": "semantic",
                "search_scope": "global",
                "entity_override": "project",
                "scope_override": bool(project_comparison_request.get("scope_override")),
            }
        return {
            "intent": "PROJECT_COMPARISON_BY_METRIC",
            "confidence": 0.98,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_project_comparison_by_metric",
            "resolution_source": "semantic",
            "search_scope": "global",
            "entity_override": str(project_comparison_request.get("entity_override") or "project"),
            "scope_override": bool(project_comparison_request.get("scope_override")),
            "comparison_metric": comparison_metric,
        }

    if project_metric_followup_request:
        return {
            "intent": "PROJECT_COMPARISON_BY_METRIC",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_project_metric_followup",
            "resolution_source": "semantic",
            "search_scope": "global",
            "entity_override": str(project_metric_followup_request.get("entity_override") or "project"),
            "scope_override": bool(project_metric_followup_request.get("scope_override")),
            "comparison_metric": str(project_metric_followup_request.get("metric") or "").strip(),
            "comparison_mode": str(project_metric_followup_request.get("comparison_mode") or "breakdown").strip(),
        }

    if project_metric_value_request:
        return {
            "intent": "PROJECT_METRIC_VALUE",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": str(project_metric_value_request.get("project_code") or "").strip().upper(),
            "excluded_project_codes": [],
            "followup": bool(selected_project_code and not chosen_project_code),
            "reason": "semantic_project_metric_value",
            "resolution_source": "semantic",
            "search_scope": "project",
            "comparison_metric": str(project_metric_value_request.get("metric") or "").strip(),
            "unit_code": None,
        }

    if _is_global_scope_override_followup(text, summary_obj):
        active_filter_type = str(active_filter.get("type") or "").strip().lower()
        active_payload = active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {}
        if not active_filter_type and last_rooms_query.get("rooms_count") is not None:
            active_filter_type = "rooms"
            active_payload = {"rooms_count": last_rooms_query.get("rooms_count")}
        if active_filter_type == "rooms":
            return {
                "intent": "GLOBAL_SCOPE_OVERRIDE",
                "confidence": 0.97,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "semantic_global_scope_override_rooms_followup",
                "resolution_source": "semantic",
                "search_scope": "global",
                "rooms_count": active_payload.get("rooms_count") or last_rooms_query.get("rooms_count"),
                "rooms_query_intent": last_rooms_query.get("intent") or active_filter.get("origin_intent"),
            }
        if active_filter_type == "feature":
            return {
                "intent": "GLOBAL_UNIT_SEARCH_BY_FEATURE",
                "confidence": 0.97,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "semantic_global_scope_override_feature_filter",
                "resolution_source": "semantic",
                "search_scope": "global",
                "feature_key": active_payload.get("feature_key"),
            }
        if active_filter_type == "surface":
            surface_payload: dict[str, Any] = {}
            if active_payload.get("min_surface_total_m2") is not None:
                surface_payload = {
                    "field": "surface_total_m2",
                    "operator": ">",
                    "value": active_payload.get("min_surface_total_m2"),
                }
            return {
                "intent": "GLOBAL_UNIT_FILTER_SEARCH",
                "confidence": 0.97,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "semantic_global_scope_override_surface_filter",
                "resolution_source": "semantic",
                "search_scope": "global",
                "surface_filter": surface_payload,
            }

    if _is_projects_matching_active_filter_question(text, summary_obj):
        return {
            "intent": "LIST_PROJECTS_MATCHING_ACTIVE_FILTER",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_projects_matching_active_filter",
            "resolution_source": "semantic",
        }

    if _is_active_set_feature_followup(text, summary_obj, feature_key):
        if result_set_extreme:
            return {
                "intent": "ACTIVE_SET_FEATURE_EXTREME",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "semantic_active_set_feature_extreme",
                "resolution_source": "semantic",
                "feature_key": feature_key,
                "result_set_extreme": result_set_extreme,
            }
        return {
            "intent": "ACTIVE_SET_FILTER_BY_FEATURE",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_active_set_feature_filter",
            "resolution_source": "semantic",
            "feature_key": feature_key,
        }

    if result_set_ranking:
        return {
            "intent": "RESULT_SET_RANKING",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_result_set_ranking",
            "result_set_ranking": result_set_ranking,
        }

    if result_set_extreme:
        return {
            "intent": "RESULT_SET_EXTREME",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_result_set_extreme",
            "result_set_extreme": result_set_extreme,
        }

    if result_set_sort:
        return {
            "intent": "RESULT_SET_SORT",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": True,
            "reason": "semantic_result_set_sort",
            "result_set_sort": result_set_sort,
        }

    global_extreme_kind = _detect_global_price_extreme(text)
    if global_extreme_kind == "highest":
        return {
            "intent": "GLOBAL_PRICE_EXTREME",
            "confidence": 0.97,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_global_price_highest",
            "subtype": "highest",
        }

    if rooms_count_query:
        return {
            "intent": "COUNT_UNITS_BY_ROOMS",
            "confidence": 0.97,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None if effective_global_scope else (chosen_project_code or selected_project_code),
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_count_units_by_rooms",
            "resolution_source": "semantic",
            "search_scope": "global" if effective_global_scope else "project",
            "rooms_count": parse_ambientes(text),
            "unit_code": None,
        }

    if rooms_list_query:
        return {
            "intent": "LIST_UNITS_BY_ROOMS",
            "confidence": 0.97,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None if effective_global_scope else (chosen_project_code or selected_project_code),
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_list_units_by_rooms",
            "resolution_source": "semantic",
            "search_scope": "global" if effective_global_scope else "project",
            "rooms_count": parse_ambientes(text),
            "unit_code": None,
        }

    if _is_surface_query(text):
        if effective_global_scope:
            return {
                "intent": "GLOBAL_UNIT_FILTER_SEARCH",
                "confidence": 0.95,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": None,
                "excluded_project_codes": [],
                "followup": False,
                "reason": "semantic_global_unit_filter_search",
                "resolution_source": "semantic",
                "search_scope": "global",
                "surface_filter": surface_filter,
            }
        return {
            "intent": "SURFACE_QUERY",
            "confidence": 0.94,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_surface_filter_query" if _is_surface_filter_list_query(text, surface_filter) else "semantic_surface_query",
            "surface_filter": surface_filter,
            "unit_code": candidate_unit_code,
        }

    if candidate_unit_code and _is_unit_rooms_query(text):
        return {
            "intent": "UNIT_TYPES",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_unit_rooms_query",
            "unit_code": candidate_unit_code,
        }

    if (chosen_project_code or selected_project_code) and _is_out_of_scope_query(text):
        return {
            "intent": "GENERAL",
            "confidence": 0.93,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_out_of_scope_selected_project",
        }

    if _is_children_suitability_query(text):
        return {
            "intent": "CHILDREN_SUITABILITY",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_children_suitability",
            "unit_code": candidate_unit_code,
        }

    if _is_pets_suitability_query(text):
        return {
            "intent": "PETS_SUITABILITY",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_pets_suitability",
            "unit_code": candidate_unit_code,
        }

    if _is_warning_query(text):
        return {
            "intent": "SAFETY_WARNINGS",
            "confidence": 0.93,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_safety_warnings",
            "unit_code": candidate_unit_code,
        }

    if _is_light_orientation_query(text):
        return {
            "intent": "LIGHT_ORIENTATION",
            "confidence": 0.93,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_light_orientation",
            "unit_code": candidate_unit_code,
        }

    if feature_key and candidate_unit_code:
        return {
            "intent": "UNIT_DETAIL_FEATURE_CHECK",
            "confidence": 0.97,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_unit_feature_check",
            "feature_key": feature_key,
            "unit_code": candidate_unit_code,
        }

    if feature_key and not effective_global_scope and (
        chosen_project_code
        or (selected_project_code and not global_feature_search and _feature_query_prefers_selected_project(text))
    ):
        return {
            "intent": "PROJECT_UNIT_SEARCH_BY_FEATURE",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_project_unit_feature_search",
            "feature_key": feature_key,
            "unit_code": None,
        }

    if feature_key and (feature_query_like or global_feature_search):
        return {
            "intent": "GLOBAL_UNIT_SEARCH_BY_FEATURE",
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_global_unit_feature_search",
            "feature_key": feature_key,
            "unit_code": None,
        }

    if _is_list_projects_request(text):
        exclusions = _project_exclusions_for_list(
            text,
            selected_project_code=selected_project_code,
        )
        return {
            "intent": "LIST_PROJECTS",
            "confidence": 0.98,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": exclusions,
            "followup": False,
            "reason": "semantic_project_catalog",
        }

    if clarification_active:
        if _is_human_contact_request(text):
            return {
                "intent": "HUMAN_CONTACT_REQUEST",
                "confidence": 0.98,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": chosen_project_code,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "clarify_followup_human_contact",
            }
        if _is_ambiguous_meeting_request(text) or _is_visit_request_intent(text):
            return {
                "intent": "VISIT_REQUEST",
                "confidence": 0.94,
                "needs_clarification": False,
                "clarification_question": None,
                "chosen_project": chosen_project_code,
                "excluded_project_codes": [],
                "followup": True,
                "reason": "clarify_followup_visit_request",
            }

    if _is_human_contact_request(text):
        return {
            "intent": "HUMAN_CONTACT_REQUEST",
            "confidence": 0.97,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_human_contact",
        }

    if _is_ambiguous_meeting_request(text) and not _is_visit_request_intent(text):
        return {
            "intent": "CLARIFY",
            "confidence": 0.74,
            "needs_clarification": True,
            "clarification_question": (
                "Claro. ¿Querés coordinar una visita al proyecto o preferís que un asesor te contacte primero?"
            ),
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_meeting_ambiguous",
        }

    if _is_visit_request_intent(text):
        return {
            "intent": "VISIT_REQUEST",
            "confidence": 0.96,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "semantic_visit_request",
        }

    fuzzy_intent, fuzzy_score, fuzzy_alias = _fuzzy_basic_intent(
        text,
        selected_project_code=selected_project_code,
    )
    if fuzzy_intent:
        return {
            "intent": fuzzy_intent,
            "confidence": round(fuzzy_score, 3),
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code or selected_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": f"semantic_fuzzy_{str(fuzzy_intent).lower()}",
            "resolution_source": "semantic_fuzzy",
            "matched_alias": fuzzy_alias,
            "unit_code": candidate_unit_code,
        }

    fallback_intent, fallback_followup, fallback_reason = _detect_project_intent(
        text,
        summary=summary_obj,
    )
    if fallback_intent != "GENERAL":
        return {
            "intent": fallback_intent,
            "confidence": 0.9,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": fallback_followup,
            "reason": fallback_reason,
            "unit_code": candidate_unit_code,
        }

    if chosen_project_code:
        return {
            "intent": "PROJECT_SELECT",
            "confidence": 0.99,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": chosen_project_code,
            "excluded_project_codes": [],
            "followup": False,
            "reason": matched_alias or "project_alias",
        }

    if selected_project_code and (_is_project_overview_request(text) or _looks_like_project_question(text)):
        return {
            "intent": "PROJECT_OVERVIEW",
            "confidence": 0.78,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "overview_from_selected_project",
        }

    if not clean:
        return {
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "needs_clarification": False,
            "clarification_question": None,
            "chosen_project": None,
            "excluded_project_codes": [],
            "followup": False,
            "reason": "empty",
        }

    return {
        "intent": "UNKNOWN",
        "confidence": 0.35,
        "needs_clarification": False,
        "clarification_question": None,
        "chosen_project": None,
        "excluded_project_codes": [],
        "followup": False,
        "reason": "semantic_unknown",
    }


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
    return bool(
        re.search(r"\b(si|dale|ok|perfecto|confirmo|confirmado|de\s+acuerdo|genial|listo)\b", clean)
    )


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


def _build_vera_contact_clarification_reply() -> str:
    return "Claro. ¿Querés coordinar una visita al proyecto o preferís que un asesor te contacte primero?"


def _build_vera_visit_requested_reply() -> str:
    return (
        "Sí, claro 🙂. Ya lo dejo en 'Pendiente de visita' para que un asesor te proponga un horario por este chat. "
        "¿Preferís por la mañana o por la tarde?"
    )


def _build_vera_human_contact_reply() -> str:
    return "Claro. Le aviso a un asesor para que te contacte por este chat."


def _build_vera_affirm_reply() -> str:
    return "Perfecto. Decime qué querés revisar y seguimos."


def _build_vera_greeting_reply(conn: Any, project_name: str) -> str:
    if project_name:
        return f"Hola 🙂. Si querés, seguimos con {project_name}."
    labels = _dedupe_texts([row.get("name") or row.get("code") for row in repo.list_projects(conn)], limit=3)
    if labels:
        return f"Hola 🙂. Tengo {', '.join(labels)}. ¿Sobre cuál querés que te cuente?"
    return "Hola 🙂. Si querés, te cuento proyectos, precios o entrega."


def _build_vera_ack_reply(question: str, project_name: str) -> str:
    clean = _normalize_short_social_text(question)
    if clean == "👍":
        return "Perfecto 🙂"
    if clean.startswith("gracias"):
        if project_name:
            return f"Gracias a vos 🙂. Cuando quieras seguimos con {project_name}."
        return "Gracias a vos 🙂. Cuando quieras seguimos."
    if project_name:
        return f"Perfecto 🙂. Seguimos con {project_name} cuando quieras."
    if clean in {"dale", "de una"}:
        return "Dale, cuando quieras seguimos."
    return "Perfecto 🙂"


def _build_vera_sensitive_reply(project_name: str) -> str:
    return (
        f"Sobre {project_name}, para ese punto prefiero confirmártelo con un asesor para darte información precisa. "
        "Si te parece, te lo gestiono ahora por este mismo chat."
    )


def _pending_question_from_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary_obj = summary if isinstance(summary, dict) else {}
    return {
        "type": str(summary_obj.get("pending_question_type") or "").strip().upper(),
        "payload": (
            dict(summary_obj.get("pending_question_payload"))
            if isinstance(summary_obj.get("pending_question_payload"), dict)
            else {}
        ),
    }


def _clear_pending_question_patch() -> dict[str, Any]:
    return {
        "pending_question_type": None,
        "pending_question_payload": None,
    }


def _build_pending_question_patch(
    *,
    question_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pending_question_type": str(question_type or "").strip().upper() or None,
        "pending_question_payload": _jsonable(payload or {}),
    }


def _pending_offer_from_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary_obj = summary if isinstance(summary, dict) else {}
    return {
        "type": str(summary_obj.get("pending_offer_type") or "").strip().upper(),
        "project": str(summary_obj.get("pending_project") or "").strip().upper(),
        "intent_source": str(summary_obj.get("pending_intent_source") or "").strip().upper(),
        "payload": (
            dict(summary_obj.get("pending_payload"))
            if isinstance(summary_obj.get("pending_payload"), dict)
            else {}
        ),
    }


def _clear_pending_offer_patch() -> dict[str, Any]:
    return {
        "pending_offer_type": None,
        "pending_project": None,
        "pending_intent_source": None,
        "pending_payload": None,
    }


def _build_pending_offer_patch(
    *,
    offer_type: str,
    project_code: str | None,
    intent_source: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pending_offer_type": str(offer_type or "").strip().upper() or None,
        "pending_project": str(project_code or "").strip().upper() or None,
        "pending_intent_source": str(intent_source or "").strip().upper() or None,
        "pending_payload": _jsonable(payload or {}),
    }


def _extract_time_preference(text: str) -> str | None:
    clean = _normalize_text(text)
    if not clean:
        return None
    if re.fullmatch(r"(por\s+la\s+)?manana", clean):
        return "morning"
    if re.fullmatch(r"(por\s+la\s+)?tarde", clean):
        return "afternoon"
    any_patterns = (
        r"es\s+igual",
        r"igual",
        r"cualquier",
        r"cualquiera",
        r"me\s+da\s+igual",
        r"indistinto",
        r"indistinta",
        r"cualquier\s+franja",
        r"cualquier\s+horario",
    )
    if any(re.fullmatch(pattern, clean) for pattern in any_patterns):
        return "any"
    return None


def _build_vera_time_preference_reply(preference: str) -> str:
    if preference == "morning":
        return "Perfecto, lo dejo indicado para que el asesor te proponga un horario por la mañana."
    if preference == "afternoon":
        return "Perfecto, lo dejo indicado para que el asesor te proponga un horario por la tarde."
    return "Perfecto, lo dejo abierto para cualquier franja y un asesor te escribe por acá."


def _feature_values_from_unit(unit_row: dict[str, Any]) -> list[str]:
    raw = unit_row.get("features_jsonb")
    values = _as_list(raw)
    commercial_features = unit_row.get("commercial_features_jsonb")
    if isinstance(commercial_features, dict):
        for key, value in commercial_features.items():
            values.append(str(key or ""))
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, bool) and value:
                values.append(str(key or ""))
    if str(unit_row.get("balcony_protection") or "").strip().lower() not in {"", "not_applicable"}:
        values.append("balcon")
    if unit_row.get("has_garden") is True:
        values.append("jardin")
    if unit_row.get("has_patio") is True:
        values.append("patio")
    if unit_row.get("has_garage") is True:
        values.append("cochera")
    if unit_row.get("has_storage") is True:
        values.append("baulera")
    if unit_row.get("pets_allowed") is True:
        values.append("mascotas")
    normalized: list[str] = []
    for item in values:
        text = _normalize_text(str(item or ""))
        if text:
            normalized.append(text)
    return normalized


def _unit_matches_feature(unit_row: dict[str, Any], feature_key: str) -> bool:
    aliases = UNIT_FEATURE_ALIASES.get(feature_key, ())
    values = _feature_values_from_unit(unit_row)
    for value in values:
        for alias in aliases:
            if _normalize_text(alias) == value or _normalize_text(alias) in value or value in _normalize_text(alias):
                return True
    return False


def _format_surface(value: Any) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{numeric:.1f}".replace(".", ",")


def _format_unit_example(unit_row: dict[str, Any], *, include_project: bool) -> str:
    bits: list[str] = []
    unit_code = str(unit_row.get("unit_code") or unit_row.get("unit_id") or "").strip()
    if unit_code:
        bits.append(unit_code)
    if include_project:
        project_name = str(unit_row.get("project_name") or unit_row.get("project_code") or "").strip()
        if project_name:
            bits.append(f"en {project_name}")
    rooms_label = str(unit_row.get("rooms_label") or unit_row.get("typology") or "").strip()
    if rooms_label:
        bits.append(rooms_label)
    total_surface = _format_surface(unit_row.get("surface_total_m2"))
    if total_surface:
        bits.append(f"{total_surface} m² totales")
    price_value = _to_float(unit_row.get("list_price"))
    currency = str(unit_row.get("currency") or "").strip().upper()
    if price_value is not None:
        bits.append(f"{currency or 'USD'} {_format_price(price_value)}")
    status = _human_availability_status(unit_row.get("availability_status"))
    if status:
        bits.append(status.rstrip("s") if status.endswith("s") else status)
    return ", ".join(bits)


def _count_units_by_rooms_reply(
    *,
    rooms_count: int,
    count: int,
    project_name: str | None = None,
    global_scope: bool = False,
) -> str:
    rooms_label = _rooms_label_from_count(rooms_count)
    if global_scope:
        return f"Tomando todos los proyectos, hoy veo {count} unidades de {rooms_label}."
    return f"En {project_name or 'este proyecto'} hoy veo {count} unidades de {rooms_label}."


def _grouped_global_rooms_list_reply(rows: list[dict[str, Any]], *, rooms_count: int) -> str:
    rooms_label = _rooms_label_from_count(rooms_count)
    grouped: dict[str, list[str]] = {}
    ordered_projects: list[str] = []
    for row in rows:
        project_name = str(row.get("project_name") or row.get("project_code") or "").strip() or "Proyecto sin nombre"
        if project_name not in grouped:
            grouped[project_name] = []
            ordered_projects.append(project_name)
        grouped[project_name].append(_format_unit_example(row, include_project=False))
    lines = [f"Tomando todos los proyectos, hoy veo {len(rows)} unidades de {rooms_label}:"]
    for project_name in ordered_projects:
        examples = "; ".join(item for item in grouped[project_name] if item)
        lines.append(f"- {project_name}: {examples}")
    return "\n".join(lines)


def _list_units_by_rooms_reply(
    rows: list[dict[str, Any]],
    *,
    rooms_count: int,
    project_name: str | None = None,
    global_scope: bool = False,
) -> str:
    rooms_label = _rooms_label_from_count(rooms_count)
    if not rows:
        if global_scope:
            return f"Tomando todos los proyectos, hoy no veo unidades de {rooms_label}."
        return f"En {project_name or 'este proyecto'} hoy no veo unidades de {rooms_label}."
    if global_scope:
        return _grouped_global_rooms_list_reply(rows, rooms_count=rooms_count)
    lines = [f"En {project_name or 'este proyecto'} hoy tengo estas unidades de {rooms_label}:"]
    lines.extend(f"- {_format_unit_example(row, include_project=False)}" for row in rows if _format_unit_example(row, include_project=False))
    return "\n".join(lines)


def _projects_matching_active_filter_reply(
    rows: list[dict[str, Any]],
    *,
    active_filter: dict[str, Any],
) -> str:
    filter_summary = str(active_filter.get("summary") or "unidades que cumplen el filtro actual").strip()
    if not rows:
        return f"Hoy no veo proyectos con {filter_summary}."
    parts: list[str] = []
    for row in rows:
        project_name = str(row.get("project_name") or row.get("project_code") or "").strip()
        try:
            units_count = int(row.get("units_count") or 0)
        except Exception:  # noqa: BLE001
            units_count = 0
        if units_count > 0:
            parts.append(f"{project_name} ({units_count})")
        else:
            parts.append(project_name)
    return f"Los proyectos que hoy tienen {filter_summary} son {', '.join(parts)}."


def _build_specific_no_info_reply(
    *,
    topic_label: str,
    project_name: str | None = None,
) -> str:
    if project_name:
        return (
            f"No tengo información sobre {topic_label} en {project_name}. "
            "Si querés, te puedo ayudar con precio, disponibilidad, entrega o coordinar contacto con un asesor."
        )
    return (
        f"No tengo información sobre {topic_label} en este momento. "
        "Si querés, decime el proyecto y veo qué dato sí tengo cargado."
    )


def _source_from_profile_payload(payload: dict[str, Any] | None) -> list[str]:
    payload_obj = payload if isinstance(payload, dict) else {}
    sources: list[str] = []
    for key in ("_source_table", "_profile_source_table"):
        source = str(payload_obj.get(key) or "").strip()
        if source and source not in sources:
            sources.append(source)
    nested_sources = payload_obj.get("_source_tables")
    if isinstance(nested_sources, list):
        for source in nested_sources:
            clean = str(source or "").strip()
            if clean and clean not in sources:
                sources.append(clean)
    return sources


def _source_from_profile_rows(rows: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for row in rows:
        for source in _source_from_profile_payload(row):
            if source not in sources:
                sources.append(source)
    return sources


def _unit_brief_label(unit_row: dict[str, Any]) -> str:
    code = str(unit_row.get("unit_code") or unit_row.get("unit_id") or "").strip()
    if not code:
        return "unidad sin código"
    return code


def _unit_brief_for_profile(unit_row: dict[str, Any]) -> str:
    label = _unit_brief_label(unit_row)
    extras: list[str] = []
    rooms_label = str(unit_row.get("rooms_label") or "").strip()
    if rooms_label:
        extras.append(rooms_label)
    if unit_row.get("has_garden") is True:
        extras.append("con jardín")
    elif unit_row.get("has_patio") is True:
        extras.append("con patio")
    elif str(unit_row.get("balcony_protection") or "").strip().lower() not in {"", "not_applicable"}:
        extras.append("con balcón")
    if str(unit_row.get("natural_light") or "").strip():
        light = str(unit_row.get("natural_light") or "").strip().lower()
        if light == "high":
            extras.append("luz alta")
        elif light == "medium":
            extras.append("luz media")
        elif light == "low":
            extras.append("luz baja")
    if not extras:
        return label
    return f"{label} ({', '.join(extras[:2])})"


def _unit_subject_summary_patch(unit_row: dict[str, Any]) -> dict[str, Any]:
    unit_code = str(unit_row.get("unit_code") or unit_row.get("unit_id") or "").strip().upper()
    if not unit_code:
        return {}
    return {
        "last_subject_type": "unit",
        "last_subject_project_code": str(unit_row.get("project_code") or "").strip().upper(),
        "last_subject_project_name": str(unit_row.get("project_name") or "").strip(),
        "last_subject_unit_id": str(unit_row.get("unit_id") or "").strip(),
        "last_subject_unit_code": unit_code,
        "last_subject_summary": _normalize_snippet(_format_unit_example(unit_row, include_project=True), limit=220),
    }


def _format_profile_examples(units: list[dict[str, Any]], *, limit: int = 3) -> str:
    labels = [_unit_brief_for_profile(row) for row in units[:limit] if _unit_brief_for_profile(row)]
    return ", ".join(labels)


def _inventory_fragments_from_breakdown(breakdown: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    ordered_statuses = ("available", "reserved", "unavailable")
    for status in ordered_statuses:
        try:
            count = int(breakdown.get(status) or 0)
        except Exception:  # noqa: BLE001
            count = 0
        if count > 0:
            fragments.append(_format_inventory_count(count, status))
    extra_statuses = [
        key for key in breakdown.keys() if key not in ordered_statuses and int(breakdown.get(key) or 0) > 0
    ]
    for status in sorted(extra_statuses):
        fragments.append(_format_inventory_count(int(breakdown.get(status) or 0), status))
    return fragments


def _inventory_total_units_reply(project_name: str, summary: dict[str, Any]) -> str:
    units_total = summary.get("units_total")
    available_units = summary.get("available_units")
    breakdown = summary.get("raw_status_breakdown_jsonb") if isinstance(summary.get("raw_status_breakdown_jsonb"), dict) else {}
    fragments = _inventory_fragments_from_breakdown(breakdown)
    inventory_complete = bool(summary.get("inventory_is_complete"))

    if units_total is not None and inventory_complete:
        answer = f"{project_name} tiene {int(units_total)} unidades en total."
        if fragments:
            answer += f" Hoy veo {', '.join(fragments)}."
        elif available_units is not None:
            answer += f" Hoy veo {_format_inventory_count(int(available_units), 'available')}."
        return answer

    if units_total is not None:
        if available_units is not None and int(available_units) == int(units_total) and not any(
            int(breakdown.get(status) or 0) > 0 for status in ("reserved", "unavailable")
        ):
            return (
                f"En el inventario demo que tengo cargado hoy para {project_name} veo {int(units_total)} unidades, "
                "todas disponibles. No tengo cargado el total completo del proyecto."
            )
        if fragments:
            return (
                f"En el inventario demo que tengo cargado hoy para {project_name} veo {int(units_total)} unidades: "
                f"{', '.join(fragments)}. No tengo cargado el total completo del proyecto."
            )
        return (
            f"En el inventario demo que tengo cargado hoy para {project_name} veo {int(units_total)} unidades. "
            "No tengo cargado el total completo del proyecto."
        )

    if available_units is not None:
        return (
            f"En el inventario demo que tengo cargado hoy para {project_name} veo "
            f"{_format_inventory_count(int(available_units), 'available')}. "
            "No tengo cargado el total completo del proyecto."
        )

    return "No tengo cargado el total completo de unidades del proyecto."


def _inventory_breakdown_reply(project_name: str, summary: dict[str, Any]) -> str:
    breakdown = summary.get("raw_status_breakdown_jsonb") if isinstance(summary.get("raw_status_breakdown_jsonb"), dict) else {}
    fragments = _inventory_fragments_from_breakdown(breakdown)
    inventory_complete = bool(summary.get("inventory_is_complete"))
    units_total = summary.get("units_total")
    if fragments and inventory_complete:
        answer = f"Hoy veo {', '.join(fragments)} para {project_name}."
        if units_total is not None:
            answer += f" El proyecto tiene {int(units_total)} unidades en total."
        return answer
    if fragments:
        return (
            f"En la base demo que tengo cargada hoy para {project_name} veo {', '.join(fragments)}. "
            "No tengo cargado el inventario completo del proyecto, así que este desglose es parcial."
        )
    if units_total is not None and inventory_complete:
        return f"{project_name} tiene {int(units_total)} unidades en total, pero no tengo el desglose por estado cargado."
    return "No tengo el desglose completo por estado del proyecto."


def _children_suitability_reply(project_name: str, summary: dict[str, Any]) -> str:
    suitable_units = summary.get("suitable_units") if isinstance(summary.get("suitable_units"), list) else []
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    project_flag = summary.get("project_children_suitable")
    family_units = summary.get("family_units") if isinstance(summary.get("family_units"), list) else []

    if suitable_units:
        answer = (
            f"Sí, en el inventario demo que tengo cargado hoy para {project_name} veo "
            f"{len(suitable_units)} unidades razonables para familia con chicos"
        )
        examples = _format_profile_examples(suitable_units or family_units)
        if examples:
            answer += f", por ejemplo {examples}"
        answer += "."
        if warnings:
            answer += f" Ojo con esto: {warnings[0]}"
        return answer

    if project_flag is True:
        answer = f"A nivel proyecto, {project_name} figura como razonable para familias con chicos."
        if family_units:
            examples = _format_profile_examples(family_units)
            if examples:
                answer += f" Hoy veo como referencia {examples}."
        if warnings:
            answer += f" Igual, tener en cuenta: {warnings[0]}"
        return answer

    if summary.get("known_units_count"):
        answer = f"No veo unidades marcadas como especialmente aptas para chicos en el inventario demo actual de {project_name}."
        if warnings:
            answer += f" Además, {warnings[0]}"
        return answer

    return f"No tengo suficiente información estructurada para confirmar si {project_name} es apto para niños."


def _pets_suitability_reply(project_name: str, summary: dict[str, Any], question: str) -> str:
    allowed_units = summary.get("allowed_units") if isinstance(summary.get("allowed_units"), list) else []
    recommended_units = summary.get("recommended_units") if isinstance(summary.get("recommended_units"), list) else []
    restrictions = str(summary.get("project_pets_restrictions_text") or "").strip()
    project_flag = summary.get("project_pets_allowed")
    asks_best = bool(re.search(r"\b(mejor|ideal|recomend)\b", _normalize_text(question)))

    if project_flag is True:
        answer = f"A nivel proyecto, en la base demo figura que se permiten mascotas en {project_name}."
        if restrictions:
            answer += f" Restricción o nota: {restrictions}"
        if recommended_units:
            examples = _format_profile_examples(recommended_units)
            if examples:
                answer += f" Las unidades más razonables para mascotas que veo hoy son {examples}."
        elif allowed_units:
            examples = _format_profile_examples(allowed_units)
            if examples:
                answer += f" Veo unidades marcadas como permitidas, por ejemplo {examples}."
        return answer

    if asks_best and recommended_units:
        answer = f"No tengo una política general confirmada para todo {project_name} sobre mascotas."
        examples = _format_profile_examples(recommended_units)
        if examples:
            answer += f" Sí veo unidades más razonables para ese perfil, por ejemplo {examples}."
        if restrictions:
            answer += f" Además, {restrictions}"
        return answer

    if allowed_units:
        answer = (
            f"No tengo una confirmación general para todo {project_name} sobre mascotas, "
            f"pero sí veo {len(allowed_units)} unidades donde figuran permitidas"
        )
        examples = _format_profile_examples(allowed_units)
        if examples:
            answer += f", por ejemplo {examples}"
        answer += "."
        if restrictions:
            answer += f" {restrictions}"
        return answer

    if project_flag is False:
        answer = f"En la base demo, {project_name} figura con mascotas no permitidas."
        if restrictions:
            answer += f" {restrictions}"
        return answer

    return f"No tengo información estructurada suficiente para confirmar si {project_name} acepta mascotas."


def _warnings_reply(conn: Any, *, project_code: str, project_name: str, question: str) -> tuple[str, list[str], list[str]]:
    project_profile = repo.get_project_profile(conn, project_code) or {}
    units = repo.get_units_with_filters(conn, project_code=project_code)
    warnings: list[str] = []
    for raw in (
        project_profile.get("child_safety_warnings_jsonb"),
        project_profile.get("usage_warnings_jsonb"),
    ):
        if isinstance(raw, list):
            for item in raw:
                clean = str(item or "").strip()
                if clean and clean not in warnings:
                    warnings.append(clean)
    for unit in units:
        for key in ("child_safety_warnings_jsonb", "usage_warnings_jsonb"):
            raw = unit.get(key)
            if isinstance(raw, list):
                for item in raw:
                    clean = str(item or "").strip()
                    if clean and clean not in warnings:
                        warnings.append(clean)

    data_sources = _dedupe_texts(
        [*(_source_from_profile_payload(project_profile)), *(_source_from_profile_rows(units))],
        limit=8,
    )
    fields_used = [
        "demo_project_profile.child_safety_warnings_jsonb",
        "demo_project_profile.usage_warnings_jsonb",
        "demo_unit_profile.child_safety_warnings_jsonb",
        "demo_unit_profile.usage_warnings_jsonb",
    ]

    if _asks_balcony_protection(question):
        balcony_units = [row for row in units if str(row.get("balcony_protection") or "").strip().lower() != "not_applicable"]
        if not balcony_units:
            return (
                f"No tengo confirmación estructurada sobre protección de balcón en {project_name}.",
                fields_used,
                data_sources,
            )
        known = [row for row in balcony_units if str(row.get("balcony_protection") or "").strip().lower() not in {"", "unknown"}]
        if not known:
            return (
                f"No tengo confirmación estructurada sobre la protección del balcón en las unidades cargadas de {project_name}; las que tienen balcón figuran con protección desconocida.",
                [*fields_used, "demo_unit_profile.balcony_protection"],
                data_sources,
            )
        protected = [row for row in known if str(row.get("balcony_protection") or "").strip().lower() == "protected"]
        partial = [row for row in known if str(row.get("balcony_protection") or "").strip().lower() == "partial"]
        unprotected = [row for row in known if str(row.get("balcony_protection") or "").strip().lower() == "unprotected"]
        fragments: list[str] = []
        if protected:
            fragments.append(f"{len(protected)} protegidas")
        if partial:
            fragments.append(f"{len(partial)} con protección parcial")
        if unprotected:
            fragments.append(f"{len(unprotected)} sin protección")
        return (
            f"Sobre el balcón en {project_name}, hoy tengo cargado esto: {', '.join(fragments)}.",
            [*fields_used, "demo_unit_profile.balcony_protection"],
            data_sources,
        )

    if warnings:
        answer = f"Sí, en {project_name} hay algunos puntos a tener en cuenta: {warnings[0]}"
        if len(warnings) > 1:
            answer += f" También {warnings[1]}"
        return answer, fields_used, data_sources

    return (
        f"No tengo warnings estructurados cargados para {project_name} en este momento.",
        fields_used,
        data_sources,
    )


def _light_orientation_reply(project_name: str, question: str, summary: dict[str, Any]) -> str:
    clean = _normalize_text(question)
    high_light_units = summary.get("high_light_units") if isinstance(summary.get("high_light_units"), list) else []
    medium_light_units = summary.get("medium_light_units") if isinstance(summary.get("medium_light_units"), list) else []
    orientation_units = summary.get("orientation_known_units") if isinstance(summary.get("orientation_known_units"), list) else []
    exposure_units = summary.get("exposure_known_units") if isinstance(summary.get("exposure_known_units"), list) else []
    sun_morning_units = summary.get("sun_morning_units") if isinstance(summary.get("sun_morning_units"), list) else []
    sun_afternoon_units = summary.get("sun_afternoon_units") if isinstance(summary.get("sun_afternoon_units"), list) else []
    cross_units = summary.get("cross_ventilation_units") if isinstance(summary.get("cross_ventilation_units"), list) else []

    if re.search(r"\b(sol\s+de\s+manana|sol\s+manana|manana)\b", clean):
        if sun_morning_units:
            return f"Sí, veo unidades con sol de mañana en {project_name}, por ejemplo {_format_profile_examples(sun_morning_units)}."
        return f"No tengo dato estructurado sobre sol de mañana para {project_name}."

    if re.search(r"\b(sol\s+de\s+la\s+tarde|sol\s+tarde|tarde)\b", clean):
        if sun_afternoon_units:
            return f"Sí, veo unidades con sol de tarde en {project_name}, por ejemplo {_format_profile_examples(sun_afternoon_units)}."
        return f"No tengo dato estructurado sobre sol de tarde para {project_name}."

    if re.search(r"\b(orientacion)\b", clean):
        if orientation_units:
            return f"Tengo orientación cargada para algunas unidades de {project_name}, por ejemplo {_format_profile_examples(orientation_units)}."
        if exposure_units:
            return (
                f"No tengo orientación cardinal confirmada para {project_name}. "
                f"Sí tengo exposición al frente/contrafrente en unidades como {_format_profile_examples(exposure_units)}."
            )
        return f"No tengo información estructurada sobre orientación en {project_name}."

    if re.search(r"\b(ventilacion\s+cruzada|ventilacion)\b", clean):
        if cross_units:
            return f"Sí, veo unidades con ventilación cruzada cargada en {project_name}, por ejemplo {_format_profile_examples(cross_units)}."
        return f"No tengo dato estructurado sobre ventilación cruzada para {project_name}."

    if re.search(r"\b(luz|luminos[oa]|habitabilidad|exposicion)\b", clean):
        if high_light_units:
            answer = (
                f"Sí, en el inventario demo que tengo cargado hoy para {project_name} veo "
                f"{len(high_light_units)} unidades con luz natural alta"
            )
            examples = _format_profile_examples(high_light_units)
            if examples:
                answer += f", por ejemplo {examples}"
            answer += "."
            if not orientation_units and not sun_morning_units and not sun_afternoon_units:
                answer += " No tengo cargada la orientación exacta ni el asoleamiento por franja."
            return answer
        if medium_light_units:
            return (
                f"Veo unidades con luz natural media en {project_name}, por ejemplo {_format_profile_examples(medium_light_units)}. "
                "No tengo orientación ni asoleamiento confirmados."
            )
        return f"No tengo información estructurada sobre luz natural en {project_name}."

    if re.search(r"\b(como\s+da)\b", clean):
        if exposure_units:
            return f"Hoy tengo exposición cargada para algunas unidades de {project_name}, por ejemplo {_format_profile_examples(exposure_units)}."
        return f"No tengo información estructurada sobre cómo da el proyecto en las unidades cargadas."

    return f"No tengo información estructurada suficiente sobre orientación, luz o sol en {project_name}."


def _unit_row_for_code(conn: Any, unit_code: str) -> dict[str, Any] | None:
    finder = getattr(repo, "find_demo_unit_by_code", None)
    if not callable(finder):
        return None
    unit_row = finder(conn, unit_code)
    if not unit_row:
        return None
    project_code = str(unit_row.get("project_code") or "").strip().upper()
    unit_id = str(unit_row.get("unit_id") or "").strip()
    if project_code and unit_id:
        merged = repo.get_units_with_filters(conn, project_code=project_code, unit_id=unit_id)
        if merged:
            return merged[0]
    return unit_row


def _unit_project_name(conn: Any, unit_row: dict[str, Any]) -> str:
    project_name = str(unit_row.get("project_name") or "").strip()
    if project_name:
        return project_name
    project_code = str(unit_row.get("project_code") or "").strip().upper()
    project_row = repo.get_project_by_code(conn, project_code) if project_code else None
    return str((project_row or {}).get("name") or project_code).strip()


def _unit_price_reply(unit_code: str, unit_row: dict[str, Any]) -> str:
    price_value = _to_float(unit_row.get("list_price"))
    currency = str(unit_row.get("currency") or "").strip().upper() or "USD"
    if price_value is None:
        return f"No tengo precio publicado para la unidad {unit_code} en este momento."
    return f"La unidad {unit_code} hoy figura en {currency} {_format_price(price_value)}."


def _unit_availability_reply(unit_code: str, unit_row: dict[str, Any]) -> str:
    status = _normalize_text(str(unit_row.get("availability_status") or ""))
    if status in {"available", "disponible", "activo", "active"}:
        return f"Sí, la unidad {unit_code} hoy figura disponible."
    if status in {"reserved", "reservada", "reservado"}:
        return f"La unidad {unit_code} hoy figura reservada."
    if status in {"sold", "vendida", "vendido"}:
        return f"La unidad {unit_code} hoy figura vendida."
    if status in {"unavailable", "no disponible", "no_disponible"}:
        return f"La unidad {unit_code} hoy figura no disponible."
    return f"No tengo confirmación estructurada sobre la disponibilidad actual de la unidad {unit_code}."


def _unit_surface_reply(unit_code: str, unit_row: dict[str, Any]) -> str:
    total_surface = _format_surface(unit_row.get("surface_total_m2"))
    if total_surface:
        return f"La unidad {unit_code} tiene {total_surface} m² totales."
    return f"No tengo metros cuadrados cargados para la unidad {unit_code}."


def _unit_rooms_reply(unit_code: str, unit_row: dict[str, Any]) -> str:
    rooms_label = str(unit_row.get("rooms_label") or unit_row.get("typology") or "").strip()
    if rooms_label:
        return f"La unidad {unit_code} es de {rooms_label}."
    rooms_count = _to_float(unit_row.get("rooms_count"))
    if rooms_count is not None:
        rooms_int = int(rooms_count)
        return f"La unidad {unit_code} es de {rooms_int} ambientes."
    return f"No tengo la tipología cargada para la unidad {unit_code}."


def _unit_children_suitability_reply(unit_code: str, unit_row: dict[str, Any]) -> str:
    suitable = unit_row.get("children_suitable")
    warnings: list[str] = []
    for key in ("child_safety_warnings_jsonb", "usage_warnings_jsonb"):
        raw = unit_row.get(key)
        if isinstance(raw, list):
            for item in raw:
                clean = str(item or "").strip()
                if clean and clean not in warnings:
                    warnings.append(clean)
    if suitable is True:
        answer = f"Sí, la unidad {unit_code} figura como razonable para chicos en la información cargada."
        if warnings:
            answer += f" Igual, tener en cuenta: {warnings[0]}"
        return answer
    if suitable is False:
        answer = f"No, la unidad {unit_code} no figura como especialmente apta para chicos en la base demo."
        if warnings:
            answer += f" Además, {warnings[0]}"
        return answer
    return f"No tengo una confirmación estructurada sobre aptitud para chicos en la unidad {unit_code}."


def _unit_pets_suitability_reply(
    conn: Any,
    *,
    unit_code: str,
    unit_row: dict[str, Any],
    question: str,
) -> str:
    pets_allowed = unit_row.get("pets_allowed")
    recommended = "pets" in [str(value).strip().lower() for value in (unit_row.get("recommended_profiles_jsonb") or [])]
    has_garden = unit_row.get("has_garden") is True
    has_patio = unit_row.get("has_patio") is True
    asks_best = bool(re.search(r"\b(mejor|ideal|recomend)\b", _normalize_text(question)))
    project_profile = repo.get_project_profile(conn, str(unit_row.get("project_code") or "").strip().upper()) or {}
    restrictions = str(project_profile.get("pets_restrictions_text") or "").strip()
    context_parts: list[str] = []
    if has_garden:
        context_parts.append("tiene jardín")
    if has_patio:
        context_parts.append("tiene patio")
    if recommended:
        context_parts.append("está entre las opciones más razonables para ese perfil")
    context_text = ""
    if context_parts:
        context_text = "Además, " + " y ".join(context_parts) + "."
    if pets_allowed is True:
        answer = f"Sí, la unidad {unit_code} figura con mascotas permitidas."
        if context_text:
            answer += f" {context_text}"
        if restrictions:
            answer += f" {restrictions}"
        return answer
    if pets_allowed is False:
        answer = f"No, la unidad {unit_code} figura con mascotas no permitidas."
        if restrictions:
            answer += f" {restrictions}"
        return answer
    if asks_best and context_parts:
        answer = f"No tengo confirmación estructurada de permiso para mascotas en la unidad {unit_code}, pero {', '.join(context_parts)}."
        if restrictions:
            answer += f" {restrictions}"
        return answer
    return f"No tengo confirmación estructurada de permiso para mascotas en la unidad {unit_code}."


def _unit_warnings_reply(unit_code: str, unit_row: dict[str, Any], question: str) -> str:
    if _asks_balcony_protection(question):
        protection = str(unit_row.get("balcony_protection") or "").strip().lower()
        if protection in {"", "unknown"}:
            return f"No tengo confirmación estructurada sobre la protección del balcón en la unidad {unit_code}."
        if protection == "not_applicable":
            return f"La unidad {unit_code} no figura con balcón aplicable en la información cargada."
        if protection == "protected":
            return f"Sí, la unidad {unit_code} figura con balcón protegido."
        if protection == "partial":
            return f"La unidad {unit_code} figura con protección parcial en el balcón."
        if protection == "unprotected":
            return f"La unidad {unit_code} figura con balcón sin protección."
    warnings: list[str] = []
    for key in ("child_safety_warnings_jsonb", "usage_warnings_jsonb"):
        raw = unit_row.get(key)
        if isinstance(raw, list):
            for item in raw:
                clean = str(item or "").strip()
                if clean and clean not in warnings:
                    warnings.append(clean)
    if warnings:
        return f"Sí, en la unidad {unit_code} hay algo a tener en cuenta: {warnings[0]}"
    return f"No tengo warnings estructurados específicos para la unidad {unit_code}."


def _unit_light_orientation_reply(unit_code: str, unit_row: dict[str, Any], question: str) -> str:
    clean = _normalize_text(question)
    if re.search(r"\b(sol\s+de\s+manana|sol\s+manana|manana)\b", clean):
        value = unit_row.get("sun_morning")
        if value is True:
            return f"Sí, la unidad {unit_code} figura con sol de mañana."
        if value is False:
            return f"No, la unidad {unit_code} no figura con sol de mañana."
        return f"No tengo dato estructurado sobre sol de mañana para la unidad {unit_code}."
    if re.search(r"\b(sol\s+de\s+la\s+tarde|sol\s+tarde|tarde)\b", clean):
        value = unit_row.get("sun_afternoon")
        if value is True:
            return f"Sí, la unidad {unit_code} figura con sol de tarde."
        if value is False:
            return f"No, la unidad {unit_code} no figura con sol de tarde."
        return f"No tengo dato estructurado sobre sol de tarde para la unidad {unit_code}."
    if re.search(r"\b(orientacion)\b", clean):
        orientation = str(unit_row.get("orientation") or "").strip()
        exposure = str(unit_row.get("exposure") or "").strip()
        if orientation:
            return f"La unidad {unit_code} figura con orientación {orientation}."
        if exposure:
            return f"No tengo orientación cardinal confirmada para la unidad {unit_code}; sí figura con exposición {exposure}."
        return f"No tengo información estructurada sobre orientación para la unidad {unit_code}."
    if re.search(r"\b(como\s+da|exposicion)\b", clean):
        exposure = str(unit_row.get("exposure") or "").strip()
        if exposure:
            return f"La unidad {unit_code} figura con exposición {exposure}."
        return f"No tengo información estructurada sobre cómo da la unidad {unit_code}."
    if re.search(r"\b(ventilacion\s+cruzada|ventilacion)\b", clean):
        value = unit_row.get("cross_ventilation")
        if value is True:
            return f"Sí, la unidad {unit_code} figura con ventilación cruzada."
        if value is False:
            return f"No, la unidad {unit_code} no figura con ventilación cruzada."
        return f"No tengo dato estructurado sobre ventilación cruzada para la unidad {unit_code}."
    if re.search(r"\b(luz|luminos[oa]|habitabilidad)\b", clean):
        natural_light = str(unit_row.get("natural_light") or "").strip().lower()
        if natural_light == "high":
            return f"Sí, la unidad {unit_code} figura con luz natural alta."
        if natural_light == "medium":
            return f"La unidad {unit_code} figura con luz natural media."
        if natural_light == "low":
            return f"La unidad {unit_code} figura con luz natural baja."
        return f"No tengo información estructurada sobre luz natural para la unidad {unit_code}."
    return f"No tengo información estructurada suficiente sobre orientación, luz o sol para la unidad {unit_code}."


def _surface_rows_for_project(
    conn: Any,
    project_code: str,
    *,
    rooms: int | None = None,
) -> list[dict[str, Any]]:
    list_units = getattr(repo, "list_demo_units", None)
    if not callable(list_units):
        return []
    return list_units(conn, project_code, rooms=rooms, currency=None) or []


def _surface_query_reply(
    conn: Any,
    *,
    project_code: str,
    project_name: str,
    question: str,
    rooms: int | None = None,
    surface_filter: dict[str, Any] | None = None,
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    rows = _surface_rows_for_project(conn, project_code, rooms=rooms)
    data_sources = _dedupe_texts(_source_from_rows(rows), limit=8)
    surface_rows = [row for row in rows if _to_float(row.get("surface_total_m2")) is not None]
    asks_extreme = _is_surface_extreme_query(question) and not _is_surface_filter_list_query(question, surface_filter)
    result_slots: dict[str, Any] = {}

    if not surface_rows:
        return (
            _build_specific_no_info_reply(topic_label="los metros cuadrados de las unidades", project_name=project_name),
            False,
            [],
            data_sources,
            {"unresolved_topic": "surface"},
        )

    if asks_extreme and len(surface_rows) != len(rows):
        return (
            (
                f"Tengo metros cuadrados cargados para algunas unidades de {project_name}, "
                "pero no puedo confirmar cuál es la más grande con certeza."
            ),
            False,
            ["demo_units.surface_total_m2"],
            data_sources,
            {"unresolved_topic": "surface"},
        )

    if asks_extreme:
        largest_row = max(surface_rows, key=lambda row: _to_float(row.get("surface_total_m2")) or 0.0)
        surface_value = _format_surface(largest_row.get("surface_total_m2"))
        unit_code = str(largest_row.get("unit_code") or largest_row.get("unit_id") or "").strip()
        rooms_label = str(largest_row.get("rooms_label") or largest_row.get("typology") or "").strip()
        bits = [f"La unidad más grande que tengo cargada en {project_name}"]
        if unit_code:
            bits.append(f"es {unit_code}")
        if rooms_label:
            bits.append(f"de {rooms_label}")
        if surface_value:
            bits.append(f"con {surface_value} m² totales")
        answer = " ".join(bits) + "."
        result_slots["surface_max_m2"] = surface_value
        if unit_code:
            result_slots["surface_max_unit_code"] = unit_code
        result_slots["last_subject_patch"] = _unit_subject_summary_patch(largest_row)
        return answer, True, ["demo_units.surface_total_m2"], data_sources, result_slots

    if surface_filter:
        min_surface_total_m2 = _to_float(surface_filter.get("value"))
        matches = [
            row
            for row in surface_rows
            if min_surface_total_m2 is None or (_to_float(row.get("surface_total_m2")) or 0.0) > float(min_surface_total_m2)
        ]
        if not matches:
            threshold_text = ""
            if min_surface_total_m2 is not None:
                threshold_text = f" de más de {_format_surface(min_surface_total_m2)} m²"
            return (
                f"No veo unidades{threshold_text} en {project_name} dentro del inventario demo que tengo cargado hoy.",
                False,
                ["demo_units.surface_total_m2"],
                data_sources,
                {
                    "surface_min_m2": _format_surface(min_surface_total_m2) if min_surface_total_m2 is not None else None,
                    "matches_count": 0,
                },
            )
        ordered_matches = sorted(matches, key=lambda row: _to_float(row.get("surface_total_m2")) or 0.0, reverse=True)
        example_rows = ordered_matches[:4]
        examples = [_format_unit_example(row, include_project=False) for row in example_rows]
        examples = [item for item in examples if item]
        threshold_text = (
            f" de más de {_format_surface(min_surface_total_m2)} m²"
            if min_surface_total_m2 is not None
            else " con superficie cargada"
        )
        if len(ordered_matches) == 1:
            single_example = examples[0] if examples else _unit_brief_label(ordered_matches[0])
            answer = f"Hoy veo una unidad{threshold_text} en {project_name}: {single_example}."
        else:
            answer = f"Hoy veo estas unidades{threshold_text} en {project_name}: {'; '.join(examples or [_unit_brief_label(row) for row in example_rows])}."
        answer += " ¿Querés que te las ordene por precio o por metros?"
        return (
            answer,
            True,
            ["demo_units.surface_total_m2", "demo_units.list_price"],
            data_sources,
            {
                "surface_min_m2": _format_surface(min_surface_total_m2) if min_surface_total_m2 is not None else None,
                "matches_count": len(ordered_matches),
                "result_set_patch": _result_set_summary_patch(ordered_matches, origin_intent="SURFACE_QUERY"),
            },
        )

    ordered_rows = sorted(surface_rows, key=lambda row: _to_float(row.get("surface_total_m2")) or 0.0)
    min_surface = _to_float(ordered_rows[0].get("surface_total_m2")) or 0.0
    max_surface = _to_float(ordered_rows[-1].get("surface_total_m2")) or 0.0
    label_scope = f"para {rooms} ambientes" if rooms is not None else "de las unidades"
    if len(ordered_rows) == 1 or abs(max_surface - min_surface) < 0.05:
        answer = (
            f"En {project_name} hoy tengo {label_scope} cargados con { _format_surface(max_surface) } m² totales."
        )
    else:
        answer = (
            f"En {project_name} hoy tengo metros cuadrados {label_scope} entre "
            f"{_format_surface(min_surface)} y {_format_surface(max_surface)} m² totales."
        )
    examples = [_format_unit_example(row, include_project=False) for row in ordered_rows[:2]]
    examples = [item for item in examples if item]
    if examples:
        answer += f" Por ejemplo: {'; '.join(examples)}."
    result_slots["surface_range_m2"] = {
        "min": _format_surface(min_surface),
        "max": _format_surface(max_surface),
    }
    return answer, True, ["demo_units.surface_total_m2"], data_sources, result_slots


def _global_surface_filter_reply(
    conn: Any,
    *,
    question: str,
    min_surface_total_m2: float | None = None,
    rooms: int | None = None,
    feature_key: str | None = None,
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    rows = repo.get_units_global_filtered(
        conn,
        min_surface_total_m2=min_surface_total_m2,
        rooms_count=rooms,
        feature_key=feature_key,
        availability="available",
    )
    data_sources = _dedupe_texts(_source_from_profile_rows(rows), limit=8) or ["demo_units"]
    if not rows:
        threshold_text = ""
        if min_surface_total_m2 is not None:
            threshold_text = f" de más de {_format_surface(min_surface_total_m2)} m²"
        return (
            f"No veo unidades{threshold_text} en el inventario demo que tengo cargado hoy.",
            False,
            ["demo_units.surface_total_m2"],
            data_sources,
            {
                "search_scope": "global",
                "surface_min_m2": _format_surface(min_surface_total_m2) if min_surface_total_m2 is not None else None,
            },
        )

    ordered_rows = sorted(rows, key=lambda row: _to_float(row.get("surface_total_m2")) or 0.0, reverse=True)
    examples: list[str] = []
    example_rows: list[dict[str, Any]] = []
    for row in ordered_rows[:4]:
        project_label = str(row.get("project_name") or row.get("project_code") or "").strip()
        unit_label = str(row.get("unit_code") or row.get("unit_id") or "").strip()
        surface_label = _format_surface(row.get("surface_total_m2"))
        price_value = _to_float(row.get("list_price"))
        currency = str(row.get("currency") or "").strip().upper() or "USD"
        bits = [project_label]
        if unit_label:
            bits.append(f"unidad {unit_label}")
        if surface_label:
            bits.append(f"{surface_label} m²")
        if price_value is not None:
            bits.append(f"{currency} {_format_price(price_value)}")
        examples.append(" — ".join([bit for bit in bits if bit]))
        example_rows.append(row)

    if min_surface_total_m2 is not None:
        answer = (
            f"Sí, hoy veo departamentos de más de {_format_surface(min_surface_total_m2)} m² en varios proyectos. "
            f"Por ejemplo: {'; '.join(examples)}. ¿Querés que te los ordene por precio o por metros?"
        )
    else:
        answer = (
            f"Hoy veo unidades con superficie cargada en varios proyectos. "
            f"Por ejemplo: {'; '.join(examples)}. ¿Querés que te las ordene por precio o por metros?"
        )
    return (
        answer,
        True,
        ["demo_units.surface_total_m2", "demo_units.list_price"],
        data_sources,
        {
            "search_scope": "global",
            "surface_min_m2": _format_surface(min_surface_total_m2) if min_surface_total_m2 is not None else None,
            "matches_count": len(rows),
            "result_set_patch": _result_set_summary_patch(ordered_rows, origin_intent="GLOBAL_UNIT_FILTER_SEARCH"),
        },
    )


def _project_surface_comparison_reply(
    conn: Any,
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    rows = getattr(repo, "get_project_surface_totals_from_demo_units", lambda _c: [])(conn) or []
    comparable_rows = [row for row in rows if _to_float(row.get("surface_total_m2_sum")) is not None]
    data_sources = _dedupe_texts(_source_from_rows(comparable_rows), limit=8) or ["demo_units"]
    if len(comparable_rows) < 2:
        return (
            "No tengo cargado el total de metros cuadrados construidos por proyecto para compararlos entre sí.",
            False,
            ["demo_units.surface_total_m2"],
            data_sources,
            {
                "search_scope": "global",
                "comparison_scope": "projects",
                "comparison_basis": "demo_units_partial",
            },
        )

    top_row = comparable_rows[0]
    top_project_code = str(top_row.get("project_code") or "").strip().upper()
    top_project_name = str(top_row.get("project_name") or top_project_code).strip() or top_project_code
    top_surface = _format_surface(top_row.get("surface_total_m2_sum"))
    top_units = int(top_row.get("units_with_surface_count") or 0)
    answer = (
        f"Tomando solo las unidades demo que tengo cargadas hoy, {top_project_name} es el proyecto que más m² suma, "
        f"con {top_surface} m² sobre {top_units} unidades cargadas. "
        "Esto compara inventario demo parcial, no el total construido real de cada proyecto."
    )
    return (
        answer,
        True,
        ["demo_units.surface_total_m2"],
        data_sources,
        {
            "search_scope": "global",
            "comparison_scope": "projects",
            "comparison_basis": "demo_units_partial",
            "project_code": top_project_code,
            "project_name": top_project_name,
            "surface_total_m2_sum": top_surface,
            "compared_projects": len(comparable_rows),
        },
    )


def _metric_count_label(metric: str, value: int) -> str:
    count = int(value)
    if metric == "reserved_units":
        return f"{count} reserva" if count == 1 else f"{count} reservas"
    if metric == "available_units":
        return f"{count} unidad disponible" if count == 1 else f"{count} unidades disponibles"
    return f"{count} unidad" if count == 1 else f"{count} unidades"


def _project_metric_value_from_inventory_summary(metric: str, summary: dict[str, Any] | None) -> int | None:
    summary_obj = summary if isinstance(summary, dict) else {}
    if not summary_obj:
        return None
    direct_value = _to_float(summary_obj.get(metric))
    if direct_value is not None:
        return int(direct_value)
    breakdown = summary_obj.get("raw_status_breakdown_jsonb") if isinstance(summary_obj.get("raw_status_breakdown_jsonb"), dict) else None
    if metric == "reserved_units":
        if isinstance(breakdown, dict):
            return int(_to_float(breakdown.get("reserved")) or 0)
        return 0
    if metric == "available_units":
        if isinstance(breakdown, dict):
            return int(_to_float(breakdown.get("available")) or 0)
    if metric == "units_total" and isinstance(breakdown, dict) and breakdown:
        total = 0
        for value in breakdown.values():
            total += int(_to_float(value) or 0)
        return total
    return None


def _project_metric_inventory_rows(
    conn: Any,
    *,
    metric: str,
) -> tuple[list[dict[str, Any]], list[str], list[str], str]:
    config = PROJECT_COMPARISON_METRIC_CONFIG.get(metric) or {}
    missing_answer = str(config.get("missing_answer") or "No tengo ese dato cargado por proyecto para comparar.")
    fields = list(config.get("fields") or [])
    if metric not in {"reserved_units", "units_total", "available_units"}:
        return [], fields, [], missing_answer

    rows: list[dict[str, Any]] = []
    for project_row in repo.list_projects(conn):
        project_code = str(project_row.get("code") or "").strip().upper()
        if not project_code:
            continue
        summary = getattr(repo, "get_project_inventory_summary", lambda _c, _code: {})(conn, project_code) or {}
        metric_value = _project_metric_value_from_inventory_summary(metric, summary)
        if metric_value is None:
            continue
        rows.append(
            {
                "project_code": project_code,
                "project_name": str(project_row.get("name") or project_code).strip(),
                metric: int(metric_value),
                "_source_table": str(summary.get("_source_table") or "").strip(),
            }
        )

    rows.sort(key=lambda row: (-int(row.get(metric) or 0), str(row.get("project_name") or row.get("project_code") or "")))
    return rows, fields, _dedupe_texts(_source_from_rows(rows), limit=8), missing_answer


def _project_metric_breakdown_reply(
    conn: Any,
    *,
    metric: str,
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    rows, fields, data_sources, missing_answer = _project_metric_inventory_rows(conn, metric=metric)
    if len(rows) < 2:
        return (
            missing_answer,
            False,
            fields,
            data_sources,
            {
                "search_scope": "global",
                "comparison_scope": "projects",
                "comparison_metric": metric,
            },
        )

    breakdown = "; ".join(
        f"{str(row.get('project_name') or row.get('project_code') or '').strip()}: {_metric_count_label(metric, int(row.get(metric) or 0))}"
        for row in rows
    )
    return (
        breakdown + ".",
        True,
        fields,
        data_sources,
        {
            "search_scope": "global",
            "comparison_scope": "projects",
            "comparison_metric": metric,
            "compared_projects": len(rows),
            "comparison_mode": "breakdown",
        },
    )


def _project_metric_value_reply(
    project_name: str,
    *,
    metric: str,
    inventory_summary: dict[str, Any] | None,
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    config = PROJECT_COMPARISON_METRIC_CONFIG.get(metric) or {}
    missing_answer = str(config.get("missing_answer") or "No tengo ese dato cargado para este proyecto.")
    fields = list(config.get("fields") or [])
    value = _project_metric_value_from_inventory_summary(metric, inventory_summary)
    data_sources = _dedupe_texts(_source_from_profile_payload(inventory_summary), limit=8)
    if value is None:
        return (
            missing_answer,
            False,
            fields,
            data_sources,
            {
                "search_scope": "project",
                "comparison_metric": metric,
            },
        )
    if metric == "reserved_units":
        answer = f"{project_name} tiene {_metric_count_label(metric, value)}."
    elif metric == "available_units":
        answer = f"{project_name} tiene {_metric_count_label(metric, value)}."
    else:
        answer = f"{project_name} tiene {_metric_count_label(metric, value)}."
    return (
        answer,
        True,
        fields,
        data_sources,
        {
            "search_scope": "project",
            "comparison_metric": metric,
            "metric_value": int(value),
        },
    )


def _project_metric_comparison_reply(
    conn: Any,
    *,
    metric: str,
    mode: str = "leader",
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    if metric == "surface_total_m2":
        return _project_surface_comparison_reply(conn)
    if mode == "breakdown":
        return _project_metric_breakdown_reply(conn, metric=metric)

    rows, fields, data_sources, missing_answer = _project_metric_inventory_rows(conn, metric=metric)
    if len(rows) < 2:
        return (
            missing_answer,
            False,
            fields,
            data_sources,
            {
                "search_scope": "global",
                "comparison_scope": "projects",
                "comparison_metric": metric,
            },
        )

    top_row = rows[0]
    top_value = int(top_row.get(metric) or 0)
    tied_rows = [row for row in rows if int(row.get(metric) or 0) == top_value]
    top_project_code = str(top_row.get("project_code") or "").strip().upper()
    top_project_name = str(top_row.get("project_name") or top_project_code).strip() or top_project_code
    config = PROJECT_COMPARISON_METRIC_CONFIG.get(metric) or {}

    if len(tied_rows) == len(rows):
        breakdown = "; ".join(
            f"{str(row.get('project_name') or row.get('project_code') or '').strip()}: {_metric_count_label(metric, top_value)}"
            for row in rows
        )
        answer = f"Hoy {breakdown}; no hay un proyecto con más reservas que otro." if metric == "reserved_units" else f"Hoy {breakdown}; no hay un proyecto por encima del resto."
    elif len(tied_rows) > 1:
        tied_names = ", ".join(str(row.get("project_name") or row.get("project_code") or "").strip() for row in tied_rows)
        answer = f"Hay empate en reservas entre {tied_names} con {_metric_count_label(metric, top_value)} cada uno." if metric == "reserved_units" else f"Hay empate entre {tied_names} con {_metric_count_label(metric, top_value)} cada uno."
    else:
        answer_template = str(config.get("answer_template") or "")
        answer = answer_template.format(project_name=top_project_name, value=top_value) if answer_template else missing_answer

    return (
        answer,
        True,
        fields,
        data_sources,
        {
            "search_scope": "global",
            "comparison_scope": "projects",
            "comparison_metric": metric,
            "project_code": top_project_code,
            "project_name": top_project_name,
            "metric_value": top_value,
            "compared_projects": len(rows),
            "comparison_mode": "leader",
        },
    )


def _search_units_by_feature(
    conn: Any,
    *,
    feature_key: str,
    project_code: str | None = None,
    rooms: int | None = None,
    unit_code: str | None = None,
) -> list[dict[str, Any]]:
    rows = getattr(repo, "get_units_with_filters", lambda *_a, **_k: [])(
        conn,
        project_code=project_code,
        rooms=rooms,
        currency=None,
        unit_code=unit_code,
        feature_key=feature_key,
    ) or []

    project_rows = repo.list_projects(conn) if hasattr(conn, "execute") else []
    project_names = {
        str(item.get("code") or "").strip().upper(): str(item.get("name") or item.get("code") or "").strip()
        for item in project_rows
        if str(item.get("code") or "").strip()
    }
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        enriched["project_code"] = str(enriched.get("project_code") or project_code or "").strip().upper()
        enriched["project_name"] = str(
            enriched.get("project_name")
            or project_names.get(enriched["project_code"], enriched.get("project_code") or "")
        ).strip()
        enriched_rows.append(enriched)
    return enriched_rows


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
    asks_availability_short = bool(
        re.search(r"\b(hay|quedan|cuanto(?:s|as)?)\b", clean)
    )
    asks_which_short = bool(
        re.search(r"\b(cuales?|cu[aá]l(?:es)?)\b", clean)
    )
    asks_catalog_short = bool(
        re.search(r"\b(cuales?|cu[aá]l(?:es)?|el\s+otro)\b", clean)
    )
    availability_intents = {"AVAILABILITY", "AVAILABLE_UNITS", "UNIT_STATUS_BREAKDOWN", "TOTAL_UNITS"}
    if last_intent in availability_intents and asks_types:
        return "UNIT_TYPES", "followup_from_availability"
    if last_intent in availability_intents and asks_availability_short:
        return "AVAILABLE_UNITS", "followup_short_availability"
    if last_intent in {"PRICE", "UNIT_TYPES"} and asks_availability_short:
        return "AVAILABLE_UNITS", "followup_short_availability_from_price"
    if last_intent in {"PRICE", *availability_intents, "UNIT_TYPES"} and asks_which_short:
        return "UNIT_TYPES", "followup_short_unit_types"
    if last_intent in {*availability_intents, "UNIT_TYPES"} and asks_prices:
        return "PRICE", "followup_from_previous"
    if last_intent == "LIST_PROJECTS" and asks_catalog_short:
        return "LIST_PROJECTS", "followup_project_catalog"
    return None, "none"


def _is_total_units_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(r"\bentre\s+todas\s+cuantas?\s+son\b", clean):
        return True
    if re.search(
        r"\bentre\s+(?:ocupad(?:as|os)?|disponibles?|reservad(?:as|os)?)(?:\s+y\s+(?:ocupad(?:as|os)?|disponibles?|reservad(?:as|os)?))*\s+cuantas?\s+unidades?\s+son\b",
        clean,
    ):
        return True
    if re.search(r"\btotal(?:\s+general)?\s+de\s+unidades\b", clean):
        return True
    if re.search(r"\bcu[aá]l\s+es\s+el\s+total\b", clean):
        return True
    if re.search(r"\bcu[aá]l\s+es\s+el\s+total\s+de\s+unidades\b", clean):
        return True
    if re.search(r"\bcuantas?\s+unidades?\s+tiene\s+el\s+edificio\b", clean):
        return True
    if re.search(r"\bcuantas?\s+unidades?\s+(?:son|tiene)\b", clean):
        if re.search(r"\b(disponib|stock|quedan|hay\s+disponibles)\b", clean):
            return False
        return True
    return False


def _is_unit_status_breakdown_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if re.search(r"\b(desglose|reparte|repartido|por\s+estado)\b", clean):
        return True
    if re.search(
        r"\bcuantas?\s+(?:disponibles?|reservad(?:as|os)?|ocupad(?:as|os)?|vendid(?:as|os)?)\s+y\s+cuantas?\s+(?:disponibles?|reservad(?:as|os)?|ocupad(?:as|os)?|vendid(?:as|os)?)\b",
        clean,
    ):
        return True
    status_patterns = (
        r"\bdisponible(?:s)?\b",
        r"\breservad(?:a|as|o|os)?\b",
        r"\bocupad(?:a|as|o|os)?\b",
        r"\bno\s+disponible(?:s)?\b",
        r"\bvendid(?:a|as|o|os)?\b",
    )
    matched = sum(1 for pattern in status_patterns if re.search(pattern, clean))
    return matched >= 2 and bool(re.search(r"\b(cuanto(?:s|as)?|como|desglose|reparte|entre)\b", clean))


def _is_available_units_query(text: str) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False
    if _is_total_units_query(clean) or _is_unit_status_breakdown_query(clean):
        return False
    if re.search(r"\bque\s+stock\s+queda\b", clean):
        return True
    if re.search(r"\bhay\s+disponibles\b", clean):
        return True
    if re.search(r"\bcuantas?\s+hay\s+disponibles\b", clean):
        return True
    if re.search(r"\bcuantas?\s+quedan\b", clean):
        return True
    if re.search(r"\bcuantas?\s+unidades?\b", clean) and re.search(r"\bdisponib", clean):
        return True
    return bool(re.search(r"\b(stock|quedan|disponible(?:s)?)\b", clean))


def _detect_project_intent(
    text: str,
    *,
    summary: dict[str, Any] | None = None,
) -> tuple[str, bool, str]:
    if _is_visit_request_intent(text):
        return "VISIT_REQUEST", False, "visit_pattern"
    clean = _normalize_text(text)
    if not clean:
        return "GENERAL", False, "empty"
    project_comparison_request = _extract_project_comparison_request(clean) or {}
    if project_comparison_request:
        comparison_metric = str(project_comparison_request.get("metric") or "").strip()
        if comparison_metric == "surface_total_m2":
            return "PROJECT_COMPARISON_BY_SURFACE", False, "semantic_project_comparison_by_surface"
        return "PROJECT_COMPARISON_BY_METRIC", False, "semantic_project_comparison_by_metric"
    if _is_count_units_by_rooms_query(clean):
        return "COUNT_UNITS_BY_ROOMS", False, "semantic_count_units_by_rooms"
    if _is_list_units_by_rooms_query(clean):
        return "LIST_UNITS_BY_ROOMS", False, "semantic_list_units_by_rooms"
    if _is_total_units_query(clean):
        return "TOTAL_UNITS", False, "semantic_total_units"
    if _is_unit_status_breakdown_query(clean):
        return "UNIT_STATUS_BREAKDOWN", False, "semantic_unit_status_breakdown"
    if _is_available_units_query(clean):
        return "AVAILABLE_UNITS", False, "semantic_available_units"
    if _is_children_suitability_query(clean):
        return "CHILDREN_SUITABILITY", False, "semantic_children_suitability"
    if _is_pets_suitability_query(clean):
        return "PETS_SUITABILITY", False, "semantic_pets_suitability"
    if _is_warning_query(clean):
        return "SAFETY_WARNINGS", False, "semantic_safety_warnings"
    if _is_light_orientation_query(clean):
        return "LIGHT_ORIENTATION", False, "semantic_light_orientation"
    followup_intent, followup_reason = _followup_intent_from_summary(text, summary)
    if followup_intent:
        return followup_intent, True, followup_reason
    if re.search(r"\btipolog[ií]a", clean):
        return "UNIT_TYPES", False, "keyword_tipologia"
    if re.search(r"\bambientes?\b", clean) and re.search(r"\bdisponib|quedan|stock\b", clean):
        return "AVAILABLE_UNITS", False, "keyword_amb_disponible"
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


def _looks_like_typology_text(value: str) -> bool:
    clean = _normalize_text(value)
    if not clean:
        return False
    return bool(
        re.search(
            r"\b(mono(?:ambiente)?|[1-4]\s*y\s*[1-4]\s+ambientes|[1-4]\s+ambientes?|ambientes?|tipolog)",
            clean,
        )
    )


def _location_aliases(overview: dict[str, Any] | None, *, project_name: str = "") -> set[str]:
    row = overview if isinstance(overview, dict) else {}
    location_value = row.get("location_jsonb")
    location_data = location_value if isinstance(location_value, dict) else {}
    values: list[str] = []
    for key in (
        "address",
        "address_alt",
        "street",
        "direccion",
        "line1",
        "neighborhood",
        "barrio",
        "zone",
        "zona",
        "district",
        "city",
        "ciudad",
    ):
        raw = str(location_data.get(key) or row.get(key) or "").strip()
        if raw:
            values.append(raw)
    if project_name:
        values.append(project_name)

    aliases: set[str] = set()
    for raw in values:
        clean = _normalize_text(raw)
        if not clean:
            continue
        aliases.add(clean)
        for part in re.split(r"[,/()\-]+", clean):
            token = " ".join(part.split()).strip()
            if token:
                aliases.add(token)
    return aliases


def _looks_like_location_text(value: str, overview: dict[str, Any] | None, *, project_name: str = "") -> bool:
    clean = _normalize_text(value)
    if not clean:
        return False
    aliases = _location_aliases(overview, project_name=project_name)
    if clean in aliases:
        return True
    return any(clean == alias or clean in alias.split() for alias in aliases if alias)


def _looks_like_real_amenity(value: str, overview: dict[str, Any] | None, *, project_name: str = "") -> bool:
    clean = _normalize_text(value)
    if not clean:
        return False
    if _looks_like_typology_text(clean):
        return False
    if _looks_like_location_text(clean, overview, project_name=project_name):
        return False
    if clean in GENERIC_OVERVIEW_TERMS:
        return False
    return any(hint in clean for hint in REAL_AMENITY_HINTS)


def _extract_feature_typologies(
    conn: Any,
    project_code: str,
    overview: dict[str, Any] | None,
) -> list[str]:
    labels = _dedupe_texts(
        [
            row.get("label")
            or (
                f"{row.get('rooms')} ambientes"
                if row.get("rooms") not in (None, "", "null")
                else ""
            )
            for row in repo.get_unit_types(conn, project_code)
        ],
        limit=4,
    )
    if labels:
        return labels

    row = overview if isinstance(overview, dict) else {}
    return _dedupe_texts(_as_list(row.get("unit_types")), limit=4)


def _extract_real_amenities(
    overview: dict[str, Any] | None,
    marketing_assets: list[dict[str, Any]],
    *,
    project_name: str,
    overview_text: str,
) -> list[str]:
    row = overview if isinstance(overview, dict) else {}
    candidates: list[Any] = []
    candidates.extend(_as_list(row.get("amenities")))
    candidates.extend(_as_list(row.get("tags")))
    for asset in marketing_assets:
        candidates.extend(_as_list(asset.get("chips")))

    description_clean = _normalize_text(overview_text)
    amenities: list[str] = []
    for raw in candidates:
        text = " ".join(str(raw or "").split()).strip()
        clean = _normalize_text(text)
        if not text or not clean:
            continue
        if not _looks_like_real_amenity(text, overview, project_name=project_name):
            continue
        if clean in description_clean:
            continue
        if text in amenities:
            continue
        amenities.append(text)
        if len(amenities) >= 4:
            break
    return amenities


def _build_project_feature_answer(
    conn: Any,
    *,
    project_code: str,
    project_name: str,
    overview: dict[str, Any] | None,
    marketing_assets: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    description = _overview_description(overview)
    marketing_copies = _extract_marketing_copies(marketing_assets)
    lead_text = description or (marketing_copies[0] if marketing_copies else "")
    fields_used: list[str] = []
    parts: list[str] = []

    if lead_text:
        if description:
            parts.append(f"{project_name}: {description}")
            fields_used.append("projects.description")
        else:
            parts.append(lead_text)
            fields_used.append("marketing_assets.short_copy")

    typologies = _extract_feature_typologies(conn, project_code, overview)
    if typologies and "ambiente" not in _normalize_text(lead_text):
        parts.append(f"Hoy tengo cargadas tipologías de {', '.join(typologies[:3])}.")
        fields_used.append("unit_types")

    amenities = _extract_real_amenities(
        overview,
        marketing_assets,
        project_name=project_name,
        overview_text=lead_text,
    )
    if amenities:
        parts.append(f"Entre los amenities reales veo {', '.join(amenities)}.")
        fields_used.append("project.amenities")

    if not parts:
        location_text = _overview_location_text(overview)
        if location_text:
            parts.append(f"{project_name} está en {location_text}.")
            fields_used.append("projects.location_jsonb")

    return " ".join(parts), fields_used


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


def _inventory_status_label(value: Any, count: int) -> str:
    clean = _normalize_text(str(value or ""))
    labels = {
        "available": ("disponible", "disponibles"),
        "disponible": ("disponible", "disponibles"),
        "reserved": ("reservada", "reservadas"),
        "reservada": ("reservada", "reservadas"),
        "reservado": ("reservada", "reservadas"),
        "unavailable": ("no disponible", "no disponibles"),
        "no disponible": ("no disponible", "no disponibles"),
        "no_disponible": ("no disponible", "no disponibles"),
        "occupied": ("ocupada", "ocupadas"),
        "ocupada": ("ocupada", "ocupadas"),
        "ocupado": ("ocupada", "ocupadas"),
        "sold": ("vendida", "vendidas"),
        "vendida": ("vendida", "vendidas"),
        "vendido": ("vendida", "vendidas"),
    }
    singular, plural = labels.get(clean, (str(value or "sin estado"), str(value or "sin estado")))
    return singular if int(count or 0) == 1 else plural


def _format_inventory_count(count: int, status: str) -> str:
    return f"{int(count)} {_inventory_status_label(status, int(count))}"


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


def _global_highest_price_row(conn: Any) -> dict[str, Any] | None:
    best_row: dict[str, Any] | None = None
    best_project_name = ""
    for project in repo.list_projects(conn):
        project_code = str(project.get("code") or "").strip()
        if not project_code:
            continue
        prices = repo.get_prices_by_rooms(conn, project_code, rooms=None, currency=None)
        for row in prices:
            price_value = _to_float(row.get("price"))
            if price_value is None:
                continue
            if best_row is not None and price_value <= float(best_row["price"]):
                continue
            best_row = {
                "project_code": project_code,
                "project_name": str(project.get("name") or project_code).strip(),
                "price": price_value,
                "currency": str(row.get("currency") or "").strip().upper() or "USD",
                "rooms": row.get("rooms"),
                "unit_ref": row.get("unit_ref"),
                "_source_table": str(row.get("_source_table") or "").strip() or "demo_units",
            }
            best_project_name = str(project.get("name") or project_code).strip()
    if best_row is None:
        return None
    best_row["project_name"] = best_project_name or str(best_row.get("project_name") or "").strip()
    return best_row


def _price_breakdown_by_rooms(
    conn: Any,
    project_code: str,
) -> tuple[list[str], list[str], list[str]]:
    rows = repo.get_prices_by_rooms(conn, project_code, rooms=None, currency=None)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        price_value = _to_float(row.get("price"))
        if price_value is None:
            continue
        rooms_raw = row.get("rooms")
        label = ""
        try:
            rooms_int = int(str(rooms_raw))
            label = f"{rooms_int} ambiente" if rooms_int == 1 else f"{rooms_int} ambientes"
        except Exception:  # noqa: BLE001
            label = str(rooms_raw or "").strip() or "sin tipología"
        bucket = grouped.setdefault(
            label,
            {
                "low": price_value,
                "high": price_value,
                "currency": str(row.get("currency") or "").strip().upper() or "USD",
                "order": int(str(rooms_raw or "999").strip() or "999") if str(rooms_raw or "").strip().isdigit() else 999,
            },
        )
        bucket["low"] = min(float(bucket["low"]), price_value)
        bucket["high"] = max(float(bucket["high"]), price_value)

    parts: list[str] = []
    for label, bucket in sorted(grouped.items(), key=lambda item: (int(item[1]["order"]), item[0])):
        currency = str(bucket.get("currency") or "USD")
        low = float(bucket["low"])
        high = float(bucket["high"])
        if abs(high - low) < 1:
            parts.append(f"{label}: {currency} {_format_price(low)}")
        else:
            parts.append(f"{label}: {currency} {_format_price(low)}–{_format_price(high)}")
    return parts, ["prices.price", "prices.currency"], _dedupe_texts([row.get("_source_table") for row in rows], limit=4)


def _list_projects_brief(conn: Any, *, exclude_codes: list[str] | None = None) -> str:
    rows = repo.list_projects(conn)
    excluded = {str(code or "").strip().upper() for code in (exclude_codes or []) if str(code or "").strip()}
    if excluded:
        filtered = [row for row in rows if str(row.get("code") or "").strip().upper() not in excluded]
        if filtered:
            rows = filtered
    labels = _dedupe_texts(
        [row.get("name") or row.get("code") for row in rows],
        limit=6,
    )
    if not labels:
        return _build_vera_project_fallback()
    prefix = "Tengo estos otros proyectos: " if excluded else "Hoy tengo estos proyectos: "
    return prefix + ", ".join(labels) + ". ¿Sobre cuál querés que te pase detalle?"


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
    recent_messages: list[dict[str, Any]] | None = None,
    semantic_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary_obj = _ticket_summary(detail)
    semantic = semantic_resolution if isinstance(semantic_resolution, dict) else _semantic_intent_resolver(
        question,
        detail=detail,
        recent_messages=recent_messages,
        summary=summary_obj,
    )
    intent = str(semantic.get("intent") or "UNKNOWN").strip().upper() or "UNKNOWN"
    is_followup = bool(semantic.get("followup"))
    intent_reason = str(semantic.get("reason") or "semantic_unknown").strip() or "semantic_unknown"
    slots = _extract_query_slots(question)
    selected_project = _ticket_selected_project(detail)
    project_code = selected_project["code"]
    project_name = selected_project["name"]
    summary_patch: dict[str, Any] = _clear_pending_offer_patch()
    summary_patch.update(_clear_pending_question_patch())
    summary_patch["unresolved_topic"] = None
    summary_patch["last_search_scope"] = "project" if project_code else None
    chosen_project_code = str(semantic.get("chosen_project") or "").strip().upper()
    pending_offer = _pending_offer_from_summary(summary_obj)
    pending_question = _pending_question_from_summary(summary_obj)
    feature_key = str(semantic.get("feature_key") or "").strip()
    comparison_metric = str(semantic.get("comparison_metric") or "").strip()
    comparison_mode = str(semantic.get("comparison_mode") or "").strip().lower()
    unit_code = str(semantic.get("unit_code") or "").strip().upper()
    search_scope = str(semantic.get("search_scope") or "").strip().lower()
    surface_filter = semantic.get("surface_filter") if isinstance(semantic.get("surface_filter"), dict) else {}
    result_set_ranking = semantic.get("result_set_ranking") if isinstance(semantic.get("result_set_ranking"), dict) else {}
    result_set_sort = semantic.get("result_set_sort") if isinstance(semantic.get("result_set_sort"), dict) else {}
    result_set_extreme = semantic.get("result_set_extreme") if isinstance(semantic.get("result_set_extreme"), dict) else {}
    time_preference = str(semantic.get("time_preference") or "").strip().lower()
    excluded_project_codes = [
        str(code or "").strip().upper()
        for code in (semantic.get("excluded_project_codes") or [])
        if str(code or "").strip()
    ]
    semantic_rooms_count = semantic.get("rooms_count")
    try:
        semantic_rooms_count = int(semantic_rooms_count) if semantic_rooms_count is not None else None
    except Exception:  # noqa: BLE001
        semantic_rooms_count = None
    last_rooms_query = _last_rooms_query(summary_obj)
    active_filter = _last_active_filter(summary_obj)

    if chosen_project_code and intent != "LIST_PROJECTS":
        project_row = repo.get_project_by_code(conn, chosen_project_code)
        if project_row:
            project_code = str(project_row.get("code") or "").strip()
            project_name = str(project_row.get("name") or "").strip()
            summary_patch["selected_project"] = {
                "id": project_row.get("id"),
                "code": project_code,
                "name": project_name,
                "matched_alias": chosen_project_code,
            }
            repo.update_ticket_activity(
                conn,
                ticket_id,
                project_id=str(project_row.get("id") or "") or None,
            )

    if pending_offer.get("project") and not project_code:
        pending_project_row = repo.get_project_by_code(conn, pending_offer["project"])
        if pending_project_row:
            project_code = str(pending_project_row.get("code") or "").strip()
            project_name = str(pending_project_row.get("name") or "").strip()
            summary_patch["selected_project"] = {
                "id": pending_project_row.get("id"),
                "code": project_code,
                "name": project_name,
            }

    if intent == "AFFIRM":
        pending_type = str(pending_offer.get("type") or "").strip().upper()
        pending_project_code = str(pending_offer.get("project") or project_code or "").strip().upper()
        if pending_type == "PRICE_BREAKDOWN_BY_ROOMS" and pending_project_code:
            if pending_project_code != project_code or not project_name:
                project_row = repo.get_project_by_code(conn, pending_project_code)
                if project_row:
                    project_code = str(project_row.get("code") or pending_project_code).strip().upper()
                    project_name = str(project_row.get("name") or pending_project_code).strip()
                    summary_patch["selected_project"] = {
                        "id": project_row.get("id"),
                        "code": project_code,
                        "name": project_name,
                    }
            parts, fields_used, data_sources = _price_breakdown_by_rooms(conn, pending_project_code)
            if parts:
                return {
                    "variant": "pending_offer_price_breakdown",
                    "intent": intent,
                    "followup": True,
                    "reason": "pending_offer_price_breakdown",
                    "answer": f"En {project_name or pending_project_code} hoy tengo: " + "; ".join(parts) + ".",
                    "found": True,
                    "fields_used": fields_used,
                    "data_sources": data_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": project_code or pending_project_code,
                    "project_name": project_name,
                    "result_slots": {},
                }
            return {
                "variant": "pending_offer_price_breakdown",
                "intent": intent,
                "followup": True,
                "reason": "pending_offer_price_breakdown_missing_data",
                "answer": f"No veo un desglose más fino cargado para {project_name or pending_project_code} ahora mismo.",
                "found": False,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": project_code or pending_project_code,
                "project_name": project_name,
                "result_slots": {},
            }
        return {
            "variant": "affirm_ack",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": _build_vera_affirm_reply(),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "GREETING":
        return {
            "variant": "social_greeting",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": _build_vera_greeting_reply(conn, project_name),
            "found": True,
            "fields_used": ["projects.list"] if not project_name else [],
            "data_sources": ["projects"] if not project_name else [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "ACKNOWLEDGEMENT":
        if search_scope == "global":
            summary_patch["last_search_scope"] = "global"
            return {
                "variant": "social_ack",
                "intent": intent,
                "followup": bool(is_followup),
                "reason": intent_reason,
                "answer": "Dale, sigo mirando en todos los proyectos.",
                "found": True,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        return {
            "variant": "social_ack",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": _build_vera_ack_reply(question, project_name),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "TIME_PREFERENCE" and str(pending_question.get("type") or "").strip().upper() == "TIME_PREFERENCE":
        return {
            "variant": "visit_time_preference",
            "intent": intent,
            "followup": True,
            "reason": intent_reason,
            "answer": _build_vera_time_preference_reply(time_preference or "any"),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": {
                **summary_patch,
                "time_preference": time_preference or "any",
            },
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {
                "time_preference": time_preference or "any",
            },
        }

    if intent == "GLOBAL_PRICE_EXTREME":
        extreme_row = _global_highest_price_row(conn)
        if extreme_row is None:
            return {
                "variant": "global_price_extreme",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": "No veo precios globales cargados ahora mismo para compararte.",
                "found": False,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        extreme_project_code = str(extreme_row.get("project_code") or "").strip().upper()
        extreme_project_name = str(extreme_row.get("project_name") or extreme_project_code).strip()
        price_value = float(extreme_row["price"])
        currency = str(extreme_row.get("currency") or "USD")
        rooms_value = str(extreme_row.get("rooms") or "").strip()
        room_text = ""
        if rooms_value.isdigit():
            rooms_int = int(rooms_value)
            room_text = f" de {rooms_int} ambiente" if rooms_int == 1 else f" de {rooms_int} ambientes"
        summary_patch.update(
            _build_pending_offer_patch(
                offer_type="PRICE_BREAKDOWN_BY_ROOMS",
                project_code=extreme_project_code,
                intent_source=intent,
                payload={"currency": currency},
            )
        )
        return {
            "variant": "global_price_extreme",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": (
                f"La unidad con precio más alto que tengo cargada hoy está en {extreme_project_name}, "
                f"con un valor de {currency} {_format_price(price_value)}{room_text}. "
                "Si querés, te lo desgloso por ambientes."
            ),
            "found": True,
            "fields_used": ["prices.price", "prices.currency"],
            "data_sources": [str(extreme_row.get("_source_table") or "demo_units")],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": extreme_project_code,
            "project_name": extreme_project_name,
            "result_slots": {},
        }

    if intent == "GLOBAL_UNIT_FILTER_SEARCH":
        min_surface_total_m2 = _to_float(surface_filter.get("value")) if surface_filter else None
        answer, found, filter_fields, filter_sources, filter_slots = _global_surface_filter_reply(
            conn,
            question=question,
            min_surface_total_m2=min_surface_total_m2,
            rooms=slots.get("ambientes"),
            feature_key=feature_key or None,
        )
        summary_patch["last_search_scope"] = "global"
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type="surface",
                filter_payload={
                    "min_surface_total_m2": min_surface_total_m2,
                    "rooms_count": slots.get("ambientes"),
                },
                scope="global",
                origin_intent=intent,
            )
        )
        result_set_patch = filter_slots.pop("result_set_patch", None) if isinstance(filter_slots, dict) else None
        if isinstance(result_set_patch, dict):
            summary_patch.update(result_set_patch)
        return {
            "variant": "global_unit_filter_search",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": answer,
            "found": found,
            "fields_used": filter_fields,
            "data_sources": filter_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": "",
            "project_name": "",
            "result_slots": filter_slots,
        }

    if intent == "PROJECT_COMPARISON_BY_SURFACE":
        answer, found, comparison_fields, comparison_sources, comparison_slots = _project_surface_comparison_reply(conn)
        summary_patch["last_search_scope"] = "global"
        summary_patch.update(_clear_unit_result_context_patch())
        return {
            "variant": "project_comparison_surface",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": answer,
            "found": found,
            "fields_used": comparison_fields,
            "data_sources": comparison_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": str(comparison_slots.get("project_code") or ""),
            "project_name": str(comparison_slots.get("project_name") or ""),
            "result_slots": comparison_slots,
        }

    if intent == "PROJECT_COMPARISON_BY_METRIC":
        answer, found, comparison_fields, comparison_sources, comparison_slots = _project_metric_comparison_reply(
            conn,
            metric=comparison_metric,
            mode=comparison_mode or "leader",
        )
        summary_patch["last_search_scope"] = "global"
        summary_patch.update(_clear_unit_result_context_patch())
        return {
            "variant": "project_comparison_metric",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": answer,
            "found": found,
            "fields_used": comparison_fields,
            "data_sources": comparison_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": str(comparison_slots.get("project_code") or ""),
            "project_name": str(comparison_slots.get("project_name") or ""),
            "result_slots": comparison_slots,
        }

    if intent == "PROJECT_METRIC_VALUE":
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
        inventory_summary = repo.get_project_inventory_summary(conn, project_code)
        answer, found, metric_fields, metric_sources, metric_slots = _project_metric_value_reply(
            project_name or project_code,
            metric=comparison_metric,
            inventory_summary=inventory_summary,
        )
        summary_patch["last_search_scope"] = "project"
        summary_patch.update(_clear_unit_result_context_patch(last_subject_type="project"))
        return {
            "variant": "project_metric_value",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": answer,
            "found": found,
            "fields_used": metric_fields,
            "data_sources": metric_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": metric_slots,
        }

    if intent in {"COUNT_UNITS_BY_ROOMS", "LIST_UNITS_BY_ROOMS", "GLOBAL_SCOPE_OVERRIDE"}:
        target_rooms = semantic_rooms_count or slots.get("ambientes") or last_rooms_query.get("rooms_count")
        target_intent = intent if intent != "GLOBAL_SCOPE_OVERRIDE" else str(last_rooms_query.get("intent") or "").strip().upper()
        target_intent = target_intent or "LIST_UNITS_BY_ROOMS"
        target_global_scope = search_scope == "global" or intent == "GLOBAL_SCOPE_OVERRIDE"
        if target_rooms is None:
            return {
                "variant": "project_qa",
                "intent": intent,
                "followup": bool(intent == "GLOBAL_SCOPE_OVERRIDE" or is_followup),
                "reason": intent_reason,
                "answer": "Decime qué tipología querés revisar: mono, 1, 2, 3 o 4 ambientes.",
                "found": False,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }

        if target_global_scope:
            rows = getattr(repo, "get_global_units_by_rooms", repo.list_units_by_rooms)(
                conn,
                rooms_count=target_rooms,
                limit=None,
            ) or []
            data_sources = _dedupe_texts(_source_from_profile_rows(rows), limit=8) or ["demo_units"]
            summary_patch["last_search_scope"] = "global"
            summary_patch.update(
                _build_rooms_query_summary_patch(
                    rooms_count=target_rooms,
                    query_intent=target_intent,
                    search_scope="global",
                )
            )
            summary_patch.update(
                _build_active_filter_summary_patch(
                    filter_type="rooms",
                    filter_payload={"rooms_count": target_rooms},
                    scope="global",
                    origin_intent=target_intent,
                )
            )
            result_slots = {
                "search_scope": "global",
                "rooms_count": int(target_rooms),
                "matches_count": len(rows),
            }
            if target_intent == "COUNT_UNITS_BY_ROOMS":
                return {
                    "variant": "global_units_by_rooms_count",
                    "intent": target_intent,
                    "followup": bool(intent == "GLOBAL_SCOPE_OVERRIDE" or is_followup),
                    "reason": intent_reason,
                    "answer": _count_units_by_rooms_reply(
                        rooms_count=target_rooms,
                        count=len(rows),
                        global_scope=True,
                    ),
                    "found": True,
                    "fields_used": ["demo_units.rooms_count", "demo_units.availability_status"],
                    "data_sources": data_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": "",
                    "project_name": "",
                    "result_slots": result_slots,
                }
            summary_patch.update(_result_set_summary_patch(rows, origin_intent=target_intent))
            result_slots["result_mode"] = "list"
            return {
                "variant": "global_units_by_rooms_list",
                "intent": target_intent,
                "followup": bool(intent == "GLOBAL_SCOPE_OVERRIDE" or is_followup),
                "reason": intent_reason,
                "answer": _list_units_by_rooms_reply(
                    rows,
                    rooms_count=target_rooms,
                    global_scope=True,
                ),
                "found": True,
                "fields_used": ["demo_units.rooms_count", "demo_units.surface_total_m2", "demo_units.list_price", "demo_units.availability_status"],
                "data_sources": data_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": result_slots,
            }

        if not project_code:
            reply = _build_missing_project_reply(selected_project["prompted_once"])
            summary_patch["project_prompted_once"] = True
            return {
                "variant": "choose_project_once" if not selected_project["prompted_once"] else "project_handoff",
                "intent": target_intent,
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

        rows = getattr(repo, "list_units_by_rooms")(
            conn,
            project_code=project_code,
            rooms_count=target_rooms,
            limit=None,
        ) or []
        data_sources = _dedupe_texts(_source_from_profile_rows(rows), limit=8) or ["demo_units"]
        summary_patch["last_search_scope"] = "project"
        summary_patch.update(
            _build_rooms_query_summary_patch(
                rooms_count=target_rooms,
                query_intent=target_intent,
                search_scope="project",
            )
        )
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type="rooms",
                filter_payload={"rooms_count": target_rooms},
                scope="project",
                origin_intent=target_intent,
                project_code=project_code,
                project_name=project_name,
            )
        )
        result_slots = {
            "search_scope": "project",
            "rooms_count": int(target_rooms),
            "matches_count": len(rows),
        }
        if target_intent == "COUNT_UNITS_BY_ROOMS":
            return {
                "variant": "project_units_by_rooms_count",
                "intent": target_intent,
                "followup": is_followup,
                "reason": intent_reason,
                "answer": _count_units_by_rooms_reply(
                    rooms_count=target_rooms,
                    count=len(rows),
                    project_name=project_name,
                ),
                "found": True,
                "fields_used": ["demo_units.rooms_count", "demo_units.availability_status"],
                "data_sources": data_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": project_code,
                "project_name": project_name,
                "result_slots": result_slots,
            }
        summary_patch.update(_result_set_summary_patch(rows, origin_intent=target_intent))
        result_slots["result_mode"] = "list"
        return {
            "variant": "project_units_by_rooms_list",
            "intent": target_intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _list_units_by_rooms_reply(
                rows,
                rooms_count=target_rooms,
                project_name=project_name,
            ),
            "found": True,
            "fields_used": ["demo_units.rooms_count", "demo_units.surface_total_m2", "demo_units.list_price", "demo_units.availability_status"],
            "data_sources": data_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": result_slots,
        }

    if intent == "UNIT_DETAIL_FEATURE_CHECK" and feature_key and unit_code:
        unit_rows = _search_units_by_feature(
            conn,
            feature_key=feature_key,
            unit_code=unit_code,
        )
        unit_row = getattr(repo, "find_demo_unit_by_code", lambda _c, _u: None)(conn, unit_code)
        if unit_row is None:
            return {
                "variant": "unit_feature_check",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": f"No encuentro la unidad {unit_code} cargada en este momento.",
                "found": False,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        enriched_project_code = str(unit_row.get("project_code") or "").strip().upper()
        enriched_project_name = str(unit_row.get("project_name") or "").strip()
        if not enriched_project_name:
            project_row = repo.get_project_by_code(conn, enriched_project_code)
            enriched_project_name = str((project_row or {}).get("name") or enriched_project_code).strip()
        summary_patch["selected_project"] = {
            "id": None,
            "code": enriched_project_code,
            "name": enriched_project_name,
        }
        summary_patch.update(_unit_subject_summary_patch(unit_row))
        feature_sources = _dedupe_texts(_source_from_profile_rows(unit_rows), limit=8) or ["demo_units"]
        if unit_rows:
            feature_row = unit_rows[0]
            extras = [
                item for item in _feature_values_from_unit(feature_row) if item != _normalize_text(_feature_label(feature_key))
            ]
            extra_text = f" y además {extras[0]}" if extras else ""
            return {
                "variant": "unit_feature_check",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": f"Sí, la unidad {unit_code} tiene {_feature_label(feature_key)}{extra_text}.",
                "found": True,
                "fields_used": _feature_fields_used(feature_key),
                "data_sources": feature_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": enriched_project_code,
                "project_name": enriched_project_name,
                "result_slots": {},
            }
        return {
            "variant": "unit_feature_check",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": f"No, la unidad {unit_code} no figura con {_feature_label(feature_key)} en la información cargada.",
            "found": True,
            "fields_used": _feature_fields_used(feature_key),
            "data_sources": feature_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": enriched_project_code,
            "project_name": enriched_project_name,
            "result_slots": {},
        }

    if intent in {"CHILDREN_SUITABILITY", "PETS_SUITABILITY", "SAFETY_WARNINGS", "LIGHT_ORIENTATION"} and unit_code:
        unit_row = _unit_row_for_code(conn, unit_code)
        if unit_row is None:
            return {
                "variant": "unit_profile_missing",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": f"No encuentro la unidad {unit_code} cargada en este momento.",
                "found": False,
                "fields_used": [],
                "data_sources": [],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        enriched_project_code = str(unit_row.get("project_code") or "").strip().upper()
        enriched_project_name = _unit_project_name(conn, unit_row)
        summary_patch["selected_project"] = {
            "id": None,
            "code": enriched_project_code,
            "name": enriched_project_name,
        }
        summary_patch.update(_unit_subject_summary_patch(unit_row))
        data_sources = _dedupe_texts(_source_from_profile_rows([unit_row]), limit=8) or ["demo_unit_profile", "demo_units"]
        fields_used = ["demo_unit_profile"]
        if intent == "CHILDREN_SUITABILITY":
            answer = _unit_children_suitability_reply(unit_code, unit_row)
        elif intent == "PETS_SUITABILITY":
            answer = _unit_pets_suitability_reply(
                conn,
                unit_code=unit_code,
                unit_row=unit_row,
                question=question,
            )
        elif intent == "SAFETY_WARNINGS":
            answer = _unit_warnings_reply(unit_code, unit_row, question)
        else:
            answer = _unit_light_orientation_reply(unit_code, unit_row, question)
        return {
            "variant": "unit_profile_answer",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": answer,
            "found": True,
            "fields_used": fields_used,
            "data_sources": data_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": enriched_project_code,
            "project_name": enriched_project_name,
            "result_slots": {},
        }

    if intent == "PROJECT_UNIT_SEARCH_BY_FEATURE" and feature_key:
        rooms = slots.get("ambientes")
        target_project_code = chosen_project_code or project_code
        target_project_row = repo.get_project_by_code(conn, target_project_code) if target_project_code else None
        target_project_name = str((target_project_row or {}).get("name") or project_name or target_project_code or "").strip()
        matches = _search_units_by_feature(
            conn,
            feature_key=feature_key,
            project_code=target_project_code,
            rooms=rooms,
        )
        feature_sources = _dedupe_texts(_source_from_profile_rows(matches), limit=8) or ["demo_units"]
        summary_patch["selected_project"] = {
            "id": (target_project_row or {}).get("id"),
            "code": target_project_code,
            "name": target_project_name,
        }
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type="feature",
                filter_payload={"feature_key": feature_key, "rooms_count": rooms},
                scope="project",
                origin_intent=intent,
                project_code=target_project_code,
                project_name=target_project_name,
            )
        )
        if matches:
            example = _format_unit_example(matches[0], include_project=False)
            rooms_text = f" de {rooms} ambientes" if rooms is not None else ""
            return {
                "variant": "project_unit_feature_search",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": (
                    f"Sí, en {target_project_name} hoy veo unidades{rooms_text} con {_feature_label(feature_key)}. "
                    f"Por ejemplo, {example}."
                ),
                "found": True,
                "fields_used": [*_feature_fields_used(feature_key), "demo_units.list_price"],
                "data_sources": feature_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": target_project_code,
                "project_name": target_project_name,
                "result_slots": {},
            }
        rooms_text = f" de {rooms} ambientes" if rooms is not None else ""
        return {
            "variant": "project_unit_feature_search",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": f"No, en {target_project_name} no tengo cargadas unidades{rooms_text} con {_feature_label(feature_key)}.",
            "found": True,
            "fields_used": _feature_fields_used(feature_key),
            "data_sources": feature_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": target_project_code,
            "project_name": target_project_name,
            "result_slots": {},
        }

    if intent == "GLOBAL_UNIT_SEARCH_BY_FEATURE" and feature_key:
        rooms = slots.get("ambientes")
        matches = _search_units_by_feature(
            conn,
            feature_key=feature_key,
            project_code=None,
            rooms=rooms,
        )
        feature_sources = _dedupe_texts(_source_from_profile_rows(matches), limit=8) or ["demo_units"]
        summary_patch["last_search_scope"] = "global"
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type="feature",
                filter_payload={"feature_key": feature_key, "rooms_count": rooms},
                scope="global",
                origin_intent=intent,
            )
        )
        if not matches:
            rooms_text = f" de {rooms} ambientes" if rooms is not None else ""
            return {
                "variant": "global_unit_feature_search",
                "intent": intent,
                "followup": False,
                "reason": intent_reason,
                "answer": f"No veo unidades{rooms_text} con {_feature_label(feature_key)} cargadas ahora mismo.",
                "found": False,
                "fields_used": _feature_fields_used(feature_key),
                "data_sources": feature_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        by_project: dict[str, int] = {}
        for row in matches:
            code = str(row.get("project_code") or "").strip().upper()
            by_project[code] = by_project.get(code, 0) + 1
        project_name_map: dict[str, str] = {}
        for row in matches:
            code = str(row.get("project_code") or "").strip().upper()
            if code and code not in project_name_map:
                project_name_map[code] = str(row.get("project_name") or code).strip()
        project_labels = [project_name_map[code] for code in sorted(by_project.keys()) if code in project_name_map]
        examples = [_format_unit_example(row, include_project=True) for row in matches[:3]]
        rooms_text = f" de {rooms} ambientes" if rooms is not None else ""
        return {
            "variant": "global_unit_feature_search",
            "intent": intent,
            "followup": False,
            "reason": intent_reason,
            "answer": (
                f"Hoy veo unidades{rooms_text} con {_feature_label(feature_key)} en {', '.join(project_labels)}. "
                f"Por ejemplo: {'; '.join(examples)}."
            ),
            "found": True,
            "fields_used": [*_feature_fields_used(feature_key), "demo_units.list_price"],
            "data_sources": feature_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": "",
            "project_name": "",
            "result_slots": {},
        }

    if intent == "LIST_PROJECTS_MATCHING_ACTIVE_FILTER":
        matches = getattr(repo, "list_projects_matching_active_filter")(
            conn,
            filter_type=active_filter.get("type") or "",
            filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
            scope=active_filter.get("scope") or "global",
            project_code=active_filter.get("project_code") or None,
        ) or []
        data_sources = _dedupe_texts(
            [source for row in matches for source in (row.get("_source_tables") or [])],
            limit=8,
        ) or ["demo_units"]
        summary_patch["last_search_scope"] = str(active_filter.get("scope") or "global").strip().lower() or "global"
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type=active_filter.get("type") or "",
                filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
                scope=active_filter.get("scope") or "global",
                origin_intent=intent,
                project_code=active_filter.get("project_code") or None,
                project_name=active_filter.get("project_name") or None,
            )
        )
        return {
            "variant": "projects_matching_active_filter",
            "intent": intent,
            "followup": True,
            "reason": intent_reason,
            "answer": _projects_matching_active_filter_reply(matches, active_filter=active_filter),
            "found": bool(matches),
            "fields_used": ["demo_units.project_code", "demo_units.rooms_count", "demo_units.availability_status"],
            "data_sources": data_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": "",
            "project_name": "",
            "result_slots": {
                "search_scope": str(active_filter.get("scope") or "global").strip().lower() or "global",
                "matching_project_codes": [str(row.get("project_code") or "").strip().upper() for row in matches if str(row.get("project_code") or "").strip()],
            },
        }

    if intent == "CLARIFY":
        answer = str(
            semantic.get("clarification_question")
            or _build_vera_contact_clarification_reply()
        )
        return {
            "variant": "intent_clarify",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": answer,
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "HUMAN_CONTACT_REQUEST":
        return {
            "variant": "human_contact_requested",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _build_vera_human_contact_reply(),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "VISIT_REQUEST":
        return {
            "variant": "visit_requested",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _build_vera_visit_requested_reply(),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": {
                **summary_patch,
                **_build_pending_question_patch(
                    question_type="TIME_PREFERENCE",
                    payload={"source_intent": intent},
                ),
            },
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "LIST_PROJECTS":
        return {
            "variant": "project_catalog",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _list_projects_brief(conn, exclude_codes=excluded_project_codes),
            "found": True,
            "fields_used": ["projects.list"],
            "data_sources": ["projects"],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent == "PROJECT_SELECT" and project_code:
        return {
            "variant": "project_selected",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _build_vera_project_selected_reply(project_name or project_code),
            "found": True,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": project_code,
            "project_name": project_name,
            "result_slots": {},
        }

    if intent in {"ACTIVE_SET_FILTER_BY_FEATURE", "ACTIVE_SET_FEATURE_EXTREME"} and feature_key:
        rows = _active_context_units(conn, summary_obj)
        data_sources = _dedupe_texts(_source_from_profile_rows(rows), limit=8) or [str(item) for item in summary_obj.get("last_data_sources") or ["demo_units"]]
        base_active_filter = active_filter
        if not base_active_filter.get("type"):
            base_active_filter = {
                "type": "feature",
                "payload": {},
                "scope": str(summary_obj.get("last_search_scope") or "project").strip().lower() or "project",
                "origin_intent": intent,
                "project_code": project_code,
                "project_name": project_name,
            }
        enriched_active_filter = _apply_feature_to_active_filter(base_active_filter, feature_key)
        summary_patch["last_search_scope"] = str(enriched_active_filter.get("scope") or summary_patch.get("last_search_scope") or "project")
        if not rows:
            summary_patch.update(
                _build_active_filter_summary_patch(
                    filter_type=enriched_active_filter.get("type") or "feature",
                    filter_payload=enriched_active_filter.get("payload") if isinstance(enriched_active_filter.get("payload"), dict) else {},
                    scope=enriched_active_filter.get("scope") or "project",
                    origin_intent=intent,
                    project_code=enriched_active_filter.get("project_code") or None,
                    project_name=enriched_active_filter.get("project_name") or None,
                )
            )
            return {
                "variant": "active_set_feature_filter",
                "intent": intent,
                "followup": True,
                "reason": intent_reason,
                "answer": "No tengo un conjunto activo de unidades para filtrar ahora mismo.",
                "found": False,
                "fields_used": [],
                "data_sources": data_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }
        if not _feature_data_available_for_result_set(rows, feature_key):
            return {
                "variant": "active_set_feature_filter",
                "intent": intent,
                "followup": True,
                "reason": intent_reason,
                "answer": f"No tengo dato suficiente para confirmar {_feature_label(feature_key)} dentro de ese grupo.",
                "found": False,
                "fields_used": _feature_fields_used(feature_key),
                "data_sources": data_sources,
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": "",
                "project_name": "",
                "result_slots": {},
            }

        filtered_rows = [row for row in rows if _unit_matches_feature(row, feature_key)]
        summary_patch.update(
            _build_active_filter_summary_patch(
                filter_type=enriched_active_filter.get("type") or "feature",
                filter_payload=enriched_active_filter.get("payload") if isinstance(enriched_active_filter.get("payload"), dict) else {},
                scope=enriched_active_filter.get("scope") or "project",
                origin_intent=intent,
                project_code=enriched_active_filter.get("project_code") or None,
                project_name=enriched_active_filter.get("project_name") or None,
            )
        )

        if intent == "ACTIVE_SET_FEATURE_EXTREME" and result_set_extreme and filtered_rows:
            target_row = _select_extreme_from_result_set(
                filtered_rows,
                field=str(result_set_extreme.get("field") or "surface_total_m2"),
                mode=str(result_set_extreme.get("mode") or "max"),
            )
            if target_row:
                summary_patch.update(_result_set_summary_patch(filtered_rows, origin_intent=intent))
                summary_patch.update(_unit_subject_summary_patch(target_row))
                summary_patch["selected_project"] = {
                    "id": None,
                    "code": str(target_row.get("project_code") or "").strip().upper(),
                    "name": str(target_row.get("project_name") or "").strip(),
                }
                return {
                    "variant": "active_set_feature_extreme",
                    "intent": intent,
                    "followup": True,
                    "reason": intent_reason,
                    "answer": _result_set_feature_extreme_reply(
                        target_row,
                        feature_key=feature_key,
                        label=str(result_set_extreme.get("label") or "más relevante").strip(),
                        field=str(result_set_extreme.get("field") or "").strip(),
                    ),
                    "found": True,
                    "fields_used": [*_feature_fields_used(feature_key), "demo_units.surface_total_m2", "demo_units.list_price"],
                    "data_sources": data_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": str(target_row.get("project_code") or "").strip().upper(),
                    "project_name": str(target_row.get("project_name") or "").strip(),
                    "result_slots": {"matches_count": len(filtered_rows)},
                }

        summary_patch.update(_result_set_summary_patch(filtered_rows, origin_intent=intent))
        return {
            "variant": "active_set_feature_filter",
            "intent": intent,
            "followup": True,
            "reason": intent_reason,
            "answer": _result_set_feature_reply(filtered_rows, feature_key=feature_key),
            "found": True,
            "fields_used": [*_feature_fields_used(feature_key), "demo_units.surface_total_m2", "demo_units.list_price"],
            "data_sources": data_sources,
            "slots": slots,
            "summary_patch": summary_patch,
            "project_code": "",
            "project_name": "",
            "result_slots": {"matches_count": len(filtered_rows)},
        }

    if intent == "RESULT_SET_RANKING":
        rows = _active_context_units(conn, summary_obj)
        if rows and result_set_ranking:
            ranked_rows = _rank_units_result_set(
                rows,
                field=str(result_set_ranking.get("field") or "surface_total_m2"),
                direction=str(result_set_ranking.get("direction") or "desc"),
                limit=int(result_set_ranking.get("limit")) if result_set_ranking.get("limit") is not None else None,
            )
            if ranked_rows:
                summary_patch.update(_result_set_summary_patch(ranked_rows, origin_intent="RESULT_SET_RANKING"))
                if active_filter.get("type"):
                    summary_patch.update(
                        _build_active_filter_summary_patch(
                            filter_type=active_filter.get("type") or "",
                            filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
                            scope=active_filter.get("scope") or "global",
                            origin_intent=active_filter.get("origin_intent") or "RESULT_SET_RANKING",
                            project_code=active_filter.get("project_code") or None,
                            project_name=active_filter.get("project_name") or None,
                        )
                    )
                project_codes = {
                    str(row.get("project_code") or "").strip().upper()
                    for row in ranked_rows
                    if str(row.get("project_code") or "").strip()
                }
                project_names = {
                    str(row.get("project_name") or "").strip()
                    for row in ranked_rows
                    if str(row.get("project_name") or "").strip()
                }
                return {
                    "variant": "unit_list_followup",
                    "intent": intent,
                    "followup": True,
                    "reason": intent_reason,
                    "answer": _format_ranked_result_set_reply(
                        ranked_rows,
                        ranking=result_set_ranking,
                        active_filter_summary=str(active_filter.get("summary") or "").strip(),
                    ),
                    "found": True,
                    "fields_used": ["demo_units.surface_total_m2", "demo_units.list_price", "demo_units.rooms_count", "demo_units.availability_status"],
                    "data_sources": _dedupe_texts(_source_from_profile_rows(rows), limit=8) or [str(item) for item in summary_obj.get("last_data_sources") or ["demo_units"]],
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": next(iter(project_codes), "") if len(project_codes) == 1 else "",
                    "project_name": next(iter(project_names), "") if len(project_names) == 1 else "",
                    "result_slots": {
                        "matches_count": len(ranked_rows),
                        "ranking_field": str(result_set_ranking.get("field") or "").strip(),
                        "ranking_direction": str(result_set_ranking.get("direction") or "").strip(),
                    },
                }

    if intent == "RESULT_SET_SORT":
        rows = _active_context_units(conn, summary_obj)
        if rows and result_set_sort:
            sorted_rows = _sort_units_result_set(
                rows,
                field=str(result_set_sort.get("field") or "surface_total_m2"),
                direction=str(result_set_sort.get("direction") or "asc"),
            )
            label = str(result_set_sort.get("label") or "criterio").strip()
            summary_patch.update(_result_set_summary_patch(sorted_rows, origin_intent="RESULT_SET_SORT"))
            if active_filter.get("type"):
                summary_patch.update(
                    _build_active_filter_summary_patch(
                        filter_type=active_filter.get("type") or "",
                        filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
                        scope=active_filter.get("scope") or "global",
                        origin_intent=active_filter.get("origin_intent") or "RESULT_SET_SORT",
                        project_code=active_filter.get("project_code") or None,
                        project_name=active_filter.get("project_name") or None,
                    )
                )
            project_codes = {
                str(row.get("project_code") or "").strip().upper()
                for row in sorted_rows
                if str(row.get("project_code") or "").strip()
            }
            project_names = {
                str(row.get("project_name") or "").strip()
                for row in sorted_rows
                if str(row.get("project_name") or "").strip()
            }
            return {
                "variant": "unit_list_followup",
                "intent": intent,
                "followup": True,
                "reason": intent_reason,
                "answer": _format_result_set_reply(sorted_rows, lead_text=f"Ordenadas por {label}:"),
                "found": True,
                "fields_used": ["demo_units.surface_total_m2", "demo_units.list_price", "demo_units.availability_status"],
                "data_sources": [str(item) for item in summary_obj.get("last_data_sources") or ["demo_units"]],
                "slots": slots,
                "summary_patch": summary_patch,
                "project_code": next(iter(project_codes), "") if len(project_codes) == 1 else "",
                "project_name": next(iter(project_names), "") if len(project_names) == 1 else "",
                "result_slots": {"matches_count": len(sorted_rows)},
            }

    if intent == "RESULT_SET_EXTREME":
        rows = _active_context_units(conn, summary_obj)
        if rows and result_set_extreme:
            target_row = _select_extreme_from_result_set(
                rows,
                field=str(result_set_extreme.get("field") or "surface_total_m2"),
                mode=str(result_set_extreme.get("mode") or "max"),
            )
            if target_row:
                summary_patch.update(_result_set_summary_patch(rows, origin_intent="RESULT_SET_EXTREME"))
                if active_filter.get("type"):
                    summary_patch.update(
                        _build_active_filter_summary_patch(
                            filter_type=active_filter.get("type") or "",
                            filter_payload=active_filter.get("payload") if isinstance(active_filter.get("payload"), dict) else {},
                            scope=active_filter.get("scope") or "global",
                            origin_intent=active_filter.get("origin_intent") or "RESULT_SET_EXTREME",
                            project_code=active_filter.get("project_code") or None,
                            project_name=active_filter.get("project_name") or None,
                        )
                    )
                unit_code = str(target_row.get("unit_code") or target_row.get("unit_id") or "").strip().upper()
                summary_patch.update(_unit_subject_summary_patch(target_row))
                summary_patch["selected_project"] = {
                    "id": None,
                    "code": str(target_row.get("project_code") or "").strip().upper(),
                    "name": str(target_row.get("project_name") or "").strip(),
                }
                label = str(result_set_extreme.get("label") or "más relevante").strip()
                field = str(result_set_extreme.get("field") or "").strip()
                if field == "price":
                    price_value = _to_float(target_row.get("list_price"))
                    currency = str(target_row.get("currency") or "").strip().upper() or "USD"
                    answer = (
                        f"La {label} del último listado es la {unit_code}, publicada en {currency} {_format_price(price_value)}."
                        if price_value is not None
                        else f"La {label} del último listado es la {unit_code}."
                    )
                else:
                    surface_value = _format_surface(target_row.get("surface_total_m2"))
                    answer = (
                        f"La {label} del último listado es la {unit_code}, con {surface_value} m² totales."
                        if surface_value
                        else f"La {label} del último listado es la {unit_code}."
                    )
                return {
                    "variant": "unit_list_followup",
                    "intent": intent,
                    "followup": True,
                    "reason": intent_reason,
                    "answer": answer,
                    "found": True,
                    "fields_used": ["demo_units.surface_total_m2", "demo_units.list_price"],
                    "data_sources": [str(item) for item in summary_obj.get("last_data_sources") or ["demo_units"]],
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": str(target_row.get("project_code") or "").strip().upper(),
                    "project_name": str(target_row.get("project_name") or "").strip(),
                    "result_slots": {},
                }

    if intent in {"PRICE", "AVAILABILITY", "AVAILABLE_UNITS", "SURFACE_QUERY", "UNIT_TYPES"} and unit_code:
        unit_row = _unit_row_for_code(conn, unit_code)
        if unit_row:
            enriched_project_code = str(unit_row.get("project_code") or "").strip().upper()
            enriched_project_name = _unit_project_name(conn, unit_row)
            summary_patch["selected_project"] = {
                "id": None,
                "code": enriched_project_code,
                "name": enriched_project_name,
            }
            summary_patch.update(_unit_subject_summary_patch(unit_row))
            unit_sources = _dedupe_texts(_source_from_profile_rows([unit_row]), limit=8) or ["demo_unit_profile", "demo_units"]
            if intent == "PRICE":
                return {
                    "variant": "unit_detail_answer",
                    "intent": intent,
                    "followup": is_followup,
                    "reason": intent_reason,
                    "answer": _unit_price_reply(unit_code, unit_row),
                    "found": True,
                    "fields_used": ["demo_units.list_price", "demo_units.currency"],
                    "data_sources": unit_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": enriched_project_code,
                    "project_name": enriched_project_name,
                    "result_slots": {},
                }
            if intent in {"AVAILABILITY", "AVAILABLE_UNITS"}:
                return {
                    "variant": "unit_detail_answer",
                    "intent": intent,
                    "followup": is_followup,
                    "reason": intent_reason,
                    "answer": _unit_availability_reply(unit_code, unit_row),
                    "found": True,
                    "fields_used": ["demo_units.availability_status"],
                    "data_sources": unit_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": enriched_project_code,
                    "project_name": enriched_project_name,
                    "result_slots": {},
                }
            if intent == "SURFACE_QUERY" and not surface_filter:
                return {
                    "variant": "unit_detail_answer",
                    "intent": intent,
                    "followup": is_followup,
                    "reason": intent_reason,
                    "answer": _unit_surface_reply(unit_code, unit_row),
                    "found": True,
                    "fields_used": ["demo_units.surface_total_m2"],
                    "data_sources": unit_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": enriched_project_code,
                    "project_name": enriched_project_name,
                    "result_slots": {},
                }
            if intent == "UNIT_TYPES":
                return {
                    "variant": "unit_detail_answer",
                    "intent": intent,
                    "followup": is_followup,
                    "reason": intent_reason,
                    "answer": _unit_rooms_reply(unit_code, unit_row),
                    "found": True,
                    "fields_used": ["demo_units.rooms_count"],
                    "data_sources": unit_sources,
                    "slots": slots,
                    "summary_patch": summary_patch,
                    "project_code": enriched_project_code,
                    "project_name": enriched_project_name,
                    "result_slots": {},
                }

    if intent == "SURFACE_QUERY" and not project_code:
        return {
            "variant": "project_qa",
            "intent": intent,
            "followup": is_followup,
            "reason": intent_reason,
            "answer": _build_specific_no_info_reply(topic_label="los metros cuadrados de las unidades"),
            "found": False,
            "fields_used": [],
            "data_sources": [],
            "slots": slots,
            "summary_patch": {
                **summary_patch,
                "unresolved_topic": "surface",
            },
            "project_code": "",
            "project_name": "",
            "result_slots": {},
        }

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
    if intent == "PROJECT_OVERVIEW":
        answer, feature_fields = _build_project_feature_answer(
            conn,
            project_code=project_code,
            project_name=project_name,
            overview=overview,
            marketing_assets=marketing_assets,
        )
        if answer:
            fields_used.extend(feature_fields)
            found = True
        else:
            answer = _build_vera_sensitive_reply(project_name)

    elif intent == "FEATURES":
        answer, feature_fields = _build_project_feature_answer(
            conn,
            project_code=project_code,
            project_name=project_name,
            overview=overview,
            marketing_assets=marketing_assets,
        )
        if answer:
            fields_used.extend(feature_fields)
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
                        summary_patch.update(
                            _build_pending_offer_patch(
                                offer_type="PRICE_BREAKDOWN_BY_ROOMS",
                                project_code=project_code,
                                intent_source=intent,
                                payload={"currency": currency_text},
                            )
                        )
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

    elif intent == "TOTAL_UNITS":
        inventory_summary = repo.get_project_inventory_summary(conn, project_code)
        answer = _inventory_total_units_reply(project_name, inventory_summary)
        fields_used.extend(
            [
                "demo_project_profile.units_total",
                "demo_project_profile.available_units",
                "demo_project_profile.raw_status_breakdown_jsonb",
            ]
        )
        data_sources = _dedupe_texts(
            [*data_sources, *(_source_from_profile_payload(inventory_summary))],
            limit=8,
        )
        found = bool(inventory_summary)

    elif intent == "UNIT_STATUS_BREAKDOWN":
        inventory_summary = repo.get_project_inventory_summary(conn, project_code)
        answer = _inventory_breakdown_reply(project_name, inventory_summary)
        fields_used.extend(
            [
                "demo_project_profile.raw_status_breakdown_jsonb",
                "demo_project_profile.inventory_is_complete",
                "demo_project_profile.units_total",
            ]
        )
        data_sources = _dedupe_texts(
            [*data_sources, *(_source_from_profile_payload(inventory_summary))],
            limit=8,
        )
        found = bool(inventory_summary.get("raw_status_breakdown_jsonb") or inventory_summary.get("units_total") is not None)

    elif intent == "CHILDREN_SUITABILITY":
        children_summary = repo.get_children_suitability_summary(conn, project_code)
        answer = _children_suitability_reply(project_name, children_summary)
        fields_used.extend(
            [
                "demo_project_profile.children_suitable",
                "demo_project_profile.child_safety_warnings_jsonb",
                "demo_unit_profile.children_suitable",
                "demo_unit_profile.recommended_profiles_jsonb",
            ]
        )
        data_sources = _dedupe_texts(
            [*data_sources, *(_source_from_profile_payload(children_summary))],
            limit=8,
        )
        found = bool(children_summary)

    elif intent == "PETS_SUITABILITY":
        pets_summary = repo.get_pets_suitability_summary(conn, project_code)
        answer = _pets_suitability_reply(project_name, pets_summary, question)
        fields_used.extend(
            [
                "demo_project_profile.pets_allowed",
                "demo_project_profile.pets_restrictions_text",
                "demo_unit_profile.pets_allowed",
                "demo_unit_profile.has_garden",
                "demo_unit_profile.has_patio",
                "demo_unit_profile.recommended_profiles_jsonb",
            ]
        )
        data_sources = _dedupe_texts(
            [*data_sources, *(_source_from_profile_payload(pets_summary))],
            limit=8,
        )
        found = bool(pets_summary)

    elif intent == "SAFETY_WARNINGS":
        answer, warning_fields, warning_sources = _warnings_reply(
            conn,
            project_code=project_code,
            project_name=project_name,
            question=question,
        )
        fields_used.extend(warning_fields)
        data_sources = _dedupe_texts([*data_sources, *warning_sources], limit=8)
        found = True

    elif intent == "LIGHT_ORIENTATION":
        light_summary = repo.get_light_orientation_summary(conn, project_code=project_code)
        answer = _light_orientation_reply(project_name, question, light_summary)
        fields_used.extend(
            [
                "demo_unit_profile.orientation",
                "demo_unit_profile.exposure",
                "demo_unit_profile.sun_morning",
                "demo_unit_profile.sun_afternoon",
                "demo_unit_profile.natural_light",
                "demo_unit_profile.cross_ventilation",
                "demo_unit_profile.thermal_comfort_notes",
            ]
        )
        data_sources = _dedupe_texts(
            [*data_sources, *(_source_from_profile_payload(light_summary))],
            limit=8,
        )
        found = True

    elif intent in {"AVAILABILITY", "AVAILABLE_UNITS"}:
        rooms = slots.get("ambientes")
        available_by_rooms = _extract_available_by_rooms(conn, project_code)
        if available_by_rooms:
            result_slots["available_by_rooms"] = {str(k): v for k, v in available_by_rooms.items()}
            data_sources = _dedupe_texts([*data_sources, "demo_units"], limit=8)
            if rooms is not None:
                count = int(available_by_rooms.get(int(rooms)) or 0)
                answer = f"Para {rooms} ambientes en {project_name} hoy veo {_format_inventory_count(count, 'available')}."
            else:
                total = sum(available_by_rooms.values())
                answer = f"Hoy veo {_format_inventory_count(total, 'available')} en {project_name}."
            fields_used.append("demo_units.availability_status")
            found = True
        else:
            available_units = repo.get_available_units_count(conn, project_code)
            if available_units is not None:
                if rooms is not None:
                    answer = f"Para {rooms} ambientes en {project_name} hoy veo {_format_inventory_count(int(available_units), 'available')}."
                else:
                    answer = f"Hoy veo {_format_inventory_count(int(available_units), 'available')} en {project_name}."
                fields_used.append("demo_units.availability_status")
                data_sources = _dedupe_texts([*data_sources, "demo_units"], limit=8)
                found = True
            elif rooms is None:
                answer = "No veo disponibilidad publicada en este momento."
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

    elif intent == "SURFACE_QUERY":
        surface_answer, surface_found, surface_fields, surface_sources, surface_result = _surface_query_reply(
            conn,
            project_code=project_code,
            project_name=project_name,
            question=question,
            rooms=slots.get("ambientes"),
            surface_filter=surface_filter,
        )
        answer = surface_answer
        found = surface_found
        fields_used.extend(surface_fields)
        data_sources = _dedupe_texts([*data_sources, *surface_sources], limit=8)
        result_set_patch = surface_result.pop("result_set_patch", None) if isinstance(surface_result, dict) else None
        if isinstance(result_set_patch, dict):
            summary_patch.update(result_set_patch)
        last_subject_patch = surface_result.pop("last_subject_patch", None) if isinstance(surface_result, dict) else None
        if isinstance(last_subject_patch, dict):
            summary_patch.update(last_subject_patch)
        if surface_result.get("unresolved_topic"):
            summary_patch["unresolved_topic"] = surface_result.get("unresolved_topic")
        else:
            result_slots.update(surface_result)
        if surface_filter:
            summary_patch.update(
                _build_active_filter_summary_patch(
                    filter_type="surface",
                    filter_payload={
                        "min_surface_total_m2": _to_float(surface_filter.get("value")),
                        "rooms_count": slots.get("ambientes"),
                    },
                    scope="project",
                    origin_intent=intent,
                    project_code=project_code,
                    project_name=project_name,
                )
            )

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
    semantic_preview = _semantic_intent_resolver(
        clean_text,
        detail=detail,
        recent_messages=context_messages[-5:],
        summary=detail_summary,
    )
    detected_intent = str(semantic_preview.get("intent") or "UNKNOWN").strip().upper() or "UNKNOWN"
    detected_followup = bool(semantic_preview.get("followup"))
    detected_reason = str(semantic_preview.get("reason") or "semantic_unknown")
    logger.info(
        "INTENT_RESOLVED correlation_id=%s intent=%s source=%s selected_project=%s matched_alias=%s confidence=%s",
        ticket_id or "-",
        detected_intent,
        semantic_preview.get("resolution_source") or "semantic",
        str(((detail or {}).get("project_code") or ((detail or {}).get("summary_jsonb") or {}).get("selected_project", {}).get("code") or "-")),
        semantic_preview.get("matched_alias") or "-",
        semantic_preview.get("confidence") or "-",
    )
    visit_requested = detected_intent == "VISIT_REQUEST"
    qa_candidate = bool(
        detected_intent != "UNKNOWN"
        or semantic_preview.get("chosen_project")
        or _looks_like_project_question(clean_text)
        or (project_name and detected_intent == "PROJECT_OVERVIEW")
    )

    if is_first_contact and detected_intent == "GREETING" and not project_name:
        variant = "onboarding"
        board_url = build_board_url(normalized_phone)
        reply_text = _build_vera_onboarding_reply(board_url)
    elif project_name and _is_confirmation_message(clean_text) and _recent_human_schedule_sent(context_messages):
        variant = "post_human_followup"
        reply_text = (
            "Perfecto, confirmado. Si querés te paso dirección exacta y qué necesitás traer para la visita."
        )
    elif qa_candidate and ticket_id:
        def _tx_resolve_qa(conn: Any) -> dict[str, Any]:
            local_detail = repo.get_ticket_detail(conn, ticket_id)
            return _resolve_project_knowledge_reply(
                conn,
                ticket_id=ticket_id,
                detail=local_detail,
                question=clean_text,
                recent_messages=context_messages[-5:],
                semantic_resolution=semantic_preview,
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
        logger.info(
            "CHOOSE_PROJECT_TRIGGERED correlation_id=%s reason=no_project_and_low_confidence selected_project=%s text=%s",
            ticket_id or "-",
            project_name or "-",
            clean_text[:80],
        )
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
