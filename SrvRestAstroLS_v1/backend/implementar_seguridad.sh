#!/bin/bash
# Script de implementación rápida de seguridad básica
# Ejecutar como root en el servidor

echo "=========================================="
echo "Implementación de Seguridad Básica"
echo "Fecha: 2026-02-12 18:36:51"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Paso 1: Crear backup de nginx.conf${NC}"
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup creado"
echo ""

echo -e "${YELLOW}Paso 2: Agregar rate limiting a nginx.conf${NC}"

# Verificar si ya existe
if grep -q "limit_req_zone" /etc/nginx/nginx.conf; then
    echo "ℹ️  Rate limiting ya configurado"
else
    # Agregar en el bloque http
    sed -i '/http {/a\    # Rate limiting zones\n    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;\n    limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=50r/s;\n    limit_conn_zone $binary_remote_addr zone=addr:10m;\n' /etc/nginx/nginx.conf
    echo "✅ Rate limiting agregado"
fi
echo ""

echo -e "${YELLOW}Paso 3: Crear configuración de seguridad${NC}"

cat > /etc/nginx/security.conf << 'EOF'
# Security configuration for Vertice360
# Generated: 2026-02-12

# Hide nginx version
server_tokens off;

# Block access to sensitive files
location ~ /\. {
    deny all;
    access_log off;
    log_not_found off;
    return 404;
}

location ~ /\.env {
    deny all;
    access_log off;
    log_not_found off;
    return 404;
}

location ~ /\.git {
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

# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
EOF

echo "✅ Configuración de seguridad creada en /etc/nginx/security.conf"
echo ""

echo -e "${YELLOW}Paso 4: Instrucciones para actualizar site config${NC}"
echo ""
echo "Editar: /etc/nginx/sites-available/demo.pozo360.imotorsoft.com"
echo ""
echo "Agregar dentro del bloque 'server {' antes de los location:"
echo ""
cat << 'EOF'
    # Include security settings
    include /etc/nginx/security.conf;
    
    # Rate limiting for API
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
    
    # Rate limiting for webhooks (higher limits)
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
EOF

echo ""
echo ""

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}Próximos pasos:${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "1. Editar el archivo de configuración del site:"
echo "   sudo nano /etc/nginx/sites-available/demo.pozo360.imotorsoft.com"
echo ""
echo "2. Agregar 'include /etc/nginx/security.conf;' al inicio del bloque server"
echo ""
echo "3. Agregar 'limit_req' y 'limit_conn' a los location de /api/ y /webhooks/"
echo ""
echo "4. Verificar configuración:"
echo "   sudo nginx -t"
echo ""
echo "5. Recargar nginx:"
echo "   sudo systemctl reload nginx"
echo ""
echo "6. Verificar que no hay errores:"
echo "   sudo tail -f /var/log/nginx/error.log"
echo ""

# Crear middleware de seguridad para Litestar
echo -e "${YELLOW}Paso 5: Crear middleware de seguridad para Litestar${NC}"

mkdir -p /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/middleware

cat > /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/middleware/__init__.py << 'EOF'
"""Middleware package for Vertice360."""
EOF

cat > /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/middleware/security.py << 'EOF'
"""Security middleware for Litestar application."""

from litestar.middleware.base import MiddlewareProtocol
from litestar.types import Scope, Receive, Send, ASGIApp
from litestar import Response
import logging

logger = logging.getLogger(__name__)


class BlockPathsMiddleware(MiddlewareProtocol):
    """Block access to sensitive paths."""
    
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.blocked_paths = [
            "/.env", "/.git", "/config.json", "/composer.json", 
            "/package.json", "/README.md", "/.htaccess", "/.htpasswd",
            "/wp-config.php", "/admin/.env", "/api/.env"
        ]
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        for blocked in self.blocked_paths:
            if path.startswith(blocked) or blocked in path:
                logger.warning(f"Blocked access to: {path}")
                response = Response(content={"error": "Not found"}, status_code=404)
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware(MiddlewareProtocol):
    """Add security headers to responses."""
    
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                security_headers = [
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-Frame-Options", b"SAMEORIGIN"),
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                ]
                headers.extend(security_headers)
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
EOF

echo "✅ Middleware creado en /middleware/security.py"
echo ""

echo -e "${YELLOW}Paso 6: Instrucciones para integrar en Litestar${NC}"
echo ""
cat << 'EOF'
# En tu archivo principal (ls_iMotorSoft_Srv01_demo.py):

from litestar import Litestar
from middleware.security import BlockPathsMiddleware, SecurityHeadersMiddleware

app = Litestar(
    # ... tu configuración actual ...
    middleware=[
        BlockPathsMiddleware,
        SecurityHeadersMiddleware,
    ],
    debug=False,  # Asegurar que debug esté en False en producción
)
EOF

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}Resumen de implementación:${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "Archivos creados:"
echo "  ✅ /etc/nginx/security.conf"
echo "  ✅ /etc/nginx/nginx.conf (modificado con rate limiting)"
echo "  ✅ /middleware/security.py"
echo ""
echo "Pendiente (requiere edición manual):"
echo "  ⚠️  /etc/nginx/sites-available/demo.pozo360.imotorsoft.com"
echo "  ⚠️  ls_iMotorSoft_Srv01_demo.py (agregar middleware)"
echo ""
