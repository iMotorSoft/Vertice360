# Análisis de Funcionalidades UX - Vertice360 Workflow

Este documento detalla las funcionalidades disponibles en la demo de Vertice360 Workflow (`/demo/vertice360-workflow/`), analizando su propósito y aplicación práctica.

## 1. Inbox de Tickets (Bandeja de Entrada)

**Descripción:**
Panel lateral izquierdo que muestra un listado en tiempo real de los tickets activos provenientes de canales como WhatsApp.

**Funcionalidades:**
- **Visualización de Estado:** Identificación visual rápida del estado del ticket (OPEN, IN_PROGRESS, WAITING_DOCS) mediante etiquetas de colores.
- **Monitoreo SLA:** Contador regresivo para el próximo vencimiento de SLA (Acuerdo de Nivel de Servicio). Muestra "BREACHED" en rojo si se ha vencido, en tiempo real.
- **Indicadores de Actividad:** Animación "pulse" (anillo brillante) cuando un ticket recibe una actualización o mensaje nuevo.
- **Búsqueda y Filtrado:** Barra de búsqueda en tiempo real que filtra por ID de ticket, nombre del cliente, asunto o contenido del último mensaje.

**Aplicación Práctica:**
Permite a los operadores priorizar su trabajo identificando rápidamente qué tickets requieren atención inmediata (por SLA o nuevos mensajes) y mantener el contexto de múltiples conversaciones simultáneas sin perder de vista los plazos críticos.

## 2. Detalle del Ticket (Ticket Drawer)

**Descripción:**
Panel principal que se despliega al seleccionar un ticket, ofreciendo una vista de 360 grados del caso.

**Pestañas Disponibles:**
1.  **Timeline:** Historial cronológico completo de eventos (creación, asignación, cambios de estado, mensajes).
2.  **Mensajes:** Vista tipo chat de la conversación (WhatsApp) entre el cliente y el bot/agente.
3.  **Docs:** "DocsChecklist" para el seguimiento específico de documentación requerida.

**Aplicación Práctica:**
Centraliza toda la información necesaria para resolver un caso. El operador no necesita cambiar de pantalla para ver qué pasó hace una hora (Timeline), qué dijo el cliente (Mensajes) o qué documentos faltan (Docs), agilizando la resolución.

## 3. Acciones de Gestión (Workflow Actions)

**Descripción:**
Conjunto de botones de acción rápida situados en la cabecera del detalle del ticket, que ejecutan transiciones de estado en el backend.

**Funcionalidades:**
- **Asignar a Administración:** Asigna el ticket a un equipo/agente específico ("Admin - Lucía") y cambia el estado a `IN_PROGRESS`.
    *   *Uso:* Toma de posesión del caso por parte de un humano.
- **Solicitar Docs:** Define una lista de documentos requeridos y cambia el estado a `WAITING_DOCS`.
    *   *Uso:* Cuando falta información crítica para avanzar. Pausa el SLA de gestión interna.
- **Marcar Docs Recibidas:** Registra la recepción de documentos y reactiva el ticket a `IN_PROGRESS`.
    *   *Uso:* Confirmación manual de que el cliente ha enviado lo solicitado.
- **Validar y Cerrar:** Cierra el ticket con una resolución exitosa (`DOCS_VALIDATED`).
    *   *Uso:* Finalización del ciclo de vida del ticket tras gestión exitosa.
- **Escalar:** Deriva el ticket a un nivel superior ("SUPERVISOR") y cambia estado a `ESCALATED`.
    *   *Uso:* Gestión de casos complejos o conflictivos.

## 4. Simulación de Escenarios (SLA & Demo Control)

**Descripción:**
Herramientas específicas para demostración y pruebas de estrés del sistema.

**Funcionalidades:**
- **Simular Breach:** Fuerza el vencimiento inmediato de un SLA (Assignment o Doc Validation).
    *   *Uso Demo:* Demostrar cómo el sistema reacciona ante incumplimientos (notificaciones, escalado automático).
- **Reiniciar Demo (TopBar):** Limpia la base de datos en memoria y "siembra" nuevos tickets de prueba.
    *   *Uso Demo:* Volver a un estado limpio para presentar el flujo desde cero.

## 5. Log de Eventos en Vivo (Live Event Log)

**Descripción:**
Panel inferior (ocultable) que muestra el flujo crudo de eventos JSON recibidos vía Server-Sent Events (SSE).

**Funcionalidades:**
- **Streaming de Datos:** Visualización técnica de eventos como `ticket.created`, `messaging.inbound`, `workflow.updated`.
- **Filtros:** Capacidad para filtrar por eventos de Mensajería, Workflow o errores.

**Aplicación Práctica:**
Aunque es una herramienta técnica, en un contexto de operación supervisada permite verificar que las automatizaciones están disparándose correctamente y ofrece transparencia total sobre lo que ocurre "bajo el capó" del sistema.
