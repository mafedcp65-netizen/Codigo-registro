@echo off
title Clasificador de registros de defuncion

echo ============================================
echo   Clasificador de registros de defuncion
echo ============================================
echo.

echo Verificando Docker...
docker --version >nul 2>&1

if errorlevel 1 (
    echo ERROR: Docker no esta instalado o no esta disponible.
    echo Abre Docker Desktop e intenta nuevamente.
    echo.
    pause
    exit /b
)

echo Docker detectado correctamente.
echo.

echo Verificando si la imagen ya esta cargada en Docker...
docker image inspect clasificador-registros:latest >nul 2>&1

if %errorlevel%==0 (
    echo La imagen ya esta cargada en Docker.
) else (
    echo La imagen no esta cargada en Docker.
    echo.

    if exist clasificador-registros.tar (
        echo Se encontro clasificador-registros.tar en esta carpeta.
        echo Cargando imagen Docker desde el archivo local...
        docker load -i clasificador-registros.tar
    ) else (
        echo No se encontro clasificador-registros.tar en esta carpeta.
        echo Descargando archivo desde GitHub Releases...
        echo.

        curl -L -o clasificador-registros.tar https://github.com/mafedcp65-netizen/Codigo-registro/releases/latest/download/clasificador-registros.tar

        if not exist clasificador-registros.tar (
            echo ERROR: No se pudo descargar clasificador-registros.tar.
            echo Revisa tu conexion a internet o descarga el archivo manualmente desde Releases.
            echo.
            pause
            exit /b
        )

        echo.
        echo Archivo descargado correctamente.
        echo Cargando imagen Docker...
        docker load -i clasificador-registros.tar
    )
)

echo.
echo Iniciando la aplicacion...
echo.
echo Cuando aparezca la aplicacion, abre esta direccion en el navegador:
echo http://localhost:8501
echo.

docker run -p 8501:8501 clasificador-registros:latest

echo.
echo Aplicacion cerrada.
pause
