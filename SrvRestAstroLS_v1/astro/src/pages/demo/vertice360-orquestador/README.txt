# Vertice360 Orquestador (LIVE + UX)

## Rutas

- LIVE oficial: `/demo/vertice360-orquestador/`
- LIVE con cliente: `/demo/vertice360-orquestador/?cliente=5491130946950`
- UX wireframe oficial: `/demo/vertice360-orquestador/ux`
- UX con cliente: `/demo/vertice360-orquestador/ux?cliente=5491100000000`

## Alcance actual

- LIVE: integración con backend (`/api/demo/vertice360-orquestador/*`) vía `api.js`.
- UX: wireframe navegable para validación de diseño con mocks.

## Navegación esperada

1. LIVE sin cliente: `/demo/vertice360-orquestador/`.
2. LIVE con cliente: `/demo/vertice360-orquestador/?cliente=5491130946950`.
3. UX sin cliente: `/demo/vertice360-orquestador/ux`.
4. UX con cliente: `/demo/vertice360-orquestador/ux?cliente=5491100000000`.

## Proximo paso (cuando avance producto)

- Reemplazar placeholders por mock data realista.
- Definir contrato de API/SSE para conectar lógica funcional.
- Integrar acciones de tabla/modal con estado real.

## LIVE route

- Ruta LIVE oficial: `/demo/vertice360-orquestador/`
- Ruta LIVE con cliente: `/demo/vertice360-orquestador/?cliente=5491130946950`
- Componente LIVE: `astro/src/components/demo/vertice360-orquestador/OrquestadorAppLive.svelte`
- API LIVE: `astro/src/lib/vertice360_orquestador/api.js`

Notas:
- El flujo UX (wireframe) se mantiene en `ux.astro` + `OrquestadorApp.svelte` + mocks.
- La ruta LIVE root usa backend real (`/api/demo/vertice360-orquestador/*`).

### Sanity checks (base URL global)

1. Verificar base URL efectivo en browser console:
   - `import('/src/components/global.js').then(m => console.log(m.getRestBaseUrl()))`
2. Verificar endpoint health con la misma base global:
   - `import('/src/components/global.js').then(async (m) => { const r = await fetch(`${m.getRestBaseUrl()}/health`); console.log(r.status); })`
3. Verificar bootstrap del orquestador LIVE:
   - `import('/src/components/global.js').then(async (m) => { const r = await fetch(`${m.getRestBaseUrl()}/api/demo/vertice360-orquestador/bootstrap`); console.log(await r.json()); })`
4. Verificar bootstrap vía cliente API (mismo patrón LIVE):
   - `Promise.all([import('/src/components/global.js'), import('/src/lib/vertice360_orquestador/api.js')]).then(async ([g, api]) => { console.log(g.getRestBaseUrl()); console.log(await api.bootstrap({ cliente: '5491130946950' })); })`
