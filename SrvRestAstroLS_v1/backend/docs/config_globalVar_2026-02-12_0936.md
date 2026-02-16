# Configuración de globalVar.py

**Fecha y hora:** 2026-02-12 09:36:36  
**Archivo:** `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/globalVar.py`

---

## Resumen de Configuración

| Variable | Valor (Dev) | Valor (Prod) | Valor (Stg) |
|----------|-------------|--------------|-------------|
| `ENVIRONMENT` | dev | prod | stg |
| `GUPSHUP_APP_NAME` | `$GUPSHUP_APP_NAME_DEV` | `vertice360pro` | `$GUPSHUP_APP_NAME_STG` |
| `GUPSHUP_API_KEY` | `$GUPSHUP_API_KEY_DEV` | `$GUPSHUP_API_KEY_PRO` | `$GUPSHUP_API_KEY_STG` |
| `GUPSHUP_SRC_NUMBER` | `$GUPSHUP_SRC_NUMBER_DEV` | `4526325250` | `$GUPSHUP_SRC_NUMBER_STG` |
| `GUPSHUP_BASE_URL` | `https://api.gupshup.io` | `$GUPSHUP_BASE_URL_PRO` | `$GUPSHUP_BASE_URL_STG` |
| `VERTICE360_PUBLIC_BASE_URL` | `$VERTICE360_PUBLIC_BASE_URL_DEV` | `$VERTICE360_PUBLIC_BASE_URL_PRO` | `$VERTICE360_PUBLIC_BASE_URL_STG` |

---

## Variables de Entorno Gupshup

### Desarrollo (DEV)
```bash
GUPSHUP_APP_NAME_DEV="${GUPSHUP_APP_NAME_DEV:-}"
GUPSHUP_API_KEY_DEV="${GUPSHUP_API_KEY_DEV:-}"
GUPSHUP_SRC_NUMBER_DEV="${GUPSHUP_SRC_NUMBER_DEV:-}"
GUPSHUP_BASE_URL_DEV="${GUPSHUP_BASE_URL_DEV:-https://api.gupshup.io}"
```

### Staging (STG)
```bash
GUPSHUP_APP_NAME_STG="${GUPSHUP_APP_NAME_STG:-$GUPSHUP_APP_NAME_DEV}"
GUPSHUP_API_KEY_STG="${GUPSHUP_API_KEY_STG:-$GUPSHUP_API_KEY_DEV}"
GUPSHUP_SRC_NUMBER_STG="${GUPSHUP_SRC_NUMBER_STG:-$GUPSHUP_SRC_NUMBER_DEV}"
GUPSHUP_BASE_URL_STG="${GUPSHUP_BASE_URL_STG:-$GUPSHUP_BASE_URL_DEV}"
```

### Producción (PRO)
```bash
GUPSHUP_APP_NAME_PRO="${GUPSHUP_APP_NAME_PRO:-vertice360pro}"
GUPSHUP_API_KEY_PRO="${GUPSHUP_API_KEY_PRO:-}"
GUPSHUP_SRC_NUMBER_PRO="${GUPSHUP_SRC_NUMBER_PRO:-4526325250}"
GUPSHUP_BASE_URL_PRO="${GUPSHUP_BASE_URL_PRO:-$GUPSHUP_BASE_URL_DEV}"
```

---

## Uso

### Selección Automática por Entorno

El sistema selecciona automáticamente la configuración basándose en la variable `VERTICE360_ENV`:

```bash
# Desarrollo (default)
python ls_iMotorSoft_Srv01_demo.py

# Staging
VERTICE360_ENV=stg python ls_iMotorSoft_Srv01_demo.py

# Producción
VERTICE360_ENV=prod python ls_iMotorSoft_Srv01_demo.py
```

### Verificar Configuración Actual

```bash
python -c "
import globalVar
print(f'ENV={globalVar.ENVIRONMENT}')
print(f'APP_NAME={globalVar.GUPSHUP_APP_NAME}')
print(f'SRC_NUMBER={globalVar.GUPSHUP_SRC_NUMBER}')
print(f'ENABLED={globalVar.gupshup_whatsapp_enabled()}')
"
```

### Self-Test

```bash
python globalVar.py
```

---

## Otras Configuraciones Importantes

| Variable | Valor por Defecto | Descripción |
|----------|-------------------|-------------|
| `APP_NAME` | Vertice360 | Nombre de la aplicación |
| `APP_VERSION` | 0.1.0 | Versión de la aplicación |
| `HOST` | 0.0.0.0 | Host del servidor |
| `PORT` | 7062 | Puerto del servidor |
| `DEBUG` | True (dev), False (prod) | Modo debug |
| `LOG_LEVEL` | DEBUG (dev), INFO (prod) | Nivel de logging |
| `VERTICE360_PUBLIC_BASE_URL_DEV` | https://attribute-lighter-vip-joined.trycloudflare.com | URL pública dev |
| `VERTICE360_PUBLIC_BASE_URL_PRO` | https://demo.pozo360.imotorsoft.com | URL pública prod |
| `DB_URL` | postgresql+psycopg://user:pass@localhost:5432/vertice360 | Base de datos |
| `VERTICE360_AI_WORKFLOW_REPLY` | True | Habilitar respuestas AI |
| `WORKFLOW_TICKET_SESSION_TTL_SECONDS` | 1800 | TTL de sesión de ticket |

---

## Estructura de Selección

```python
def _pick_env(dev, stg, prod):
    """Select value based on current ENVIRONMENT."""
    return {"dev": dev, "stg": stg, "prod": prod}[ENVIRONMENT]

# Selección automática
GUPSHUP_APP_NAME = _pick_env(GUPSHUP_APP_NAME_DEV, GUPSHUP_APP_NAME_STG, GUPSHUP_APP_NAME_PRO)
GUPSHUP_API_KEY = _pick_env(GUPSHUP_API_KEY_DEV, GUPSHUP_API_KEY_STG, GUPSHUP_API_KEY_PRO)
GUPSHUP_SRC_NUMBER = _pick_env(GUPSHUP_SRC_NUMBER_DEV, GUPSHUP_SRC_NUMBER_STG, GUPSHUP_SRC_NUMBER_PRO)
GUPSHUP_BASE_URL = _pick_env(GUPSHUP_BASE_URL_DEV, GUPSHUP_BASE_URL_STG, GUPSHUP_BASE_URL_PRO)
```

---

## Configuración de URL Pública

### IMPORTANTE: Production URL Setting

La variable `VERTICE360_PUBLIC_BASE_URL` **debe** apuntar a la URL de producción en el servidor de producción:

```python
# En globalVar.py línea 57:
VERTICE360_PUBLIC_BASE_URL: str = VERTICE360_PUBLIC_BASE_URL_PRO
```

**⚠️ CRÍTICO para Producción:**
```bash
# Asegurar que esté seteada la variable de entorno:
export VERTICE360_PUBLIC_BASE_URL_PRO="https://demo.pozo360.imotorsoft.com"

# Verificar que el código use PRO:
grep "VERTICE360_PUBLIC_BASE_URL: str = VERTICE360_PUBLIC_BASE_URL_PRO" globalVar.py
```

### Configuración por Ambiente

**Desarrollo:**
```python
VERTICE360_PUBLIC_BASE_URL_DEV = "https://attribute-lighter-vip-joined.trycloudflare.com"
VERTICE360_PUBLIC_BASE_URL = VERTICE360_PUBLIC_BASE_URL_DEV  # Cuando ENV=dev
```

**Producción:**
```python
VERTICE360_PUBLIC_BASE_URL_PRO = "https://demo.pozo360.imotorsoft.com"
VERTICE360_PUBLIC_BASE_URL = VERTICE360_PUBLIC_BASE_URL_PRO  # Cuando ENV=prod
```

---

## Checklist de Deploy a Producción

Antes de iniciar el servidor en producción, verificar:

### 1. Variables de Entorno Requeridas
```bash
# OBLIGATORIAS:
export VERTICE360_ENV=prod
export GUPSHUP_API_KEY_PRO="tu-api-key-real-de-gupshup"
export VERTICE360_PUBLIC_BASE_URL_PRO="https://demo.pozo360.imotorsoft.com"

# Opcionales (tienen defaults):
export GUPSHUP_APP_NAME_PRO="vertice360prod"
export GUPSHUP_SRC_NUMBER_PRO="4526325250"
```

### 2. Verificación Rápida
```bash
python3 -c "
import globalVar
assert globalVar.ENVIRONMENT == 'prod', 'ENV debe ser prod'
assert 'pozo360' in globalVar.VERTICE360_PUBLIC_BASE_URL, 'URL debe ser producción'
assert globalVar.GUPSHUP_API_KEY, 'API key debe estar configurada'
assert globalVar.GUPSHUP_APP_NAME == 'vertice360prod', 'App name debe ser prod'
print('✅ Configuración de producción OK')
"
```

### 3. Comandos de Verificación
```bash
# Ver configuración actual
python globalVar.py

# Debe mostrar:
# ENV=prod gupshup_app=vertice360prod gupshup_src=4526325250 gupshup_enabled=True
```

### 4. Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `HTTP 401` en Gupshup | `VERTICE360_ENV` no seteado | `export VERTICE360_ENV=prod` |
| `ENV=dev` en prod | Variable no exportada | Verificar `echo $VERTICE360_ENV` |
| URL incorrecta en webhook | `VERTICE360_PUBLIC_BASE_URL_PRO` apunta a dev | Setear URL correcta |
| API key vacío | `GUPSHUP_API_KEY_PRO` no seteado | Exportar API key |

---

## Notas

- **Fecha de generación:** 2026-02-12 09:36:36
- **Última actualización:** 2026-02-12 (agregado checklist producción)
- **Validación:** Si `VERTICE360_ENV` no es válido, se defaultea a `dev` con warning
- **Secrets:** Los API keys nunca se loguean en `boot_log()`
- **Fallback Staging:** Si no se definen variables `*_STG`, usan los valores `*_DEV`
- **CRÍTICO:** En producción, `VERTICE360_PUBLIC_BASE_URL` siempre debe ser `VERTICE360_PUBLIC_BASE_URL_PRO`

---

*Documento generado automáticamente desde globalVar.py*
