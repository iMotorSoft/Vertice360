# Informe de Seguridad - Vertice360 API

**Fecha:** 2026-02-12 18:36:51  
**Servidor:** demo.pozo360.imotorsoft.com  
**Estado:** Análisis de intentos de acceso no autorizado

---

## 🔴 Amenazas Detectadas

### 1. Intentos de Acceso a Archivos Sensibles

**Patrones detectados:**
```
/api/.env
/.env
/.git/config
/config.json
/api/config
/wp-config.php
/admin/.env
.env.local
.env.production
```

**Riesgo:** CRÍTICO  
**Impacto:** Exposición de credenciales, API keys, contraseñas de base de datos

---

## Análisis de Configuración Nginx Actual

### ✅ Aspectos Positivos
- SSL/TLS configurado con Certbot
- Proxy a backend en localhost (no expuesto directamente)
- Headers de forward correctos (X-Real-IP, X-Forwarded-For, etc.)

### ❌ Vulnerabilidades Identificadas

#### 1. **Sin Protección contra Escaneo de Archivos**
- No hay bloqueo de rutas sensibles (/.env, /.git, etc.)
- Atacantes pueden verificar existencia de archivos

#### 2. **Sin Rate Limiting**
- Múltiples intentos desde misma IP no son limitados
- Vulnerable a fuerza bruta y DoS

#### 3. **Sin Headers de Seguridad**
- Falta X-Content-Type-Options
- Falta X-Frame-Options
- Falta Content-Security-Policy
- Falta Strict-Transport-Security (HSTS)

#### 4. **Exposición de Versión**
- Nginx puede revelar versión en errores

#### 5. **Sin Protección contra Bots**
- No hay validación de User-Agent
- No hay bloqueo de bots maliciosos

---

## 🛡️ Recomendaciones de Seguridad

### A. Configuración Nginx (Prioridad ALTA)

#### 1. Bloquear Acceso a Archivos Sensibles

```nginx
# Bloquear archivos y directorios sensibles
location ~ /\. {
    deny all;
    return 404;
}

location ~ /\.env {
    deny all;
    return 404;
}

location ~ /\.git {
    deny all;
    return 404;
}

location ~ /(composer\.json|composer\.lock|package\.json|README\.md|CHANGELOG\.md)$ {
    deny all;
    return 404;
}

# Bloquear extensiones peligrosas
location ~* \.(env|config|ini|log|sh|sql|bak|backup|swp|old|orig|save)$ {
    deny all;
    return 404;
}
```

#### 2. Implementar Rate Limiting

```nginx
# Zona de rate limiting (agregar en http block de nginx.conf)
# http {
#     limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
#     limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=50r/s;
#     limit_conn_zone $binary_remote_addr zone=addr:10m;
# }

# Aplicar a location /api/
location ^~ /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    limit_conn addr 10;
    
    proxy_pass http://127.0.0.1:7062;
    # ... resto de configuración
}

# Webhooks pueden tener límites más altos
location ^~ /webhooks/ {
    limit_req zone=webhook_limit burst=100 nodelay;
    
    proxy_pass http://127.0.0.1:7062;
    # ... resto de configuración
}
```

#### 3. Headers de Seguridad

```nginx
# Agregar a todos los location
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# HSTS (solo si SSL está bien configurado)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# CSP (ajustar según necesidades)
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';" always;
```

#### 4. Ocultar Versión de Nginx

```nginx
# En nginx.conf
server_tokens off;
```

---

### B. Implementación en Litestar (Python)

#### 1. Middleware de Seguridad

Crear archivo: `middleware/security.py`

```python
"""Security middleware for Litestar application."""

from typing import TYPE_CHECKING
from litestar import Response
from litestar.middleware import AbstractMiddleware
from litestar.types import Scope, Receive, Send
import time
from collections import defaultdict
import logging

if TYPE_CHECKING:
    from litestar import Litestar

logger = logging.getLogger(__name__)

# Simple in-memory rate limiting (use Redis in production)
class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True

# Global rate limiter
rate_limiter = RateLimiter(max_requests=60, window=60)


class SecurityHeadersMiddleware(AbstractMiddleware):
    """Add security headers to all responses."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                
                # Add security headers
                security_headers = [
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-Frame-Options", b"SAMEORIGIN"),
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                    (b"Permissions-Policy", b"geolocation=(), microphone=(), camera=()"),
                ]
                
                headers.extend(security_headers)
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)


class RateLimitMiddleware(AbstractMiddleware):
    """Rate limiting middleware."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get client IP
        client_ip = (
            scope.get("headers", [])
            .get(b"x-forwarded-for", b"")
            .decode("utf-8")
            .split(",")[0]
            .strip()
        ) or scope.get("client", ("", 0))[0]
        
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            response = Response(
                content={"error": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"}
            )
            await response(scope, receive, send)
            return
        
        await self.app(scope, receive, send)


class BlockPathsMiddleware(AbstractMiddleware):
    """Block access to sensitive paths."""
    
    BLOCKED_PATHS = [
        "/.env",
        "/.git",
        "/config.json",
        "/composer.json",
        "/package.json",
        "/README.md",
        "/.htaccess",
        "/.htpasswd",
        "/wp-config.php",
        "/admin/.env",
        "/api/.env",
    ]
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Check blocked paths
        for blocked in self.BLOCKED_PATHS:
            if path.startswith(blocked) or blocked in path:
                logger.warning(f"Blocked access to sensitive path: {path} from {scope.get('client', '')}")
                response = Response(
                    content={"error": "Not found"},
                    status_code=404
                )
                await response(scope, receive, send)
                return
        
        # Block common attack patterns
        attack_patterns = [
            "../",  # Directory traversal
            "%2e%2e%2f",  # URL encoded traversal
            "..%2f",
            "%2e%2e/",
            "etc/passwd",
            "win.ini",
            "boot.ini",
        ]
        
        lower_path = path.lower()
        for pattern in attack_patterns:
            if pattern in lower_path:
                logger.warning(f"Blocked attack pattern '{pattern}' in path: {path}")
                response = Response(
                    content={"error": "Not found"},
                    status_code=404
                )
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)
```

#### 2. Configuración en App Principal

```python
# En ls_iMotorSoft_Srv01_demo.py o donde crees la app

from litestar import Litestar
from litestar.middleware import RateLimitMiddleware, SecurityHeadersMiddleware, BlockPathsMiddleware
from litestar.config import CORSConfig

# ... otras importaciones

def create_app() -> Litestar:
    app = Litestar(
        # ... tu configuración actual
        
        # CORS seguro
        cors_config=CORSConfig(
            allow_origins=["https://demo.pozo360.imotorsoft.com"],  # Solo tu dominio
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "Authorization", "X-API-Key"],
            allow_credentials=True,
            max_age=3600,
        ),
        
        # Middlewares de seguridad
        middleware=[
            # Orden importante: primero bloquear, luego rate limit, luego headers
            BlockPathsMiddleware,
            RateLimitMiddleware,
            SecurityHeadersMiddleware,
        ],
        
        # Opciones de debug (apagar en producción)
        debug=False,
    )
    
    return app

app = create_app()
```

#### 3. Validación de Webhooks

```python
# middleware/webhook_validation.py

import hmac
import hashlib
from litestar import Response
from litestar.middleware import AbstractMiddleware
from litestar.types import Scope, Receive, Send
import logging

logger = logging.getLogger(__name__)

class WebhookSignatureMiddleware(AbstractMiddleware):
    """Validate webhook signatures (ejemplo para Gupshup)."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Solo validar webhooks
        if not path.startswith("/webhooks/"):
            await self.app(scope, receive, send)
            return
        
        # Aquí agregar validación específica del provider
        # Por ejemplo, verificar X-Hub-Signature de Gupshup
        
        headers = dict(scope.get("headers", []))
        
        # Log webhook receipt
        logger.info(f"Webhook received: {path}")
        
        await self.app(scope, receive, send)
```

---

### C. Configuración de Logging de Seguridad

```python
# logging_config.py

import logging
from logging.handlers import RotatingFileHandler
import os

def setup_security_logging():
    """Setup dedicated security logging."""
    
    # Security log
    security_handler = RotatingFileHandler(
        "logs/security.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    security_handler.setLevel(logging.WARNING)
    
    security_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    security_handler.setFormatter(security_formatter)
    
    security_logger = logging.getLogger("security")
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.WARNING)
    
    # Access log
    access_handler = RotatingFileHandler(
        "logs/access.log",
        maxBytes=50_000_000,  # 50MB
        backupCount=10
    )
    access_handler.setLevel(logging.INFO)
    
    access_logger = logging.getLogger("access")
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)

# Llamar en startup
setup_security_logging()
```

---

### D. Fail2ban (Protección a nivel de Sistema)

Crear: `/etc/fail2ban/jail.local`

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-req-limit]
enabled = true
filter = nginx-req-limit
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/access.log
maxretry = 10
findtime = 60
bantime = 7200

[nginx-auth]
enabled = true
filter = nginx-auth
action = iptables-multiport[name=HTTPAuth, port="http,https", protocol=tcp]
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600

[nginx-env-scan]
enabled = true
filter = nginx-env-scan
action = iptables-multiport[name=EnvScan, port="http,https", protocol=tcp]
logpath = /var/log/nginx/access.log
maxretry = 2
findtime = 60
bantime = 86400
```

Crear filtro: `/etc/fail2ban/filter.d/nginx-env-scan.conf`

```ini
[Definition]
failregex = ^<HOST>.*\.(env|git|config|json).*HTTP/[0-9.]*" [0-9]{3}
ignoreregex =
```

---

## Configuración Nginx Completa Recomendada

```nginx
server {
    listen 443 ssl;
    server_name demo.pozo360.imotorsoft.com;

    client_max_body_size 50M;
    
    # Ocultar versión de nginx
    server_tokens off;

    # Headers de seguridad globales
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Bloquear archivos sensibles
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
        return 404;
    }

    location ~* \.(env|config|ini|log|sh|sql|bak|backup|swp|old|orig|save)$ {
        deny all;
        access_log off;
        log_not_found off;
        return 404;
    }

    # Webhooks -> Backend Litestar
    location ^~ /webhooks/ {
        limit_req zone=webhook_limit burst=100 nodelay;
        limit_conn addr 20;
        
        proxy_pass http://127.0.0.1:7062;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
        proxy_buffering off;
        
        add_header Cache-Control "no-store";
    }
    
    # API -> Backend Litestar
    location ^~ /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn addr 10;
        
        proxy_pass http://127.0.0.1:7062;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
        proxy_buffering off;
        
        add_header Cache-Control "no-store";
    }

    # Frontend Astro (static)
    location / {
        root /home/administrator/project/iMotorSoft/ai/Pozo360/SrvRestAstroLS_v1/astro/dist;
        try_files $uri $uri/ /index.html$is_args$args;
        
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # SSL (Certbot)
    ssl_certificate /etc/letsencrypt/live/demo.pozo360.imotorsoft.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/demo.pozo360.imotorsoft.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
```

---

## Checklist de Implementación

### Inmediato (Bloquear Ataques Actuales)
- [ ] Agregar bloqueo de `/.env` y similares en nginx
- [ ] Activar rate limiting en nginx
- [ ] Implementar BlockPathsMiddleware en Litestar

### Corto Plazo (1-2 días)
- [ ] Implementar SecurityHeadersMiddleware
- [ ] Configurar fail2ban
- [ ] Activar logs de seguridad

### Mediano Plazo (1 semana)
- [ ] Implementar RateLimitMiddleware con Redis
- [ ] Configurar monitoreo de seguridad
- [ ] Realizar auditoría de seguridad

---

## Comandos de Verificación

```bash
# Ver logs de ataques actuales
sudo tail -f /var/log/nginx/access.log | grep -E "(\.env|\.git|config)"

# Ver IPs bloqueadas por fail2ban
sudo fail2ban-client status nginx-env-scan

# Test de headers de seguridad
curl -I https://demo.pozo360.imotorsoft.com/api/health

# Verificar rate limiting
for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\n" https://demo.pozo360.imotorsoft.com/api/; done
```

---

**Prioridad:** ALTA  
**Tiempo estimado de implementación:** 2-4 horas  
**Riesgo si no se implementa:** Exposición de credenciales, acceso no autorizado

