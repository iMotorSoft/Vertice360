# Operativa Nginx: Alias demo.vertice360 -> demo.pozo360

Fecha/Hora de ejecucion (local): 2026-03-09 18:45:43 -0300  
Fecha/Hora de ejecucion (UTC): 2026-03-09 21:45:43Z

## Contexto
- Servidor: `imotorsoft.com`
- Usuario: `administrator`
- Objetivo: exponer `https://demo.vertice360.imotorsoft.com` exactamente igual que `https://demo.pozo360.imotorsoft.com`.

## Error detectado
Al ejecutar `sudo systemctl reload nginx`:

```text
cannot load certificate "/etc/letsencrypt/live/demo.vertice360.imotorsoft.com/fullchain.pem"
```

Causa: existia un vhost de `demo.vertice360.imotorsoft.com` apuntando a un certificado que todavia no existia.

## Acciones realizadas
1. Se identifico el vhost activo principal:
   - `/etc/nginx/sites-available/demo.pozo360.imotorsoft.com`
2. Se comprobo DNS:
   - `demo.pozo360.imotorsoft.com -> 148.113.196.80`
   - `demo.vertice360.imotorsoft.com -> 148.113.196.80`
3. Se unifico el `server_name` del vhost principal para ambos dominios:
   - `server_name demo.pozo360.imotorsoft.com demo.vertice360.imotorsoft.com;`
4. Se deshabilito el sitio duplicado/conflictivo:
   - symlink removido: `/etc/nginx/sites-enabled/demo.vertice360.imotorsoft.com`
5. Se emitio/renovo certificado con Certbot para ambos dominios en un solo cert:
   - `certbot --nginx --cert-name demo.pozo360.imotorsoft.com -d demo.pozo360.imotorsoft.com -d demo.vertice360.imotorsoft.com`
6. Se valido y recargo Nginx:
   - `nginx -t` OK
   - `systemctl reload nginx` OK

## Validacion final
- `https://demo.pozo360.imotorsoft.com` responde `HTTP/1.1 200 OK`.
- `https://demo.vertice360.imotorsoft.com` responde `HTTP/1.1 200 OK`.
- Certificado activo:
  - `Certificate Name: demo.pozo360.imotorsoft.com`
  - `Identifiers: demo.pozo360.imotorsoft.com demo.vertice360.imotorsoft.com`
  - Expira: `2026-06-07`.

## Backups generados
- `/etc/nginx/sites-available/demo.pozo360.imotorsoft.com.bak_<timestamp>`
- `/etc/nginx/sites-available/demo.vertice360.imotorsoft.com.bak_<timestamp>`

## Nota operativa
Si se agrega otro subdominio similar en el futuro:
1. Primero crear/validar DNS.
2. Luego agregar el dominio en `server_name`.
3. Finalmente expandir certificado con Certbot antes de recargar Nginx.

