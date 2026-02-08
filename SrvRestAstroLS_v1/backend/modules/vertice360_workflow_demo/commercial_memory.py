from __future__ import annotations

import re
import unicodedata
import datetime as dt
from typing import Any

# Principales slots comerciales
COMMERCIAL_SLOT_PRIORITY = ("zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza")


# Regex helpers
CURRENCY_PATTERN = r"(?:usd|u\$s|us\$|ars|\$|pesos|peso|argentinos|arg|dolares|dolar|dólares|dólar|us)"

# Matches: prefix (optional), amount (required), magnitude (optional), suffix (optional)
# e.g. "usd 90k", "90.000 pesos", "1.5 millones", "120000", "120 k"
BUDGET_RE = re.compile(
    rf"(?P<prefix>{CURRENCY_PATTERN})?\s*"
    r"(?P<amount>\d[\d.,]*)\s*"
    r"(?P<magnitude>millones|millon|miles|mil|k|m)?\b\s*"
    rf"(?P<suffix>{CURRENCY_PATTERN})?",
    re.IGNORECASE,
)

ROOMS_RE = re.compile(r"(\d+)\s*amb(?:ientes)?", re.IGNORECASE)

NEIGHBORHOOD_GAZETTEER = [
    "Villa Lugano", "Villa Urquiza", "Villa Devoto", "Parque Chacabuco", "Nueva Pompeya",
    "Villa Crespo", "Villa del Parque", "Parque Patricios", "Recoleta", "Palermo",
    "Almagro", "Caballito", "Belgrano", "Puerto Madero", "San Telmo", "Monserrat",
    "San Nicolas", "Retiro", "Constitucion", "Barracas", "La Boca", "San Cristobal",
    "Boedo", "Flores", "Floresta", "Velez Sarsfield", "Villa Luro", "Liniers",
    "Mataderos", "Villa Real", "Versalles", "Villa Santa Rita", "Villa Mitre",
    "Villa General Mitre", "Chacarita", "Paternal", "Villa Ortuzar", "Colegiales",
    "Nuñez", "Saavedra", "Coghlan", "Villa Pueyrredon", "Agronomia",
    "San Telmo", "Las Cañitas", "Barrio Norte"
]

CITY_ALIASES = {
    "caba": "CABA",
    "capital": "CABA",
    "buenos aires": "CABA",
    "capital federal": "CABA"
}

MONTH_TOKENS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

TEMPORAL_KEYWORDS = (
    "mañana", "hoy", "semana", "mes", "quincena", "mediados", "fin", "principios", "dia", "fecha",
    "fines", "inicios", "año", "ano", "mitad"
)

# Regex for visit scheduling
VISIT_DAY_RE = re.compile(
    r"\b(?:d[ií]a\s+)?(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\b",
    re.IGNORECASE
)
# Matches "16 horas", "16hs", "16 h", "16:00", "4pm", "8 am", "a las 16"
# capture full time string
VISIT_TIME_RE = re.compile(
    r"\b(?:a\s+las?|a\s+la|alas?|hora)?\s*(?P<time>\d{1,2}(?::\d{2})?)\s*(?:horas|hs|h|:|am|pm)?\b",
    re.IGNORECASE
)
# Matches "de 8 a 12", "8 a 12", "14 a 16", "14hs a 16hs"
VISIT_RANGE_RE = re.compile(
    r"(?:de\s+)?(?P<start>\d{1,2}(?::\d{2})?(?:am|pm)?(?:hs|h|horas)?)\s*(?:a|hasta)\s*(?P<end>\d{1,2}(?::\d{2})?(?:am|pm)?(?:hs|h|horas)?)",
    re.IGNORECASE
)

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()

def _title_case_zona(text: str) -> str:
    words = text.split()
    fixed = []
    for w in words:
        if w.lower() in ("de", "del", "la", "las", "los", "en"):
            fixed.append(w.lower())
        else:
            fixed.append(w.capitalize())
    return " ".join(fixed)

def parse_zona(text: str) -> str | None:
    norm = _normalize_text(text)
    
    # 1. Check Gazetteer (multi-word priorities)
    for zone in NEIGHBORHOOD_GAZETTEER:
        # Check if zone name appears in normalized text
        # normalized_zone handles stripping accents/lowercasing
        normalized_zone = _normalize_text(zone)
        # Simple containment is robust enough for these specific names
        if normalized_zone in norm:
             return zone # Return original casing from gazetteer
            
    # 2. Check Aliases (City)
    for alias, proper in CITY_ALIASES.items():
        if alias in norm:
            return proper

    # 3. Regex Fallback for "en X", "zona X"
    # Capture up to punctuation or end
    # pattern: (?:en|zona|barrio|por)\s+([a-z\s]+)
    match = re.search(r"\b(?:en|zona|barrio|por)\s+([a-z\s]+?)(?:$|[.,;]|\s(?:y|con|para)\s)", norm)
    if match:
        extracted = match.group(1).strip()
        # Filter out common junk
        if len(extracted) > 3 and extracted not in ("caba", "capital"):
            return _title_case_zona(extracted)
            
    return None


def parse_tipologia(text: str) -> str | None:
    norm = _normalize_text(text)
    match = ROOMS_RE.search(norm)
    if match:
        try:
            rooms = int(match.group(1))
            return f"{rooms} ambientes"
        except ValueError:
            pass
            
    if "monoambiente" in norm:
        return "monoambiente"
    if "2 ambientes" in norm or "2 amb" in norm or "dos ambientes" in norm:
        return "2 ambientes"
    if "3 ambientes" in norm or "3 amb" in norm or "tres ambientes" in norm:
        return "3 ambientes"
    if "4 ambientes" in norm or "4 amb" in norm or "cuatro ambientes" in norm:
        return "4 ambientes"
        
    return None


def _normalize_budget_magnitude(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower().strip()
    if t in ("millones", "millon", "m"):
        return "million"
    if t in ("miles", "mil", "k"):
        return "thousand"
    return None

def _clean_amount_str(raw: str) -> float | None:
    if not raw:
        return None
    # If 120.000 -> 120000; if 120,000 -> 120000
    # If 120 k -> 120
    clean = raw.replace(",", ".").replace(" ", "")
    # Remove dots if they look like thousand separators (e.g. 120.000)
    # Heuristic: if more than one dot, or dot followed by 3 digits at end
    if clean.count(".") > 1:
        clean = clean.replace(".", "")
    elif "." in clean and len(clean.split(".")[-1]) == 3:
         # ambiguous 120.000 (120k) vs 120.00 (120)
         # usually in property prices 120.000 is 120k
         if float(clean.replace(".","")) > 1000:
             clean = clean.replace(".", "")
             
    try:
        return float(clean)
    except ValueError:
        return None


def parse_budget_currency(text: str) -> tuple[int | None, str | None]:
    norm = _normalize_text(text)
    
    fallback_currency = None
    if any(t in norm for t in ("usd", "u$s", "us$", "dolar")):
        fallback_currency = "USD"
    elif any(t in norm for t in ("ars", "peso", "argentino", "arg", "$")):
        fallback_currency = "ARS"

    matches = list(BUDGET_RE.finditer(norm))
    if not matches:
        # Check for bare number only if explicit digits present
        # but verify it's not a small integer (date/time)
        # Use a simple regex for bare number
        bare_match = re.search(r"\b(\d{4,})\b", norm)
        if bare_match:
             val = int(bare_match.group(1))
             return val, fallback_currency
        return None, fallback_currency
    
    best_amount = None

    for m in matches:
        prefix = m.group("prefix")
        suffix = m.group("suffix")
        magnitude = m.group("magnitude")
        raw_amount = m.group("amount")
        
        cur = None
        context_tokens = [t.lower() for t in (prefix, suffix) if t]
        context_str = " ".join(context_tokens)
        
        if any(x in context_str for x in ("usd", "u$s", "us$", "dolar", "us", "u$")):
            cur = "USD"
        elif any(x in context_str for x in ("ars", "peso", "argentino", "arg", "$")):
            cur = "ARS"
            
        # If we found global currency signals in text, force it if we didn't find specific ones
        if not cur and fallback_currency:
            cur = fallback_currency

        val_float = _clean_amount_str(raw_amount)
        if val_float is None:
            continue
            
        norm_mag = _normalize_budget_magnitude(magnitude)
        
        final_val = val_float
        if norm_mag == "thousand":
            final_val = val_float * 1000
        elif norm_mag == "million":
            final_val = val_float * 1_000_000
        
        # Heuristic: Ignore small integers without currency/magnitude (e.g. dates, hours like "16")
        if cur is None and norm_mag is None and final_val < 500:
            continue
        
        if cur:
            return int(final_val), cur
        
        best_amount = int(final_val)

    if best_amount is not None and fallback_currency:
        return best_amount, fallback_currency

    if best_amount is not None:
        return best_amount, None

    return None, fallback_currency

def _normalize_time_str(t_str: str) -> str | None:
    if not t_str: return None
    # Remove letters
    clean = re.sub(r"[a-z]", "", t_str.lower()).strip()
    clean = clean.replace(" ", "")
    if ":" in clean:
        parts = clean.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if parts[1] else 0
            return f"{h:02d}:{m:02d}"
        except:
            return None
    else:
        try:
            h = int(clean)
            return f"{h:02d}:00"
        except ValueError:
            return None


def parse_visita(text: str) -> dict[str, Any] | None:
    norm = _normalize_text(text)
    
    # Day
    day_match = VISIT_DAY_RE.search(norm)
    day = day_match.group(1).lower() if day_match else None
    
    # Time Range
    start = None
    end = None
    
    range_match = VISIT_RANGE_RE.search(norm)
    if range_match:
        s_raw = range_match.group("start")
        e_raw = range_match.group("end")
        start = _normalize_time_str(s_raw)
        end = _normalize_time_str(e_raw)
    else:
        # Single time ("a las 16", "16hs")
        time_match = VISIT_TIME_RE.search(norm)
        if time_match:
             t_raw = time_match.group("time")
             start = _normalize_time_str(t_raw)

    if not day and not start and not end:
        return None
        
    return {
        "visit_day_of_week": day,
        "visit_time_from": start,  # HH:MM
        "visit_time_to": end,      # HH:MM
        "visit_raw": text
    }


def parse_fecha_mudanza(text: str) -> str | None:
    norm = _normalize_text(text)
    
    # 1. Explicit dates: "15 de febrero", "15/2", "15-02"
    for i, month in enumerate(MONTH_TOKENS):
        pattern = r"\b(\d{1,2})\s*(?:de)?\s*" + month + r"\b"
        match = re.search(pattern, norm)
        if match:
            day = match.group(1)
            year = dt.datetime.now().year
            try:
                return f"{year}-{i+1:02d}-{int(day):02d}"
            except ValueError:
                pass

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", norm)
    if match:
        day_str, month_str = match.groups()
        try:
            day = int(day_str)
            month = int(month_str)
            year = dt.datetime.now().year
            if 1 <= month <= 12 and 1 <= day <= 31:
                 return f"{year}-{month:02d}-{day:02d}"
        except ValueError:
            pass

    # 2. Relative expressions
    prefixes = "mediados|fines|fin|principios|inicios|mitad|mediado"
    for month in MONTH_TOKENS:
        pattern = r"\b(" + prefixes + r")\s*(?:de)?\s*" + month + r"\b"
        match = re.search(pattern, norm)
        if match:
             return f"{match.group(1)} de {month}"

    # 3. Fallback: Contains month name
    for month in MONTH_TOKENS:
        if month in norm:
            if norm.strip() == month:
                return month
            if re.search(rf"\ben\s+{month}\b", norm):
                return month
            return norm.strip() # Return full text context if month is present

    # 4. Temporal keywords
    for kw in TEMPORAL_KEYWORDS:
        if kw in norm:
            return norm.strip()
            
    return None


def calculate_missing_slots(memory: dict[str, Any]) -> list[str]:
    """
    Returns list of missing keys from COMMERCIAL_SLOT_PRIORITY.
    Strictly checks for None, empty string, or "UNKNOWN".
    """
    missing = []
    for slot in COMMERCIAL_SLOT_PRIORITY:
        val = memory.get(slot)
        if val is None or val == "" or val == "UNKNOWN":
            missing.append(slot)
    return missing


def build_next_best_question(missing: list[str]) -> tuple[str | None, str | None]:
    """
    Returns (question_text, key_for_that_question).
    Priority:
       1) zona (+ opcional tipologia si ambas faltan) -> key="zona"
       2) tipologia -> key="tipologia"
       3) presupuesto + moneda -> key="presupuesto"
       4) fecha_mudanza -> key="fecha_mudanza"
    """
    if not missing:
        return None, None
        
    m_set = set(missing)
    
    # 1) Zona
    if "zona" in m_set:
        if "tipologia" in m_set:
            return "¿Por qué zona buscás y qué tipología (ambientes)?", "zona"
        return "¿En qué zona o barrio estás buscando?", "zona"
        
    # 2) Tipologia
    if "tipologia" in m_set:
        return "¿Qué tipología buscás? (Ej: 2 ambientes, monoambiente)", "tipologia"
        
    # 3) Presupuesto
    if "presupuesto" in m_set or "moneda" in m_set:
        return "¿Cuál es tu presupuesto aproximado y moneda?", "presupuesto"
        
    # 4) Fecha mudanza
    if "fecha_mudanza" in m_set:
        return "¿Para cuándo necesitás mudarte?", "fecha_mudanza"
        
    return None, None


def get_next_question_with_anti_repetition(
    memory: dict[str, Any],
    last_question_key: str | None,
    current_update_keys: set[str],
) -> tuple[str | None, str | None]:
    """
    Returns: (question_text, question_key)
    """
    missing = calculate_missing_slots(memory)
    if not missing:
        # All complete
        return None, "summary_close"
        
    question, key = build_next_best_question(missing)
    
    if key and key == last_question_key and key not in current_update_keys:
        remaining_missing = [m for m in missing if m != key and m != "moneda"] 
        if not remaining_missing:
            return None, "summary_close"
        alt_question, alt_key = build_next_best_question(remaining_missing)
        return alt_question, alt_key

    return question, key
