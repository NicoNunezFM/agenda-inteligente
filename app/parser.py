import re
from datetime import datetime, timedelta


def extraer_numero(texto: str):
    palabras = texto.replace(",", ".").split()
    for palabra in palabras:
        try:
            return float(palabra)
        except ValueError:
            continue
    return None


def extraer_duracion_minutos(texto: str):
    texto = texto.lower().replace(",", ".")

    # 1h / 2h / 1.5h
    match = re.search(r"(\d+(?:\.\d+)?)\s*h\b", texto)
    if match:
        horas = float(match.group(1))
        return int(horas * 60)

    # 30m / 45min
    match = re.search(r"(\d+(?:\.\d+)?)\s*(m|min)\b", texto)
    if match:
        return int(float(match.group(1)))

    # 2 horas / 1 hora / 1.5 horas
    match = re.search(r"(\d+(?:\.\d+)?)\s*(hora|horas)\b", texto)
    if match:
        horas = float(match.group(1))
        return int(horas * 60)

    # 40 minutos / 15 minuto
    match = re.search(r"(\d+(?:\.\d+)?)\s*(minuto|minutos)\b", texto)
    if match:
        return int(float(match.group(1)))

    return None


def interpretar_texto(texto: str):
    texto_limpio = texto.strip().lower()
    monto = extraer_numero(texto_limpio)
    duracion_minutos = extraer_duracion_minutos(texto_limpio)

    # GASTOS
    if any(p in texto_limpio for p in [
        "gast", "compr", "pagué", "pague", "salida", "uber", "taxi", "bondi",
        "colectivo", "tren", "sube", "transporte",
        "comida", "almuerzo", "cena", "desayuno", "pizza", "hamburguesa",
        "coca", "gaseosa", "bebida", "agua", "cerveza", "jugo",
        "super", "mercado", "farmacia", "medicamento", "remedio",
        "ropa", "remera", "pantalon", "pantalón", "zapatillas",
        "celular", "cuota", "electronica", "electrónica", "tecnologia", "tecnología"
    ]):
        if any(p in texto_limpio for p in ["super", "mercado"]):
            categoria = "supermercado"
        elif any(p in texto_limpio for p in ["comida", "almuerzo", "cena", "desayuno", "pizza", "hamburguesa"]):
            categoria = "comida"
        elif any(p in texto_limpio for p in ["coca", "gaseosa", "bebida", "agua", "cerveza", "jugo"]):
            categoria = "bebida"
        elif any(p in texto_limpio for p in ["salida", "bar", "boliche", "cine"]):
            categoria = "salida"
        elif any(p in texto_limpio for p in ["uber", "taxi", "sube", "bondi", "colectivo", "tren", "transporte"]):
            categoria = "transporte"
        elif any(p in texto_limpio for p in ["farmacia", "medicamento", "remedio"]):
            categoria = "salud"
        elif any(p in texto_limpio for p in ["ropa", "remera", "pantalon", "pantalón", "zapatillas"]):
            categoria = "ropa"
        elif any(p in texto_limpio for p in ["celular", "cuota", "electronica", "electrónica", "tecnologia", "tecnología"]):
            categoria = "tecnologia"
        else:
            categoria = "otros"

        return {
            "tipo": "gasto",
            "categoria": categoria,
            "detalle": texto.strip(),
            "monto": monto,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": None,
        }

    # INGRESOS
    if any(p in texto_limpio for p in ["cobr", "ingres", "gane", "gané", "me pagaron", "sueldo"]):
        return {
            "tipo": "ingreso",
            "categoria": "general",
            "detalle": texto.strip(),
            "monto": monto,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": None,
        }

    # HÁBITOS
    if any(p in texto_limpio for p in ["fum", "pucho", "cigarrillo"]):
        return {
            "tipo": "habito",
            "categoria": "fumar",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": monto if monto is not None else 1,
            "unidad": "cigarrillos",
            "duracion_minutos": duracion_minutos,
        }

    # PÉRDIDA DE TIEMPO
    if any(p in texto_limpio for p in ["reels", "tiktok", "instagram", "scroll", "youtube", "videos", "bolude", "boludié", "boludee"]):
        return {
            "tipo": "actividad",
            "categoria": "distraccion",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": duracion_minutos,
        }

    # ACTIVIDADES
    if any(p in texto_limpio for p in ["gim", "gym", "entren"]):
        return {
            "tipo": "actividad",
            "categoria": "gimnasio",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": duracion_minutos,
        }

    if any(p in texto_limpio for p in ["bomber", "guardia", "cuartel"]):
        return {
            "tipo": "actividad",
            "categoria": "bomberos",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": duracion_minutos,
        }

    if any(p in texto_limpio for p in ["estudi", "python", "program", "curso"]):
        return {
            "tipo": "actividad",
            "categoria": "estudio",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": duracion_minutos,
        }

    if any(p in texto_limpio for p in ["trabaj", "labur", "turno", "seguridad"]):
        return {
            "tipo": "actividad",
            "categoria": "trabajo",
            "detalle": texto.strip(),
            "monto": None,
            "cantidad": None,
            "unidad": None,
            "duracion_minutos": duracion_minutos,
        }

    return {
        "tipo": "nota",
        "categoria": "general",
        "detalle": texto.strip(),
        "monto": None,
        "cantidad": None,
        "unidad": None,
        "duracion_minutos": duracion_minutos,
    }


def obtener_filtro_fecha(texto_limpio: str):
    ahora = datetime.now()

    if "hoy" in texto_limpio:
        inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        return inicio.strftime("%Y-%m-%d")

    if "semana" in texto_limpio:
        inicio_semana = ahora - timedelta(days=ahora.weekday())
        inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)
        return inicio_semana.strftime("%Y-%m-%d")

    if "mes" in texto_limpio:
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return inicio_mes.strftime("%Y-%m-%d")

    return None


def es_consulta(texto_limpio: str):
    palabras_consulta = [
        "cuanto", "cuánto",
        "cuantos", "cuántos",
        "balance", "total",
        "resumen", "cuenta",
        "modo dueño", "modo dueno",
        "analiza",
        "situacion", "situación",
        "ingres",
        "detalle",
        "compar",
        "gasto mas", "gasto más",
        "que hice", "qué hice",
        "historial",
        "como estuvo", "cómo estuvo",
        "mi dia", "mi día",
        "productividad",
        "perdi tiempo", "perdí tiempo",
        "malversadores de tiempo",
        "horas productivas",
        "tiempo productivo",
        "tiempo perdido"
    ]

    return any(p in texto_limpio for p in palabras_consulta)


def clasificar_productividad(datos: dict):
    tipo = datos.get("tipo", "")
    categoria = datos.get("categoria", "")
    detalle = datos.get("detalle", "").lower()

    if tipo == "gasto":
        return "necesario"

    if tipo == "ingreso":
        return "productivo"

    if tipo == "habito":
        if categoria == "fumar":
            return "perdida_tiempo"
        return "necesario"

    if tipo == "actividad":
        if categoria in ["estudio", "gimnasio", "bomberos"]:
            return "productivo"

        if categoria == "trabajo":
            return "necesario"

        if categoria == "distraccion":
            return "perdida_tiempo"

        if any(p in detalle for p in ["reels", "tiktok", "instagram", "scroll", "youtube", "videos"]):
            return "perdida_tiempo"

        return "necesario"

    if tipo == "nota":
        if any(p in detalle for p in ["reels", "tiktok", "instagram", "bolude", "perdi tiempo", "perdí tiempo"]):
            return "perdida_tiempo"
        return "neutro"

    return "neutro"