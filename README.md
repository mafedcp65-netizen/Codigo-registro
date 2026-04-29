# Clasificador de registros de defunción

Esta aplicación permite cargar una base de datos de registros de defunción y ejecutar una clasificación automática mediante una aplicación web.

La aplicación viene empaquetada en **Docker**, por lo que no es necesario instalar Python ni instalar librerías manualmente.

---

## Requisitos

Antes de usar la aplicación, se necesita tener instalado:

- Docker Desktop
- Un navegador web, como Google Chrome, Microsoft Edge o Firefox

---

## ¿Dónde está el archivo de la aplicación?

El archivo de la aplicación **no aparece directamente en la lista principal de archivos del repositorio**.

La aplicación se encuentra en la sección **Releases** de GitHub.

Para encontrarla:

1. Entrar a este repositorio en GitHub.
2. Mirar el lado derecho de la página.
3. Buscar la sección llamada **Releases**.
4. Hacer clic en la versión publicada, por ejemplo:

```text
v1.0
```

5. En la página de la versión, bajar hasta la sección **Assets**.
6. Descargar el archivo:

```text
clasificador-registros.tar
```

Este archivo contiene la aplicación completa.

**Importante:**  
No se debe abrir ni descomprimir manualmente el archivo `clasificador-registros.tar`.

---

## Paso 1: Descargar la aplicación

Desde la sección **Releases > Assets**, descargar el archivo:

```text
clasificador-registros.tar
```

Se recomienda guardarlo en una carpeta fácil de encontrar, por ejemplo:

```text
Descargas
```

---

## Paso 2: Abrir Docker Desktop

Antes de ejecutar la aplicación, abrir **Docker Desktop**.

Esperar unos segundos hasta que Docker esté funcionando correctamente.

---

## Paso 3: Abrir PowerShell en la carpeta del archivo

Buscar la carpeta donde se descargó el archivo:

```text
clasificador-registros.tar
```

Por ejemplo, puede estar en:

```text
Descargas
```

Luego realizar lo siguiente:

1. Entrar a la carpeta donde está el archivo.
2. Hacer clic en la barra de dirección de la carpeta.
3. Escribir:

```text
powershell
```

4. Presionar **Enter**.

Esto abrirá una ventana de PowerShell directamente en esa carpeta.

---

## Paso 4: Cargar la imagen Docker

En PowerShell, copiar y pegar el siguiente comando:

```powershell
docker load -i clasificador-registros.tar
```

Esperar a que el proceso termine. Puede tardar algunos minutos.

---

## Paso 5: Ejecutar la aplicación

Después de cargar la imagen, ejecutar el siguiente comando:

```powershell
docker run -p 8501:8501 clasificador-registros:latest
```

La ventana de PowerShell debe permanecer abierta mientras se usa la aplicación.

---

## Paso 6: Abrir la aplicación

Abrir un navegador web y entrar a la siguiente dirección:

```text
http://localhost:8501
```

Allí debería abrirse la aplicación.

---

## ¿Cómo cerrar la aplicación?

Para cerrar la aplicación:

1. Volver a la ventana de PowerShell donde se está ejecutando la aplicación.
2. Presionar las teclas:

```text
Ctrl + C
```

3. Si PowerShell pregunta si desea terminar el proceso, escribir:

```text
S
```

o:

```text
Y
```

según el idioma del sistema.

4. Presionar **Enter**.

Después de esto, la aplicación quedará cerrada.

---
