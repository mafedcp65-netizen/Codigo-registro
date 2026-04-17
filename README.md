# Clasificador SVM jerárquico de registros de defunción

Esta aplicación permite cargar una base de datos, procesarla y ejecutar un modelo de clasificación de registros de defunción.

## Archivos necesarios

La carpeta debe contener estos archivos:

- `app.py`
- `requirements.txt`
- `modelos_svm_dos_etapas.zip`

## Requisitos

Antes de usar la app, se necesita:

- Windows
- Python instalado
- Conexión a internet la primera vez para instalar dependencias
- Navegador web

## Instalación

1. Descomprime la carpeta del proyecto.
2. Abre la carpeta.
3. Haz clic derecho e ingrersa a powershell o terminal.
4. Ejecuta estos comandos uno por uno:

```powershell/ terminal
python -m pip install -r requirements.txt
python -m pip install msoffcrypto-tool
python -m streamlit run app.py
