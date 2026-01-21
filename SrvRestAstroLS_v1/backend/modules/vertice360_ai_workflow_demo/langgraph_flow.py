from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.modules.vertice360_ai_workflow_demo import events, store


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
    input: str
    mode: str | None
    clean_input: str
    normalized_input: str
    intent: str
    intents: list[dict[str, Any]]
    primary_intent: str
    secondary_intents: list[str]
    entities: dict[str, list[str]]
    pragmatics: dict[str, Any]
    decision: str
    response_text: str


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{6,}\d")
DNI_CUIT_RE = re.compile(r"\b\d{7,8}\b|\b\d{2}-\d{8}-\d{1}\b")
AMOUNT_RE = re.compile(r"(?:usd|\$)\s?\d[\d.,]*|\b\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?\b", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"\b(?:calle|av\.?|avenida|ruta|direccion)\s+[A-Za-z0-9\s]{3,40}",
    re.IGNORECASE,
)

INTENT_SCORE_THRESHOLD = 1.0
INTENT_PRIORITY = [
    "docs",
    "visit",
    "price",
    "location",
    "financing",
    "availability",
    "handoff_agent",
]
INTENT_KEYWORDS = {
    "price": ["precio", "valor", "cuanto", "usd", "ars", "$", "presupuesto"],
    "location": ["ubicacion", "zona", "barrio", "direccion", "donde", "mapa"],
    "visit": ["visita", "ver", "recorrer", "tour", "mostrar", "coordinar"],
    "docs": ["docs", "documentacion", "documentos", "dni", "cuit", "recibo", "ingresos"],
    "availability": ["disponible", "hay", "quedan", "stock", "unidades"],
    "financing": ["financiacion", "cuotas", "anticipo", "plan", "credito"],
    "handoff_agent": ["humano", "asesor", "llamar", "contacto", "agente"],
}
PRAGMATICS_MISSING_SLOTS = {
    "price": ["currency", "budget", "unit"],
    "location": ["project_or_zone"],
    "visit": ["date_range"],
    "docs": ["dni", "income_proof"],
    "availability": ["unit_type"],
    "financing": ["down_payment", "terms"],
    "handoff_agent": ["contact_method"],
}
QUESTION_TEMPLATES = {
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


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


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
        raw_input = str(state.get("input") or "")
        clean_input = " ".join(raw_input.split())
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
        return {"clean_input": clean_input, "normalized_input": normalized}
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

        scored: list[dict[str, Any]] = []
        for intent_name, keywords in INTENT_KEYWORDS.items():
            evidence = [kw for kw in keywords if _contains_keyword(match_text, kw)]
            score = float(len(evidence))
            if score > 0:
                scored.append({"name": intent_name, "score": score, "evidence": evidence})

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
        emails = _dedupe(EMAIL_RE.findall(raw_input))
        phones = _dedupe(PHONE_RE.findall(raw_input))
        dni_cuit = _dedupe(DNI_CUIT_RE.findall(raw_input))
        amounts = _dedupe(AMOUNT_RE.findall(raw_input))
        addresses = _dedupe(ADDRESS_RE.findall(raw_input))
        entities = {
            "emails": emails,
            "phones": phones,
            "dni_cuit": dni_cuit,
            "amounts": amounts,
            "addresses": addresses,
        }
        summary = f"entities: email={len(emails)} phone={len(phones)} dni_cuit={len(dni_cuit)}"
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

        relevant = [
            item for item in intents if float(item.get("score", 0.0)) >= INTENT_SCORE_THRESHOLD
        ]
        missing_slots: dict[str, list[str]] = {}
        for item in relevant:
            intent_name = item.get("name")
            slots = list(PRAGMATICS_MISSING_SLOTS.get(intent_name, []))
            if not slots:
                continue
            if intent_name == "price":
                if entities.get("amounts"):
                    slots = [slot for slot in slots if slot != "budget"]
                if any(token in match_text for token in ("usd", "ars", "$")):
                    slots = [slot for slot in slots if slot != "currency"]
            missing_slots[intent_name] = slots

        recommended: list[str] = []
        for intent_name in sorted(missing_slots.keys(), key=_intent_order):
            if not missing_slots[intent_name]:
                continue
            question = QUESTION_TEMPLATES.get(intent_name)
            if question and question not in recommended:
                recommended.append(question)
            if len(recommended) >= 2:
                break
        if not recommended and relevant:
            fallback_intent = sorted(
                (item.get("name") for item in relevant),
                key=_intent_order,
            )[0]
            fallback_question = QUESTION_TEMPLATES.get(fallback_intent)
            if fallback_question:
                recommended.append(fallback_question)

        payload = {
            "speechAct": speech_act,
            "urgency": urgency,
            "missingSlots": missing_slots,
            "recommendedQuestions": recommended[:2],
        }
        summary = f"speechAct={speech_act} urgency={urgency}"
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "pragmatics",
            "completed",
            started_at,
            ended_at,
            summary,
            payload,
            state=state,
        )
        return {"pragmatics": payload}
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
        primary_intent = state.get("primary_intent") or state.get("intent") or "general"
        intents = state.get("intents") or []
        relevant = [
            item for item in intents if float(item.get("score", 0.0)) >= INTENT_SCORE_THRESHOLD
        ]
        relevant_names = {item.get("name") for item in relevant}

        if primary_intent == "docs":
            decision = "ask_docs"
        elif "handoff_agent" in relevant_names:
            decision = "handoff_agent"
        elif len(relevant_names) >= 2:
            decision = "answer_multi"
        else:
            decision = "answer_basic"

        summary = f"decision={decision}"
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "decide_next",
            "completed",
            started_at,
            ended_at,
            summary,
            {"decision": decision},
            state=state,
        )
        return {"decision": decision}
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
        intent = state.get("primary_intent") or state.get("intent") or "general"
        decision = state.get("decision") or "answer_basic"

        if decision == "ask_docs":
            response = (
                "Para avanzar con tu solicitud necesito la documentacion basica: "
                "DNI frente/dorso y comprobante de pago. Si ya la tenes, enviala por este canal."
            )
        elif decision == "handoff_agent":
            response = (
                "Perfecto, te paso con un asesor humano para continuar. "
                "Si podes, deja telefono o email para coordinar."
            )
        elif decision == "answer_multi":
            intents = state.get("intents") or []
            intent_scores = {
                item.get("name"): float(item.get("score", 0.0)) for item in intents
            }
            ordered = sorted(
                intent_scores.items(),
                key=lambda item: (
                    -item[1],
                    _intent_order(item[0]),
                ),
            )
            lines = []
            for name, score in ordered:
                if score < INTENT_SCORE_THRESHOLD:
                    continue
                if name == "price":
                    lines.append("Precio y opciones: compartime presupuesto y moneda.")
                elif name == "location":
                    lines.append("Ubicacion y zona: decime ciudad o barrio y envio mapa.")
                elif name == "visit":
                    lines.append("Visitas: decime dia y horario preferido.")
                elif name == "docs":
                    lines.append("Documentacion: DNI frente/dorso y comprobante.")
                elif name == "availability":
                    lines.append("Disponibilidad: indico unidades segun tipologia.")
                elif name == "financing":
                    lines.append("Financiacion: opciones de cuotas y anticipo.")
                elif name == "handoff_agent":
                    lines.append("Asesor humano: te contacto para continuar.")
                if len(lines) >= 4:
                    break
            response = "\n".join(f"- {line}" for line in lines) or (
                "Puedo ayudarte con precios, ubicacion, visitas y documentacion."
            )
        else:
            if intent == "price":
                response = (
                    "Los precios varian segun unidad y etapa. "
                    "Indica presupuesto y moneda y te comparto opciones."
                )
            elif intent == "location":
                response = (
                    "Estamos ubicados en una zona de facil acceso. "
                    "Decime la ciudad y te envio mapa y referencias."
                )
            elif intent == "visit":
                response = "Podemos coordinar una visita. Decime dia y horario preferido."
            else:
                response = (
                    "Gracias por el mensaje. Puedo ayudarte con disponibilidad, precios, ubicacion y visitas."
                )

        if decision in ("answer_basic", "answer_multi"):
            pragmatics_data = state.get("pragmatics") or {}
            questions = pragmatics_data.get("recommendedQuestions") or []
            questions = [question for question in questions if question][:2]
            if questions:
                prompt = " ".join(questions)
                response = f"{response} Para afinar: {prompt}"
                if len(response) > 400:
                    if len(questions) > 1:
                        prompt = questions[0]
                        response = f"{response.split(' Para afinar:')[0]} Para afinar: {prompt}"
                    if len(response) > 400:
                        response = response[:400].rstrip()

        summary = f"response length={len(response)}"
        ended_at = _epoch_ms()
        await _record_step(
            run_id,
            "build_response",
            "completed",
            started_at,
            ended_at,
            summary,
            {"responseText": response},
            {"responsePreview": _shorten_text(response, 120), "responseLength": len(response)},
            state=state,
        )
        return {"response_text": response}
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
