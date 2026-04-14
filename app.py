import streamlit as st
import pandas as pd
import numpy as np
import joblib
import tempfile
import shutil
import unicodedata
import json
import re
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

try:
    import ftfy
except Exception:
    ftfy = None

try:
    import msoffcrypto
except Exception:
    msoffcrypto = None

from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

st.set_page_config(page_title="Clasificador SVM de registros", layout="wide")

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

manual_mojibake = {
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ",
    "Ã\x81": "Á", "Ã‰": "É", "Ã\x8d": "Í", "Ã“": "Ó", "Ãš": "Ú", "Ã‘": "Ñ",
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
        "mencion de cancer 0= sin mencion de cancer 1= mencion explicita de cancer 2= sospechoso de cancer (ej. tumor de comportamiento incierto; masa en abdomen u otra localizacion)"
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


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def normalize_text(value: str) -> str:
    text = str(value).strip().lower().replace("_", " ")
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split())


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


def _leer_excel_desde_buffer(buffer: BytesIO) -> pd.DataFrame:
    try:
        buffer.seek(0)
        return pd.read_excel(buffer, sheet_name=HOJA)
    except Exception:
        buffer.seek(0)
        xls = pd.ExcelFile(buffer)
        hojas = xls.sheet_names
        if not hojas:
            raise ValueError("El archivo Excel no contiene hojas legibles.")
        buffer.seek(0)
        return pd.read_excel(buffer, sheet_name=hojas[0])


def load_input_file(input_file, password: str | None = None) -> pd.DataFrame:
    nombre = input_file.name.lower()

    if nombre.endswith(".xlsx") or nombre.endswith(".xls"):
        input_file.seek(0)

        if password:
            if msoffcrypto is None:
                raise ValueError(
                    "Para abrir archivos Excel con contraseña debes instalar la librería "
                    "'msoffcrypto-tool'."
                )

            archivo_desencriptado = BytesIO()
            try:
                office_file = msoffcrypto.OfficeFile(input_file)
                office_file.load_key(password=password)
                office_file.decrypt(archivo_desencriptado)
                archivo_desencriptado.seek(0)
                return _leer_excel_desde_buffer(archivo_desencriptado)
            except Exception as e:
                raise ValueError(
                    "No se pudo abrir el Excel con la contraseña proporcionada. "
                    "Verifica la clave o que el archivo realmente sea un Excel cifrado."
                ) from e

        try:
            input_file.seek(0)
            return _leer_excel_desde_buffer(input_file)
        except Exception as e:
            raise ValueError(
                "No se pudo leer el archivo Excel. "
                "Si tiene contraseña, escríbela en el campo correspondiente."
            ) from e

    if nombre.endswith(".csv"):
        try:
            input_file.seek(0)
            return pd.read_csv(input_file, encoding="utf-8")
        except UnicodeDecodeError:
            input_file.seek(0)
            return pd.read_csv(input_file, encoding="latin-1")

    if nombre.endswith(".tsv"):
        try:
            input_file.seek(0)
            return pd.read_csv(input_file, sep="\t", encoding="utf-8")
        except UnicodeDecodeError:
            input_file.seek(0)
            return pd.read_csv(input_file, sep="\t", encoding="latin-1")

    raise ValueError("Formato no soportado. Usa .xlsx, .xls, .csv o .tsv")


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


def guardar_modelos_en_memoria(modelo_etapa1, modelo_etapa2, metadata):
    temp_dir = tempfile.mkdtemp()
    carpeta = Path(temp_dir) / "modelos_svm_dos_etapas"
    carpeta.mkdir(parents=True, exist_ok=True)

    joblib.dump(modelo_etapa1, carpeta / "modelo_etapa1.joblib")
    joblib.dump(modelo_etapa2, carpeta / "modelo_etapa2.joblib")

    with open(carpeta / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zipf:
        for item in carpeta.iterdir():
            zipf.write(item, arcname=f"modelos_svm_dos_etapas/{item.name}")
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def cargar_modelos_desde_zip_bytes(zip_bytes_io):
    temp_dir = tempfile.mkdtemp()
    zip_path = Path(temp_dir) / "modelos.zip"

    zip_bytes_io.seek(0)
    with open(zip_path, "wb") as f:
        f.write(zip_bytes_io.read())

    extract_dir = Path(temp_dir) / "extraido"
    extract_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(zip_path), str(extract_dir))

    candidatos = [extract_dir] + [p for p in extract_dir.rglob("*") if p.is_dir()]
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
            "El ZIP no contiene 'modelo_etapa1.joblib' y 'modelo_etapa2.joblib'."
        )

    modelo_etapa1 = joblib.load(carpeta_origen / "modelo_etapa1.joblib")
    modelo_etapa2 = joblib.load(carpeta_origen / "modelo_etapa2.joblib")

    metadata = {}
    metadata_path = carpeta_origen / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    return modelo_etapa1, modelo_etapa2, metadata


def preparar_salida_predicciones(df_pred: pd.DataFrame) -> pd.DataFrame:
    salida = df_pred.copy()
    if "clase_predicha" in salida.columns:
        salida = salida.rename(columns={"clase_predicha": "prediccion"})
    columnas = [
        "Certificado de defunción",
        "Número de identificación",
        "texto",
        "prediccion",
    ]
    return salida[columnas].copy()


def ejecutar_entrenamiento(df_base):
    df_base = df_base.copy()
    df_base["texto"] = df_base.apply(construir_texto_fila, axis=1)
    df_base = df_base[df_base["texto"].str.strip() != ""].copy()

    _, serie_etiquetas, mask_etiquetas_validas = detectar_etiquetas_validas(df_base)
    df = df_base.loc[mask_etiquetas_validas].copy()
    df[COLUMNA_ETIQUETA] = serie_etiquetas.loc[mask_etiquetas_validas].astype(int)

    X = df["texto"]
    y = df[COLUMNA_ETIQUETA]

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    y_train_etapa1 = (y_train != 0).astype(int)

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
        verbose=0,
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

    mask_train_pos = y_train != 0
    X_train_pos = X_train[mask_train_pos]
    y_train_pos = y_train[mask_train_pos]

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
        verbose=0,
        refit=True,
        return_train_score=False,
    )
    grid_etapa2.fit(X_train_pos, y_train_pos)

    mejor_etapa2 = grid_etapa2.best_estimator_
    score_etapa2_train = mejor_etapa2.decision_function(X_train_pos)
    umbral_baja_confianza_etapa2 = float(
        np.quantile(np.abs(score_etapa2_train), PERCENTIL_BAJA_CONFIANZA_ETAPA2)
    )

    pred_etapa2_todo = mejor_etapa2.predict(X_test)
    pred_final = np.where(pred_etapa1_test_binaria == 0, 0, pred_etapa2_todo).astype(int)
    pred_final[reasignado_de_0_a_2] = 2

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

    salida_base = df.loc[idx_test].copy()
    salida_base["texto"] = X_test.values

    predicciones_clase = pd.DataFrame({
        "Certificado de defunción": salida_base["Certificado de defunción"].values,
        "Número de identificación": salida_base["Número de identificación"].values,
        "texto": salida_base["texto"].values,
        "clase_predicha": pred_final,
    })

    zip_modelos = guardar_modelos_en_memoria(mejor_etapa1, mejor_etapa2, metadata_modelos)

    return {
        "predicciones_clase": preparar_salida_predicciones(predicciones_clase),
        "zip_modelos": zip_modelos,
    }


def ejecutar_inferencia(df_base, zip_bytes_io):
    df = df_base.copy()
    df["texto"] = df.apply(construir_texto_fila, axis=1)
    df = df[df["texto"].str.strip() != ""].copy()

    mejor_etapa1, mejor_etapa2, metadata_modelos = cargar_modelos_desde_zip_bytes(zip_bytes_io)

    X_inferencia = df["texto"]
    pred_etapa1_inf_cruda = mejor_etapa1.predict(X_inferencia)
    score_etapa1_inf = mejor_etapa1.decision_function(X_inferencia)

    umbral_reasignacion = metadata_modelos.get("umbral_reasignacion_etapa1", UMBRAL_REASIGNACION_ETAPA1)
    reasignado_de_0_a_2 = (
        (pred_etapa1_inf_cruda == 0) &
        (score_etapa1_inf > umbral_reasignacion)
    )
    pred_etapa1_inf_binaria = np.where(reasignado_de_0_a_2, 1, pred_etapa1_inf_cruda).astype(int)

    pred_etapa2_inf = mejor_etapa2.predict(X_inferencia)
    pred_final = np.where(pred_etapa1_inf_binaria == 0, 0, pred_etapa2_inf).astype(int)
    pred_final[reasignado_de_0_a_2] = 2

    predicciones_clase = pd.DataFrame({
        "Certificado de defunción": df["Certificado de defunción"].values,
        "Número de identificación": df["Número de identificación"].values,
        "texto": X_inferencia.values,
        "clase_predicha": pred_final,
    })

    return {
        "predicciones_clase": preparar_salida_predicciones(predicciones_clase),
    }


def main():
    st.title("Clasificador SVM jerárquico de registros de defunción")
    st.write("La app decide automáticamente si entrena o si hace inferencia según lo que cargues.")

    archivo_base = st.file_uploader(
        "Sube la base de datos",
        type=["xlsx", "xls", "csv", "tsv"]
    )

    password_excel = st.text_input(
        "Contraseña del Excel (solo si el archivo está protegido)",
        type="password"
    )

    if archivo_base is None:
        st.info("Carga una base de datos para continuar.")
        return

    try:
        df_original = load_input_file(archivo_base, password=password_excel or None)

        st.subheader("Vista previa de la base original")
        st.dataframe(df_original.head())

        df_base = estandarizar_base(df_original)

        st.subheader("Vista previa de la base estandarizada")
        st.dataframe(df_base.head())

        _, serie_etiquetas, mask_etiquetas_validas = detectar_etiquetas_validas(df_base)
        base_entrenable, motivo_entrenabilidad = evaluar_entrenabilidad(
            serie_etiquetas, mask_etiquetas_validas
        )

        if base_entrenable:
            st.success("Modo automático: se entrenará el modelo con la base cargada.")
        else:
            st.info("Modo automático: se realizará inferencia con los modelos ya disponibles en la app.")
            st.write(motivo_entrenabilidad)

        ejecutar = st.button("Ejecutar modelo")

        if ejecutar:
            if base_entrenable:
                with st.spinner("Entrenando modelo... Esto puede tardar un poco."):
                    resultados = ejecutar_entrenamiento(df_base)

                st.success("Entrenamiento finalizado.")
                st.subheader("Predicciones")
                st.dataframe(resultados["predicciones_clase"].head())

                st.download_button(
                    "Descargar predicciones",
                    data=to_excel_bytes(resultados["predicciones_clase"]),
                    file_name="predicciones_clase.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.download_button(
                    "Descargar modelos entrenados (ZIP)",
                    data=resultados["zip_modelos"],
                    file_name="modelos_svm_dos_etapas.zip",
                    mime="application/zip"
                )
            else:
                with st.spinner("Ejecutando inferencia..."):
                    ruta_zip_modelos = Path(__file__).resolve().parent / "modelos_svm_dos_etapas.zip"
                    if not ruta_zip_modelos.exists():
                        st.error("No se encontró el archivo local 'modelos_svm_dos_etapas.zip' en la carpeta de la app.")
                        return

                    with open(ruta_zip_modelos, "rb") as f:
                        zip_bytes = BytesIO(f.read())

                    resultados = ejecutar_inferencia(df_base, zip_bytes)

                st.success("Inferencia finalizada.")
                st.subheader("Predicciones")
                st.dataframe(resultados["predicciones_clase"].head())

                st.download_button(
                    "Descargar predicciones",
                    data=to_excel_bytes(resultados["predicciones_clase"]),
                    file_name="predicciones_clase.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")


if __name__ == "__main__":
    main()
