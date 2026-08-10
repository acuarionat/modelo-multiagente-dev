import csv

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

COLUMNAS_MULTILINEA = {"Descripción", "Observación"}


def exportar_csv_excel(filas, ruta):
    """
    Exporta una lista plana de diccionarios a CSV legible en Excel: cada
    campo en su propia columna (delimiter=';'), con BOM UTF-8 para que los
    acentos se muestren correctamente. Reutilizable para Requerimientos,
    Diseño, Codificación y Pruebas.
    """
    if not filas:
        return ruta

    columnas = list(filas[0].keys())

    with open(
        ruta,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as archivo:
        writer = csv.DictWriter(
            archivo,
            fieldnames=columnas,
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )

        writer.writeheader()
        writer.writerows(filas)

    return ruta


def exportar_filas_xlsx(filas, ruta, nombre_hoja="Trazabilidad", resumen=None):
    """
    Exporta una lista plana de diccionarios a un libro XLSX nativo (openpyxl,
    sin LibreOffice): encabezados en la primera fila, cada campo en su celda,
    fila 1 congelada, filtros activos, columnas ajustadas y salto de línea
    habilitado en Descripción/Observación. Si se recibe `resumen`, agrega una
    segunda hoja "Resumen" con sus pares clave/valor.
    """
    if not filas:
        return ruta

    columnas = list(filas[0].keys())

    workbook = Workbook()
    hoja = workbook.active
    hoja.title = nombre_hoja

    hoja.append(columnas)
    for fila in filas:
        hoja.append([fila.get(columna, "") for columna in columnas])

    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    for indice, columna in enumerate(columnas, start=1):
        letra = get_column_letter(indice)
        longitud = max(
            [len(str(columna))] + [len(str(fila.get(columna, ""))) for fila in filas]
        )
        hoja.column_dimensions[letra].width = min(longitud + 2, 60)

        if columna in COLUMNAS_MULTILINEA:
            for celda in hoja[letra][1:]:
                celda.alignment = celda.alignment.copy(wrap_text=True)

    if resumen:
        hoja_resumen = workbook.create_sheet("Resumen")
        for clave, valor in resumen.items():
            hoja_resumen.append([clave, valor])
        hoja_resumen.column_dimensions["A"].width = 30
        hoja_resumen.column_dimensions["B"].width = 15

    workbook.save(ruta)
    return ruta


def importar_matriz_csv(archivo) -> list:
    """
    Importa una matriz de Requerimientos desde un CSV (ruta o archivo tipo
    Streamlit UploadedFile) y la normaliza al mismo contrato interno que
    produce el Mapper de GitLab (codigo, nombre, descripcion, tipo,
    historia_origen, estado). GitLab y Excel convergen al mismo formato.
    """
    from core.design_context import normalizar_fila_trazabilidad

    if hasattr(archivo, "read"):
        contenido = archivo.read()
        if isinstance(contenido, bytes):
            contenido = contenido.decode("utf-8-sig")
        lineas = contenido.splitlines()
        filas_crudas = list(csv.DictReader(lineas, delimiter=";"))
        if filas_crudas and len(filas_crudas[0]) <= 1:
            filas_crudas = list(csv.DictReader(lineas))
    else:
        with open(archivo, encoding="utf-8-sig", newline="") as handle:
            filas_crudas = list(csv.DictReader(handle, delimiter=";"))
        if filas_crudas and len(filas_crudas[0]) <= 1:
            with open(archivo, encoding="utf-8-sig", newline="") as handle:
                filas_crudas = list(csv.DictReader(handle))

    return [normalizar_fila_trazabilidad(fila) for fila in filas_crudas]


def importar_matriz_xlsx(archivo) -> list:
    """
    Importa una matriz de Requerimientos desde un XLSX (ruta o archivo tipo
    Streamlit UploadedFile) y la normaliza al mismo contrato interno que
    produce el Mapper de GitLab. GitLab y Excel convergen al mismo formato.
    """
    from openpyxl import load_workbook

    from core.design_context import normalizar_fila_trazabilidad

    workbook = load_workbook(archivo, data_only=True)
    hoja = workbook.active
    filas_iter = hoja.iter_rows(values_only=True)
    encabezados = next(filas_iter, None)
    if not encabezados:
        return []

    filas_crudas = [
        {encabezado: valor for encabezado, valor in zip(encabezados, fila_valores)}
        for fila_valores in filas_iter
        if not all(valor is None for valor in fila_valores)
    ]

    return [normalizar_fila_trazabilidad(fila) for fila in filas_crudas]
