BSD

nano ~/.bashrc

source .venv/bin/activate

rm -rf .venv           # limpiar entorno
uv cache prune         # (opcional) limpiar caché
uv sync                # recrear entorno según pyproject
uv run python ls_iMotorSoft_Srv01.py  # correr tu app

sftp://administrator@imotorsoft.com/home/administrator/project/iMotorSoft/ai/Vertice360/SrvRestAstroLS_v1/backend/

/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend

rsync -avz \
    /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/astro/dist/ \
    administrator@imotorsoft.com:/home/administrator/project/iMotorSoft/ai/Vertice360/SrvRestAstroLS_v1/astro/dist/
    
rsync -avz --exclude '__pycache__' --exclude '.git' --exclude '*.pyc' --exclude '_uploads' --exclude 'storage' --exclude 'clientA/' --exclude '.env' --exclude '.venv/' /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/ administrator@imotorsoft.com:/home/administrator/project/iMotorSoft/ai/Vertice360/SrvRestAstroLS_v1/backend/

Sos un experto en UI para este proyecto conversacional, tenemos que modificar la pagina index.astro de pages.
que cuente el proyecto, un boton para ir a ver la demo que esta en 
/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/astro/src/pages/demo/modal
dar detalles de todo lo que puede hacer con la demo, principalmente consultar en el chat todo lo que ve en el dashboard


