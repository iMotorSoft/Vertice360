# Informe de Solución: Integración Gupshup WhatsApp
**Fecha**: 2026-02-08 13:48 (GMT-3)
**Autor**: Antigravity (AI Assistant)
**Contexto**: Debugging de mensajes entrantes y salientes (Reply) en integración Gupshup.

## Resumen Ejecutivo
Se logró restablecer el flujo de mensajes Inbound y Outbound para Gupshup WhatsApp. El problema principal residía en diferencias no documentadas entre el payload de "Test" y "Live" de Gupshup, así como en la lógica de enrutamiento de respuestas que no consideraba el proveedor `gupshup`.

## Problemas Identificados y Soluciones

### 1. Estructura de Payload Anidado (Live vs Test)
**Síntoma**: Los webhooks llegaban al servidor (evento `sandbox-start` recibido), pero los mensajes de usuario (`Hi`) eran ignorados silenciosamente.
**Causa**: Las apps "Live" de Gupshup envían el contenido del mensaje anidado un nivel más profundo (`payload.payload.text`) que las de prueba (`payload.text`). El parser `_looks_like_message` devolvía `False`.
**Solución**: Se actualizó `mapper.py` para inspeccionar recursivamente cargas anidadas.

### 2. Extracción Incorrecta de Número Telefónico (Número Duplicado)
**Síntoma**: El sistema intentaba responder a números inválidos como `54911309469505491130946950` (el número repetido dos veces).
**Causa**: El campo `sender` en el payload venía como un objeto `dict` (`{"phone": "...", "dial_code": "..."}`). La lógica de extracción convertía el diccionario a string y luego extraía *todos* los dígitos, concatenando el `dial_code` y el `phone`.
**Solución**: Se modificó `mapper.py` para detectar si `sender` es un diccionario y extraer específicamente la clave `phone`.

### 3. Error de Validación de Formato (Símbolo `+`)
**Síntoma**: Error `WhatsApp 'to' must contain only digits`.
**Causa**: Los números de teléfono incluían el símbolo `+` (ej: `+54911...`), lo cual fallaba la validación estricta del workflow.
**Solución**: Se agregó sanitización en `messaging.py` para remover cualquier caracter no numérico de los campos `from` y `to` antes de procesar.

### 4. Enrutamiento de Respuesta (Provider Mismatch)
**Síntoma**: Error `Recipient phone number not in allowed list` (Facebook Graph API error).
**Causa**: El sistema intentaba responder usando el cliente de **Meta WhatsApp** (directo) en lugar del cliente de **Gupshup**. Esto fallaba porque el usuario de Gupshup no es un usuario de prueba de la App de Meta directa.
**Solución**: 
- Se refactorizó `start_demo_reply` y `process_inbound_message` en `services.py`.
- Se implementó `_send_whatsapp_text` con lógica condicional: si el proveedor es `gupshup_whatsapp`, usa el servicio de Gupshup; de lo contrario, usa Meta.

## Archivos Modificados

1.  `backend/modules/messaging/providers/gupshup/whatsapp/mapper.py` (Parser fix & Phone extraction)
2.  `backend/routes/messaging.py` (Sanitization)
3.  `backend/modules/vertice360_workflow_demo/services.py` (Reply routing)

## Estado Final
- **Inbound**: Correctamente parseado y normalizado.
- **Workflow**: Se dispara correctamente, creando tickets y eventos.
- **Outbound (Reply)**: Se enruta vía Gupshup API, permitiendo la comunicación bidireccional.

---
*Fin del informe.*
