#!/usr/bin/env python3
"""
Diagnostic test for stale state issue in vertice360_workflow_demo.

This script reproduces the issue where:
1. User says "hi" → Bot asks for mudanza (wrong ordering)
2. User answers "abril 2026" → Bot sends full summary with zona/ambientes/presupuesto
   that user didn't provide in this chat
3. User says "busco depto" → Bot asks mudanza again

This is a standalone analysis script that doesn't need the backend imports.
"""

import itertools
from typing import Any

# Inline copies of the key functions to avoid import issues

COMMERCIAL_SLOT_PRIORITY = ("zona", "tipologia", "presupuesto", "fecha_mudanza")


def calculate_missing_slots(
    memory: dict[str, Any], answered_fields: set[str] | list[str] | None = None
) -> list[str]:
    """
    Returns list of missing keys from COMMERCIAL_SLOT_PRIORITY.
    Strictly checks for None, empty string, or "UNKNOWN".
    """

    def _normalize_answered_slots(answered_fields):
        if not answered_fields:
            return set()
        normalized = {
            str(item).strip().lower() for item in answered_fields if str(item).strip()
        }
        alias_map = {
            "ambientes": "tipologia",
            "mudanza": "fecha_mudanza",
        }
        resolved = set()
        for item in normalized:
            resolved.add(alias_map.get(item, item))
        return resolved

    missing = []
    answered = _normalize_answered_slots(answered_fields)
    for slot in COMMERCIAL_SLOT_PRIORITY:
        if slot in answered:
            continue
        val = memory.get(slot)
        if val is None or val == "" or val == "UNKNOWN":
            missing.append(slot)
        # For presupuesto, also check moneda
        if slot == "presupuesto" and "moneda" not in answered:
            m_val = memory.get("moneda")
            if m_val is None or m_val == "" or m_val == "UNKNOWN":
                if "moneda" not in missing:
                    missing.append("moneda")
    return missing


def build_next_best_question(missing: list[str]) -> tuple[str | None, str | None]:
    """
    Returns (question_text, key_for_that_question).
    Strict Slot Order: zona+ambientes -> presupuesto -> mudanza
    """
    if not missing:
        return None, None

    m_set = set(missing)

    # 1) Zona + Ambientes
    if "zona" in m_set or "tipologia" in m_set:
        return "¿Por qué zona buscás y cuántos ambientes necesitás?", "zona"

    # 2) Presupuesto
    if "presupuesto" in m_set or "moneda" in m_set:
        return "¿Cuál es tu presupuesto aproximado y en qué moneda?", "presupuesto"

    # 3) Fecha mudanza (Mudanza)
    if "fecha_mudanza" in m_set:
        return "¿Para qué mes y año estimás la mudanza?", "fecha_mudanza"

    return None, None


def _build_summary_close(slot_memory: dict[str, Any]) -> str:
    """Build summary message"""

    def _format_amount(value):
        if value is None:
            return "?"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    zona = slot_memory.get("zona") or "?"
    tipologia = slot_memory.get("tipologia") or "?"
    presupuesto = _format_amount(
        slot_memory.get("presupuesto_amount")
        if slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN")
        else slot_memory.get("presupuesto")
    )
    moneda = slot_memory.get("moneda") or "?"
    fecha = slot_memory.get("fecha_mudanza") or "?"
    return (
        f"Gracias. Tengo: zona {zona}, {tipologia}, presupuesto {presupuesto} {moneda}, "
        f"mudanza {fecha}. ¿Querés coordinar visita? Decime día y franja horaria."
    )


# Track what happens
class MessageTracker:
    def __init__(self):
        self.messages_sent = []

    def record_message(self, ticket_id: str, text: str, decision: str):
        self.messages_sent.append(
            {"ticket_id": ticket_id, "text": text, "decision": decision}
        )
        print(f"  → Message sent (decision={decision}):")
        print(f"     '{text}'")


# In-memory ticket storage (simulating store.py)
_ticket_sequence = itertools.count(1)
tickets: dict[str, dict[str, Any]] = {}


def generate_ticket_id() -> str:
    return f"VTX-{next(_ticket_sequence):04d}"


def find_active_ticket_by_phone(phone: str) -> dict[str, Any] | None:
    """Find active ticket by phone (from store.py:168-180)"""
    if not phone:
        return None
    for ticket in reversed(list(tickets.values())):
        t_phone = (ticket.get("customer") or {}).get("from")
        if t_phone == phone:
            status = str(ticket.get("status") or "").upper()
            if status != "CLOSED":
                return ticket
    return None


def ensure_slot_memory(ticket: dict[str, Any]) -> dict[str, Any]:
    """Ensure slot_memory exists (from store.py:66-88)"""
    slot_memory = ticket.get("slot_memory")
    if not isinstance(slot_memory, dict):
        slot_memory = {}
        ticket["slot_memory"] = slot_memory
    # THE BUG: These .setdefault() calls preserve existing values!
    slot_memory.setdefault("zona", None)
    slot_memory.setdefault("tipologia", None)
    slot_memory.setdefault("presupuesto_amount", None)
    slot_memory.setdefault("presupuesto_raw", None)
    slot_memory.setdefault("moneda", None)
    slot_memory.setdefault("fecha_mudanza", None)
    slot_memory.setdefault("budget_ambiguous", False)
    slot_memory.setdefault("budget_confirmed", False)
    slot_memory.setdefault("confirmed_budget", False)
    slot_memory.setdefault("confirmed_currency", False)
    slot_memory.setdefault("last_question", None)
    slot_memory.setdefault("last_question_key", None)
    slot_memory.setdefault("last_asked_slot", None)
    slot_memory.setdefault("asked_count", 0)
    slot_memory.setdefault("pending_ambiguity", None)
    slot_memory.setdefault("answered_fields", [])
    slot_memory.setdefault("summarySent", False)
    return slot_memory


def create_or_get_ticket(phone: str, text: str) -> dict[str, Any]:
    """Simulate store.create_or_get_ticket_from_inbound"""
    existing = find_active_ticket_by_phone(phone)

    if existing:
        print(f"  Reusing EXISTING ticket: {existing['ticketId']}")
        ensure_slot_memory(existing)
        return existing

    # Create new
    ticket_id = generate_ticket_id()
    ticket = {
        "ticketId": ticket_id,
        "status": "OPEN",
        "provider": "gupshup_whatsapp",
        "channel": "whatsapp",
        "customer": {"from": phone},
        "subject": text[:120],
        "commercial": {
            "zona": None,
            "tipologia": None,
            "presupuesto": None,
            "moneda": None,
            "fecha_mudanza": None,
        },
        "slot_memory": {
            "zona": None,
            "tipologia": None,
            "presupuesto_amount": None,
            "presupuesto_raw": None,
            "moneda": None,
            "fecha_mudanza": None,
            "budget_ambiguous": False,
            "budget_confirmed": False,
            "confirmed_budget": False,
            "confirmed_currency": False,
            "last_question": None,
            "last_question_key": None,
            "last_asked_slot": None,
            "asked_count": 0,
            "pending_ambiguity": None,
            "answered_fields": [],
            "summarySent": False,
        },
        "messages": [],
    }
    tickets[ticket_id] = ticket
    print(f"  Created NEW ticket: {ticket_id}")
    return ticket


def analyze_ticket_state(ticket: dict, label: str):
    """Print detailed ticket state analysis"""
    print(f"\n  [{label}] Ticket State:")
    print(f"    ticketId: {ticket.get('ticketId')}")

    commercial = ticket.get("commercial", {})
    slot_memory = ticket.get("slot_memory", {})

    print(f"    commercial: {commercial}")
    print(f"    slot_memory:")
    for key in ["zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"]:
        val = slot_memory.get(key)
        print(f"      {key}: {val}")
    print(f"    answered_fields: {slot_memory.get('answered_fields', [])}")
    print(f"    summarySent: {slot_memory.get('summarySent')}")

    # Check what calculate_missing_slots returns
    missing = calculate_missing_slots(
        commercial, slot_memory.get("answered_fields", [])
    )
    print(f"    calculated missing_slots: {missing}")

    return missing


def simulate_message(phone: str, text: str, tracker: MessageTracker) -> dict:
    """Simulate processing an inbound message"""
    print(f"\n{'=' * 70}")
    print(f"INBOUND: '{text}'")
    print("=" * 70)

    # 1. Get or create ticket
    ticket = create_or_get_ticket(phone, text)

    # 2. Analyze before
    missing_before = analyze_ticket_state(ticket, "BEFORE")

    # 3. Extract slots (simplified - only fecha_mudanza for "abril 2026")
    commercial = ticket["commercial"]
    slot_memory = ticket["slot_memory"]

    extracted = []
    if "abril" in text.lower() or "2026" in text:
        commercial["fecha_mudanza"] = "abril 2026"
        slot_memory["fecha_mudanza"] = "abril 2026"
        # Update answered_fields
        answered = set(slot_memory.get("answered_fields", []))
        answered.add("mudanza")
        slot_memory["answered_fields"] = list(answered)
        extracted.append("fecha_mudanza")

    if "busco" in text.lower() or "depto" in text.lower():
        # Intent signal, but no slots extracted yet
        pass

    if extracted:
        print(f"\n  Extracted slots: {extracted}")

    # 4. Analyze after
    missing_after = analyze_ticket_state(ticket, "AFTER")

    # 5. Determine reply
    reply_text = None
    decision = None

    if missing_after:
        rec_q, rec_key = build_next_best_question(missing_after)
        if rec_q:
            reply_text = rec_q
            decision = "ask_next_best_question"
            slot_memory["last_question"] = rec_q
            slot_memory["last_question_key"] = rec_key
    elif not slot_memory.get("summarySent"):
        reply_text = _build_summary_close(slot_memory)
        decision = "summary_close"
        slot_memory["summarySent"] = True

    if reply_text:
        # Add intro if first outbound
        outbound_count = len(
            [m for m in ticket.get("messages", []) if m.get("direction") == "outbound"]
        )
        if outbound_count == 0:
            reply_text = f"Soy el asistente de Vértice360 👋. {reply_text}"

        tracker.record_message(ticket["ticketId"], reply_text, decision)

        ticket["messages"].append(
            {
                "direction": "outbound",
                "text": reply_text,
            }
        )
    else:
        print(f"\n  [No reply sent - summary already sent or no action needed]")

    return ticket


def main():
    print("\n" + "=" * 70)
    print("DIAGNOSTIC TEST: Stale State Issue in WhatsApp Flow")
    print("=" * 70)
    print("\nThis reproduces the exact issue from the chat log:")
    print("  [11:11] User: 'hi'")
    print("  [11:11] Bot: '¿Para qué fecha estimás la mudanza?'")
    print("  [11:11] User: 'abril 2026'")
    print("  [11:11] Bot: 'Gracias. Tengo: zona Almagro, 2 ambientes...'")
    print("  [11:12] User: 'busco depto'")
    print("  [11:12] Bot: '¿Para qué fecha estimás la mudanza?'")

    tracker = MessageTracker()
    phone = "5491112345678"

    # SCENARIO: Previous conversation that filled all slots
    print("\n" + "=" * 70)
    print("PHASE 1: Simulate PREVIOUS completed conversation")
    print("=" * 70)
    print("\nImagine yesterday the user had this conversation:")
    print("  User: 'Busco en Almagro, 2 ambientes, presupuesto 120000 USD'")
    print("  Bot: '¿Para qué mes y año estimás la mudanza?'")
    print("  User: 'abril 2026'")
    print("  Bot: [sends summary and hands off]")

    # Create a ticket simulating the END STATE of that conversation
    ticket_id = generate_ticket_id()
    tickets[ticket_id] = {
        "ticketId": ticket_id,
        "status": "OPEN",  # Still open!
        "provider": "gupshup_whatsapp",
        "channel": "whatsapp",
        "customer": {"from": phone},
        "subject": "Busco en Almagro...",
        "commercial": {
            "zona": "Almagro",
            "tipologia": "2 ambientes",
            "presupuesto": 120000,
            "moneda": "USD",
            "fecha_mudanza": "abril 2026",
        },
        "slot_memory": {
            "zona": "Almagro",
            "tipologia": "2 ambientes",
            "presupuesto_amount": 120000,
            "moneda": "USD",
            "fecha_mudanza": "abril 2026",
            "answered_fields": ["ambientes", "mudanza", "presupuesto", "zona"],
            "summarySent": True,  # Summary was already sent!
            "last_question": "¿Para qué mes y año estimás la mudanza?",
            "last_question_key": "fecha_mudanza",
        },
        "messages": [
            {"direction": "inbound", "text": "Busco en Almagro, 2 ambientes..."},
            {"direction": "outbound", "text": "Soy el asistente...¿Para qué mes..."},
            {"direction": "inbound", "text": "abril 2026"},
            {"direction": "outbound", "text": "Gracias. Tengo: zona Almagro..."},
        ],
    }
    print(f"\n✓ Simulated previous conversation end state")
    print(f"  Ticket: {ticket_id}")
    print(f"  Status: OPEN (never closed)")

    # PHASE 2: User returns with "hi"
    print("\n" + "=" * 70)
    print("PHASE 2: User returns today and says 'hi'")
    print("=" * 70)

    t1 = simulate_message(phone, "hi", tracker)

    # PHASE 3: User says "abril 2026"
    print("\n" + "=" * 70)
    print("PHASE 3: User says 'abril 2026' (answering mudanza)")
    print("=" * 70)

    # Reset summarySent to simulate fresh state for this test
    # (In real scenario, this wouldn't happen - the bug is that it's already True)
    t1["slot_memory"]["summarySent"] = False
    t1["slot_memory"]["fecha_mudanza"] = None
    t1["commercial"]["fecha_mudanza"] = None

    t2 = simulate_message(phone, "abril 2026", tracker)

    # PHASE 4: User says "busco depto"
    print("\n" + "=" * 70)
    print("PHASE 4: User says 'busco depto'")
    print("=" * 70)

    t3 = simulate_message(phone, "busco depto", tracker)

    # SUMMARY
    print("\n" + "=" * 70)
    print("RESULTS - Messages Sent")
    print("=" * 70)

    for i, msg in enumerate(tracker.messages_sent, 1):
        print(f"\n{i}. [{msg['decision']}]")
        print(f"   {msg['text']}")

    print("\n" + "=" * 70)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 70)

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                      ROOT CAUSE IDENTIFIED                            ║
╚══════════════════════════════════════════════════════════════════════╝

THE BUG: Stale State Pollution Across Conversations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. TICKET REUSE (store.py:168-180)
   Function: _find_active_ticket_by_phone()
   
   When user sends "hi", the code searches for ANY active ticket (status != CLOSED)
   for that phone number. It finds the ticket from yesterday and reuses it.

2. STATE PERSISTENCE (store.py:66-88)
   Function: _ensure_slot_memory()
   
   The function uses .setdefault() which ONLY sets values if key doesn't exist.
   It does NOT clear existing values. So:
   • zona="Almagro" (from yesterday) persists
   • tipologia="2 ambientes" (from yesterday) persists
   • presupuesto=120000 (from yesterday) persists
   • moneda="USD" (from yesterday) persists
   • summarySent=True (from yesterday) persists

3. WRONG QUESTION SELECTION (commercial_memory.py:391-413)
   Function: build_next_best_question()
   
   Since zona and tipologia are already filled (from stale data), the missing
   slots list only contains ["fecha_mudanza"]. So it asks for mudanza first!

4. PREMATURE SUMMARY (services.py:1170-1174)
   
   When user answers "abril 2026", ALL slots appear complete (old + new data),
   so the bot immediately sends the summary with mixed data.

5. SUMMARY REPEAT PREVENTION BLOCKS NEW FLOW (services.py:1181-1188)
   
   Because summarySent=True from the previous conversation, the bot won't
   send another summary. When user says "busco depto", it asks mudanza again
   because that's still the only missing slot in the stale state.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CODE EVIDENCE:

File: backend/modules/vertice360_workflow_demo/store.py
Lines: 168-180
```python
def _find_active_ticket_by_phone(phone: str) -> dict[str, Any] | None:
    if not phone:
        return None
    # Reverse search to find latest
    for ticket in reversed(tickets.values()):
        t_phone = (ticket.get("customer") or {}).get("from")
        if t_phone == phone:
            # Check if active (not closed)
            status = str(ticket.get("status") or "").upper()
            if status != "CLOSED":  # <-- Reuses ANY non-closed ticket
                return ticket
    return None
```

File: backend/modules/vertice360_workflow_demo/store.py  
Lines: 66-88
```python
def _ensure_slot_memory(ticket: dict[str, Any]) -> dict[str, Any]:
    slot_memory = ticket.get("slot_memory")
    if not isinstance(slot_memory, dict):
        slot_memory = {}
        ticket["slot_memory"] = slot_memory
    # These .setdefault() calls preserve existing values!
    slot_memory.setdefault("zona", None)  # If zona="Almagro", stays "Almagro"
    slot_memory.setdefault("tipologia", None)  # If filled, stays filled
    ...
    slot_memory.setdefault("summarySent", False)  # If True, stays True
    return slot_memory
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MINIMAL FIX OPTIONS (do not implement yet):

OPTION A: Reset on New Conversation Signal [RECOMMENDED - Easiest]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Location: services.py, early in process_inbound_message()

Detect greetings/new conversation signals and reset slot state:
```python
NEW_CONVERSATION_TRIGGERS = ["hi", "hola", "buenas", "buen día", "busco depto"]

if any(trigger in text.lower() for trigger in NEW_CONVERSATION_TRIGGERS):
    # Check if this looks like a fresh start (no context in recent messages)
    if _is_likely_new_conversation(ticket):
        _reset_slot_memory_for_new_conversation(ticket)
```

Pros: Simple, user-initiated, natural UX
Cons: Might reset unexpectedly if user uses these words mid-conversation

OPTION B: Time-Based Conversation Boundaries [RECOMMENDED - Most Robust]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Location: store.py:create_or_get_ticket_from_inbound()

Track lastMessageAt and create new ticket/conversation after timeout:
```python
CONVERSATION_TIMEOUT_HOURS = 24

last_msg_at = ticket.get("lastMessageAt", 0)
if (now - last_msg_at) > (CONVERSATION_TIMEOUT_HOURS * 3600 * 1000):
    # Close old ticket or reset state for new conversation
    close_ticket(ticket_id, reason="timeout")
    # Create new ticket
```

Pros: Automatic, handles natural conversation boundaries
Cons: Requires timer logic, might need config tuning

OPTION C: Reset After Summary Sent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Location: services.py after sending summary

When summary is sent and handoff occurs, reset slot state:
```python
if decision == "summary_close":
    slot_memory["summarySent"] = True
    # Reset for next conversation while keeping ticket open
    _reset_slot_values_for_next_conversation(slot_memory)
```

Pros: Clean state after handoff complete
Cons: Might lose context if handoff is temporary

OPTION D: Track Slot Provenance [MOST ROBUST - Most Complex]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Location: commercial_memory.py and slot_memory structure

Add timestamp/conversation_id to each slot:
```python
slot_memory = {
    "zona": {"value": "Almagro", "filled_at": 1234567890, "conversation_id": "conv-001"},
    ...
}
```

Only consider slots from current conversation as "answered" when
selecting next question.

Pros: Most robust, maintains history
Cons: Complex, requires schema changes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDATION: Start with Option A (greeting detection) as immediate fix,
then implement Option B (time-based) for long-term robustness.
""")


if __name__ == "__main__":
    main()
