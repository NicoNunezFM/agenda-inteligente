from datetime import datetime
from typing import Any, Dict, List
import json
from app.database import get_connection


def construir_contexto_base() -> Dict[str, Any]:
    ahora = datetime.now()
    return {
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora_actual": ahora.strftime("%H:%M:%S"),
        "tipo_dia": "normal",
        "eventos": [],
        "es_exigente": False,
        "fuentes": ["base"],
    }


def aplicar_contexto_manual(contexto: Dict[str, Any], extras: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not extras:
        return contexto

    contexto_final = contexto.copy()

    if "tipo_dia" in extras and extras["tipo_dia"]:
        contexto_final["tipo_dia"] = extras["tipo_dia"]

    if "eventos" in extras and isinstance(extras["eventos"], list):
        contexto_final["eventos"] = extras["eventos"]

    if "es_exigente" in extras:
        contexto_final["es_exigente"] = bool(extras["es_exigente"])

    contexto_final["fuentes"] = list(set(contexto_final.get("fuentes", []) + ["manual"]))

    return contexto_final


def construir_contexto_del_dia(extras: Dict[str, Any] | None = None) -> Dict[str, Any]:
    contexto = construir_contexto_base()

    guardado = obtener_contexto_guardado_hoy()
    if guardado:
        contexto = aplicar_contexto_manual(contexto, guardado)

    contexto = aplicar_contexto_manual(contexto, extras)
    return contexto

def guardar_contexto_manual_hoy(tipo_dia: str, eventos: list[str] | None = None, es_exigente: bool = False) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    eventos_json = json.dumps(eventos or [], ensure_ascii=False)

    cursor.execute("DELETE FROM contexto_diario WHERE fecha = ?", (fecha_hoy,))

    cursor.execute("""
        INSERT INTO contexto_diario (fecha, tipo_dia, eventos, es_exigente, fuente)
        VALUES (?, ?, ?, ?, ?)
    """, (
        fecha_hoy,
        tipo_dia,
        eventos_json,
        1 if es_exigente else 0,
        "manual"
    ))

    conn.commit()
    conn.close()


def obtener_contexto_guardado_hoy() -> Dict[str, Any] | None:
    conn = get_connection()
    cursor = conn.cursor()

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT tipo_dia, eventos, es_exigente, fuente
        FROM contexto_diario
        WHERE fecha = ?
        ORDER BY id DESC
        LIMIT 1
    """, (fecha_hoy,))

    fila = cursor.fetchone()
    conn.close()

    if not fila:
        return None

    tipo_dia, eventos, es_exigente, fuente = fila

    try:
        eventos = json.loads(eventos) if eventos else []
    except Exception:
        eventos = []

    return {
        "tipo_dia": tipo_dia or "normal",
        "eventos": eventos,
        "es_exigente": bool(es_exigente),
        "fuentes": [fuente or "manual"]
    }

def interpretar_contexto_manual_desde_texto(texto: str) -> dict | None:
    texto_limpio = (texto or "").strip().lower()

    if "hoy tuve facultad" in texto_limpio or "hoy tengo facultad" in texto_limpio:
        return {
            "tipo_dia": "facultad",
            "eventos": ["Facultad"],
            "es_exigente": True
        }

    if "hoy trabajo" in texto_limpio or "hoy tengo trabajo" in texto_limpio or "hoy laburo" in texto_limpio:
        return {
            "tipo_dia": "trabajo",
            "eventos": ["Trabajo"],
            "es_exigente": True
        }

    if "hoy estoy de guardia" in texto_limpio or "hoy tengo guardia" in texto_limpio:
        return {
            "tipo_dia": "guardia",
            "eventos": ["Guardia"],
            "es_exigente": True
        }

    if "hoy bomberos" in texto_limpio or "hoy tengo bomberos" in texto_limpio:
        return {
            "tipo_dia": "bomberos",
            "eventos": ["Bomberos"],
            "es_exigente": True
        }

    if "hoy es un dia exigente" in texto_limpio or "hoy es un día exigente" in texto_limpio:
        return {
            "tipo_dia": "mixto",
            "eventos": ["Día exigente"],
            "es_exigente": True
        }

    if "hoy es un dia libre" in texto_limpio or "hoy es un día libre" in texto_limpio:
        return {
            "tipo_dia": "libre",
            "eventos": ["Día libre"],
            "es_exigente": False
        }

    return None