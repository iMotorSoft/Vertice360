# Vertice360 Orquestador (Wireframe UX-only)

## Rutas

- Landing: `/demo/vertice360-orquestador/`
- Tablero: `/demo/vertice360-orquestador/orquestador?cliente=5491100000000`
- Single entrypoint con cliente: `/demo/vertice360-orquestador/?cliente=5491100000000`

## Alcance actual

- Wireframe navegable para validación de diseño.
- Sin integración a backend.
- Sin dataset realista (placeholders mínimos).
- Modal "Proponer visita" solo UI (sin persistencia).

## Navegación esperada

1. Abrir landing en `/demo/vertice360-orquestador/`.
2. Abrir single entrypoint con cliente en `/demo/vertice360-orquestador/?cliente=5491100000000`.
3. En tablero, abrir `Proponer visita`.
4. Enviar opciones (feedback visual local).

## Proximo paso (cuando avance producto)

- Reemplazar placeholders por mock data realista.
- Definir contrato de API/SSE para conectar lógica funcional.
- Integrar acciones de tabla/modal con estado real.
