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