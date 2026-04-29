@echo off
echo ============================================
echo Clasificador de registros de defuncion
echo ============================================
echo.

echo Verificando si la imagen Docker ya esta cargada...
docker image inspect clasificador-registros:latest >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo La imagen no esta cargada. Cargando desde clasificador-registros.tar...
    docker load -i clasificador-registros.tar
) else (
    echo La imagen ya esta cargada.
)

echo.
echo Iniciando la aplicacion...
echo Cuando la aplicacion este lista, abra:
echo http://localhost:8501
echo.
echo Para cerrar la aplicacion, presione Ctrl + C en esta ventana.
echo.

docker run --rm -p 8501:8501 clasificador-registros:latest

pause
