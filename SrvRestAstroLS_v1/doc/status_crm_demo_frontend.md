# Estado CRM Demo Frontend (Astro / Svelte 5 / DaisyUI)

- Fecha: 2025-12-16 03:52:31Z (UTC)
- Página: `/demo/crm` (AppShell, Inbox, Conversación, Pipeline, Tareas, Timeline)
- Utilidades: `astro/src/lib/crm/{api,sse,time,state.svelte}.js`
- Componentes clave: `astro/src/components/demo/crm/*` y `astro/src/components/demo/crm/ui/*`
- Config: `astro/src/components/global.js` (URL_REST apunta a localhost; URL_SSE expuesta)

Pendientes para retomar:
- Probar visualmente la página (npm dev) y validar SSE en vivo.
- Revisar drag & drop del pipeline contra el backend mock.
- Ajustar estilos finos si es necesario.
