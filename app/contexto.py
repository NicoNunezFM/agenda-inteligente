from datetime import datetime
from typing import Any, Dict, List


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
    contexto = aplicar_contexto_manual(contexto, extras)
    return contexto

def interpretar_contexto_manual_desde_texto(texto: str):
    texto = (texto or "").lower().strip()

    eventos = []
    tipo_dia = None
    es_exigente = False

    if "facultad" in texto or "cursada" in texto or "clase" in texto:
        tipo_dia = "facultad"
        eventos.append("facultad")
        es_exigente = True

    elif "trabajo" in texto or "laburo" in texto or "turno" in texto:
        tipo_dia = "trabajo"
        eventos.append("trabajo")
        es_exigente = True

    elif "guardia" in texto or "bomberos" in texto or "cuartel" in texto:
        tipo_dia = "guardia"
        eventos.append("guardia")
        es_exigente = True

    elif "libre" in texto or "descanso" in texto:
        tipo_dia = "libre"
        eventos.append("libre")
        es_exigente = False

    if not tipo_dia:
        return None

    return {
        "tipo_dia": tipo_dia,
        "eventos": eventos,
        "es_exigente": es_exigente
    }