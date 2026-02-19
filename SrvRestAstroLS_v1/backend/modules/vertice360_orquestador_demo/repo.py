from __future__ import annotations

import json
from typing import Any


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


def list_project_codes(conn: Any) -> list[str]:
    rows = fetch_all(conn, "select code from projects order by code asc")
    return [str(row.get("code") or "") for row in rows if row.get("code")]


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
            created_at,
            updated_at
        """,
        tuple(params),
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
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            p.code as project_code,
            p.name as project_name,
            c.status as conversation_status,
            c.channel as conversation_channel,
            c.last_message_at as conversation_last_message_at
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
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
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            l.source as lead_source,
            p.code as project_code,
            p.name as project_name,
            coalesce(lm.text, t.last_message_snippet, '') as last_message_text,
            lm.direction as last_message_direction,
            lm.actor as last_message_actor,
            lm.created_at as last_message_at,
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
            t.created_at,
            t.updated_at,
            l.phone_e164,
            l.name as lead_name,
            l.source as lead_source,
            p.code as project_code,
            p.name as project_name
        from tickets t
        join leads l on l.id = t.lead_id
        left join projects p on p.id = t.project_id
        where t.id = %s
        limit 1
        """,
        (ticket_id,),
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
