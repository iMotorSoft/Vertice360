from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import events, llm_service, mock_data, store, templates
from backend.modules.vertice360_workflow_demo import commercial_memory


WORKFLOW_ID = "vertice360-ai-workflow"
WORKFLOW_NAME = "AI Workflow Studio"
WORKFLOW_DESCRIPTION = "Deterministic demo workflow with step-by-step execution."
WORKFLOW_NODES = [
    "normalize_input",
    "intent_classify",
    "extract_entities",
    "pragmatics",
    "decide_next",
    "build_response",
]


class AiWorkflowState(TypedDict, total=False):
    run_id: str
    workflow_id: str
    input: Any
    mode: str | None
    clean_input: str
    normalized_input: str
    intent: str
    intents: list[dict[str, Any]]
    primary_intent: str
    secondary_intents: list[str]
    intent_hint: str | None
    commercial_slots: dict[str, Any] | None
    entities: dict[str, Any]
    pragmatics: dict[str, Any]
    decision: str
    search_filters: dict[str, Any]
    options: dict[str, Any] | None
    missing_slots_count: int
    recommended_question: str | None
    recommended_questions: list[str]
    recommended_question_model: str | None
    response_text: str
    used_fallback: bool
    fallback_reason: str | None
    response_model: str | None
    summary: str | None
    next_action_question: str | None


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{6,}\d")
DNI_CUIT_RE = re.compile(r"\b\d{7,8}\b|\b\d{2}-\d{8}-\d{1}\b")
AMOUNT_RE = re.compile(
    r"(?:usd|u\$s|us\$|ars|\$)\s*\d[\d.,]*\s*(?:millones|millon|mil|k)?"
    r"|\b\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?\b"
    r"|\b\d+\s*(?:millones|millon|mil|k)\b",
    re.IGNORECASE,
)
CURRENCY_HINT_PATTERN = r"(?:usd|u\$s|us\$|ars|\$|peso|pesos|dolar|dolares)"
AMBIGUOUS_BUDGET_RE = re.compile(
    rf"(?P<cur>{CURRENCY_HINT_PATTERN})?\s*"
    r"(?P<amount>\d{1,4}(?:[.,]\d+)?)\s*"
    r"(?P<magnitude>millones|millon|miles|mil|k|m)?\b\s*"
    rf"(?P<cur2>{CURRENCY_HINT_PATTERN})?",
    re.IGNORECASE,
)
PRESUPUESTO_RE = re.compile(r"(?:presupuesto|budget)\s*[=:]?\s*(\d[\d.,]*\s*(?:millones|millon|mil|k)?\b)", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"\b(?:calle|av\.?|avenida|ruta|direccion)\s+[A-Za-z0-9\s]{3,40}",
    re.IGNORECASE,
)
ROOMS_RE = re.compile(r"\b(\d{1,2})\s*(ambientes|ambiente|amb)\b")

CITY_ALIASES = {
    "caba": "CABA",
    "capital federal": "CABA",
    "capital": "CABA",
    "buenos aires": "CABA",
}
NEIGHBORHOOD_ALIASES = {
    "caballito": "Caballito",
    "palermo": "Palermo",
    "almagro": "Almagro",
}

INTENT_SCORE_THRESHOLD = 1.0
INTENT_PRIORITY = [
    "property_search",
    "docs",
    "visit",
    "price",
    "location",
    "financing",
    "availability",
    "handoff_agent",
]
INTENT_KEYWORDS = {
    "property_search": ["depto", "departamento", "ambientes", "ambiente", "unidad", "propiedad", "monoambiente"],
    "price": ["precio", "valor", "cuanto", "usd", "ars", "$", "presupuesto"],
    "location": ["ubicacion", "zona", "barrio", "direccion", "donde", "mapa"],
    "visit": ["visita", "ver", "recorrer", "tour", "mostrar", "coordinar"],
    "docs": ["docs", "documentacion", "documentos", "dni", "cuit", "recibo", "ingresos"],
    "availability": ["disponible", "hay", "quedan", "stock", "unidades"],
    "financing": ["financiacion", "cuotas", "anticipo", "plan", "credito"],
    "handoff_agent": ["humano", "asesor", "llamar", "contacto", "agente"],
}
PRAGMATICS_MISSING_SLOTS = {
    "property_search": ["zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"],
    "price": ["currency", "budget", "unit"],
    "location": ["project_or_zone"],
    "visit": ["date_range"],
    "docs": ["dni", "income_proof"],
    "availability": ["unit_type"],
    "financing": ["down_payment", "terms"],
    "handoff_agent": ["contact_method"],
}
QUESTION_TEMPLATES = {
    "property_search": "Que zona, cantidad de ambientes y presupuesto con moneda buscas?",
    "price": "Cual es tu presupuesto y moneda?",
    "location": "Que zona o proyecto te interesa?",
    "visit": "Que rango de fechas preferis para la visita?",
    "docs": "Podes enviar DNI y comprobante?",
    "availability": "Que tipo de unidad buscas?",
    "financing": "Preferis cuotas y anticipo estimado?",
    "handoff_agent": "Queres que te contacte un asesor?",
}
QUESTION_TOKENS = ("como", "donde", "cuanto")
GREETING_TOKENS = ("hola", "buenas")
URGENT_TOKENS = ("ya", "urgente", "hoy", "ahora")
COMPLAINT_TOKENS = ("mal", "no funciona", "nadie responde")
COMMERCIAL_SLOT_PRIORITY = ("zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza")


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def _shorten_text(text: str, max_len: int = 160) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _allow_ai_question() -> bool:
    return bool(globalVar.OpenAI_Key) and (
        globalVar.FEATURE_AI or globalVar.VERTICE360_AI_WORKFLOW_REPLY
    )


def _sanitize_question(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    if "?" in normalized:
        normalized = normalized.split("?")[0].strip() + "?"
    elif not normalized.endswith("?"):
        normalized = f"{normalized}?"
    if len(normalized) > 140:
        normalized = normalized[:137].rstrip()
        if not normalized.endswith("?"):
            normalized = f"{normalized}?"
    return normalized


def _build_template_next_best_question(missing_slots: list[str]) -> str:
    slot_set = set(missing_slots)
    if "zona" in slot_set:
        if "tipologia" in slot_set:
            return "En que zona buscas y cuantos ambientes necesitas?"
        return "En que zona te interesa buscar?"
    if "tipologia" in slot_set:
        return "Que tipologia o cantidad de ambientes buscas?"
    if "presupuesto" in slot_set or "moneda" in slot_set:
        return "Cual es tu presupuesto y en que moneda?"
    if "fecha_mudanza" in slot_set:
        return "Para cuando necesitas mudarte?"
    return "Que dato adicional podes compartir para avanzar?"


def _build_openai_next_best_question(missing_slots: list[str]) -> tuple[str, str | None]:
    try:
        from openai import OpenAI
    except Exception:
        return "", None

    ordered_missing = [slot for slot in COMMERCIAL_SLOT_PRIORITY if slot in missing_slots]
    if not ordered_missing:
        ordered_missing = list(missing_slots)
    missing_text = ", ".join(ordered_missing) if ordered_missing else "zona, tipologia"

    system_prompt = (
        "Sos un asistente inmobiliario. "
        "Responde con una sola pregunta en espanol."
    )
    user_prompt = (
        "Genera EXACTAMENTE una pregunta, maximo 140 caracteres, "
        "para pedir el dato mas importante faltante. "
        "Podes pedir como maximo 2 piezas de informacion. "
        "Slots faltantes (prioridad descendente): "
        f"{missing_text}. "
        "Responde solo con la pregunta, sin comillas."
    )

    client = OpenAI(api_key=globalVar.OpenAI_Key)
    response = client.chat.completions.create(
        model=globalVar.OpenAI_Model or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=60,
    )
    if not response.choices:
        return "", response.model
    content = response.choices[0].message.content or ""
    return _sanitize_question(content), response.model


def _build_next_best_question(missing_slots: list[str]) -> tuple[str, bool, str | None]:
    ordered_missing = [slot for slot in COMMERCIAL_SLOT_PRIORITY if slot in missing_slots]
    template_question = _build_template_next_best_question(ordered_missing or missing_slots)
    if not _allow_ai_question():
        return template_question, False, None
    try:
        question, model = _build_openai_next_best_question(ordered_missing or missing_slots)
    except Exception:
        return template_question, False, None
    if question:
        return question, True, model
    return template_question, False, None


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _extract_rooms(text: str) -> int | None:
    match = ROOMS_RE.search(text)
    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None
    if "monoambiente" in text:
        return 1
    return None


def _extract_currency(text: str) -> str | None:
    if any(token in text for token in ("usd", "u$s", "us$", "dolar")):
        return "USD"
    if any(token in text for token in ("ars", "peso", "pesos")):
        return "ARS"
    if "$" in text:
        return "ARS"
    return None


def _parse_ambiguous_amount(raw: str) -> int | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d]", "", raw)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _detect_budget_ambiguous(text: str) -> dict[str, Any]:
    normalized = _strip_accents(str(text or "").lower())
    for match in AMBIGUOUS_BUDGET_RE.finditer(normalized):
        magnitude = match.group("magnitude")
        if magnitude:
            continue
        amount = _parse_ambiguous_amount(match.group("amount"))
        if amount is None or amount >= 5000:
            continue
        matched_currency = " ".join(
            [part for part in (match.group("cur"), match.group("cur2")) if part]
        )
        currency = _extract_currency(matched_currency) or _extract_currency(normalized)
        if not currency:
            continue
        return {"ambiguous": True, "amount": amount, "currency": currency}
    return {"ambiguous": False, "amount": None, "currency": None}


def _build_budget_ambiguous_question(amount: int | None, currency: str | None) -> str:
    if amount and currency:
        return f"¿Confirmás si es {currency} {amount} o {currency} {amount} mil aprox.?"
    if amount:
        return f"¿Confirmás si es {amount} o {amount} mil aprox.?"
    return "¿Podés confirmar si el presupuesto es en miles?"


def _slot_has_value(value: Any) -> bool:
    return value not in (None, "", "UNKNOWN")


def _missing_slots_from_commercial(commercial_slots: dict[str, Any] | None) -> list[str]:
    slots: list[str] = []
    source = commercial_slots if isinstance(commercial_slots, dict) else {}
    for key in COMMERCIAL_SLOT_PRIORITY:
        if not _slot_has_value(source.get(key)):
            slots.append(key)
    return slots


def _parse_amount(value: str) -> float | None:
    if not value:
        return None
    cleaned = value.lower()
    multiplier = 1.0
    if "millones" in cleaned or "millon" in cleaned:
        multiplier = 1000000.0
        cleaned = cleaned.replace("millones", "").replace("millon", "")
    elif "mil" in cleaned:
        multiplier = 1000.0
        cleaned = cleaned.replace("mil", "")
    if "k" in cleaned:
        multiplier = 1000.0
        cleaned = cleaned.replace("k", "")
    cleaned = (
        cleaned.replace("usd", "")
        .replace("u$s", "")
        .replace("us$", "")
        .replace("$", "")
        .replace("ars", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", "")
    )
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def _extract_max_price(entities: dict[str, Any], text: str) -> float | None:
    amounts = entities.get("amounts") if isinstance(entities, dict) else None
    if isinstance(amounts, list):
        for amount in amounts:
            parsed = _parse_amount(str(amount))
            if parsed:
                return parsed
    budget_match = PRESUPUESTO_RE.search(text)
    if budget_match:
        parsed = _parse_amount(budget_match.group(1))
        if parsed:
            return parsed
    match = AMOUNT_RE.search(text)
    if match:
        return _parse_amount(match.group(0))
    return None


def _extract_search_filters(state: AiWorkflowState) -> dict[str, Any]:
    normalized = _strip_accents(str(state.get("normalized_input") or "").lower())
    entities = state.get("entities") or {}

    filters: dict[str, Any] = {}
    for alias, city in CITY_ALIASES.items():
        if alias in normalized:
            filters["city"] = city
            break

    for alias, neighborhood in NEIGHBORHOOD_ALIASES.items():
        if alias in normalized:
            filters["neighborhood"] = neighborhood
            break

    rooms = _extract_rooms(normalized)
    if rooms:
        filters["rooms"] = rooms

    currency = _extract_currency(normalized)
    if currency:
        filters["currency"] = currency

    max_price = _extract_max_price(entities, normalized)
    if max_price:
        filters["max_price"] = max_price

    return filters


def _contains_keyword(text: str, keyword: str) -> bool:
    if keyword == "$":
        return "$" in text
    cleaned = _strip_accents(keyword.lower())
    if cleaned.isalnum():
        return re.search(rf"\b{re.escape(cleaned)}\b", text) is not None
    return cleaned in text


def _has_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _intent_order(intent_name: str) -> int:
    return INTENT_PRIORITY.index(intent_name) if intent_name in INTENT_PRIORITY else len(INTENT_PRIORITY)


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    return [str(value)]


def _build_event_data(state: AiWorkflowState, data: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(data or {})
    primary_intent = (
        base.pop("primaryIntent", None)
        or state.get("primary_intent")
        or state.get("intent")
        or "general"
    )
    secondary_intents = base.pop("secondaryIntents", None) or state.get("secondary_intents") or []
    pragmatics_data = state.get("pragmatics") or {}
    speech_act = base.pop("speechAct", None) or pragmatics_data.get("speechAct")
    missing_slots = base.pop("missingSlots", None) or pragmatics_data.get("missingSlots") or {}
    missing_count = state.get("missing_slots_count")
    if missing_count is None:
        missing_count = 0
        if isinstance(missing_slots, dict):
            missing_count = sum(len(slots) for slots in missing_slots.values() if isinstance(slots, list))

    event_data: dict[str, Any] = {
        "primaryIntent": str(primary_intent),
        "secondaryIntents": _ensure_list(secondary_intents),
        "missingSlotsCount": missing_count,
    }
    if speech_act:
        event_data["speechAct"] = speech_act

    decision = base.get("decision") or state.get("decision")
    if decision == "ask_next_best_question":
        question = (
            base.get("recommendedQuestion")
            or pragmatics_data.get("recommendedQuestion")
            or state.get("recommended_question")
        )
        if isinstance(question, str) and question and len(question) <= 160:
            event_data["recommendedQuestion"] = question

    for key, value in base.items():
        if key in ("cleanInput", "normalizedInput", "responseText"):
            continue
        if isinstance(value, str):
            if len(value) > 160:
                continue
            event_data[key] = value
            continue
        event_data[key] = value

    return event_data


async def _record_step(
    run_id: str,
    node_id: str,
    status: str,
    started_at: int,
    ended_at: int,
    summary: str,
    data: dict[str, Any] | None = None,
    event_data: dict[str, Any] | None = None,
    state: AiWorkflowState | None = None,
) -> None:
    step = {
        "runId": run_id,
        "nodeId": node_id,
        "status": status,
        "startedAt": started_at,
        "endedAt": ended_at,
        "summary": summary,
        "data": data or {},
    }
    store.add_step(run_id, step)
    emit_summary = _shorten_text(summary)
    emit_data = _build_event_data(state or {}, event_data if event_data is not None else data)
    await events.emit_run_step(run_id, node_id, status, started_at, ended_at, emit_summary, emit_data)


async def normalize_input(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        raw_input = state.get("input")
        commercial_slots = state.get("commercial_slots")
        intent_hint = state.get("intent_hint")
        clean_input = ""
        
        if isinstance(raw_input, dict):
            clean_input = " ".join(str(raw_input.get("text") or "").split())
            context = raw_input.get("context")
            if isinstance(context, dict):
                commercial = context.get("commercial")
                if isinstance(commercial, dict):
                    commercial_slots = commercial
                hint = context.get("intentHint")
                if hint:
                    intent_hint = str(hint)
        else:
            clean_input = " ".join(str(raw_input or "").split())

        normalized = clean_input.lower()
        summary = f"normalized length={len(clean_input)}"
        data = {"cleanInput": clean_input, "normalizedInput": normalized}
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "normalize_input",
            "completed",
            started_at,
            ended_at,
            summary,
            data,
            state=state,
        )
        return {
            "clean_input": clean_input, 
            "normalized_input": normalized,
            "commercial_slots": commercial_slots,
            "intent_hint": intent_hint
        }
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "normalize_input",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


async def intent_classify(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        normalized = state.get("normalized_input") or ""
        match_text = _strip_accents(normalized.lower())

        intent_hint = state.get("intent_hint")
        if intent_hint and intent_hint in INTENT_KEYWORDS:
            primary_intent = intent_hint
            scored = [{"name": intent_hint, "score": 100.0, "evidence": ["intent_hint"]}]
            secondary = []
        else:
            scored: list[dict[str, Any]] = []
            for intent_name, keywords in INTENT_KEYWORDS.items():
                evidence = [kw for kw in keywords if _contains_keyword(match_text, kw)]
                score = float(len(evidence))
                if score > 0:
                    scored.append({"name": intent_name, "score": score, "evidence": evidence})

            # Check intent_hint for boosting if we didn't force it (e.g. if we want to just boost property_search)
            # Actually if intent_hint is "property_search" we force it above now.
            # But let's keep the existing logic structure if intent_hint wasn't in keys (unlikely).
            
            if scored:
                scored.sort(
                    key=lambda item: (
                        -item.get("score", 0.0),
                        _intent_order(item["name"]),
                    )
                )
                primary_intent = scored[0]["name"]
                secondary = [item["name"] for item in scored[1:] if item.get("score", 0.0) >= INTENT_SCORE_THRESHOLD]
            else:
                primary_intent = "general"
                secondary = []

        summary = f"primary={primary_intent} intents={len(scored)}"
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "intent_classify",
            "completed",
            started_at,
            ended_at,
            summary,
            {"primaryIntent": primary_intent, "secondaryIntents": secondary, "intents": scored},
            state=state,
        )
        return {
            "intents": scored,
            "primary_intent": primary_intent,
            "secondary_intents": secondary,
            "intent": primary_intent,
        }
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "intent_classify",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


async def extract_entities(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        raw_input = state.get("input") or ""
        text_input = ""
        if isinstance(raw_input, dict):
            text_input = str(raw_input.get("text") or "")
        else:
            text_input = str(raw_input or "")

        emails = _dedupe(EMAIL_RE.findall(text_input))
        phones = _dedupe(PHONE_RE.findall(text_input))
        dni_cuit = _dedupe(DNI_CUIT_RE.findall(text_input))
        addresses = _dedupe(ADDRESS_RE.findall(text_input))
        
        # Check expected slot to guard against mis-parsing
        comm_slots = state.get("commercial_slots") or {}
        expected_slot = comm_slots.get("expected_slot")

        # Use commercial_memory parsing
        zona = commercial_memory.parse_zona(text_input)
        tipologia = commercial_memory.parse_tipologia(text_input)
        visit_preference = commercial_memory.parse_visita(text_input)
        
        # If expected is visit_schedule, we should NOT parse budget/mudanza usually,
        # unless it's very explicit.
        if expected_slot == "visit_schedule" and visit_preference:
            presupuesto, moneda = None, None
            fecha_mudanza = None
        else:
            presupuesto, moneda = commercial_memory.parse_budget_currency(text_input)
            fecha_mudanza = commercial_memory.parse_fecha_mudanza(text_input)
        
        # Guard: fecha_mudanza generic text vs real date
        # If we are NOT expecting a date, and the parsed text is generic (no digits, no month), ignore it.
        if fecha_mudanza and expected_slot != "fecha_mudanza":
            # Heuristic: check if it contains any month name or digits
            has_month = any(m in fecha_mudanza.lower() for m in commercial_memory.MONTH_TOKENS)
            has_digit = any(c.isdigit() for c in fecha_mudanza)
            if not has_month and not has_digit:
                fecha_mudanza = None

        # Guard: Budget mis-parsing (e.g. years like 2026 being parsed as budget)
        # If we are NOT expecting budget, and we found a number without currency, ignore it.
        if presupuesto is not None and expected_slot != "budget":
            if not moneda:
                # If ambiguity is high and we are expecting something else, ignore bare number
                presupuesto = None

        entities = {
            "emails": emails,
            "phones": phones,
            "dni_cuit": dni_cuit,
            "addresses": addresses,
            # Extracted commercial slots
            "zona": zona,
            "tipologia": tipologia,
            "presupuesto": presupuesto,
            "moneda": moneda,
            "fecha_mudanza": fecha_mudanza,
            "visit": visit_preference,
        }
        # Simplified ambiguity detection since commercial_memory handles most
        # But we still want to flag it if currency is missing so services can ask ambiguity question
        if presupuesto and not moneda:
             entities["budget_ambiguous"] = True

        summary = f"entities: email={len(emails)} phone={len(phones)} commercial="
        found_comm = [k for k in COMMERCIAL_SLOT_PRIORITY if entities.get(k)]
        summary += ",".join(found_comm) if found_comm else "none"
        if visit_preference:
            summary += " +visit"
        
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "extract_entities",
            "completed",
            started_at,
            ended_at,
            summary,
            entities,
            state=state,
        )
        return {"entities": entities}
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "extract_entities",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


async def pragmatics(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        normalized = state.get("normalized_input") or ""
        match_text = _strip_accents(normalized.lower())
        intents = state.get("intents") or []
        entities = state.get("entities") or {}
        
        # Merge commercial slots: start with known history, override with new entities
        current_commercial = state.get("commercial_slots") or {}
        merged_commercial = dict(current_commercial)
        
        # Override with extracted entities if present
        if entities.get("zona"):
            merged_commercial["zona"] = entities["zona"]
        if entities.get("tipologia"):
            merged_commercial["tipologia"] = entities["tipologia"]
        
        # Budget logic update
        new_amt = entities.get("presupuesto")
        new_cur = entities.get("moneda")
        
        if new_amt is not None:
             merged_commercial["presupuesto"] = new_amt
             merged_commercial["budget_ambiguous"] = False
        
        if new_cur is not None:
             merged_commercial["moneda"] = new_cur
             merged_commercial["budget_ambiguous"] = False
        
        if entities.get("budget_ambiguous"):
            merged_commercial["budget_ambiguous"] = True
            
        if entities.get("fecha_mudanza"):
            merged_commercial["fecha_mudanza"] = entities["fecha_mudanza"]
            
        if entities.get("visit"):
            merged_commercial["visit"] = entities["visit"]
            
        state["commercial_slots"] = merged_commercial

        speech_act = "other"
        if _has_any_token(match_text, COMPLAINT_TOKENS):
            speech_act = "complaint"
        elif "?" in match_text or _has_any_token(match_text, QUESTION_TOKENS):
            speech_act = "question"
        elif _has_any_token(match_text, GREETING_TOKENS):
            speech_act = "greeting"
        elif any(token in match_text for token in ("quiero", "necesito", "solicito")):
            speech_act = "request"

        urgency = "high" if _has_any_token(match_text, URGENT_TOKENS) else "low"

        primary_intent = state.get("primary_intent") or state.get("intent") or "general"
        secondary_intents = state.get("secondary_intents") or []
        property_search_hint = (
            state.get("intent_hint") == "property_search"
            or primary_intent == "property_search"
        )
        missing_slots: dict[str, list[str]] = {}
        recommended_questions: list[str] = []
        
        if property_search_hint:
            slots = commercial_memory.calculate_missing_slots(merged_commercial)
            filters = _extract_search_filters(state)
            if filters.get("city") or filters.get("neighborhood"):
                slots = [slot for slot in slots if slot != "zona"]
            if filters.get("rooms"):
                slots = [slot for slot in slots if slot != "tipologia"]
            if filters.get("max_price"):
                slots = [slot for slot in slots if slot != "presupuesto"]
            if filters.get("currency"):
                slots = [slot for slot in slots if slot != "moneda"]
            
            # Check budget ambiguity
            if merged_commercial.get("budget_ambiguous"):
                if "moneda" not in slots:
                    slots.append("moneda")

            missing_slots["property_search"] = slots
            if slots:
                rec_q, _ = commercial_memory.build_next_best_question(slots)
                if rec_q:
                    recommended_questions.append(rec_q)
                    state["recommended_question"] = rec_q

        intents_for_missing: list[str] = []
        if primary_intent and primary_intent != "general":
            intents_for_missing.append(primary_intent)
        for intent_name in secondary_intents:
            if intent_name and intent_name != "general" and intent_name not in intents_for_missing:
                intents_for_missing.append(intent_name)

        for intent_name in intents_for_missing:
            if intent_name == "property_search":
                continue
            template_slots = PRAGMATICS_MISSING_SLOTS.get(intent_name) or []
            if not template_slots:
                continue
            missing_for_intent: list[str] = []
            for slot in template_slots:
                has_value = False
                if slot == "currency":
                    has_value = bool(entities.get("moneda") or merged_commercial.get("moneda"))
                elif slot == "budget":
                    has_value = bool(entities.get("presupuesto") or merged_commercial.get("presupuesto"))
                elif slot == "project_or_zone":
                    has_value = bool(entities.get("zona") or merged_commercial.get("zona"))
                elif slot == "date_range":
                    has_value = bool(entities.get("visit") or entities.get("fecha_mudanza"))
                elif slot == "dni":
                    has_value = bool(entities.get("dni_cuit"))
                elif slot == "income_proof":
                    has_value = "recibo" in match_text or "ingresos" in match_text
                elif slot == "contact_method":
                    has_value = bool(entities.get("phones") or entities.get("emails"))
                elif slot == "unit":
                    has_value = bool(entities.get("tipologia") or merged_commercial.get("tipologia"))
                elif slot == "unit_type":
                    has_value = bool(entities.get("tipologia") or merged_commercial.get("tipologia"))
                else:
                    has_value = bool(entities.get(slot))
                if not has_value:
                    missing_for_intent.append(slot)
            if missing_for_intent:
                missing_slots[intent_name] = missing_for_intent
                question_template = QUESTION_TEMPLATES.get(intent_name)
                if question_template:
                    recommended_questions.append(question_template)
            
        recommended_questions = _dedupe(recommended_questions)
        missing_slots_count = sum(len(slots) for slots in missing_slots.values())

        summary = (
            f"speechAct={speech_act} urgency={urgency} "
            f"missing={missing_slots.get('property_search')} count={missing_slots_count}"
        )
        
        data = {
            "speechAct": speech_act,
            "urgency": urgency,
            "missingSlots": missing_slots,
            "missingSlotsCount": missing_slots_count,
            "recommendedQuestions": recommended_questions,
        }

        # Calculate recommended question immediately for use in decide_next
        if property_search_hint:
            slots = missing_slots.get("property_search")
            if slots:
                rec_q, _ = commercial_memory.build_next_best_question(slots)
                if rec_q:
                    data["recommendedQuestion"] = rec_q
                    state["recommended_question"] = rec_q
        elif recommended_questions:
            data["recommendedQuestion"] = recommended_questions[0]
            state["recommended_question"] = recommended_questions[0]

        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "pragmatics",
            "completed",
            started_at,
            ended_at,
            summary,
            data,
            state=state,
        )
        return {
            "pragmatics": data,
            "commercial_slots": merged_commercial,
            "missing_slots_count": missing_slots_count,
            "recommended_questions": recommended_questions,
        }
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "pragmatics",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


async def decide_next(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        # Init variables for payload
        search_filters: dict[str, Any] = {}
        options: dict[str, Any] | None = None
        step_data: dict[str, Any] = {}
        
        decision = "search"
        intent = state.get("intent") or state.get("primary_intent") or "general"
        pragmatics = state.get("pragmatics") or {}
        missing_slots = pragmatics.get("missingSlots") or {}
        comm_slots = state.get("commercial_slots") or {}
        missing_slots_count = int(
            state.get("missing_slots_count")
            or pragmatics.get("missingSlotsCount")
            or 0
        )
        property_search_mode = (
            state.get("intent_hint") == "property_search"
            or intent == "property_search"
        )
        
        if intent == "handoff_agent":
            decision = "handoff"
        elif intent == "docs":
            decision = "request_docs"
        elif property_search_mode:
            prop_missing = missing_slots.get("property_search")
            if prop_missing is None and not missing_slots:
                prop_missing = []
            if prop_missing:
                decision = "ask_next_best_question"
            else:
                # All slots filled. Check visit.
                visit = comm_slots.get("visit")
                handoff_done = comm_slots.get("handoff_done")
                
                if not visit:
                    decision = "close_commercial" if intent == "property_search" else "ask_visit_schedule"
                    comm_slots["expected_slot"] = "visit_schedule"
                
                elif visit and not handoff_done:
                    decision = "handoff_to_sales"
                    comm_slots["handoff_done"] = True
                    comm_slots["expected_slot"] = None
                else:
                    # Already handed off or just chatting?
                    decision = "search" # Fallback to search/reply
        else:
            primary_missing = missing_slots.get(intent) or []
            if primary_missing:
                decision = "ask_next_best_question"
            elif pragmatics.get("urgency") == "high":
                decision = "escalate"
            elif pragmatics.get("speechAct") == "greeting" and intent == "general" and not comm_slots:
                decision = "welcome"
            
        summary = f"decision={decision}"
        ended_at = _epoch_ms()
        if search_filters:
            step_data["filters"] = search_filters
        if options:
            step_data["optionsCount"] = len(options)
        if missing_slots_count > 0:
            step_data["missingSlotsCount"] = missing_slots_count
        await _record_step(
            run_id,
            "decide_next",
            "completed",
            started_at,
            ended_at,
            summary,
            step_data,
            state=state,
        )
        
        payload: dict[str, Any] = {"decision": decision}
        if search_filters:
            payload["search_filters"] = search_filters
        if options:
            payload["options"] = options
        if missing_slots_count > 0:
            payload["missing_slots_count"] = missing_slots_count
        
        # Include merged commercial state in output
        if state.get("commercial_slots"):
            payload["commercial"] = state.get("commercial_slots")
        recommended_question = (
            state.get("recommended_question")
            or pragmatics.get("recommendedQuestion")
        )
        if recommended_question:
            payload["recommended_question"] = recommended_question
        recommended_questions = pragmatics.get("recommendedQuestions") or state.get("recommended_questions") or []
        if recommended_questions:
            payload["recommended_questions"] = recommended_questions

        return payload
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "decide_next",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


async def build_response(state: AiWorkflowState) -> dict[str, Any]:
    run_id = state.get("run_id", "")
    started_at = _epoch_ms()
    try:
        decision = state.get("decision")
        intent = state.get("intent")
        pragmatics = state.get("pragmatics") or {}
        comm_slots = state.get("commercial_slots") or {}
        
        response_text = "Lo siento, no entendí bien."

        if decision == "ask_next_best_question":
            response_text = (
                state.get("recommended_question")
                or pragmatics.get("recommendedQuestion")
                or ((pragmatics.get("recommendedQuestions") or [None])[0])
                or "Cuéntame más sobre lo que buscas."
            )
            
        elif decision == "ask_visit_schedule" or decision == "close_commercial":
             zona = comm_slots.get("zona") or "?"
             tipo = comm_slots.get("tipologia") or "?"
             pres = comm_slots.get("presupuesto") or "?"
             mon = comm_slots.get("moneda") or ""
             response_text = (
                 f"¡Perfecto! Tengo tus preferencias: {zona}, {tipo}, {mon} {pres}. "
                 "¿Qué día y horario te queda bien para visitar?"
             )
             
        elif decision == "handoff_to_sales":
             # Confirm schedule, summarize slots, handoff
             # visit is dict {visit_day_of_week..., visit_time_from...}
             visit = comm_slots.get("visit") or {}
             day = visit.get("visit_day_of_week") or "?"
             time = visit.get("visit_time_from") or "?"
             
             zona = comm_slots.get("zona") or "?"
             tipo = comm_slots.get("tipologia") or "?"
             pres = comm_slots.get("presupuesto") or "?"
             mon = comm_slots.get("moneda") or ""
             mud = comm_slots.get("fecha_mudanza") or ""
             mid_text = ""
             if mud:
                 mid_text = f", mudanza {mud}"

             response_text = (
                 f"Excelente. Agendamos para el {day} a las {time}. "
                 f"Resumen: {zona}, {tipo}, {mon} {pres}{mid_text}. "
                 "Un asesor te confirma en breve. ¿WhatsApp o llamada?"
             )

        elif decision == "welcome":
            response_text = "¡Hola! Soy el asistente de Vértice360. ¿En qué zona estás buscando propiedad?"
        elif decision == "request_docs":
            response_text = "Por favor enviame tu DNI y recibo de sueldo por aquí para avanzar."
        else:
            # Fallback / General Search
            response_text = "Estoy buscando propiedades que coincidan con tu criterio..."
        
        summary = f"response len={len(response_text)}"
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "build_response",
            "completed",
            started_at,
            ended_at,
            summary,
            {"responseText": response_text},
            state=state,
        )
        return {"response_text": response_text}
    except Exception as exc:
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "build_response",
            "failed",
            started_at,
            ended_at,
            f"failed: {exc}",
            {"error": str(exc)},
            state=state,
        )
        raise


def build_graph() -> Any:
    graph = StateGraph(AiWorkflowState)
    graph.add_node("normalize_input", normalize_input)
    graph.add_node("intent_classify", intent_classify)
    graph.add_node("extract_entities", extract_entities)
    graph.add_node("pragmatics", pragmatics)
    graph.add_node("decide_next", decide_next)
    graph.add_node("build_response", build_response)

    graph.set_entry_point("normalize_input")
    graph.add_edge("normalize_input", "intent_classify")
    graph.add_edge("intent_classify", "extract_entities")
    graph.add_edge("extract_entities", "pragmatics")
    graph.add_edge("pragmatics", "decide_next")
    graph.add_edge("decide_next", "build_response")
    graph.add_edge("build_response", END)
    return graph.compile()


workflow_graph = build_graph()


def workflow_definition() -> dict[str, Any]:
    return {
        "workflowId": WORKFLOW_ID,
        "name": WORKFLOW_NAME,
        "description": WORKFLOW_DESCRIPTION,
        "nodes": list(WORKFLOW_NODES),
    }
