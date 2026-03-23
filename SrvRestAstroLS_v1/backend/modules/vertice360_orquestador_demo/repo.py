from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_SCHEMA_CACHE: dict[str, list[str]] | None = None
_PROJECT_CAPABILITIES_CACHE: dict[str, bool] | None = None

_PROJECT_TABLE_KEYWORDS = (
    "project",
    "marketing",
    "unit",
    "price",
    "availability",
    "payment",
    "finance",
    "delivery",
    "amenit",
    "tipolog",
)


def _column_names(cursor: Any) -> list[str]:
    description = cursor.description or []
    names: list[str] = []
    for col in description:
        names.append(getattr(col, "name", col[0]))
    return names


def fetch_all(conn: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    columns = _column_names(cursor)
    return [dict(zip(columns, row, strict=False)) for row in rows]


def fetch_one(conn: Any, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    if row is None:
        return None
    columns = _column_names(cursor)
    return dict(zip(columns, row, strict=False))


def ensure_ticket_inbound_line_columns(conn: Any) -> None:
    if not hasattr(conn, "execute"):
        return
    conn.execute("alter table tickets add column if not exists inbound_line_key text")
    conn.execute("alter table tickets add column if not exists inbound_line_phone text")


def list_projects(conn: Any) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        select id, code, name, description, location_jsonb, tags, status, created_at, updated_at
        from projects
        order by code asc
        """,
    )


def list_marketing_assets(conn: Any) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        select
            ma.id,
            ma.project_id,
            p.code as project_code,
            p.name as project_name,
            ma.channel,
            ma.title,
            ma.short_copy,
            ma.chips,
            ma.whatsapp_prefill,
            ma.is_active,
            ma.sort_order,
            ma.created_at
        from marketing_assets ma
        join projects p on p.id = ma.project_id
        order by ma.sort_order asc, ma.created_at asc
        """,
    )


def list_users(conn: Any) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        select id, full_name, role, phone_e164, is_active, created_at
        from users
        order by created_at asc
        """,
    )


def get_project_by_code(conn: Any, project_code: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select id, code, name
        from projects
        where upper(code) = upper(%s)
        limit 1
        """,
        (project_code,),
    )


def get_project_by_id(conn: Any, project_id: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select id, code, name
        from projects
        where id = %s
        limit 1
        """,
        (project_id,),
    )


def list_project_codes(conn: Any) -> list[str]:
    rows = fetch_all(conn, "select code from projects order by code asc")
    return [str(row.get("code") or "") for row in rows if row.get("code")]


def get_project_context(conn: Any, project_code: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select
            p.id,
            p.code,
            p.name,
            p.description,
            p.location_jsonb,
            p.tags,
            p.status,
            ma.channel as asset_channel,
            ma.title as asset_title,
            ma.short_copy as asset_short_copy,
            ma.chips as asset_chips
        from projects p
        left join lateral (
            select channel, title, short_copy, chips
            from marketing_assets
            where project_id = p.id
              and is_active = true
            order by sort_order asc, created_at asc
            limit 1
        ) ma on true
        where upper(p.code) = upper(%s)
        limit 1
        """,
        (project_code,),
    )


def get_lead_by_phone(conn: Any, phone_e164: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select id, phone_e164, name, source, consent, utm_jsonb, created_at, updated_at
        from leads
        where phone_e164 = %s
        limit 1
        """,
        (phone_e164,),
    )


def reset_by_phone(conn: Any, phone_e164: str) -> dict[str, int]:
    counts = {
        "events": 0,
        "visit_confirmations": 0,
        "visit_proposals": 0,
        "messages": 0,
        "tickets": 0,
        "conversations": 0,
        "leads": 0,
    }
    clean_phone = str(phone_e164 or "").strip()
    if not clean_phone:
        return counts

    lead = get_lead_by_phone(conn, clean_phone)
    if lead is None:
        return counts

    lead_id = str(lead["id"])
    ticket_rows = fetch_all(conn, "select id from tickets where lead_id = %s", (lead_id,))
    ticket_ids = [str(row["id"]) for row in ticket_rows if row.get("id")]

    if ticket_ids:
        placeholders = ", ".join(["%s"] * len(ticket_ids))
        params = tuple(ticket_ids)

        cursor = conn.execute(
            f"delete from events where correlation_id in ({placeholders})",
            params,
        )
        counts["events"] = int(cursor.rowcount or 0)

        cursor = conn.execute(
            f"delete from visit_confirmations where ticket_id in ({placeholders})",
            params,
        )
        counts["visit_confirmations"] = int(cursor.rowcount or 0)

        cursor = conn.execute(
            f"delete from visit_proposals where ticket_id in ({placeholders})",
            params,
        )
        counts["visit_proposals"] = int(cursor.rowcount or 0)

    cursor = conn.execute("delete from messages where lead_id = %s", (lead_id,))
    counts["messages"] = int(cursor.rowcount or 0)

    cursor = conn.execute("delete from tickets where lead_id = %s", (lead_id,))
    counts["tickets"] = int(cursor.rowcount or 0)

    cursor = conn.execute("delete from conversations where lead_id = %s", (lead_id,))
    counts["conversations"] = int(cursor.rowcount or 0)

    cursor = conn.execute("delete from leads where id = %s", (lead_id,))
    counts["leads"] = int(cursor.rowcount or 0)

    return counts


def create_lead(conn: Any, phone_e164: str, source: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into leads (phone_e164, source, updated_at)
        values (%s, %s::channel_type, now())
        returning id, phone_e164, source, created_at, updated_at
        """,
        (phone_e164, source),
    )
    if row is None:
        raise RuntimeError("Failed to create lead")
    return row


def touch_lead(conn: Any, lead_id: str, source: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        update leads
        set source = %s::channel_type,
            updated_at = now()
        where id = %s
        returning id, phone_e164, source, created_at, updated_at
        """,
        (source, lead_id),
    )
    if row is None:
        raise KeyError("lead not found")
    return row


def get_open_conversation_for_lead(conn: Any, lead_id: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select id, lead_id, channel, status, last_message_at, created_at, updated_at
        from conversations
        where lead_id = %s and channel = 'whatsapp'::channel_type
        order by (status = 'open') desc, updated_at desc
        limit 1
        """,
        (lead_id,),
    )


def create_conversation(conn: Any, lead_id: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into conversations (lead_id, channel, status, last_message_at, updated_at)
        values (%s, 'whatsapp'::channel_type, 'open', now(), now())
        returning id, lead_id, channel, status, last_message_at, created_at, updated_at
        """,
        (lead_id,),
    )
    if row is None:
        raise RuntimeError("Failed to create conversation")
    return row


def touch_conversation_activity(conn: Any, conversation_id: str) -> None:
    conn.execute(
        """
        update conversations
        set status = 'open',
            last_message_at = now(),
            updated_at = now()
        where id = %s
        """,
        (conversation_id,),
    )


def get_ticket_by_conversation(conn: Any, conversation_id: str) -> dict[str, Any] | None:
    ensure_ticket_inbound_line_columns(conn)
    return fetch_one(
        conn,
        """
        select
            id,
            conversation_id,
            lead_id,
            project_id,
            stage,
            ai_intervened,
            assigned_advisor_id,
            last_activity_at,
            last_message_snippet,
            visit_scheduled_at,
            inbound_line_key,
            inbound_line_phone,
            summary_jsonb,
            created_at,
            updated_at
        from tickets
        where conversation_id = %s
        limit 1
        """,
        (conversation_id,),
    )


def create_ticket(
    conn: Any,
    conversation_id: str,
    lead_id: str,
    project_id: str | None,
    last_message_snippet: str,
) -> dict[str, Any]:
    ensure_ticket_inbound_line_columns(conn)
    row = fetch_one(
        conn,
        """
        insert into tickets (
            conversation_id,
            lead_id,
            project_id,
            stage,
            ai_intervened,
            last_activity_at,
            last_message_snippet,
            summary_jsonb,
            updated_at
        )
        values (
            %s,
            %s,
            %s,
            'Nuevo'::lead_stage,
            false,
            now(),
            %s,
            %s::jsonb,
            now()
        )
        returning
            id,
            conversation_id,
            lead_id,
            project_id,
            stage,
            assigned_advisor_id,
            last_activity_at,
            last_message_snippet,
            visit_scheduled_at,
            inbound_line_key,
            inbound_line_phone,
            summary_jsonb,
            created_at,
            updated_at
        """,
        (conversation_id, lead_id, project_id, last_message_snippet, json.dumps({})),
    )
    if row is None:
        raise RuntimeError("Failed to create ticket")
    return row


def update_ticket_activity(
    conn: Any,
    ticket_id: str,
    *,
    stage: str | None = None,
    project_id: str | None = None,
    assigned_advisor_id: str | None = None,
    last_message_snippet: str | None = None,
    visit_scheduled_at: Any | None = None,
) -> dict[str, Any]:
    ensure_ticket_inbound_line_columns(conn)
    sets = ["last_activity_at = now()", "updated_at = now()"]
    params: list[Any] = []

    if stage is not None:
        sets.append("stage = %s::lead_stage")
        params.append(stage)
    if project_id is not None:
        sets.append("project_id = %s")
        params.append(project_id)
    if assigned_advisor_id is not None:
        sets.append("assigned_advisor_id = %s")
        params.append(assigned_advisor_id)
    if last_message_snippet is not None:
        sets.append("last_message_snippet = %s")
        params.append(last_message_snippet)
    if visit_scheduled_at is not None:
        sets.append("visit_scheduled_at = %s")
        params.append(visit_scheduled_at)

    params.append(ticket_id)
    row = fetch_one(
        conn,
        f"""
        update tickets
        set {", ".join(sets)}
        where id = %s
        returning
            id,
            conversation_id,
            lead_id,
            project_id,
            stage,
            assigned_advisor_id,
            last_activity_at,
            last_message_snippet,
            visit_scheduled_at,
            inbound_line_key,
            inbound_line_phone,
            summary_jsonb,
            created_at,
            updated_at
        """,
        tuple(params),
    )
    if row is None:
        raise KeyError("ticket not found")
    return row


def update_ticket_requirements(
    conn: Any,
    ticket_id: str,
    requirements_patch: dict[str, Any],
) -> dict[str, Any]:
    ensure_ticket_inbound_line_columns(conn)
    row = fetch_one(
        conn,
        """
        update tickets
        set summary_jsonb = jsonb_set(
                coalesce(summary_jsonb, '{}'::jsonb),
                '{requirements}',
                coalesce(summary_jsonb->'requirements', '{}'::jsonb) || %s::jsonb,
                true
            ),
            last_activity_at = now(),
            updated_at = now()
        where id = %s
        returning
            id,
            conversation_id,
            lead_id,
            project_id,
            stage,
            assigned_advisor_id,
            last_activity_at,
            last_message_snippet,
            visit_scheduled_at,
            inbound_line_key,
            inbound_line_phone,
            summary_jsonb,
            created_at,
            updated_at
        """,
        (json.dumps(requirements_patch or {}, default=str), ticket_id),
    )
    if row is None:
        raise KeyError("ticket not found")
    return row


def merge_ticket_summary(
    conn: Any,
    ticket_id: str,
    summary_patch: dict[str, Any],
) -> dict[str, Any]:
    ensure_ticket_inbound_line_columns(conn)
    row = fetch_one(
        conn,
        """
        update tickets
        set summary_jsonb = coalesce(summary_jsonb, '{}'::jsonb) || %s::jsonb,
            last_activity_at = now(),
            updated_at = now()
        where id = %s
        returning
            id,
            conversation_id,
            lead_id,
            project_id,
            stage,
            assigned_advisor_id,
            last_activity_at,
            last_message_snippet,
            visit_scheduled_at,
            inbound_line_key,
            inbound_line_phone,
            summary_jsonb,
            created_at,
            updated_at
        """,
        (json.dumps(summary_patch or {}, default=str), ticket_id),
    )
    if row is None:
        raise KeyError("ticket not found")
    return row


def insert_message(
    conn: Any,
    *,
    conversation_id: str,
    lead_id: str,
    direction: str,
    actor: str,
    text: str,
    provider_message_id: str | None = None,
    provider_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into messages (
            conversation_id,
            lead_id,
            direction,
            actor,
            text,
            provider_message_id,
            provider_meta_jsonb
        )
        values (%s, %s, %s, %s::actor_role, %s, %s, %s::jsonb)
        returning id, conversation_id, lead_id, direction, actor, text, provider_message_id, provider_meta_jsonb, created_at
        """,
        (
            conversation_id,
            lead_id,
            direction,
            actor,
            text,
            provider_message_id,
            json.dumps(provider_meta or {}, default=str),
        ),
    )
    if row is None:
        raise RuntimeError("Failed to insert message")
    return row


def ensure_messages_provider_columns(conn: Any) -> None:
    conn.execute("alter table messages add column if not exists provider_name text")
    conn.execute("alter table messages add column if not exists provider_status text")
    conn.execute("alter table messages add column if not exists provider_response_jsonb jsonb")
    conn.execute("alter table messages add column if not exists provider_error text")
    conn.execute("alter table messages add column if not exists sent_at timestamptz")


def update_message_provider_result(
    conn: Any,
    *,
    message_id: str,
    provider_name: str,
    provider_status: str,
    provider_message_id: str | None,
    provider_response: dict[str, Any] | None,
    provider_error: str | None,
    sent_at: Any | None,
) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        update messages
        set provider_name = %s,
            provider_status = %s,
            provider_message_id = coalesce(%s, provider_message_id),
            provider_response_jsonb = %s::jsonb,
            provider_error = %s,
            sent_at = %s
        where id = %s
        returning
            id,
            conversation_id,
            lead_id,
            direction,
            actor,
            text,
            provider_message_id,
            provider_name,
            provider_status,
            provider_response_jsonb,
            provider_error,
            sent_at,
            provider_meta_jsonb,
            created_at
        """,
        (
            provider_name,
            provider_status,
            provider_message_id,
            json.dumps(provider_response or {}, default=str),
            provider_error,
            sent_at,
            message_id,
        ),
    )
    if row is None:
        raise KeyError("message not found")
    return row


def insert_event(
    conn: Any,
    *,
    correlation_id: str,
    domain: str,
    name: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into events (correlation_id, domain, name, actor, payload)
        values (%s, %s, %s, %s::actor_role, %s::jsonb)
        returning id, correlation_id, domain, name, actor, payload, created_at
        """,
        (
            correlation_id,
            domain,
            name,
            actor,
            json.dumps(payload or {}, default=str),
        ),
    )
    if row is None:
        raise RuntimeError("Failed to insert event")
    return row


def get_ticket_context(conn: Any, ticket_id: str) -> dict[str, Any] | None:
    ensure_ticket_inbound_line_columns(conn)
    return fetch_one(
        conn,
        """
        select
            t.id as ticket_id,
            t.conversation_id,
            t.lead_id,
            t.project_id,
            t.stage,
            t.assigned_advisor_id,
            t.last_activity_at,
            t.last_message_snippet,
            t.visit_scheduled_at,
            t.inbound_line_key,
            t.inbound_line_phone,
            t.summary_jsonb,
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            au.phone_e164 as assigned_advisor_phone_e164,
            p.code as project_code,
            p.name as project_name,
            c.status as conversation_status,
            c.channel as conversation_channel,
            c.last_message_at as conversation_last_message_at
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
        left join users au on au.id = t.assigned_advisor_id
        join conversations c on c.id = t.conversation_id
        where t.id = %s
        limit 1
        """,
        (ticket_id,),
    )


def find_advisor_by_name(conn: Any, advisor_name: str | None) -> dict[str, Any] | None:
    clean = str(advisor_name or "").strip()
    if clean:
        return fetch_one(
            conn,
            """
            select id, full_name, role, phone_e164, is_active
            from users
            where role = 'advisor'::actor_role
              and is_active = true
              and full_name ilike %s
            order by
                case when lower(full_name) = lower(%s) then 0 else 1 end,
                created_at asc
            limit 1
            """,
            (f"%{clean}%", clean),
        )

    return fetch_one(
        conn,
        """
        select id, full_name, role, phone_e164, is_active
        from users
        where role = 'advisor'::actor_role
          and is_active = true
        order by created_at asc
        limit 1
        """,
    )


def create_visit_proposal(
    conn: Any,
    *,
    ticket_id: str,
    conversation_id: str,
    lead_id: str,
    advisor_id: str | None,
    mode: str,
    option1: Any | None,
    option2: Any | None,
    option3: Any | None,
    message_out: str,
) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into visit_proposals (
            ticket_id,
            conversation_id,
            lead_id,
            advisor_id,
            mode,
            option1,
            option2,
            option3,
            message_out,
            status,
            sent_to_client_at
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent'::visit_proposal_status, now())
        returning
            id,
            ticket_id,
            conversation_id,
            lead_id,
            advisor_id,
            mode,
            option1,
            option2,
            option3,
            message_out,
            status,
            timezone,
            expires_at,
            sent_to_client_at,
            created_at
        """,
        (
            ticket_id,
            conversation_id,
            lead_id,
            advisor_id,
            mode,
            option1,
            option2,
            option3,
            message_out,
        ),
    )
    if row is None:
        raise RuntimeError("Failed to create visit proposal")
    return row


def supersede_active_proposals(conn: Any, ticket_id: str) -> int:
    cursor = conn.execute(
        """
        update visit_proposals
        set status = 'superseded'::visit_proposal_status
        where ticket_id = %s
          and status in ('draft'::visit_proposal_status, 'sent'::visit_proposal_status)
        """,
        (ticket_id,),
    )
    return int(cursor.rowcount or 0)


def get_visit_proposal(conn: Any, proposal_id: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select
            vp.id,
            vp.ticket_id,
            vp.conversation_id,
            vp.lead_id,
            vp.advisor_id,
            vp.mode,
            vp.option1,
            vp.option2,
            vp.option3,
            vp.message_out,
            vp.status,
            vp.timezone,
            vp.expires_at,
            vp.sent_to_client_at,
            vp.created_at
        from visit_proposals vp
        where vp.id = %s
        limit 1
        """,
        (proposal_id,),
    )


def mark_visit_proposal_accepted(conn: Any, proposal_id: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        update visit_proposals
        set status = 'accepted'::visit_proposal_status
        where id = %s
        returning
            id,
            ticket_id,
            conversation_id,
            lead_id,
            advisor_id,
            mode,
            option1,
            option2,
            option3,
            message_out,
            status,
            timezone,
            expires_at,
            sent_to_client_at,
            created_at
        """,
        (proposal_id,),
    )
    if row is None:
        raise KeyError("proposal not found")
    return row


def insert_visit_confirmation(
    conn: Any,
    *,
    proposal_id: str,
    ticket_id: str,
    confirmed_option: int,
    confirmed_at: Any,
    confirmed_by: str,
) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        insert into visit_confirmations (
            proposal_id,
            ticket_id,
            confirmed_option,
            confirmed_at,
            confirmed_by
        )
        values (%s, %s, %s, %s, %s::actor_role)
        returning
            id,
            proposal_id,
            ticket_id,
            confirmed_option,
            confirmed_at,
            confirmed_by,
            created_at
        """,
        (proposal_id, ticket_id, confirmed_option, confirmed_at, confirmed_by),
    )
    if row is None:
        raise RuntimeError("Failed to insert visit confirmation")
    return row


def get_dashboard_ticket_rows(conn: Any, cliente: str | None) -> list[dict[str, Any]]:
    ensure_ticket_inbound_line_columns(conn)
    clean = str(cliente or "").strip()
    like = f"%{clean}%" if clean else ""
    return fetch_all(
        conn,
        """
        select
            t.id as ticket_id,
            t.stage,
            t.project_id,
            t.lead_id,
            t.conversation_id,
            t.last_activity_at,
            t.last_message_snippet,
            t.visit_scheduled_at,
            t.inbound_line_key as ticket_inbound_line_key,
            t.inbound_line_phone as ticket_inbound_line_phone,
            t.summary_jsonb,
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            l.source as lead_source,
            p.code as project_code,
            p.name as project_name,
            (t.summary_jsonb->'requirements'->>'ambientes')::int as req_ambientes,
            (t.summary_jsonb->'requirements'->>'presupuesto')::bigint as req_presupuesto,
            upper(nullif(t.summary_jsonb->'requirements'->>'moneda', '')) as req_moneda,
            coalesce(lm.text, t.last_message_snippet, '') as last_message_text,
            lm.direction as last_message_direction,
            lm.actor as last_message_actor,
            lm.created_at as last_message_at,
            nullif(li.provider_meta_jsonb->>'inbound_line_key', '') as message_inbound_line_key,
            nullif(li.provider_meta_jsonb->>'inbound_line_phone', '') as message_inbound_line_phone,
            nullif(li.provider_meta_jsonb->>'to', '') as message_to_phone,
            nullif(li.provider_meta_jsonb->>'phone_number_id', '') as message_phone_number_id,
            nullif(li.provider_meta_jsonb->>'provider', '') as message_provider,
            case
                when %s <> '' and (
                    l.phone_e164 ilike %s
                    or coalesce(l.name, '') ilike %s
                ) then true
                else false
            end as cliente_match
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
        left join lateral (
            select m.text, m.direction, m.actor, m.created_at
            from messages m
            where m.conversation_id = t.conversation_id
            order by m.created_at desc
            limit 1
        ) lm on true
        left join lateral (
            select m.provider_meta_jsonb
            from messages m
            where m.conversation_id = t.conversation_id
              and m.direction = 'in'
            order by m.created_at desc
            limit 1
        ) li on true
        order by cliente_match desc,
                 coalesce(t.last_activity_at, t.updated_at, t.created_at) desc
        """,
        (clean, like, like),
    )


def get_dashboard_kpis(conn: Any) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        select
            count(*)::int as tickets_total,
            count(*) filter (where stage = 'Nuevo'::lead_stage)::int as tickets_nuevo,
            count(*) filter (where stage = 'En seguimiento'::lead_stage)::int as tickets_en_seguimiento,
            count(*) filter (where stage = 'Pendiente de visita'::lead_stage)::int as tickets_pendiente_visita,
            count(*) filter (where stage = 'Esperando confirmación'::lead_stage)::int as tickets_esperando_confirmacion,
            count(*) filter (where stage = 'Visita confirmada'::lead_stage)::int as tickets_visita_confirmada,
            count(*) filter (where visit_scheduled_at is not null)::int as tickets_con_visita,
            count(*) filter (
                where coalesce(last_activity_at, updated_at, created_at) >= now() - interval '24 hours'
            )::int as activos_24h
        from tickets
        """,
    )
    return row or {
        "tickets_total": 0,
        "tickets_nuevo": 0,
        "tickets_en_seguimiento": 0,
        "tickets_pendiente_visita": 0,
        "tickets_esperando_confirmacion": 0,
        "tickets_visita_confirmada": 0,
        "tickets_con_visita": 0,
        "activos_24h": 0,
    }


def get_ticket_detail(conn: Any, ticket_id: str) -> dict[str, Any] | None:
    ensure_ticket_inbound_line_columns(conn)
    return fetch_one(
        conn,
        """
        select
            t.id as ticket_id,
            t.stage,
            t.project_id,
            t.lead_id,
            t.conversation_id,
            t.assigned_advisor_id,
            t.last_activity_at,
            t.last_message_snippet,
            t.visit_scheduled_at,
            t.inbound_line_key,
            t.inbound_line_phone,
            t.summary_jsonb,
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            l.source as lead_source,
            p.code as project_code,
            p.name as project_name,
            (t.summary_jsonb->'requirements'->>'ambientes')::int as req_ambientes,
            (t.summary_jsonb->'requirements'->>'presupuesto')::bigint as req_presupuesto,
            upper(nullif(t.summary_jsonb->'requirements'->>'moneda', '')) as req_moneda
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
        where t.id = %s
        limit 1
        """,
        (ticket_id,),
    )


def set_ticket_inbound_line(
    conn: Any,
    *,
    ticket_id: str,
    inbound_line_key: str | None,
    inbound_line_phone: str | None = None,
) -> dict[str, Any] | None:
    if not hasattr(conn, "execute"):
        return None
    ensure_ticket_inbound_line_columns(conn)
    return fetch_one(
        conn,
        """
        update tickets
        set inbound_line_key = coalesce(nullif(%s, ''), inbound_line_key),
            inbound_line_phone = coalesce(nullif(%s, ''), inbound_line_phone),
            updated_at = now()
        where id = %s
        returning id, inbound_line_key, inbound_line_phone
        """,
        (
            str(inbound_line_key or "").strip() or None,
            str(inbound_line_phone or "").strip() or None,
            ticket_id,
        ),
    )


def find_cliente_activo(conn: Any, cliente: str) -> dict[str, Any] | None:
    clean = str(cliente or "").strip()
    if not clean:
        return None
    like = f"%{clean}%"
    return fetch_one(
        conn,
        """
        select
            t.id as ticket_id,
            t.stage,
            t.last_activity_at,
            l.id as lead_id,
            l.phone_e164,
            l.name as lead_name,
            p.code as project_code,
            p.name as project_name
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
        where l.phone_e164 ilike %s or coalesce(l.name, '') ilike %s
        order by coalesce(t.last_activity_at, t.updated_at, t.created_at) desc
        limit 1
        """,
        (like, like),
    )


def list_conversation_messages(
    conn: Any,
    conversation_id: str,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 200), 500))
    return fetch_all(
        conn,
        """
        select
            id,
            conversation_id,
            lead_id,
            direction,
            actor,
            text,
            provider_message_id,
            provider_meta_jsonb,
            created_at
        from messages
        where conversation_id = %s
        order by created_at asc
        limit %s
        """,
        (conversation_id, safe_limit),
    )


def get_active_visit_proposal_for_ticket(conn: Any, ticket_id: str) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        select
            id,
            ticket_id,
            conversation_id,
            lead_id,
            advisor_id,
            mode,
            option1,
            option2,
            option3,
            message_out,
            status,
            timezone,
            expires_at,
            sent_to_client_at,
            created_at
        from visit_proposals
        where ticket_id = %s
          and status in ('draft'::visit_proposal_status, 'sent'::visit_proposal_status)
        order by sent_to_client_at desc nulls last, created_at desc
        limit 1
        """,
        (ticket_id,),
    )


def _safe_identifier(name: str) -> str:
    candidate = str(name or "").strip()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", candidate):
        raise ValueError(f"invalid SQL identifier: {candidate!r}")
    return candidate


def _q(name: str) -> str:
    return f'"{_safe_identifier(name)}"'


def _compact_sql(query: str) -> str:
    return " ".join(str(query or "").split())


def _dedupe_sources(values: list[str]) -> list[str]:
    items: list[str] = []
    for raw in values:
        clean = str(raw or "").strip()
        if clean and clean not in items:
            items.append(clean)
    return items


def _log_knowledge_sql(name: str, query: str, params: tuple[Any, ...]) -> None:
    logger.info(
        "ORQ_KNOWLEDGE_SQL name=%s sql=%s params=%s",
        name,
        _compact_sql(query),
        params,
    )


def _fetch_all_knowledge(
    conn: Any,
    name: str,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    _log_knowledge_sql(name, query, params)
    return fetch_all(conn, query, params)


def _fetch_one_knowledge(
    conn: Any,
    name: str,
    query: str,
    params: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    _log_knowledge_sql(name, query, params)
    return fetch_one(conn, query, params)


def _find_column(
    columns: list[str],
    *,
    exact: tuple[str, ...] = (),
    contains: tuple[str, ...] = (),
) -> str | None:
    lower_columns = [str(col or "").lower() for col in columns]
    for candidate in exact:
        clean = str(candidate or "").lower()
        if clean in lower_columns:
            return clean
    for token in contains:
        clean_token = str(token or "").lower()
        for col in lower_columns:
            if clean_token and clean_token in col:
                return col
    return None


def _is_project_knowledge_table(table_name: str) -> bool:
    clean = str(table_name or "").lower()
    if clean in {
        "projects",
        "marketing_assets",
        "units",
        "unidades",
        "unit_types",
        "price_lists",
        "availability",
        "payment_plans",
        "financing_terms",
    }:
        return True
    return any(keyword in clean for keyword in _PROJECT_TABLE_KEYWORDS)


def discover_project_schema(
    conn: Any,
    *,
    force_refresh: bool = False,
) -> dict[str, list[str]]:
    global _PROJECT_SCHEMA_CACHE
    if _PROJECT_SCHEMA_CACHE is not None and not force_refresh:
        return dict(_PROJECT_SCHEMA_CACHE)

    rows = _fetch_all_knowledge(
        conn,
        "discover_project_schema",
        """
        select lower(table_name) as table_name, lower(column_name) as column_name
        from information_schema.columns
        where table_schema = current_schema()
        order by table_name asc, ordinal_position asc
        """,
    )
    schema_map: dict[str, list[str]] = {}
    for row in rows:
        table_name = str(row.get("table_name") or "").lower()
        column_name = str(row.get("column_name") or "").lower()
        if not table_name or not column_name:
            continue
        if not _is_project_knowledge_table(table_name):
            continue
        schema_map.setdefault(table_name, []).append(column_name)

    _PROJECT_SCHEMA_CACHE = schema_map
    return dict(schema_map)


def _find_table(schema_map: dict[str, list[str]], candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        clean = str(name or "").lower()
        if clean in schema_map:
            return clean
    return None


def _find_tables_containing(
    schema_map: dict[str, list[str]],
    token: str,
) -> list[str]:
    clean = str(token or "").lower()
    return [name for name in schema_map if clean and clean in name]


def _table_exists(schema_map: dict[str, list[str]], table_name: str) -> bool:
    return str(table_name or "").lower() in schema_map


def _table_row_count(conn: Any, table_name: str) -> int:
    safe_table = _q(str(table_name).lower())
    query = f"select count(*)::int as total from {safe_table}"
    row = _fetch_one_knowledge(conn, "table_row_count", query)
    if not row:
        return 0
    return int(row.get("total") or 0)


def get_demo_project_facts(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None
    if not hasattr(conn, "execute"):
        return None
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_project_facts"):
        return None
    row = _fetch_one_knowledge(
        conn,
        "get_demo_project_facts",
        """
        select *
        from demo_project_facts
        where upper(project_code) = upper(%s)
        limit 1
        """,
        (clean_code,),
    )
    if row:
        row["_source_table"] = "demo_project_facts"
    return row


def get_demo_project_bundle(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None
    if not hasattr(conn, "execute"):
        return None
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_project_bundles"):
        return None
    row = _fetch_one_knowledge(
        conn,
        "get_demo_project_bundle",
        """
        select *
        from demo_project_bundles
        where upper(project_code) = upper(%s)
        limit 1
        """,
        (clean_code,),
    )
    if row:
        row["_source_table"] = "demo_project_bundles"
    return row


def get_project_profile(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code or not hasattr(conn, "execute"):
        return None
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_project_profile"):
        return None
    row = _fetch_one_knowledge(
        conn,
        "get_project_profile",
        """
        select *
        from demo_project_profile
        where upper(project_code) = upper(%s)
        limit 1
        """,
        (clean_code,),
    )
    if row:
        row["_source_table"] = "demo_project_profile"
    return row


def get_unit_profiles_for_project(conn: Any, project_code: str) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code or not hasattr(conn, "execute"):
        return []
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_unit_profile"):
        return []
    rows = _fetch_all_knowledge(
        conn,
        "get_unit_profiles_for_project",
        """
        select *
        from demo_unit_profile
        where upper(project_code) = upper(%s)
        order by unit_id asc
        """,
        (clean_code,),
    )
    for row in rows:
        row["_source_table"] = "demo_unit_profile"
    return rows


def get_unit_profile_by_unit_id(
    conn: Any,
    project_code: str,
    unit_id: str,
) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    clean_unit_id = str(unit_id or "").strip()
    if not clean_code or not clean_unit_id or not hasattr(conn, "execute"):
        return None
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_unit_profile"):
        return None
    row = _fetch_one_knowledge(
        conn,
        "get_unit_profile_by_unit_id",
        """
        select *
        from demo_unit_profile
        where upper(project_code) = upper(%s)
          and unit_id = %s
        limit 1
        """,
        (clean_code, clean_unit_id),
    )
    if row:
        row["_source_table"] = "demo_unit_profile"
    return row


def list_demo_units(
    conn: Any,
    project_code: str,
    *,
    rooms: int | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return []
    schema_map = discover_project_schema(conn)
    if not _table_exists(schema_map, "demo_units"):
        return []

    where_clauses = ["upper(project_code) = upper(%s)"]
    params: list[Any] = [clean_code]
    if rooms is not None:
        where_clauses.append("rooms_count = %s")
        params.append(int(rooms))
    if currency:
        where_clauses.append("upper(currency) = upper(%s)")
        params.append(str(currency))

    query = (
        """
        select
            workspace_id,
            project_code,
            unit_id,
            unit_code,
            typology,
            rooms_label,
            rooms_count,
            bedrooms,
            bathrooms,
            surface_total_m2,
            surface_covered_m2,
            currency,
            list_price,
            availability_status,
            features_jsonb,
            source_url
        from demo_units
        where """
        + " and ".join(where_clauses)
        + """
        order by rooms_count asc nulls last, list_price asc nulls last, unit_id asc
        """
    )
    rows = _fetch_all_knowledge(conn, "list_demo_units", query, tuple(params))
    for row in rows:
        row["_source_table"] = "demo_units"
    return rows


def list_all_demo_units(
    conn: Any,
    *,
    rooms: int | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    project_rows = list_projects(conn)
    project_names = {
        str(row.get("code") or "").strip().upper(): str(row.get("name") or row.get("code") or "").strip()
        for row in project_rows
        if str(row.get("code") or "").strip()
    }
    units: list[dict[str, Any]] = []
    for project_code in project_names:
        rows = list_demo_units(conn, project_code, rooms=rooms, currency=currency)
        for row in rows:
            unit = dict(row)
            unit["project_code"] = str(unit.get("project_code") or project_code).strip().upper()
            unit["project_name"] = project_names.get(unit["project_code"], unit["project_code"])
            units.append(unit)
    return units


def get_project_surface_totals_from_demo_units(conn: Any) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in list_all_demo_units(conn, rooms=None, currency=None):
        project_code = str(row.get("project_code") or "").strip().upper()
        if not project_code:
            continue
        surface_total = _coerce_float(row.get("surface_total_m2"))
        if surface_total is None:
            continue
        project_row = grouped.setdefault(
            project_code,
            {
                "project_code": project_code,
                "project_name": str(row.get("project_name") or project_code).strip(),
                "surface_total_m2_sum": 0.0,
                "units_with_surface_count": 0,
                "_source_table": "demo_units",
            },
        )
        project_row["surface_total_m2_sum"] = float(project_row.get("surface_total_m2_sum") or 0.0) + float(surface_total)
        project_row["units_with_surface_count"] = int(project_row.get("units_with_surface_count") or 0) + 1
    return sorted(
        grouped.values(),
        key=lambda row: (
            -float(row.get("surface_total_m2_sum") or 0.0),
            str(row.get("project_name") or row.get("project_code") or ""),
        ),
    )


def list_units_by_rooms(
    conn: Any,
    *,
    project_code: str | None = None,
    rooms_count: int | None = None,
    rooms_label: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    target_rooms = rooms_count
    if target_rooms is None and rooms_label is not None:
        match = re.search(r"\b([1-4])\b", str(rooms_label))
        if match:
            target_rooms = int(match.group(1))
        elif re.search(r"\bmono(?:ambiente)?s?\b", str(rooms_label), re.IGNORECASE):
            target_rooms = 1
    if target_rooms is None:
        return []

    rows = get_units_with_filters(
        conn,
        project_code=str(project_code).strip().upper() or None if project_code else None,
        rooms=int(target_rooms),
        availability="available",
    )
    project_name = ""
    if project_code:
        project_row = get_project_by_code(conn, str(project_code).strip().upper())
        project_name = str((project_row or {}).get("name") or "").strip()

    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["project_code"] = str(item.get("project_code") or project_code or "").strip().upper()
        if not item.get("project_name"):
            item["project_name"] = project_name or item["project_code"]
        normalized.append(item)

    normalized.sort(
        key=lambda row: (
            str(row.get("project_name") or row.get("project_code") or "").strip(),
            _coerce_float(row.get("list_price")) if _coerce_float(row.get("list_price")) is not None else float("inf"),
            str(row.get("unit_code") or row.get("unit_id") or "").strip().upper(),
        )
    )
    if limit is not None and int(limit) >= 0:
        return normalized[: int(limit)]
    return normalized


def count_units_by_rooms(
    conn: Any,
    *,
    project_code: str | None = None,
    rooms_count: int | None = None,
    rooms_label: str | None = None,
) -> int:
    return len(
        list_units_by_rooms(
            conn,
            project_code=project_code,
            rooms_count=rooms_count,
            rooms_label=rooms_label,
            limit=None,
        )
    )


def get_global_units_by_rooms(
    conn: Any,
    *,
    rooms_count: int | None = None,
    rooms_label: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    return list_units_by_rooms(
        conn,
        project_code=None,
        rooms_count=rooms_count,
        rooms_label=rooms_label,
        limit=limit,
    )


def list_units_matching_active_filter(
    conn: Any,
    *,
    filter_type: str,
    filter_payload: dict[str, Any] | None = None,
    scope: str = "global",
    project_code: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clean_type = str(filter_type or "").strip().lower()
    payload = dict(filter_payload or {})
    clean_scope = str(scope or "").strip().lower() or "global"
    scoped_project_code = str(project_code or "").strip().upper() or None

    rooms_count: int | None = None
    try:
        rooms_count = int(payload.get("rooms_count")) if payload.get("rooms_count") is not None else None
    except Exception:  # noqa: BLE001
        rooms_count = None

    feature_key = str(payload.get("feature_key") or "").strip().lower() or None
    min_surface_total_m2 = _coerce_float(payload.get("min_surface_total_m2"))
    max_surface_total_m2 = _coerce_float(payload.get("max_surface_total_m2"))
    facets_applied = [
        str(item or "").strip().lower()
        for item in (payload.get("facets_applied") or [])
        if str(item or "").strip()
    ]

    if clean_scope in {"global", "transversal"}:
        base_rows = get_units_global_filtered(
            conn,
            min_surface_total_m2=min_surface_total_m2 if clean_type == "surface" else None,
            max_surface_total_m2=max_surface_total_m2 if clean_type == "surface" else None,
            rooms_count=rooms_count,
            feature_key=feature_key if clean_type == "feature" else None,
            availability="available",
        )
    else:
        base_rows = get_units_with_filters(
            conn,
            project_code=scoped_project_code,
            rooms=rooms_count,
            feature_key=feature_key if clean_type == "feature" else None,
            min_surface_total_m2=min_surface_total_m2 if clean_type == "surface" else None,
            max_surface_total_m2=max_surface_total_m2 if clean_type == "surface" else None,
            availability="available",
        )

    filtered: list[dict[str, Any]] = []
    for row in base_rows:
        if facets_applied and not all(_unit_matches_feature_profile(row, facet) for facet in facets_applied):
            continue
        filtered.append(dict(row))

    filtered.sort(
        key=lambda row: (
            str(row.get("project_name") or row.get("project_code") or "").strip(),
            _coerce_float(row.get("list_price")) if _coerce_float(row.get("list_price")) is not None else float("inf"),
            str(row.get("unit_code") or row.get("unit_id") or "").strip().upper(),
        )
    )
    if limit is not None and int(limit) >= 0:
        return filtered[: int(limit)]
    return filtered


def list_projects_matching_active_filter(
    conn: Any,
    *,
    filter_type: str,
    filter_payload: dict[str, Any] | None = None,
    scope: str = "global",
    project_code: str | None = None,
) -> list[dict[str, Any]]:
    project_rows = list_projects(conn)
    project_names = {
        str(row.get("code") or "").strip().upper(): str(row.get("name") or row.get("code") or "").strip()
        for row in project_rows
        if str(row.get("code") or "").strip()
    }
    rows = list_units_matching_active_filter(
        conn,
        filter_type=filter_type,
        filter_payload=filter_payload,
        scope=scope,
        project_code=project_code,
        limit=None,
    )

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("project_code") or project_code or "").strip().upper()
        if not code:
            continue
        bucket = grouped.setdefault(
            code,
            {
                "project_code": code,
                "project_name": str(row.get("project_name") or project_names.get(code, code)).strip(),
                "units_count": 0,
                "_source_tables": [],
            },
        )
        bucket["units_count"] = int(bucket.get("units_count") or 0) + 1
        for source_key in ("_source_table", "_profile_source_table"):
            source = str(row.get(source_key) or "").strip()
            if source and source not in bucket["_source_tables"]:
                bucket["_source_tables"].append(source)

    return sorted(grouped.values(), key=lambda row: (str(row.get("project_name") or "").strip(), str(row.get("project_code") or "").strip()))


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            clean = str(item or "").strip()
            if clean and clean not in result:
                result.append(clean)
        return result
    return []


def _as_json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unit_profile_index(
    conn: Any,
    *,
    project_code: str | None = None,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    if project_code:
        profiles = get_unit_profiles_for_project(conn, project_code)
    else:
        for row in list_projects(conn):
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            profiles.extend(get_unit_profiles_for_project(conn, code))
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in profiles:
        key = (
            str(row.get("workspace_id") or "").strip(),
            str(row.get("project_code") or "").strip().upper(),
            str(row.get("unit_id") or "").strip(),
        )
        indexed[key] = row
    return indexed


def _unit_feature_values(unit_row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in _as_text_list(unit_row.get("features_jsonb")):
        values.append(str(item).strip().lower())
    return values


def _unit_matches_feature_profile(unit_row: dict[str, Any], feature_key: str) -> bool:
    clean_feature = str(feature_key or "").strip().lower()
    if not clean_feature:
        return False

    features = _unit_feature_values(unit_row)
    recommended_profiles = [value.lower() for value in _as_text_list(unit_row.get("recommended_profiles_jsonb"))]
    commercial_features = {
        str(key or "").strip().lower(): value
        for key, value in _as_json_object(unit_row.get("commercial_features_jsonb")).items()
    }

    def _raw_has(*aliases: str) -> bool:
        for alias in aliases:
            normalized = str(alias or "").strip().lower()
            if any(normalized == value or normalized in value or value in normalized for value in features):
                return True
        return False

    if clean_feature == "balcon":
        return bool(
            commercial_features.get("balcony")
            or _raw_has("balcon", "balcon terraza", "balcón", "balcón terraza", "terraza")
        )
    if clean_feature == "cochera":
        return unit_row.get("has_garage") is True or _raw_has("cochera", "garage", "parking")
    if clean_feature == "jardin":
        return bool(unit_row.get("has_garden") is True or commercial_features.get("garden") or _raw_has("jardin", "jardín", "garden"))
    if clean_feature == "patio":
        return unit_row.get("has_patio") is True or _raw_has("patio")
    if clean_feature == "baulera":
        return unit_row.get("has_storage") is True or _raw_has("baulera", "storage")
    if clean_feature == "mascotas":
        return bool(unit_row.get("pets_allowed") is True or "pets" in recommended_profiles or _raw_has("mascotas", "pet friendly", "pets allowed"))
    if clean_feature == "en_suite":
        suite_count = commercial_features.get("suite_bedrooms")
        return bool((isinstance(suite_count, int) and suite_count > 0) or _raw_has("suite", "en suite"))
    if clean_feature == "walk_in_closet":
        return _raw_has("walk in closet", "vestidor")
    if clean_feature == "lavadero":
        return _raw_has("lavadero", "laundry")
    if clean_feature == "parrilla":
        return _raw_has("parrilla")
    return _raw_has(clean_feature)


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except Exception:  # noqa: BLE001
        return None


def get_units_with_filters(
    conn: Any,
    *,
    project_code: str | None = None,
    rooms: int | None = None,
    currency: str | None = None,
    unit_id: str | None = None,
    unit_code: str | None = None,
    feature_key: str | None = None,
    children_suitable: bool | None = None,
    pets_allowed: bool | None = None,
    has_garden: bool | None = None,
    has_patio: bool | None = None,
    has_garage: bool | None = None,
    has_storage: bool | None = None,
    natural_light: str | None = None,
    balcony_protection: str | None = None,
    recommended_profile: str | None = None,
    min_surface_total_m2: float | None = None,
    max_surface_total_m2: float | None = None,
    availability: str | None = None,
) -> list[dict[str, Any]]:
    base_rows = (
        list_demo_units(conn, str(project_code), rooms=rooms, currency=currency)
        if project_code
        else list_all_demo_units(conn, rooms=rooms, currency=currency)
    )
    profile_map = _unit_profile_index(conn, project_code=project_code)

    clean_unit_id = str(unit_id or "").strip()
    clean_unit_code = str(unit_code or "").strip().upper()
    clean_natural_light = str(natural_light or "").strip().lower()
    clean_balcony = str(balcony_protection or "").strip().lower()
    clean_recommended = str(recommended_profile or "").strip().lower()
    clean_availability = str(availability or "").strip().lower()
    filtered: list[dict[str, Any]] = []

    def _matches_bool(value: Any, expected: bool | None) -> bool:
        if expected is None:
            return True
        return isinstance(value, bool) and value is expected

    for row in base_rows:
        merged = dict(row)
        key = (
            str(row.get("workspace_id") or "").strip(),
            str(row.get("project_code") or "").strip().upper(),
            str(row.get("unit_id") or "").strip(),
        )
        profile = profile_map.get(key)
        if profile:
            merged.update(profile)
            merged["_profile_source_table"] = "demo_unit_profile"
        if clean_unit_id and str(merged.get("unit_id") or "").strip() != clean_unit_id:
            continue
        if clean_unit_code and str(merged.get("unit_code") or "").strip().upper() != clean_unit_code:
            continue
        if feature_key and not _unit_matches_feature_profile(merged, feature_key):
            continue
        if not _matches_bool(merged.get("children_suitable"), children_suitable):
            continue
        if not _matches_bool(merged.get("pets_allowed"), pets_allowed):
            continue
        if not _matches_bool(merged.get("has_garden"), has_garden):
            continue
        if not _matches_bool(merged.get("has_patio"), has_patio):
            continue
        if not _matches_bool(merged.get("has_garage"), has_garage):
            continue
        if not _matches_bool(merged.get("has_storage"), has_storage):
            continue
        if clean_natural_light and str(merged.get("natural_light") or "").strip().lower() != clean_natural_light:
            continue
        if clean_balcony and str(merged.get("balcony_protection") or "").strip().lower() != clean_balcony:
            continue
        if clean_recommended:
            recommended = [value.lower() for value in _as_text_list(merged.get("recommended_profiles_jsonb"))]
            if clean_recommended not in recommended:
                continue
        surface_total = _coerce_float(merged.get("surface_total_m2"))
        if min_surface_total_m2 is not None:
            if surface_total is None or surface_total < float(min_surface_total_m2):
                continue
        if max_surface_total_m2 is not None:
            if surface_total is None or surface_total > float(max_surface_total_m2):
                continue
        if clean_availability:
            current_status = _normalize_inventory_status(merged.get("availability_status"))
            if current_status != _normalize_inventory_status(clean_availability):
                continue
        filtered.append(merged)
    return filtered


def get_units_global_filtered(
    conn: Any,
    *,
    min_surface_total_m2: float | None = None,
    max_surface_total_m2: float | None = None,
    rooms_count: int | None = None,
    feature_key: str | None = None,
    has_garden: bool | None = None,
    has_patio: bool | None = None,
    has_garage: bool | None = None,
    has_storage: bool | None = None,
    availability: str | None = None,
) -> list[dict[str, Any]]:
    return get_units_with_filters(
        conn,
        project_code=None,
        rooms=rooms_count,
        feature_key=feature_key,
        has_garden=has_garden,
        has_patio=has_patio,
        has_garage=has_garage,
        has_storage=has_storage,
        min_surface_total_m2=min_surface_total_m2,
        max_surface_total_m2=max_surface_total_m2,
        availability=availability,
    )


def _unit_summary_brief(unit_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": unit_row.get("unit_id"),
        "unit_code": unit_row.get("unit_code"),
        "rooms_label": unit_row.get("rooms_label"),
        "children_suitable": unit_row.get("children_suitable"),
        "pets_allowed": unit_row.get("pets_allowed"),
        "has_garden": unit_row.get("has_garden"),
        "has_patio": unit_row.get("has_patio"),
        "has_garage": unit_row.get("has_garage"),
        "has_storage": unit_row.get("has_storage"),
        "natural_light": unit_row.get("natural_light"),
        "orientation": unit_row.get("orientation"),
        "exposure": unit_row.get("exposure"),
        "sun_morning": unit_row.get("sun_morning"),
        "sun_afternoon": unit_row.get("sun_afternoon"),
        "cross_ventilation": unit_row.get("cross_ventilation"),
        "balcony_protection": unit_row.get("balcony_protection"),
    }


def get_project_inventory_summary(conn: Any, project_code: str) -> dict[str, Any]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return {}

    project_profile = get_project_profile(conn, clean_code)
    if project_profile:
        breakdown = _as_json_object(project_profile.get("raw_status_breakdown_jsonb"))
        return {
            "project_code": clean_code.upper(),
            "units_total": _coerce_int(project_profile.get("units_total")),
            "available_units": _coerce_int(project_profile.get("available_units")),
            "reserved_units": _coerce_int(project_profile.get("reserved_units")),
            "unavailable_units": _coerce_int(project_profile.get("unavailable_units")),
            "inventory_is_complete": bool(project_profile.get("inventory_is_complete")),
            "inventory_scope_type": project_profile.get("inventory_scope_type"),
            "inventory_scope_label": project_profile.get("inventory_scope_label"),
            "inventory_as_of": project_profile.get("inventory_as_of"),
            "raw_status_breakdown_jsonb": breakdown,
            "_source_table": "demo_project_profile",
        }

    total_units = get_total_units_for_project(conn, clean_code)
    breakdown = get_unit_status_breakdown(conn, clean_code)
    available_units = get_available_units_count(conn, clean_code)
    return {
        "project_code": clean_code.upper(),
        "units_total": total_units,
        "available_units": available_units,
        "reserved_units": _coerce_int(breakdown.get("reserved")),
        "unavailable_units": _coerce_int(breakdown.get("unavailable")),
        "inventory_is_complete": is_full_inventory_known(conn, clean_code),
        "inventory_scope_type": None,
        "inventory_scope_label": None,
        "inventory_as_of": None,
        "raw_status_breakdown_jsonb": breakdown,
        "_source_table": "demo_units" if breakdown else "",
    }


def get_project_recommended_profiles(conn: Any, project_code: str) -> list[str]:
    project_profile = get_project_profile(conn, project_code)
    return _as_text_list((project_profile or {}).get("recommended_profiles_jsonb"))


def get_children_suitability_summary(conn: Any, project_code: str) -> dict[str, Any]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return {}
    project_profile = get_project_profile(conn, clean_code) or {}
    rows = get_units_with_filters(conn, project_code=clean_code)
    known_units = [row for row in rows if isinstance(row.get("children_suitable"), bool)]
    suitable_units = [row for row in known_units if row.get("children_suitable") is True]
    family_units = [
        row for row in rows if "family" in [value.lower() for value in _as_text_list(row.get("recommended_profiles_jsonb"))]
    ]
    warnings = _as_text_list(project_profile.get("child_safety_warnings_jsonb"))
    for row in rows:
        for warning in _as_text_list(row.get("child_safety_warnings_jsonb")):
            if warning not in warnings:
                warnings.append(warning)
    return {
        "project_code": clean_code.upper(),
        "project_children_suitable": project_profile.get("children_suitable"),
        "project_recommended_profiles": _as_text_list(project_profile.get("recommended_profiles_jsonb")),
        "warnings": warnings,
        "known_units_count": len(known_units),
        "suitable_units_count": len(suitable_units),
        "family_recommended_units_count": len(family_units),
        "suitable_units": [_unit_summary_brief(row) for row in suitable_units[:5]],
        "family_units": [_unit_summary_brief(row) for row in family_units[:5]],
        "_source_tables": _dedupe_sources(["demo_project_profile", "demo_unit_profile"]),
    }


def get_pets_suitability_summary(conn: Any, project_code: str) -> dict[str, Any]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return {}
    project_profile = get_project_profile(conn, clean_code) or {}
    rows = get_units_with_filters(conn, project_code=clean_code)
    known_units = [row for row in rows if isinstance(row.get("pets_allowed"), bool)]
    allowed_units = [row for row in known_units if row.get("pets_allowed") is True]
    recommended_units = [
        row
        for row in rows
        if "pets" in [value.lower() for value in _as_text_list(row.get("recommended_profiles_jsonb"))]
        or row.get("has_garden") is True
        or row.get("has_patio") is True
    ]
    warnings = _as_text_list(project_profile.get("usage_warnings_jsonb"))
    restrictions = str(project_profile.get("pets_restrictions_text") or "").strip() or None
    return {
        "project_code": clean_code.upper(),
        "project_pets_allowed": project_profile.get("pets_allowed"),
        "project_pets_restrictions_text": restrictions,
        "project_recommended_profiles": _as_text_list(project_profile.get("recommended_profiles_jsonb")),
        "known_units_count": len(known_units),
        "pets_allowed_units_count": len(allowed_units),
        "pets_recommended_units_count": len(recommended_units),
        "garden_units_count": sum(1 for row in rows if row.get("has_garden") is True),
        "patio_units_count": sum(1 for row in rows if row.get("has_patio") is True),
        "allowed_units": [_unit_summary_brief(row) for row in allowed_units[:5]],
        "recommended_units": [_unit_summary_brief(row) for row in recommended_units[:5]],
        "warnings": warnings,
        "_source_tables": _dedupe_sources(["demo_project_profile", "demo_unit_profile"]),
    }


def get_light_orientation_summary(
    conn: Any,
    *,
    project_code: str | None = None,
    unit_id: str | None = None,
) -> dict[str, Any]:
    clean_code = str(project_code or "").strip()
    clean_unit_id = str(unit_id or "").strip()
    if clean_unit_id and clean_code:
        unit_rows = get_units_with_filters(conn, project_code=clean_code, unit_id=clean_unit_id)
        if not unit_rows:
            return {}
        row = unit_rows[0]
        return {
            "project_code": clean_code.upper(),
            "unit": _unit_summary_brief(row),
            "thermal_comfort_notes": row.get("thermal_comfort_notes"),
            "_source_tables": _dedupe_sources(["demo_unit_profile", "demo_units"]),
        }

    if not clean_code:
        return {}

    rows = get_units_with_filters(conn, project_code=clean_code)
    return {
        "project_code": clean_code.upper(),
        "units_count": len(rows),
        "orientation_known_units": [_unit_summary_brief(row) for row in rows if str(row.get("orientation") or "").strip()][:5],
        "exposure_known_units": [_unit_summary_brief(row) for row in rows if str(row.get("exposure") or "").strip()][:5],
        "high_light_units": [_unit_summary_brief(row) for row in rows if str(row.get("natural_light") or "").strip().lower() == "high"][:5],
        "medium_light_units": [_unit_summary_brief(row) for row in rows if str(row.get("natural_light") or "").strip().lower() == "medium"][:5],
        "low_light_units": [_unit_summary_brief(row) for row in rows if str(row.get("natural_light") or "").strip().lower() == "low"][:5],
        "sun_morning_units": [_unit_summary_brief(row) for row in rows if row.get("sun_morning") is True][:5],
        "sun_afternoon_units": [_unit_summary_brief(row) for row in rows if row.get("sun_afternoon") is True][:5],
        "cross_ventilation_units": [_unit_summary_brief(row) for row in rows if row.get("cross_ventilation") is True][:5],
        "_source_tables": _dedupe_sources(["demo_unit_profile", "demo_units"]),
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nested_value(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except Exception:  # noqa: BLE001
        return None
    return parsed if parsed >= 0 else None


def _extract_units_total_from_payload(payload: dict[str, Any] | None) -> int | None:
    data = payload if isinstance(payload, dict) else {}
    candidates = (
        _nested_value(data, "building", "structure", "units_total"),
        _nested_value(data, "condominium", "structure", "units_total"),
        _nested_value(data, "structure", "units_total"),
        data.get("units_total"),
    )
    for candidate in candidates:
        total = _coerce_int(candidate)
        if total is not None:
            return total
    return None


def _normalize_inventory_status(value: Any) -> str:
    clean = str(value or "").strip().lower().replace(" ", "_")
    if not clean:
        return "unknown"
    if clean in {"available", "disponible", "activo", "active"}:
        return "available"
    if clean in {"reserved", "reservada", "reservado"}:
        return "reserved"
    if clean in {
        "sold",
        "vendida",
        "vendido",
        "unavailable",
        "no_disponible",
        "occupied",
        "ocupada",
        "ocupado",
        "inactive",
        "inactivo",
        "inactiva",
    }:
        return "unavailable"
    if clean.startswith("reserv"):
        return "reserved"
    if clean.startswith("dispon") or clean.startswith("active") or clean.startswith("activ"):
        return "available"
    if (
        clean.startswith("ocup")
        or clean.startswith("vend")
        or clean.startswith("no_dispon")
        or clean.startswith("unavail")
    ):
        return "unavailable"
    return clean


def get_total_units_for_project(conn: Any, project_code: str) -> int | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None

    project_profile = get_project_profile(conn, clean_code)
    profile_total = _coerce_int((project_profile or {}).get("units_total"))
    if profile_total is not None:
        return profile_total

    facts = get_demo_project_facts(conn, clean_code)
    facts_total = _extract_units_total_from_payload(facts)
    if facts_total is not None:
        return facts_total

    bundle_row = get_demo_project_bundle(conn, clean_code)
    bundle = _as_dict((bundle_row or {}).get("bundle_jsonb"))
    return _extract_units_total_from_payload(bundle)


def get_unit_status_breakdown(conn: Any, project_code: str) -> dict[str, int]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return {}

    project_profile = get_project_profile(conn, clean_code)
    raw_breakdown = _as_json_object((project_profile or {}).get("raw_status_breakdown_jsonb"))
    if raw_breakdown:
        normalized: dict[str, int] = {}
        for key, value in raw_breakdown.items():
            normalized_key = _normalize_inventory_status(key)
            normalized[normalized_key] = normalized.get(normalized_key, 0) + (_coerce_int(value) or 0)
        if normalized:
            return normalized

    demo_rows = list_demo_units(conn, clean_code, rooms=None, currency=None)
    if demo_rows:
        grouped: dict[str, int] = {}
        for row in demo_rows:
            key = _normalize_inventory_status(row.get("availability_status"))
            grouped[key] = grouped.get(key, 0) + 1
        return grouped

    availability_rows = get_availability_by_rooms(conn, clean_code, rooms=None)
    grouped: dict[str, int] = {}
    for row in availability_rows:
        key = _normalize_inventory_status(row.get("status"))
        count = _coerce_int(row.get("units_count")) or 0
        grouped[key] = grouped.get(key, 0) + count
    return grouped


def get_available_units_count(conn: Any, project_code: str) -> int | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None

    project_profile = get_project_profile(conn, clean_code)
    profile_available = _coerce_int((project_profile or {}).get("available_units"))
    if profile_available is not None:
        return profile_available

    demo_rows = list_demo_units(conn, clean_code, rooms=None, currency=None)
    if demo_rows:
        return sum(1 for row in demo_rows if _normalize_inventory_status(row.get("availability_status")) == "available")

    breakdown = get_unit_status_breakdown(conn, clean_code)
    if breakdown:
        return int(breakdown.get("available") or 0)
    return None


def is_full_inventory_known(conn: Any, project_code: str) -> bool:
    project_profile = get_project_profile(conn, project_code)
    if project_profile:
        return bool(project_profile.get("inventory_is_complete"))
    total_units = get_total_units_for_project(conn, project_code)
    if total_units is None:
        return False
    breakdown = get_unit_status_breakdown(conn, project_code)
    if not breakdown:
        return False
    return sum(int(value or 0) for value in breakdown.values()) == total_units


def find_demo_unit_by_code(conn: Any, unit_code: str) -> dict[str, Any] | None:
    clean_code = str(unit_code or "").strip()
    if not clean_code:
        return None
    target = clean_code.upper()
    for row in list_all_demo_units(conn):
        if str(row.get("unit_code") or "").strip().upper() == target:
            return row
    return None


def _has_project_scope(schema_map: dict[str, list[str]], table_name: str) -> bool:
    table_columns = schema_map.get(str(table_name or "").lower(), [])
    if not table_columns:
        return False
    direct_project_col = _find_column(
        table_columns,
        exact=("project_code", "code", "codigo_proyecto"),
        contains=("project_code", "codigo", "proyecto"),
    )
    if direct_project_col:
        return True
    project_id_col = _find_column(
        table_columns,
        exact=("project_id", "id_project", "projectid", "fk_project"),
        contains=("project_id", "id_project"),
    )
    if not project_id_col:
        return False
    projects_table = _find_table(schema_map, ("projects",))
    if not projects_table:
        return False
    project_columns = schema_map.get(projects_table, [])
    project_id = _find_column(project_columns, exact=("id", "project_id"))
    project_code = _find_column(
        project_columns,
        exact=("code", "project_code", "codigo"),
        contains=("code", "codigo"),
    )
    return bool(project_id and project_code)


def _project_scope_sql(
    schema_map: dict[str, list[str]],
    table_name: str,
    table_alias: str,
    project_code: str,
) -> tuple[str, str, tuple[Any, ...]] | None:
    clean_table = str(table_name or "").lower()
    columns = schema_map.get(clean_table, [])
    if not columns:
        return None

    if clean_table == "projects":
        code_col = _find_column(
            columns,
            exact=("code", "project_code", "codigo"),
            contains=("code", "codigo"),
        )
        if not code_col:
            return None
        return (
            "",
            f"upper({table_alias}.{_q(code_col)}::text) = upper(%s)",
            (project_code,),
        )

    direct_code_col = _find_column(
        columns,
        exact=("project_code", "code", "codigo_proyecto"),
        contains=("project_code", "codigo_proyecto"),
    )
    if direct_code_col:
        return (
            "",
            f"upper({table_alias}.{_q(direct_code_col)}::text) = upper(%s)",
            (project_code,),
        )

    project_id_col = _find_column(
        columns,
        exact=("project_id", "id_project", "projectid", "fk_project"),
        contains=("project_id", "id_project"),
    )
    if not project_id_col:
        return None

    projects_table = _find_table(schema_map, ("projects",))
    if not projects_table:
        return None
    project_columns = schema_map.get(projects_table, [])
    project_id = _find_column(project_columns, exact=("id", "project_id"))
    project_code_col = _find_column(
        project_columns,
        exact=("code", "project_code", "codigo"),
        contains=("code", "codigo"),
    )
    if not project_id or not project_code_col:
        return None

    join_sql = (
        f" join {_q(projects_table)} p"
        f" on p.{_q(project_id)} = {table_alias}.{_q(project_id_col)} "
    )
    where_sql = f"upper(p.{_q(project_code_col)}::text) = upper(%s)"
    return join_sql, where_sql, (project_code,)


def get_project_capabilities(
    conn: Any,
    *,
    force_refresh: bool = False,
) -> dict[str, bool]:
    global _PROJECT_CAPABILITIES_CACHE
    if _PROJECT_CAPABILITIES_CACHE is not None and not force_refresh:
        return dict(_PROJECT_CAPABILITIES_CACHE)

    schema_map = discover_project_schema(conn, force_refresh=force_refresh)
    projects_table = _find_table(schema_map, ("projects",))
    project_cols = schema_map.get(projects_table or "", [])
    marketing_table = _find_table(schema_map, ("marketing_assets",))
    units_table = _find_table(schema_map, ("demo_units", "unit_types", "units", "unidades"))
    demo_facts_table = _find_table(schema_map, ("demo_project_facts",))
    demo_units_table = _find_table(schema_map, ("demo_units",))

    def _table_with_price() -> str | None:
        preferred = ("units", "unidades", "price_lists", "prices", "unit_prices")
        for name in preferred:
            if name not in schema_map:
                continue
            cols = schema_map[name]
            price_col = _find_column(
                cols,
                exact=("price", "list_price", "price_amount", "precio", "amount", "value"),
                contains=("price", "precio"),
            )
            if price_col and _has_project_scope(schema_map, name):
                return name
        for table_name, cols in schema_map.items():
            price_col = _find_column(cols, contains=("price", "precio"))
            if price_col and _has_project_scope(schema_map, table_name):
                return table_name
        return None

    def _table_with_availability() -> str | None:
        preferred = ("availability", "units", "unidades")
        for name in preferred:
            if name not in schema_map:
                continue
            cols = schema_map[name]
            status_col = _find_column(
                cols,
                exact=("status", "availability_status", "estado", "state"),
                contains=("status", "estado", "dispon"),
            )
            bool_col = _find_column(
                cols,
                exact=("is_available", "available"),
                contains=("available", "dispon"),
            )
            if (status_col or bool_col) and _has_project_scope(schema_map, name):
                return name
        return None

    def _table_with_financing() -> str | None:
        preferred = ("payment_plans", "financing_terms", "financing", "payment_options")
        for name in preferred:
            if name in schema_map and _has_project_scope(schema_map, name):
                return name
        for name in _find_tables_containing(schema_map, "financ"):
            if _has_project_scope(schema_map, name):
                return name
        for name in _find_tables_containing(schema_map, "payment"):
            if _has_project_scope(schema_map, name):
                return name
        return None

    delivery_col = _find_column(
        project_cols,
        exact=(
            "delivery_date",
            "estimated_delivery_date",
            "entrega_estimada",
            "handover_date",
            "possession_date",
            "delivery_at",
        ),
        contains=("delivery", "entrega", "posesion", "handover"),
    )

    demo_prices_loaded = False
    demo_financing_loaded = False
    demo_delivery_loaded = False
    if demo_units_table:
        price_row = _fetch_one_knowledge(
            conn,
            "capabilities_demo_prices",
            "select count(*)::int as total from demo_units where list_price is not null",
        )
        demo_prices_loaded = bool(int((price_row or {}).get("total") or 0) > 0)
    if demo_facts_table:
        financing_row = _fetch_one_knowledge(
            conn,
            "capabilities_demo_financing",
            """
            select count(*)::int as total
            from demo_project_facts
            where financing_jsonb is not null
              and financing_jsonb::text not in ('null', '{}')
            """,
        )
        demo_financing_loaded = bool(int((financing_row or {}).get("total") or 0) > 0)
        delivery_row = _fetch_one_knowledge(
            conn,
            "capabilities_demo_delivery",
            """
            select count(*)::int as total
            from demo_project_facts
            where construction_jsonb ? 'delivery_estimated_at'
            """,
        )
        demo_delivery_loaded = bool(int((delivery_row or {}).get("total") or 0) > 0)

    capabilities = {
        "project_overview": bool(projects_table),
        "location": bool(projects_table and _find_column(project_cols, contains=("location", "barrio", "zona", "address", "direccion"))),
        "amenities": bool(
            demo_facts_table
            or marketing_table
            or (projects_table and _find_column(project_cols, contains=("amenit", "tag", "feature", "servicio", "domot", "seguridad")))
        ),
        "marketing_assets": bool(marketing_table),
        "unit_types": bool((demo_units_table and _table_row_count(conn, demo_units_table) >= 0) or (units_table and _has_project_scope(schema_map, units_table))),
        "prices_by_rooms": bool(demo_prices_loaded or _table_with_price()),
        "availability_by_rooms": bool((demo_units_table and _table_row_count(conn, demo_units_table) > 0) or _table_with_availability()),
        "financing": bool(
            demo_financing_loaded
            or _table_with_financing()
            or (projects_table and _find_column(project_cols, contains=("financ", "cuota", "payment", "anticipo")))
        ),
        "delivery_date": bool(
            demo_delivery_loaded
            or delivery_col
            or _find_table(schema_map, ("deliveries", "project_delivery", "delivery_schedule"))
        ),
    }

    _PROJECT_CAPABILITIES_CACHE = capabilities
    return dict(capabilities)


def get_project_schema_and_capabilities(
    conn: Any,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    schema_map = discover_project_schema(conn, force_refresh=force_refresh)
    capabilities = get_project_capabilities(conn, force_refresh=force_refresh)
    return {
        "schema_map": schema_map,
        "capabilities": capabilities,
    }


def get_project_overview(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None

    facts = get_demo_project_facts(conn, clean_code)
    schema_map = discover_project_schema(conn)
    projects_table = _find_table(schema_map, ("projects",))
    base: dict[str, Any] | None = None
    if projects_table:
        scope = _project_scope_sql(schema_map, projects_table, "p", clean_code)
        if scope is not None:
            join_sql, where_sql, params = scope
            query = (
                f"select p.* from {_q(projects_table)} p "
                f"{join_sql} where {where_sql} limit 1"
            )
            base = _fetch_one_knowledge(conn, "get_project_overview", query, params)
            if isinstance(base, dict):
                base["_source_table"] = projects_table

    if facts is None:
        return base

    merged = dict(base or {})
    merged["code"] = str(merged.get("code") or facts.get("project_code") or clean_code)
    merged["description"] = str(facts.get("description") or merged.get("description") or "")
    if facts.get("location_jsonb"):
        merged["location_jsonb"] = facts.get("location_jsonb")
    if facts.get("tags_jsonb"):
        merged["tags"] = facts.get("tags_jsonb")
    if facts.get("amenities_jsonb"):
        merged["amenities"] = facts.get("amenities_jsonb")
    if facts.get("construction_jsonb"):
        merged["construction"] = facts.get("construction_jsonb")
    if facts.get("financing_jsonb"):
        merged["financing"] = facts.get("financing_jsonb")
    if facts.get("unit_types_jsonb"):
        merged["unit_types"] = facts.get("unit_types_jsonb")
    merged["_source_table"] = "demo_project_facts"
    merged["_source_tables"] = _dedupe_sources(
        [
            "demo_project_facts",
            str((base or {}).get("_source_table") or ""),
        ]
    )
    return merged


def get_project_marketing_assets(conn: Any, project_code: str) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return []

    schema_map = discover_project_schema(conn)
    table_name = _find_table(schema_map, ("marketing_assets",))
    if not table_name:
        return []

    table_cols = schema_map.get(table_name, [])
    scope = _project_scope_sql(schema_map, table_name, "ma", clean_code)
    if scope is None:
        return []
    join_sql, where_sql, params = scope

    active_col = _find_column(table_cols, exact=("is_active", "active"), contains=("active",))
    sort_col = _find_column(table_cols, exact=("sort_order", "priority"), contains=("sort", "priority"))
    created_col = _find_column(table_cols, exact=("created_at",), contains=("created",))

    where_clauses = [where_sql]
    if active_col:
        where_clauses.append(f"coalesce(ma.{_q(active_col)}, true) = true")

    order_clauses: list[str] = []
    if sort_col:
        order_clauses.append(f"ma.{_q(sort_col)} asc")
    if created_col:
        order_clauses.append(f"ma.{_q(created_col)} asc")
    if not order_clauses:
        order_clauses.append("1 asc")

    query = (
        f"select ma.* from {_q(table_name)} ma {join_sql}"
        f" where {' and '.join(where_clauses)}"
        f" order by {', '.join(order_clauses)}"
        " limit 30"
    )
    rows = _fetch_all_knowledge(conn, "get_project_marketing_assets", query, params)
    for row in rows:
        row["_source_table"] = table_name
    if rows:
        return rows

    facts = get_demo_project_facts(conn, clean_code)
    if isinstance(facts, dict):
        chips = facts.get("amenities_jsonb")
        if not isinstance(chips, list):
            chips = facts.get("tags_jsonb")
        return [
            {
                "title": clean_code,
                "short_copy": facts.get("description"),
                "chips": chips if isinstance(chips, list) else [],
                "_source_table": "demo_project_facts",
            }
        ]
    return rows


def get_unit_types(conn: Any, project_code: str) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return []

    schema_map = discover_project_schema(conn)
    demo_units = list_demo_units(conn, clean_code)
    if demo_units:
        grouped: dict[tuple[str, str], int] = {}
        for unit in demo_units:
            rooms = str(unit.get("rooms_count") or "").strip()
            label = str(unit.get("rooms_label") or unit.get("typology") or "").strip()
            key = (rooms, label)
            grouped[key] = grouped.get(key, 0) + 1
        output: list[dict[str, Any]] = []
        for (rooms, label), count in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
            output.append(
                {
                    "rooms": rooms or None,
                    "label": label or None,
                    "units_count": count,
                    "_source_table": "demo_units",
                }
            )
        if output:
            return output

    table_name = _find_table(schema_map, ("demo_units", "unit_types", "units", "unidades"))
    if not table_name:
        facts = get_demo_project_facts(conn, clean_code)
        unit_types = facts.get("unit_types_jsonb") if isinstance(facts, dict) else []
        if isinstance(unit_types, list) and unit_types:
            return [
                {"rooms": None, "label": str(item), "units_count": None, "_source_table": "demo_project_facts"}
                for item in unit_types
            ]
        return []
    table_cols = schema_map.get(table_name, [])
    scope = _project_scope_sql(schema_map, table_name, "u", clean_code)
    if scope is None:
        return []
    join_sql, where_sql, params = scope

    rooms_col = _find_column(
        table_cols,
        exact=("rooms", "ambientes", "room_count", "num_rooms", "bedrooms"),
        contains=("room", "ambiente", "bed"),
    )
    label_col = _find_column(
        table_cols,
        exact=("unit_type", "typology", "tipo_unidad", "label", "name", "ambiente"),
        contains=("typolog", "tipo", "ambiente", "name", "label"),
    )
    if not rooms_col and not label_col:
        return []

    rooms_expr = f"u.{_q(rooms_col)}::text" if rooms_col else "null::text"
    label_expr = f"u.{_q(label_col)}::text" if label_col else "null::text"
    query = (
        "select "
        f"{rooms_expr} as rooms, "
        f"{label_expr} as label, "
        "count(*)::int as units_count "
        f"from {_q(table_name)} u {join_sql}"
        f" where {where_sql}"
        " group by 1, 2"
        " order by 1 nulls last, 2 asc"
        " limit 30"
    )
    rows = _fetch_all_knowledge(conn, "get_unit_types", query, params)
    for row in rows:
        row["_source_table"] = table_name
    return rows


def get_prices_by_rooms(
    conn: Any,
    project_code: str,
    rooms: int | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return []

    clean_currency = str(currency or "").strip().upper() or None
    demo_rows = list_demo_units(
        conn,
        clean_code,
        rooms=rooms,
        currency=clean_currency,
    )
    priced_demo = [row for row in demo_rows if row.get("list_price") is not None]
    if priced_demo:
        mapped: list[dict[str, Any]] = []
        for row in priced_demo:
            mapped.append(
                {
                    "rooms": row.get("rooms_count"),
                    "price": row.get("list_price"),
                    "currency": row.get("currency"),
                    "status": row.get("availability_status"),
                    "unit_ref": row.get("unit_code") or row.get("unit_id"),
                    "_source_table": "demo_units",
                }
            )
        return mapped

    schema_map = discover_project_schema(conn)

    candidate_tables = ["demo_units", "units", "unidades", "price_lists", "prices", "unit_prices"]
    for table_name in schema_map:
        if "price" in table_name and table_name not in candidate_tables:
            candidate_tables.append(table_name)

    for table_name in candidate_tables:
        if table_name not in schema_map:
            continue
        table_cols = schema_map[table_name]
        price_col = _find_column(
            table_cols,
            exact=("price", "list_price", "price_amount", "precio", "amount", "value"),
            contains=("price", "precio"),
        )
        if not price_col:
            continue

        rooms_col = _find_column(
            table_cols,
            exact=("rooms", "ambientes", "room_count", "num_rooms", "bedrooms"),
            contains=("room", "ambiente", "bed"),
        )
        currency_col = _find_column(
            table_cols,
            exact=("currency", "moneda"),
            contains=("currency", "moneda"),
        )
        unit_col = _find_column(
            table_cols,
            exact=("unit_code", "code", "name", "unidad", "numero"),
            contains=("unit", "code", "name", "unidad", "numero"),
        )
        status_col = _find_column(
            table_cols,
            exact=("status", "availability_status", "estado", "state"),
            contains=("status", "estado"),
        )
        scope = _project_scope_sql(schema_map, table_name, "u", clean_code)
        if scope is None:
            continue
        join_sql, where_sql, params = scope

        where_clauses = [where_sql]
        query_params: list[Any] = list(params)
        if rooms is not None:
            if not rooms_col:
                continue
            where_clauses.append(f"u.{_q(rooms_col)}::text = %s")
            query_params.append(str(int(rooms)))
        if clean_currency and currency_col:
            where_clauses.append(f"upper(u.{_q(currency_col)}::text) = upper(%s)")
            query_params.append(clean_currency)

        rooms_expr = f"u.{_q(rooms_col)}::text" if rooms_col else "null::text"
        currency_expr = f"u.{_q(currency_col)}::text" if currency_col else "null::text"
        unit_expr = f"u.{_q(unit_col)}::text" if unit_col else "null::text"
        status_expr = f"u.{_q(status_col)}::text" if status_col else "null::text"

        query = (
            "select "
            f"{rooms_expr} as rooms, "
            f"u.{_q(price_col)} as price, "
            f"{currency_expr} as currency, "
            f"{status_expr} as status, "
            f"{unit_expr} as unit_ref "
            f"from {_q(table_name)} u {join_sql}"
            f" where {' and '.join(where_clauses)}"
            f" order by u.{_q(price_col)} asc nulls last"
            " limit 200"
        )
        rows = _fetch_all_knowledge(conn, "get_prices_by_rooms", query, tuple(query_params))
        if rows:
            for row in rows:
                row["_source_table"] = table_name
            return rows
    return []


def get_availability_by_rooms(
    conn: Any,
    project_code: str,
    rooms: int | None = None,
) -> list[dict[str, Any]]:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return []

    demo_rows = list_demo_units(conn, clean_code, rooms=rooms)
    if demo_rows:
        grouped: dict[str, int] = {}
        for row in demo_rows:
            status = str(row.get("availability_status") or "unknown")
            grouped[status] = grouped.get(status, 0) + 1
        output: list[dict[str, Any]] = []
        for status, total in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
            output.append(
                {"status": status, "units_count": total, "_source_table": "demo_units"}
            )
        if output:
            return output

    schema_map = discover_project_schema(conn)
    candidate_tables = ["demo_units", "availability", "units", "unidades"]
    for table_name in schema_map:
        if "avail" in table_name and table_name not in candidate_tables:
            candidate_tables.append(table_name)

    for table_name in candidate_tables:
        if table_name not in schema_map:
            continue
        table_cols = schema_map[table_name]
        scope = _project_scope_sql(schema_map, table_name, "u", clean_code)
        if scope is None:
            continue
        join_sql, where_sql, params = scope

        rooms_col = _find_column(
            table_cols,
            exact=("rooms", "ambientes", "room_count", "num_rooms", "bedrooms"),
            contains=("room", "ambiente", "bed"),
        )
        status_col = _find_column(
            table_cols,
            exact=("status", "availability_status", "estado", "state"),
            contains=("status", "estado", "dispon"),
        )
        available_col = _find_column(
            table_cols,
            exact=("is_available", "available"),
            contains=("available",),
        )
        if not status_col and not available_col:
            continue

        where_clauses = [where_sql]
        query_params: list[Any] = list(params)
        if rooms is not None:
            if not rooms_col:
                continue
            where_clauses.append(f"u.{_q(rooms_col)}::text = %s")
            query_params.append(str(int(rooms)))

        if status_col:
            status_expr = f"coalesce(u.{_q(status_col)}::text, 'sin_estado')"
        else:
            status_expr = (
                f"case when coalesce(u.{_q(available_col)}, false) "
                "then 'disponible' else 'no_disponible' end"
            )
        query = (
            "select "
            f"{status_expr} as status, "
            "count(*)::int as units_count "
            f"from {_q(table_name)} u {join_sql}"
            f" where {' and '.join(where_clauses)}"
            " group by 1"
            " order by 2 desc, 1 asc"
        )
        rows = _fetch_all_knowledge(conn, "get_availability_by_rooms", query, tuple(query_params))
        if rows:
            for row in rows:
                row["_source_table"] = table_name
            return rows
    return []


def get_financing_terms(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None

    facts = get_demo_project_facts(conn, clean_code)
    if isinstance(facts, dict):
        financing_data = facts.get("financing_jsonb")
        if financing_data not in (None, "", {}, []):
            return {
                "source_table": "demo_project_facts",
                "fields": ["financing_jsonb"],
                "items": [{"financing_data": financing_data}],
            }

    schema_map = discover_project_schema(conn)
    projects_table = _find_table(schema_map, ("projects",))
    if projects_table:
        project_cols = schema_map.get(projects_table, [])
        financing_col = _find_column(
            project_cols,
            exact=(
                "financing_terms",
                "financing",
                "payment_terms",
                "payment_plan",
                "financiacion",
                "cuotas",
                "anticipo",
            ),
            contains=("financ", "cuota", "payment", "anticipo"),
        )
        if financing_col:
            scope = _project_scope_sql(schema_map, projects_table, "p", clean_code)
            if scope is not None:
                join_sql, where_sql, params = scope
                query = (
                    f"select p.{_q(financing_col)} as financing_data "
                    f"from {_q(projects_table)} p {join_sql} where {where_sql} limit 1"
                )
                row = _fetch_one_knowledge(conn, "get_financing_terms.projects", query, params)
                if row and row.get("financing_data") not in (None, "", [], {}):
                    return {
                        "source_table": projects_table,
                        "fields": [financing_col],
                        "items": [row],
                    }

    candidates = ["payment_plans", "financing_terms", "financing", "payment_options"]
    for table_name in list(schema_map):
        if ("financ" in table_name or "payment" in table_name) and table_name not in candidates:
            candidates.append(table_name)

    for table_name in candidates:
        if table_name not in schema_map:
            continue
        scope = _project_scope_sql(schema_map, table_name, "f", clean_code)
        if scope is None:
            continue
        join_sql, where_sql, params = scope
        query = (
            f"select f.* from {_q(table_name)} f {join_sql}"
            f" where {where_sql}"
            " order by 1"
            " limit 20"
        )
        rows = _fetch_all_knowledge(conn, "get_financing_terms.table", query, params)
        if rows:
            for row in rows:
                row["_source_table"] = table_name
            return {
                "source_table": table_name,
                "fields": list(schema_map.get(table_name, [])),
                "items": rows,
            }
    return None


def get_delivery_info(conn: Any, project_code: str) -> dict[str, Any] | None:
    clean_code = str(project_code or "").strip()
    if not clean_code:
        return None

    facts = get_demo_project_facts(conn, clean_code)
    if isinstance(facts, dict):
        construction = facts.get("construction_jsonb")
        if isinstance(construction, dict) and construction:
            delivery_date = construction.get("delivery_estimated_at")
            stage = construction.get("stage")
            if delivery_date or stage:
                return {
                    "source_table": "demo_project_facts",
                    "fields": ["construction_jsonb"],
                    "items": [
                        {
                            "delivery_date": delivery_date,
                            "status": stage,
                            "construction": construction,
                        }
                    ],
                }

    schema_map = discover_project_schema(conn)
    projects_table = _find_table(schema_map, ("projects",))
    if projects_table:
        project_cols = schema_map.get(projects_table, [])
        delivery_col = _find_column(
            project_cols,
            exact=(
                "delivery_date",
                "estimated_delivery_date",
                "entrega_estimada",
                "handover_date",
                "possession_date",
                "delivery_at",
            ),
            contains=("delivery", "entrega", "handover", "posesion"),
        )
        status_col = _find_column(
            project_cols,
            exact=("status", "project_status", "estado"),
            contains=("status", "estado"),
        )
        if delivery_col or status_col:
            scope = _project_scope_sql(schema_map, projects_table, "p", clean_code)
            if scope is not None:
                join_sql, where_sql, params = scope
                selects: list[str] = []
                if delivery_col:
                    selects.append(f"p.{_q(delivery_col)} as delivery_date")
                if status_col:
                    selects.append(f"p.{_q(status_col)} as status")
                query = (
                    f"select {', '.join(selects)} "
                    f"from {_q(projects_table)} p {join_sql} "
                    f"where {where_sql} limit 1"
                )
                row = _fetch_one_knowledge(conn, "get_delivery_info.projects", query, params)
                if row and any(value not in (None, "", [], {}) for value in row.values()):
                    return {
                        "source_table": projects_table,
                        "fields": [field for field in (delivery_col, status_col) if field],
                        "items": [row],
                    }

    candidates = ["deliveries", "project_delivery", "delivery_schedule", "construction_stages"]
    for table_name in list(schema_map):
        if "delivery" in table_name and table_name not in candidates:
            candidates.append(table_name)

    for table_name in candidates:
        if table_name not in schema_map:
            continue
        scope = _project_scope_sql(schema_map, table_name, "d", clean_code)
        if scope is None:
            continue
        join_sql, where_sql, params = scope
        query = (
            f"select d.* from {_q(table_name)} d {join_sql}"
            f" where {where_sql}"
            " order by 1"
            " limit 20"
        )
        rows = _fetch_all_knowledge(conn, "get_delivery_info.table", query, params)
        if rows:
            for row in rows:
                row["_source_table"] = table_name
            return {
                "source_table": table_name,
                "fields": list(schema_map.get(table_name, [])),
                "items": rows,
            }
    return None
