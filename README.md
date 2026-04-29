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

El archivo principal de la aplicación **no aparece directamente en la lista principal de archivos del repositorio**.

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

## Ejecución recomendada con `abrir_app.bat`

Para facilitar el uso, este repositorio incluye el archivo:

```text
abrir_app.bat
```

Este archivo permite cargar y ejecutar la aplicación sin escribir comandos manualmente en PowerShell.

Para que funcione correctamente, los siguientes archivos deben estar en la **misma carpeta**:

```text
clasificador-registros.tar
abrir_app.bat
```

La aplicación se puede ejecutar desde el **Escritorio** del computador, siempre que ambos archivos estén juntos en una misma carpeta. Por ejemplo:

```text
Escritorio/
└── Clasificador_Registros/
    ├── clasificador-registros.tar
    └── abrir_app.bat
```

Si `abrir_app.bat` está en una carpeta y `clasificador-registros.tar` está en otra, la aplicación no podrá cargarse correctamente.

---

## Pasos para ejecutar la aplicación

### Paso 1: Descargar los archivos necesarios

Descargar desde este repositorio:

```text
abrir_app.bat
```

Y desde **Releases > Assets**, descargar:

```text
clasificador-registros.tar
```

Se recomienda guardar ambos archivos en una carpeta fácil de encontrar, por ejemplo:

```text
Escritorio/Clasificador_Registros
```

---

### Paso 2: Abrir Docker Desktop

Antes de ejecutar la aplicación, abrir **Docker Desktop**.

Esperar unos segundos hasta que Docker esté funcionando correctamente.

---

### Paso 3: Ejecutar la aplicación

Entrar a la carpeta donde están juntos:

```text
clasificador-registros.tar
abrir_app.bat
```

Luego dar doble clic en:

```text
abrir_app.bat
```

Se abrirá una ventana negra de comandos.

Si es la primera vez que se ejecuta la aplicación, el archivo cargará automáticamente la imagen Docker desde `clasificador-registros.tar`. Después iniciará la aplicación.

La ventana debe permanecer abierta mientras se usa la aplicación.

---

### Paso 4: Abrir la aplicación en el navegador

Abrir un navegador web y entrar a la siguiente dirección:

```text
http://localhost:8501
```

Allí debería abrirse la aplicación.

---

## ¿Cómo cerrar la aplicación?

Para cerrar la aplicación:

1. Volver a la ventana negra donde se está ejecutando la aplicación.
2. Presionar las teclas:

```text
Ctrl + C
```

3. Si la terminal pregunta si desea terminar el proceso, escribir:

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

## Uso después de la primera vez

La primera vez, `abrir_app.bat` carga la imagen Docker desde:

```text
clasificador-registros.tar
```

Después de eso, la imagen queda guardada en Docker.

Por lo tanto, para usos posteriores solo se necesita:

1. Entrar a la carpeta donde está guardado el archivo:

```text
abrir_app.bat
```

2. Dar doble clic en:

```text
abrir_app.bat
```

3. Abrir en el navegador:

```text
http://localhost:8501
```

No es necesario volver a descargar ni cargar la imagen manualmente, a menos que se publique una nueva versión de la aplicación.

Tampoco es necesario abrir Docker Desktop manualmente después de la primera vez; al ejecutar `abrir_app.bat`, la aplicación debería iniciar normalmente si Docker ya quedó configurado en el computador.

## Ejecución manual en PowerShell

Si se prefiere ejecutar la aplicación manualmente, abrir PowerShell en la carpeta donde está `clasificador-registros.tar` y ejecutar:

```powershell
docker load -i clasificador-registros.tar
docker run -p 8501:8501 clasificador-registros:latest
```

Luego abrir en el navegador:

```text
http://localhost:8501
```

Para cerrar la aplicación, volver a PowerShell y presionar:

```text
Ctrl + C
```
