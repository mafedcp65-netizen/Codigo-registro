# -*- coding: utf-8 -*-
"""
Versión .py generada desde SVM_FINAL_registro.ipynb para ejecución en Visual Studio / VS Code.
Se conserva la lógica del modelo y del entrenamiento.
"""



#pip install openpyxl ftfy joblib scikit-learn pandas numpy


# ## 1. Carga única de archivos
# Sube en este único paso la base de datos (`.xlsx`, `.xls`, `.csv` o `.tsv`). Si la base no tiene etiquetas y vas a correr en inferencia, también puedes subir aquí el `.zip` con los modelos entrenados.


from pathlib import Path

# =============================================================================
# CARGA DE ARCHIVOS PARA VS / VS CODE
# =============================================================================
# Opción 1:
#   Deja USAR_SELECTOR = True para escoger los archivos con ventana emergente.
#
# Opción 2:
#   Pon USAR_SELECTOR = False y escribe las rutas manualmente en ARCHIVO
#   y ARCHIVO_MODELOS_ZIP.
#
# NOTA:
# - ARCHIVO es obligatorio.
# - ARCHIVO_MODELOS_ZIP solo es necesario si vas a correr en inferencia
#   con modelos ya entrenados.
# - Esto solo cambia la forma de cargar archivos. El código del modelo no se toca.

USAR_SELECTOR = True

ARCHIVO = r""
ARCHIVO_MODELOS_ZIP = r""

def _seleccionar_archivo(titulo: str, tipos):
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise RuntimeError(
            "No se pudo abrir el selector de archivos. "
            "Desactiva USAR_SELECTOR y escribe las rutas manualmente."
        ) from e

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    ruta = filedialog.askopenfilename(
        title=titulo,
        filetypes=tipos,
    )

    root.destroy()
    return ruta

if USAR_SELECTOR:
    ruta_base = _seleccionar_archivo(
        "Selecciona la base de datos",
        [
            ("Archivos de datos", "*.xlsx *.xls *.csv *.tsv"),
            ("Excel", "*.xlsx *.xls"),
            ("CSV", "*.csv"),
            ("TSV", "*.tsv"),
            ("Todos los archivos", "*.*"),
        ],
    )

    if not ruta_base:
        raise ValueError("No seleccionaste la base de datos.")

    ARCHIVO = ruta_base

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        cargar_zip = messagebox.askyesno(
            "Modelo ZIP",
            "¿Quieres seleccionar también el ZIP de modelos ya entrenados?\n\n"
            "Elige 'Sí' si vas a correr inferencia con una base sin etiquetas.\n"
            "Elige 'No' si vas a entrenar desde la base.",
        )
        root.destroy()
    except Exception:
        cargar_zip = False

    if cargar_zip:
        ruta_zip = _seleccionar_archivo(
            "Selecciona el ZIP de modelos",
            [
                ("ZIP", "*.zip"),
                ("Todos los archivos", "*.*"),
            ],
        )
        ARCHIVO_MODELOS_ZIP = ruta_zip if ruta_zip else None
    else:
        ARCHIVO_MODELOS_ZIP = None

if not ARCHIVO:
    raise ValueError(
        "Debes seleccionar o escribir la ruta de la base de datos "
        "(.xlsx, .xls, .csv o .tsv)."
    )

ARCHIVO = str(Path(ARCHIVO).expanduser())
ARCHIVO_MODELOS_ZIP = str(Path(ARCHIVO_MODELOS_ZIP).expanduser()) if ARCHIVO_MODELOS_ZIP else None

if not Path(ARCHIVO).exists():
    raise FileNotFoundError(f"No se encontró la base de datos: {ARCHIVO}")

if ARCHIVO_MODELOS_ZIP and not Path(ARCHIVO_MODELOS_ZIP).exists():
    raise FileNotFoundError(f"No se encontró el ZIP de modelos: {ARCHIVO_MODELOS_ZIP}")

print("Base seleccionada:")
print(ARCHIVO)

if ARCHIVO_MODELOS_ZIP:
    print("ZIP de modelos seleccionado:")
    print(ARCHIVO_MODELOS_ZIP)
else:
    print("No se seleccionó ZIP de modelos.")


# ## 2. Imports y configuración general


import os
import re
import json
import shutil
import tempfile
import unicodedata
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    import ftfy
except Exception:
    ftfy = None

from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

HOJA = "Base_estandarizada"
RANDOM_STATE = 42
TEST_SIZE = 0.20

COLUMNA_ETIQUETA = "Mención de cáncer"
COLUMNAS_TEXTO = [
    "Diagnóstico A",
    "Diagnóstico B",
    "Diagnóstico C",
    "Diagnóstico D",
    "Otros Estados Patológicos",
    "Otros Estados Patológicos 2",
]

COLUMNAS_IDENTIFICADORAS = [
    "Certificado de defunción",
    "Número de identificación",
]

PERCENTIL_BAJA_CONFIANZA_ETAPA2 = 0.20
UMBRAL_REASIGNACION_ETAPA1 = -0.10

ARCHIVO_SALIDA_CLASES = "predicciones_clase.xlsx"
ARCHIVO_SALIDA_SCORES = "predicciones_scores.xlsx"

# 'auto' = solo entrena si la base es realmente entrenable en ambas etapas; de lo contrario usa inferencia
# 'train' = obliga entrenamiento y evaluación
# 'inferencia' = obliga carga de carpeta de modelos
MODO_EJECUCION = "auto"

RUTA_CARPETA_MODELOS = "modelos_svm_dos_etapas"

ARCHIVO_MODELOS_ZIP = globals().get("ARCHIVO_MODELOS_ZIP", None)


# ## 3. Funciones de carga, limpieza, normalización y estandarización de columnas


def load_input_file(input_path: Path) -> pd.DataFrame:
    suffix = input_path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        try:
            return pd.read_excel(input_path, sheet_name=HOJA)
        except Exception:
            xls = pd.ExcelFile(input_path)
            hojas = xls.sheet_names
            if not hojas:
                raise ValueError("El archivo Excel no contiene hojas legibles.")
            for hoja in hojas:
                df_tmp = pd.read_excel(input_path, sheet_name=hoja)
                if len(df_tmp.columns) > 0:
                    return df_tmp
            return pd.read_excel(input_path, sheet_name=hojas[0])

    if suffix == ".csv":
        try:
            return pd.read_csv(input_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(input_path, encoding="latin-1")

    if suffix == ".tsv":
        try:
            return pd.read_csv(input_path, sep="\t", encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(input_path, sep="\t", encoding="latin-1")

    raise ValueError(f"Formato no soportado: {suffix}. Usa .xlsx, .xls, .csv o .tsv")

def normalize_text(value: str) -> str:
    text = str(value).strip().lower().replace("_", " ")
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())

COLUMN_ALIASES = {
    "certificado_defuncion": [
        "certificado_defuncion", "certificado defuncion", "certificado de defuncion",
        "numero certificado", "numero de certificado", "certificado",
        "cert defuncion", "cert defunción", "nro certificado defuncion"
    ],
    "numero_identificacion": [
        "numero_identificacion", "numero identificacion", "número identificación",
        "numero de identificacion", "número de identificación",
        "numero documento", "número documento", "numero de documento",
        "numero documento fallecido", "documento", "doc identidad",
        "identificacion", "identificación", "no identificacion", "no identificación",
        "cc", "cedula", "cédula"
    ],
    "diagnostico_a": ["diagnostico a", "diagnóstico a", "diagnótico a", "dx a"],
    "diagnostico_b": ["diagnostico b", "diagnóstico b", "dx b"],
    "diagnostico_c": ["diagnostico c", "diagnóstico c", "dx c"],
    "diagnostico_d": ["diagnostico d", "diagnóstico d", "dx d"],
    "otros_estados_patologicos": [
        "otros estados patologicos", "otros estados patológicos", "otros estados patologicos 1"
    ],
    "otros_estados_patologicos_2": [
        "otros estados patologicos 2", "otros estados patológicos 2"
    ],
    "etiqueta": [
        "etiqueta", "label", "clase", "target", "y", "mencion de cancer", "mención de cáncer",
        "mencion de cancer 0= sin mencion de cancer 1= mencion explicita de cancer 2= sospechoso de cancer (ej. tumor de comportamiento incierto; masa en [abdomen u otra localizacion])"
    ],
}

PRETTY_NAMES = {
    "certificado_defuncion": "Certificado de defunción",
    "numero_identificacion": "Número de identificación",
    "diagnostico_a": "Diagnóstico A",
    "diagnostico_b": "Diagnóstico B",
    "diagnostico_c": "Diagnóstico C",
    "diagnostico_d": "Diagnóstico D",
    "otros_estados_patologicos": "Otros Estados Patológicos",
    "otros_estados_patologicos_2": "Otros Estados Patológicos 2",
    "etiqueta": "Mención de cáncer",
}

FINAL_COLUMN_ORDER = [
    "certificado_defuncion",
    "numero_identificacion",
    "diagnostico_a",
    "diagnostico_b",
    "diagnostico_c",
    "diagnostico_d",
    "otros_estados_patologicos",
    "otros_estados_patologicos_2",
    "etiqueta",
]

def find_columns(df: pd.DataFrame) -> dict:
    normalized_to_original = {normalize_text(col): col for col in df.columns}
    found = {}

    for canonical_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = normalized_to_original.get(normalize_text(alias))
            if original:
                found[canonical_name] = original
                break
    return found

manual_mojibake = {
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ",
    "Ã": "Á", "Ã‰": "É", "Ã": "Í", "Ã“": "Ó", "Ãš": "Ú", "Ã‘": "Ñ",
    "Â": "", "": ""
}

reemplazos_directos = {
    "sindrome de lynch": "síndrome de lynch",
    "sindrome proliferativo": "síndrome proliferativo",
    "sindrome mielodisplasico": "síndrome mielodisplásico",
    "sindrome mielodisplásico": "síndrome mielodisplásico",
    "linfohistiocitosis hemofagocitica": "linfohistiocitosis hemofagocítica",
    "linfohistiocitosis hemofagocítica": "linfohistiocitosis hemofagocítica",
    "metastasis": "metástasis",
    "metastasico": "metastásico",
    "metastasica": "metastásica",
    "metastasicos": "metastásicos",
    "metastasicas": "metastásicas",
    "cancer": "cáncer"
}

patrones_regex = [
    (r"(?i)\bca\b\.?", "cáncer"),
    (r"(?i)\bmetastasis\b", "metástasis"),
    (r"(?i)\bmetastasico\b", "metastásico"),
    (r"(?i)\bmetastasica\b", "metastásica"),
    (r"(?i)\bmetastasicos\b", "metastásicos"),
    (r"(?i)\bmetastasicas\b", "metastásicas"),
    (r"(?i)\bsindrome\b", "síndrome"),
    (r"(?i)\bmielodisplasico\b", "mielodisplásico"),
    (r"(?i)\bmielodisplasia\b", "mielodisplasia"),
]

def reparar_codificacion(texto: str) -> str:
    if pd.isna(texto):
        return texto

    texto = str(texto)

    if ftfy is not None:
        texto = ftfy.fix_text(texto)

    for malo, bueno in manual_mojibake.items():
        texto = texto.replace(malo, bueno)

    return texto

def limpiar_texto_clinico(texto):
    if pd.isna(texto):
        return texto

    texto = reparar_codificacion(texto)
    texto = str(texto).strip()
    texto = re.sub(r"\s+", " ", texto)

    for patron, reemplazo in patrones_regex:
        texto = re.sub(patron, reemplazo, texto)

    texto_lower = texto.lower().strip()
    if texto_lower in reemplazos_directos:
        texto = reemplazos_directos[texto_lower]

    texto = re.sub(r"\s*[,;:]+\s*", ", ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" ,;:")

    if texto:
        texto = texto[0].upper() + texto[1:]

    return texto

def estandarizar_base(df_entrada: pd.DataFrame) -> pd.DataFrame:
    df = df_entrada.copy()
    found_columns = find_columns(df)

    required = [
        "certificado_defuncion",
        "numero_identificacion",
        "diagnostico_a",
        "diagnostico_b",
        "diagnostico_c",
        "diagnostico_d",
        "otros_estados_patologicos",
        "otros_estados_patologicos_2",
    ]
    # If 'etiqueta' is expected, add it to required list
    if "etiqueta" in found_columns:
        required.append("etiqueta")

    missing_required = [col for col in required if col not in found_columns]
    if missing_required:
        raise ValueError(
            "Faltan columnas requeridas después de normalizar nombres: "
            f"{missing_required}"
        )

    rename_map = {found_columns[k]: PRETTY_NAMES[k] for k in found_columns}
    df = df.rename(columns=rename_map)

    # Filter FINAL_COLUMN_ORDER to include only columns actually found and renamed
    ordered_pretty = [PRETTY_NAMES[k] for k in FINAL_COLUMN_ORDER if k in found_columns]
    df = df[ordered_pretty].copy()

    clinical_columns = [
        "Diagnóstico A",
        "Diagnóstico B",
        "Diagnóstico C",
        "Diagnóstico D",
        "Otros Estados Patológicos",
        "Otros Estados Patológicos 2",
    ]

    for col in clinical_columns:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_texto_clinico)

    for col in COLUMNAS_IDENTIFICADORAS:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""}).fillna("").str.strip()

    return df


# ## 4. Cargar y dejar lista la base


input_path = Path(ARCHIVO)

df_original = load_input_file(input_path)
print("Dimensión original:", df_original.shape)
print("Columnas originales:")
print(list(df_original.columns))

df_base = estandarizar_base(df_original)

print("\nDimensión estandarizada:", df_base.shape)
print("Columnas estandarizadas:")
print(list(df_base.columns))

print(df_base.head())


# ## 5. Funciones auxiliares del SVM


def limpiar_campo(x):
    if pd.isna(x):
        return ""
    x = str(x).strip()
    if x in {"", "0", "0.0", "nan", "None"}:
        return ""
    return x.lower()

def construir_texto_fila(row):
    partes = []
    for col in COLUMNAS_TEXTO:
        valor = limpiar_campo(row[col])
        if valor:
            partes.append(valor)
    return " [SEP] ".join(partes)

def metricas_binarias(y_true, y_pred, pos_label=1):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
    }

def metricas_multiclase(y_true, y_pred, labels=None):
    metricas = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }

    if labels is not None:
        reporte_dict = classification_report(
            y_true, y_pred, labels=labels, output_dict=True, zero_division=0
        )
        for label in labels:
            clave = str(label)
            if clave in reporte_dict:
                metricas[f"precision_clase_{label}"] = float(reporte_dict[clave]["precision"])
                metricas[f"recall_clase_{label}"] = float(reporte_dict[clave]["recall"])
                metricas[f"f1_clase_{label}"] = float(reporte_dict[clave]["f1-score"])
    return metricas

def descripcion_score_etapa2(clases_modelo):
    if len(clases_modelo) != 2:
        return "Score no disponible"
    return (
        f"Score > 0 favorece clase {clases_modelo[1]}; "
        f"score < 0 favorece clase {clases_modelo[0]}"
    )

def detectar_etiquetas_validas(df):
    if COLUMNA_ETIQUETA not in df.columns:
        return False, None, None
    serie = pd.to_numeric(df[COLUMNA_ETIQUETA], errors="coerce")
    mask_validas = serie.isin([0, 1, 2])
    return bool(mask_validas.any()), serie, mask_validas

def evaluar_entrenabilidad(serie_etiquetas, mask_etiquetas_validas):
    if serie_etiquetas is None or mask_etiquetas_validas is None:
        return False, "La columna de etiqueta no existe o no contiene valores válidos 0, 1 o 2."

    y_valid = serie_etiquetas.loc[mask_etiquetas_validas].astype(int)
    n_validos = int(len(y_valid))

    if n_validos == 0:
        return False, "No hay filas con etiquetas válidas 0, 1 o 2."

    conteo_total = y_valid.value_counts().sort_index()

    if len(conteo_total) < 2:
        return False, (
            "La base no es entrenable: se necesitan al menos 2 clases distintas "
            f"en la etiqueta. Conteos actuales: {conteo_total.to_dict()}"
        )

    if (conteo_total < 2).any():
        return False, (
            "La base no es entrenable: cada clase presente necesita al menos 2 registros "
            f"para la partición estratificada. Conteos actuales: {conteo_total.to_dict()}"
        )

    y_etapa2 = y_valid[y_valid != 0]
    conteo_etapa2 = y_etapa2.value_counts().sort_index()

    if not {1, 2}.issubset(set(conteo_etapa2.index.tolist())):
        return False, (
            "La base no es entrenable para la etapa 2: se necesitan ejemplos de ambas "
            f"clases 1 y 2. Conteos actuales etapa 2: {conteo_etapa2.to_dict()}"
        )

    if (conteo_etapa2.reindex([1, 2], fill_value=0) < 2).any():
        return False, (
            "La base no es entrenable para la etapa 2: las clases 1 y 2 necesitan al menos "
            f"2 registros cada una. Conteos actuales etapa 2: {conteo_etapa2.to_dict()}"
        )

    return True, "La base tiene etiquetas suficientes para entrenar ambas etapas."

def guardar_modelos_en_carpeta(carpeta, modelo_etapa1, modelo_etapa2, metadata):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)

    joblib.dump(modelo_etapa1, carpeta / "modelo_etapa1.joblib")
    joblib.dump(modelo_etapa2, carpeta / "modelo_etapa2.joblib")

    with open(carpeta / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Modelos guardados en la carpeta: {carpeta.resolve()}")

def descomprimir_zip_modelos(ruta_zip, carpeta_destino):
    ruta_zip = Path(ruta_zip)
    carpeta_destino = Path(carpeta_destino)

    if not ruta_zip.exists():
        raise FileNotFoundError(f"No se encontró el ZIP de modelos: {ruta_zip}")

    if carpeta_destino.exists():
        shutil.rmtree(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.unpack_archive(str(ruta_zip), str(tmpdir))

        candidatos = [tmpdir] + [p for p in tmpdir.rglob("*") if p.is_dir()]
        carpeta_origen = None

        for candidato in candidatos:
            if (
                (candidato / "modelo_etapa1.joblib").exists()
                and (candidato / "modelo_etapa2.joblib").exists()
            ):
                carpeta_origen = candidato
                break

        if carpeta_origen is None:
            raise FileNotFoundError(
                "El ZIP no contiene los archivos esperados: "
                "'modelo_etapa1.joblib' y 'modelo_etapa2.joblib'."
            )

        for item in carpeta_origen.iterdir():
            destino = carpeta_destino / item.name
            if item.is_dir():
                shutil.copytree(item, destino, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destino)

    print(f"ZIP de modelos descomprimido en: {carpeta_destino.resolve()}")

def preparar_y_cargar_modelos(ruta_carpeta, ruta_zip=None):
    carpeta = Path(ruta_carpeta)

    if ruta_zip is not None:
        descomprimir_zip_modelos(ruta_zip, carpeta)

    if not carpeta.exists() or not carpeta.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta de modelos: {carpeta}. "
            "Si la base no tiene etiquetas, sube también el ZIP de modelos en la carga inicial."
        )

    ruta_etapa1 = carpeta / "modelo_etapa1.joblib"
    ruta_etapa2 = carpeta / "modelo_etapa2.joblib"
    ruta_metadata = carpeta / "metadata.json"

    if not ruta_etapa1.exists():
        raise FileNotFoundError(f"No se encontró: {ruta_etapa1}")
    if not ruta_etapa2.exists():
        raise FileNotFoundError(f"No se encontró: {ruta_etapa2}")

    modelo_etapa1 = joblib.load(ruta_etapa1)
    modelo_etapa2 = joblib.load(ruta_etapa2)

    metadata = {}
    if ruta_metadata.exists():
        with open(ruta_metadata, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    return modelo_etapa1, modelo_etapa2, metadata

def pedir_zip_modelos_si_falta():
    global ARCHIVO_MODELOS_ZIP

    carpeta = Path(RUTA_CARPETA_MODELOS)
    carpeta_lista = (
        carpeta.exists()
        and (carpeta / "modelo_etapa1.joblib").exists()
        and (carpeta / "modelo_etapa2.joblib").exists()
    )

    if ARCHIVO_MODELOS_ZIP is None and not carpeta_lista:
        raise ValueError(
            "La base no tiene etiquetas y no se encontró una carpeta local de modelos. "
            "Debes subir el ZIP de modelos en la carga inicial."
        )


# ## 6. Preparación final de datos para el modelo


faltantes_texto = [c for c in COLUMNAS_TEXTO if c not in df_base.columns]
if faltantes_texto:
    raise ValueError(f"Faltan columnas requeridas para texto: {faltantes_texto}")

faltantes_identificadores = [c for c in COLUMNAS_IDENTIFICADORAS if c not in df_base.columns]
if faltantes_identificadores:
    raise ValueError(f"Faltan columnas identificadoras requeridas: {faltantes_identificadores}")

filas_iniciales = len(df_base)

df_base["texto"] = df_base.apply(construir_texto_fila, axis=1)
df_base = df_base[df_base["texto"].str.strip() != ""].copy()

tiene_etiquetas_validas, serie_etiquetas, mask_etiquetas_validas = detectar_etiquetas_validas(df_base)
base_entrenable, motivo_entrenabilidad = evaluar_entrenabilidad(
    serie_etiquetas, mask_etiquetas_validas
)

if MODO_EJECUCION.lower() == "auto":
    MODO_REAL = "train" if base_entrenable else "inferencia"
elif MODO_EJECUCION.lower() == "train":
    if not base_entrenable:
        raise ValueError(
            "Se solicitó entrenamiento, pero la base no es entrenable. "
            + motivo_entrenabilidad
        )
    MODO_REAL = "train"
elif MODO_EJECUCION.lower() == "inferencia":
    MODO_REAL = "inferencia"
else:
    raise ValueError("MODO_EJECUCION debe ser 'auto', 'train' o 'inferencia'.")

if MODO_REAL == "train":
    df = df_base.loc[mask_etiquetas_validas].copy()
    df[COLUMNA_ETIQUETA] = serie_etiquetas.loc[mask_etiquetas_validas].astype(int)

    print("Modo seleccionado: ENTRENAMIENTO")
    print("Filas iniciales:", filas_iniciales)
    print("Filas utilizables con texto:", len(df_base))
    print("Filas utilizables con etiqueta válida:", len(df))
    print("Diagnóstico de entrenabilidad:", motivo_entrenabilidad)
    print("\nDistribución de clases:")
    print(df[COLUMNA_ETIQUETA].value_counts().sort_index())
else:
    df = df_base.copy()
    print("Modo seleccionado: INFERENCIA")
    print("Filas iniciales:", filas_iniciales)
    print("Filas utilizables con texto:", len(df))
    print("Motivo para no entrenar:", motivo_entrenabilidad)
    if ARCHIVO_MODELOS_ZIP is not None:
        print(f"Se usará el ZIP de modelos cargado: {ARCHIVO_MODELOS_ZIP}")
    else:
        print(
            "No se entrenará con esta base. "
            "Se usará la carpeta de modelos local si existe."
        )


# ## 7. Ejecución del modelo SVM jerárquico


predicciones_clase = None
predicciones_scores = None
pred_final = None
reasignado_de_0_a_2 = None

metricas_etapa1 = cm_etapa1 = reporte_etapa1 = None
metricas_etapa2 = cm_etapa2 = reporte_etapa2 = None
metricas_finales = cm_final = reporte_final = None
bandera_revision_manual = None
umbral_baja_confianza_etapa2 = None
metadata_modelos = {}

grid_etapa1 = grid_etapa2 = None
mejor_etapa1 = mejor_etapa2 = None
X_train = X_test = y_train = y_test = None
idx_train = idx_test = None

if MODO_REAL == "train":
    X = df["texto"]
    y = df[COLUMNA_ETIQUETA]

    conteo_clases = y.value_counts()
    clases_presentes = sorted(conteo_clases.index.tolist())
    if len(clases_presentes) < 2:
        raise ValueError(
            "La base etiquetada no tiene suficientes clases para entrenar. "
            f"Clases encontradas: {clases_presentes}"
        )
    if (conteo_clases < 2).any():
        raise ValueError(
            "Cada clase necesita al menos 2 registros para poder hacer partición estratificada. "
            f"Conteos actuales: {conteo_clases.to_dict()}"
        )

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    print("Tamaño train:", len(X_train))
    print("Tamaño test:", len(X_test))

    y_train_etapa1 = (y_train != 0).astype(int)
    y_test_etapa1 = (y_test != 0).astype(int)

    pipeline_etapa1 = Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, strip_accents="unicode")),
        ("svm", LinearSVC(class_weight="balanced", random_state=RANDOM_STATE, max_iter=5000)),
    ])

    param_grid_etapa1 = [
        {
            "tfidf__analyzer": ["char_wb"],
            "tfidf__ngram_range": [(3, 5), (4, 6)],
            "tfidf__min_df": [2, 5],
            "tfidf__sublinear_tf": [True],
            "svm__C": [0.25, 0.5, 1.0, 2.0, 4.0],
        },
        {
            "tfidf__analyzer": ["word"],
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "tfidf__min_df": [1, 2, 5],
            "tfidf__max_df": [0.95, 0.98],
            "tfidf__sublinear_tf": [True],
            "svm__C": [0.25, 0.5, 1.0, 2.0, 4.0],
        },
    ]

    cv_etapa1 = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    grid_etapa1 = GridSearchCV(
        estimator=pipeline_etapa1,
        param_grid=param_grid_etapa1,
        scoring="recall",
        cv=cv_etapa1,
        n_jobs=-1,
        verbose=1,
        refit=True,
        return_train_score=False,
    )

    grid_etapa1.fit(X_train, y_train_etapa1)

    mejor_etapa1 = grid_etapa1.best_estimator_
    pred_etapa1_test_cruda = mejor_etapa1.predict(X_test)
    score_etapa1_test = mejor_etapa1.decision_function(X_test)

    reasignado_de_0_a_2 = (
        (pred_etapa1_test_cruda == 0) &
        (score_etapa1_test > UMBRAL_REASIGNACION_ETAPA1)
    )
    pred_etapa1_test_binaria = np.where(reasignado_de_0_a_2, 1, pred_etapa1_test_cruda).astype(int)

    metricas_etapa1 = metricas_binarias(y_test_etapa1, pred_etapa1_test_binaria, pos_label=1)
    cm_etapa1 = confusion_matrix(y_test_etapa1, pred_etapa1_test_binaria)
    reporte_etapa1 = classification_report(y_test_etapa1, pred_etapa1_test_binaria, digits=4, zero_division=0)

    mask_train_pos = y_train != 0
    mask_test_pos = y_test != 0

    X_train_pos = X_train[mask_train_pos]
    y_train_pos = y_train[mask_train_pos]
    X_test_pos = X_test[mask_test_pos]
    y_test_pos = y_test[mask_test_pos]

    if len(np.unique(y_train_pos)) < 2:
        raise ValueError(
            "La etapa 2 necesita ejemplos de ambas clases (1 y 2) en train para entrenar."
        )

    pipeline_etapa2 = Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, strip_accents="unicode")),
        ("svm", LinearSVC(class_weight="balanced", random_state=RANDOM_STATE, max_iter=5000)),
    ])

    param_grid_etapa2 = [
        {
            "tfidf__analyzer": ["word"],
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "tfidf__min_df": [1, 2],
            "tfidf__max_df": [0.95, 0.98],
            "tfidf__sublinear_tf": [True],
            "svm__C": [0.25, 0.5, 1.0, 2.0, 4.0],
        },
        {
            "tfidf__analyzer": ["char_wb"],
            "tfidf__ngram_range": [(3, 5), (4, 6)],
            "tfidf__min_df": [1, 2],
            "tfidf__sublinear_tf": [True],
            "svm__C": [0.25, 0.5, 1.0, 2.0],
        },
    ]

    cv_etapa2 = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)

    grid_etapa2 = GridSearchCV(
        estimator=pipeline_etapa2,
        param_grid=param_grid_etapa2,
        scoring="recall_macro",
        cv=cv_etapa2,
        n_jobs=-1,
        verbose=1,
        refit=True,
        return_train_score=False,
    )

    grid_etapa2.fit(X_train_pos, y_train_pos)

    mejor_etapa2 = grid_etapa2.best_estimator_

    pred_etapa2_pos = mejor_etapa2.predict(X_test_pos)
    score_etapa2_pos = mejor_etapa2.decision_function(X_test_pos)

    metricas_etapa2 = metricas_multiclase(y_test_pos, pred_etapa2_pos, labels=[1, 2])
    cm_etapa2 = confusion_matrix(y_test_pos, pred_etapa2_pos, labels=[1, 2])
    reporte_etapa2 = classification_report(y_test_pos, pred_etapa2_pos, labels=[1, 2], digits=4, zero_division=0)

    score_etapa2_train = mejor_etapa2.decision_function(X_train_pos)
    umbral_baja_confianza_etapa2 = float(
        np.quantile(np.abs(score_etapa2_train), PERCENTIL_BAJA_CONFIANZA_ETAPA2)
    )

    pred_etapa2_todo = mejor_etapa2.predict(X_test)
    score_etapa2_todo = mejor_etapa2.decision_function(X_test)

    pred_final = np.where(pred_etapa1_test_binaria == 0, 0, pred_etapa2_todo).astype(int)
    pred_final[reasignado_de_0_a_2] = 2

    bandera_baja_confianza_etapa2 = (
        (pred_etapa1_test_binaria == 1) &
        (~reasignado_de_0_a_2) &
        (np.abs(score_etapa2_todo) <= umbral_baja_confianza_etapa2)
    )

    bandera_revision_manual = (pred_final == 2) | bandera_baja_confianza_etapa2

    metricas_finales = metricas_multiclase(y_test, pred_final, labels=[0, 1, 2])
    cm_final = confusion_matrix(y_test, pred_final, labels=[0, 1, 2])
    reporte_final = classification_report(y_test, pred_final, labels=[0, 1, 2], digits=4, zero_division=0)

    metadata_modelos = {
        "hoja": HOJA,
        "columnas_texto": COLUMNAS_TEXTO,
        "columnas_identificadoras": COLUMNAS_IDENTIFICADORAS,
        "columna_etiqueta": COLUMNA_ETIQUETA,
        "percentil_baja_confianza_etapa2": PERCENTIL_BAJA_CONFIANZA_ETAPA2,
        "umbral_baja_confianza_etapa2": umbral_baja_confianza_etapa2,
        "umbral_reasignacion_etapa1": UMBRAL_REASIGNACION_ETAPA1,
        "mejores_hiperparametros_etapa1": grid_etapa1.best_params_,
        "mejores_hiperparametros_etapa2": grid_etapa2.best_params_,
        "clases_modelo_etapa2": mejor_etapa2.named_steps["svm"].classes_.tolist(),
        "interpretacion_score_etapa2": descripcion_score_etapa2(mejor_etapa2.named_steps["svm"].classes_),
    }

    guardar_modelos_en_carpeta(
        RUTA_CARPETA_MODELOS,
        mejor_etapa1,
        mejor_etapa2,
        metadata_modelos
    )

    salida_base = df.loc[idx_test].copy()
    salida_base["texto"] = X_test.values

    predicciones_clase = pd.DataFrame({
        "Certificado de defunción": salida_base["Certificado de defunción"].values,
        "Número de identificación": salida_base["Número de identificación"].values,
        "texto": salida_base["texto"].values,
        "pred_etapa1_cruda": pred_etapa1_test_cruda,
        "reasignado_de_0_a_2": reasignado_de_0_a_2,
        "clase_predicha": pred_final,
    })

    predicciones_scores = pd.DataFrame({
        "Certificado de defunción": salida_base["Certificado de defunción"].values,
        "Número de identificación": salida_base["Número de identificación"].values,
        "texto": salida_base["texto"].values,
        "score_etapa1_hacia_mencion": score_etapa1_test,
        "score_etapa2_hacia_clase_2": score_etapa2_todo,
        "abs_score_etapa2": np.abs(score_etapa2_todo),
        "reasignado_de_0_a_2": reasignado_de_0_a_2,
    })

else:
    pedir_zip_modelos_si_falta()

    mejor_etapa1, mejor_etapa2, metadata_modelos = preparar_y_cargar_modelos(
        RUTA_CARPETA_MODELOS,
        ARCHIVO_MODELOS_ZIP,
    )

    X_inferencia = df["texto"]

    pred_etapa1_inf_cruda = mejor_etapa1.predict(X_inferencia)
    score_etapa1_inf = mejor_etapa1.decision_function(X_inferencia)

    umbral_reasignacion_etapa1 = metadata_modelos.get(
        "umbral_reasignacion_etapa1",
        UMBRAL_REASIGNACION_ETAPA1,
    )

    reasignado_de_0_a_2 = (
        (pred_etapa1_inf_cruda == 0) &
        (score_etapa1_inf > umbral_reasignacion_etapa1)
    )
    pred_etapa1_inf_binaria = np.where(reasignado_de_0_a_2, 1, pred_etapa1_inf_cruda).astype(int)

    pred_etapa2_inf = mejor_etapa2.predict(X_inferencia)
    pred_final = np.where(pred_etapa1_inf_binaria == 0, 0, pred_etapa2_inf).astype(int)
    pred_final[reasignado_de_0_a_2] = 2

    predicciones_clase = pd.DataFrame({
        "Certificado de defunción": df["Certificado de defunción"].values,
        "Número de identificación": df["Número de identificación"].values,
        "texto": X_inferencia.values,
        "pred_etapa1_cruda": pred_etapa1_inf_cruda,
        "reasignado_de_0_a_2": reasignado_de_0_a_2,
        "clase_predicha": pred_final,
    })

    score_etapa2_inf = mejor_etapa2.decision_function(X_inferencia)

    umbral_baja_confianza_etapa2 = metadata_modelos.get("umbral_baja_confianza_etapa2", 0.0)

    bandera_baja_confianza_etapa2 = (
        (pred_etapa1_inf_binaria == 1) &
        (~reasignado_de_0_a_2) &
        (np.abs(score_etapa2_inf) <= umbral_baja_confianza_etapa2)
    )

    bandera_revision_manual = (pred_final == 2) | bandera_baja_confianza_etapa2

    predicciones_scores = pd.DataFrame({
        "Certificado de defunción": df["Certificado de defunción"].values,
        "Número de identificación": df["Número de identificación"].values,
        "texto": X_inferencia.values,
        "score_etapa1_hacia_mencion": score_etapa1_inf,
        "score_etapa2_hacia_clase_2": score_etapa2_inf,
        "abs_score_etapa2": np.abs(score_etapa2_inf),
        "reasignado_de_0_a_2": reasignado_de_0_a_2,
    })


# ## 8. Resumen de métricas


if MODO_REAL == "train":
    resumen_metricas = {
        "filas_iniciales": int(filas_iniciales),
        "filas_utilizables_texto": int(len(df_base)),
        "filas_utilizables_etiqueta": int(len(df)),
        "tamano_train": int(len(X_train)),
        "tamano_test": int(len(X_test)),
        "distribucion_clases_total": {
            str(k): int(v) for k, v in df[COLUMNA_ETIQUETA].value_counts().sort_index().items()
        },
        "etapa_1": {
            "criterio_cv": "recall",
            "mejor_score_cv": float(grid_etapa1.best_score_),
            "mejores_hiperparametros": grid_etapa1.best_params_,
            "umbral_reasignacion_etapa1": UMBRAL_REASIGNACION_ETAPA1,
            "casos_reasignados_0_a_2": int(reasignado_de_0_a_2.sum()),
            "metricas_test": metricas_etapa1,
            "matriz_confusion": cm_etapa1.tolist(),
        },
        "etapa_2": {
            "criterio_cv": "recall_macro",
            "mejor_score_cv": float(grid_etapa2.best_score_),
            "mejores_hiperparametros": grid_etapa2.best_params_,
            "metricas_test": metricas_etapa2,
            "matriz_confusion": cm_etapa2.tolist(),
            "clases_modelo": mejor_etapa2.named_steps["svm"].classes_.tolist(),
            "interpretacion_score": descripcion_score_etapa2(mejor_etapa2.named_steps["svm"].classes_),
            "umbral_baja_confianza_etapa2": umbral_baja_confianza_etapa2,
        },
        "modelo_final": {
            "metricas_test": metricas_finales,
            "matriz_confusion": cm_final.tolist(),
            "casos_reasignados_0_a_2": int(reasignado_de_0_a_2.sum()),
            "casos_marcados_revision_manual": int(bandera_revision_manual.sum()),
        }
    }

    print("="*80)
    print("RESUMEN DE MÉTRICAS")
    print("="*80)

    print("\nETAPA 1: 0 vs (1+2)")
    print("Mejores hiperparámetros:", grid_etapa1.best_params_)
    print(f"Mejor recall CV: {grid_etapa1.best_score_:.4f}")
    print(f"Umbral de reasignación etapa 1: {UMBRAL_REASIGNACION_ETAPA1:.6f}")
    print("Casos reasignados de 0 a 2:", int(reasignado_de_0_a_2.sum()))
    print("Métricas:", metricas_etapa1)
    print("Matriz de confusión:")
    print(cm_etapa1)
    print("Reporte:")
    print(reporte_etapa1)

    print("\n" + "="*80)
    print("ETAPA 2: 1 vs 2")
    print("Mejores hiperparámetros:", grid_etapa2.best_params_)
    print(f"Mejor recall macro CV: {grid_etapa2.best_score_:.4f}")
    print("Métricas:", metricas_etapa2)
    print("Matriz de confusión:")
    print(cm_etapa2)
    print("Reporte:")
    print(reporte_etapa2)
    print("Interpretación del score:", descripcion_score_etapa2(mejor_etapa2.named_steps["svm"].classes_))
    print(f"Umbral de baja confianza etapa 2: {umbral_baja_confianza_etapa2:.6f}")

    print("\n" + "="*80)
    print("MODELO FINAL JERÁRQUICO")
    print("Métricas:", metricas_finales)
    print("Matriz de confusión:")
    print(cm_final)
    print("Reporte:")
    print(reporte_final)
else:
    print("Modo inferencia: no se calculan métricas ni scores de evaluación.")
    print("Metadata cargada de la carpeta de modelos:")
    print(metadata_modelos if metadata_modelos else "Sin metadata.json")


# ## 9. Exportar salidas


# Salida principal: solo identificadores reales + clase predicha
salida_final_clases = predicciones_clase[
    ["Certificado de defunción", "Número de identificación", "clase_predicha"]
].copy()

salida_final_clases.to_excel(ARCHIVO_SALIDA_CLASES, index=False)
print("Archivo generado:")
print("-", ARCHIVO_SALIDA_CLASES)

# Salida opcional con scores
salida_final_scores = predicciones_scores[
    [
        "Certificado de defunción",
        "Número de identificación",
        "score_etapa1_hacia_mencion",
        "score_etapa2_hacia_clase_2",
        "abs_score_etapa2",
        "reasignado_de_0_a_2",
    ]
].copy()

salida_final_scores.to_excel(ARCHIVO_SALIDA_SCORES, index=False)
print("-", ARCHIVO_SALIDA_SCORES)


# ## 10. Descargar resultados


print("Proceso finalizado.")
print(f"Archivo principal generado: {Path(ARCHIVO_SALIDA_CLASES).resolve()}")

print("La salida principal corresponde al archivo final de resultados.")
print("Si quieres abrirlo, búscalo en la carpeta actual del notebook o cambia la ruta de salida en la configuración.")

# Archivo opcional con scores
print(f"Archivo opcional de scores: {Path(ARCHIVO_SALIDA_SCORES).resolve()}")

if MODO_REAL == "train":
    nombre_zip_modelos = shutil.make_archive(
        base_name=str(Path(RUTA_CARPETA_MODELOS)),
        format="zip",
        root_dir=str(Path(RUTA_CARPETA_MODELOS).parent),
        base_dir=str(Path(RUTA_CARPETA_MODELOS).name),
    )
    print(f"También se creó el archivo de modelos: {Path(nombre_zip_modelos).resolve()}")
