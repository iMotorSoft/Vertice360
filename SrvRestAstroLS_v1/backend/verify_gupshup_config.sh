#!/bin/bash
# Script de verificación de configuración Gupshup para producción
# Uso: ./verify_gupshup_config.sh

echo "=========================================="
echo "Verificación de Configuración Gupshup"
echo "=========================================="
echo ""

# Verificar VERTICE360_ENV
if [ -z "$VERTICE360_ENV" ]; then
    echo "❌ ERROR: VERTICE360_ENV no está seteada"
    echo "   Está usando: dev (default)"
    echo "   Debería ser: prod"
    echo ""
    echo "Fix: export VERTICE360_ENV=prod"
    echo ""
else
    echo "✅ VERTICE360_ENV = $VERTICE360_ENV"
fi

# Verificar variables Gupshup PRO
echo "Verificando variables Gupshup PRO:"
echo ""

if [ -z "$GUPSHUP_API_KEY_PRO" ]; then
    echo "❌ GUPSHUP_API_KEY_PRO no está seteada"
else
    echo "✅ GUPSHUP_API_KEY_PRO está configurada"
fi

if [ -z "$GUPSHUP_APP_NAME_PRO" ]; then
    echo "⚠️  GUPSHUP_APP_NAME_PRO no está seteada (usando default: vertice360pro)"
else
    echo "✅ GUPSHUP_APP_NAME_PRO = $GUPSHUP_APP_NAME_PRO"
fi

if [ -z "$GUPSHUP_SRC_NUMBER_PRO" ]; then
    echo "⚠️  GUPSHUP_SRC_NUMBER_PRO no está seteada (usando default: 4526325250)"
else
    echo "✅ GUPSHUP_SRC_NUMBER_PRO = $GUPSHUP_SRC_NUMBER_PRO"
fi

echo ""
echo "=========================================="
echo "Configuración Recomendada para Producción:"
echo "=========================================="
echo ""
cat << 'EOF'
# Agregar a ~/.bashrc, ~/.profile, /etc/environment, o archivo .env:

export VERTICE360_ENV=prod
export GUPSHUP_API_KEY_PRO="tu-api-key-real-de-gupshup"
export GUPSHUP_APP_NAME_PRO="vertice360prod"
export GUPSHUP_SRC_NUMBER_PRO="4526325250"
export VERTICE360_PUBLIC_BASE_URL_PRO="https://demo.pozo360.imotorsoft.com"

# Variables opcionales de staging (fallback a dev si no están seteadas):
# export GUPSHUP_API_KEY_STG="..."
# export GUPSHUP_APP_NAME_STG="..."
# export GUPSHUP_SRC_NUMBER_STG="..."

EOF

echo ""
echo "=========================================="
echo "Comandos para aplicar cambios:"
echo "=========================================="
echo ""
echo "1. Setear variable temporal (solo esta sesión):"
echo "   export VERTICE360_ENV=prod"
echo ""
echo "2. Verificar configuración actual:"
echo "   python3 -c \"import globalVar; print(f'ENV={globalVar.ENVIRONMENT}'); print(f'APP={globalVar.GUPSHUP_APP_NAME}'); print(f'ENABLED={globalVar.gupshup_whatsapp_enabled()}')\""
echo ""
echo "3. Reiniciar el servidor después de setear variables:"
echo "   # Detener el proceso actual (Ctrl+C o kill)"
echo "   # Volver a iniciar: python ls_iMotorSoft_Srv01_demo.py"
echo ""
