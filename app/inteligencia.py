from __future__ import annotations

import sqlite3
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "agenda.db"

UMBRAL_REDES_DIA = 45
UMBRAL_REDES_SEMANA = 180
UMBRAL_TIEMPO_PERDIDO_DIA = 45
UMBRAL_TIEMPO_PERDIDO_SEMANA = 120
UMBRAL_BLOQUE_PRODUCTIVO_MINIMO = 60
UMBRAL_PRODUCTIVO_BUENO = 90
UMBRAL_PRODUCTIVO_MUY_BUENO = 120
UMBRAL_DIA_CON_MUCHOS_REGISTROS = 4
UMBRAL_BLOQUE_PRODUCTIVO_FUERTE = 90
UMBRAL_HABITO_FORMACION = 3
UMBRAL_HABITO_CONSOLIDADO = 5
UMBRAL_DIAS_CONSTANCIA = 3
UMBRAL_MIN_REGISTROS_RELACION = 2
UMBRAL_MIN_DIAS_RELACION = 2
UMBRAL_SEMANAS_TENDENCIA = 3
UMBRAL_CAMBIO_RELEVANTE_MIN = 30
UMBRAL_DIAS_MALOS_SEGUIDOS = 3
UMBRAL_DIAS_REDES_SEGUIDOS = 3
UMBRAL_DIAS_SIN_HABITO_IMPORTANTE = 4
UMBRAL_ALERTA_ALTA_PUNTAJE = 4
UMBRAL_ALERTA_MEDIA_PUNTAJE = 2
UMBRAL_GRAVEDAD_ALTA = 4
UMBRAL_GRAVEDAD_MEDIA = 2
UMBRAL_PLAN_MINIMO_PRODUCTIVO = 30
UMBRAL_PLAN_CONSOLIDACION = 90
UMBRAL_PLAN_CIERRE_REDES = 20
UMBRAL_GASTO_RELEVANTE = 5000
UMBRAL_AUMENTO_GASTO_RELEVANTE = 3000
UMBRAL_GASTO_REPETIDO = 3
DIAS_MEMORIA_HISTORICA = 30
UMBRAL_DESVIO_RELEVANTE = 30
UMBRAL_RIESGO_ALTO = 4
UMBRAL_RIESGO_MEDIO = 2

TIPOS_DIA_VALIDOS = {
    "facultad",
    "trabajo",
    "bomberos",
    "guardia",
    "libre",
    "mixto",
    "normal",
}

PALABRAS_CONTEXTO = {
    "facultad": ["facultad", "cursada", "clase", "universidad"],
    "trabajo": ["trabajo", "laburo", "turno"],
    "bomberos": ["bomberos", "guardia", "cuartel", "salida"],
}


palabras_redes = [
    "reels", "instagram", "ig", "tiktok", "facebook",
    "youtube", "shorts", "twitter", "x", "scroll", "redes"
]

TONOS_VALIDOS = {"neutral", "ejecutivo", "calmo", "correctivo", "positivo"}

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def obtener_registros_hoy() -> List[dict]:
    hoy = datetime.now().strftime("%Y-%m-%d")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            fecha,
            texto_original,
            tipo,
            categoria,
            detalle,
            monto,
            cantidad,
            unidad,
            respuesta,
            productividad,
            duracion_minutos
        FROM registros
        WHERE DATE(fecha) = ?
        ORDER BY fecha ASC
    """, (hoy,))

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def normalizar_nombre_actividad(registro: dict) -> str:
    detalle = (registro.get("detalle") or "").strip()
    texto_original = (registro.get("texto_original") or "").strip()

    if detalle:
        return detalle.lower()
    if texto_original:
        return texto_original.lower()

    return "sin_detalle"


def obtener_minutos(registro: dict) -> int:
    duracion = registro.get("duracion_minutos")

    if duracion is None:
        return 0

    try:
        return int(float(duracion))
    except Exception:
        return 0

def es_actividad_de_redes(registro: dict) -> bool:
    texto_control = f"{normalizar_nombre_actividad(registro)} {(registro.get('texto_original') or '').lower()}"
    return any(p in texto_control for p in palabras_redes)

def detectar_contexto_desde_registros(registros: List[dict]) -> Dict[str, Any]:
    contextos = set()

    for r in registros:
        texto = f"{(r.get('texto_original') or '').lower()} {(r.get('detalle') or '').lower()} {(r.get('categoria') or '').lower()}"

        for contexto, palabras in PALABRAS_CONTEXTO.items():
            if any(p in texto for p in palabras):
                contextos.add(contexto)

    if not contextos:
        tipo_dia = "normal"
    elif len(contextos) == 1:
        tipo_dia = list(contextos)[0]
    else:
        tipo_dia = "mixto"

    exigente = tipo_dia in {"trabajo", "facultad", "bomberos", "guardia", "mixto"}

    return {
        "tipo_dia": tipo_dia,
        "contextos_detectados": sorted(list(contextos)),
        "es_exigente": exigente,
    }

def detectar_tono_respuesta() -> str:
    gravedad = analizar_gravedad_actual()
    diagnostico = generar_diagnostico_actual()
    lectura = generar_lectura_historica_personal()

    if gravedad["gravedad"] == "alta":
        return "correctivo"

    if diagnostico["estado"] == "bien_encaminado" or lectura["conclusion"] == "por_encima_de_tu_base":
        return "positivo"

    if diagnostico["estado"] in {"disperso", "interrumpido"}:
        return "ejecutivo"

    if diagnostico["estado"] == "sin_foco":
        return "calmo"

    return "neutral"

def adaptar_texto_segun_tono(base: str, tono: str) -> str:
    if tono not in TONOS_VALIDOS:
        tono = "neutral"

    variantes = {
        "neutral": base,
        "ejecutivo": f"Vamos a lo importante: {base}",
        "calmo": f"Sin dramatizar: {base}",
        "correctivo": f"Atención. {base}",
        "positivo": f"Bien. {base}",
    }

    return variantes.get(tono, base)

def construir_respuesta_natural(
    mensaje_principal: str,
    detalle: str | None = None,
    sugerencia: str | None = None,
    tono: str | None = None,
) -> str:
    tono_final = tono or detectar_tono_respuesta()

    texto = adaptar_texto_segun_tono(mensaje_principal, tono_final)

    partes = [texto]

    if detalle:
        partes.append(detalle)

    if sugerencia:
        if tono_final == "correctivo":
            partes.append(f"Lo más conveniente ahora es: {sugerencia}")
        elif tono_final == "positivo":
            partes.append(f"Para sostenerlo, conviene: {sugerencia}")
        else:
            partes.append(f"Sugerencia: {sugerencia}")

    return "\n".join(partes)

def resumir_tiempos(registros: List[dict]) -> Dict[str, int]:
    minutos_productivos = 0
    minutos_necesarios = 0
    minutos_perdidos = 0
    minutos_neutros = 0
    minutos_redes = 0

    for r in registros:
        productividad = (r.get("productividad") or "neutro").lower()
        minutos = obtener_minutos(r)

        if productividad == "productivo":
            minutos_productivos += minutos
        elif productividad == "necesario":
            minutos_necesarios += minutos
        elif productividad == "perdida_tiempo":
            minutos_perdidos += minutos
        else:
            minutos_neutros += minutos

        if es_actividad_de_redes(r):
            minutos_redes += minutos

    return {
        "productivo": minutos_productivos,
        "necesario": minutos_necesarios,
        "perdido": minutos_perdidos,
        "neutro": minutos_neutros,
        "redes": minutos_redes,
    }

def resumir_gastos(registros: List[dict]) -> Dict[str, Any]:
    total_gastos = 0.0
    gastos_por_categoria = defaultdict(float)
    cantidad_gastos = 0

    for r in registros:
        if (r.get("tipo") or "").lower() != "gasto":
            continue

        categoria = (r.get("categoria") or "sin_categoria").lower()
        monto = r.get("monto") or 0

        try:
            monto = float(monto)
        except Exception:
            monto = 0

        total_gastos += monto
        gastos_por_categoria[categoria] += monto
        cantidad_gastos += 1

    categoria_top = None
    if gastos_por_categoria:
        cat = max(gastos_por_categoria, key=gastos_por_categoria.get)
        categoria_top = {
            "categoria": cat,
            "total": round(gastos_por_categoria[cat], 2)
        }

    return {
        "total_gastos": round(total_gastos, 2),
        "cantidad_gastos": cantidad_gastos,
        "gastos_por_categoria": dict(gastos_por_categoria),
        "categoria_top": categoria_top,
    }

def analizar_dia() -> Dict[str, Any]:
    registros = obtener_registros_hoy()

    if not registros:
        return {
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "cantidad_registros": 0,
            "mensaje": "Todavía no hay registros hoy.",
            "resumen_tipos": {},
            "resumen_productividad": {},
            "minutos_productivos": 0,
            "minutos_necesarios": 0,
            "minutos_perdidos": 0,
            "minutos_neutros": 0,
            "minutos_redes": 0,
            "malversadores_tiempo": [],
            "alertas": [],
            "prioridades": [],
            "recomendaciones": [],
            "actividad_mas_repetida": None,
            "contexto": {
                "tipo_dia": "sin_datos",
                "contextos_detectados": [],
                "es_exigente": False,
            },
        }

    contexto = detectar_contexto_desde_registros(registros)
    tipo_dia = contexto["tipo_dia"]
    es_exigente = contexto["es_exigente"]

    if not registros:
        return {
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "cantidad_registros": 0,
            "mensaje": "Todavía no hay registros hoy.",
            "resumen_tipos": {},
            "resumen_productividad": {},
            "minutos_productivos": 0,
            "minutos_necesarios": 0,
            "minutos_perdidos": 0,
            "minutos_neutros": 0,
            "minutos_redes": 0,
            "malversadores_tiempo": [],
            "alertas": [],
            "prioridades": [],
            "recomendaciones": [],
            "actividad_mas_repetida": None,
        }

    resumen_tipos = Counter()
    resumen_productividad = Counter()
    repeticiones = Counter()
    minutos_por_actividad = defaultdict(int)

    minutos_productivos = 0
    minutos_necesarios = 0
    minutos_perdidos = 0
    minutos_neutros = 0

    alertas = []
    recomendaciones = []
    prioridades = []

       

    minutos_redes = 0
    cantidad_actividades_perdida = 0
    cantidad_actividades_productivas = 0

    for r in registros:
        tipo = (r.get("tipo") or "sin_tipo").lower()
        productividad = (r.get("productividad") or "neutro").lower()
        nombre = normalizar_nombre_actividad(r)
        minutos = obtener_minutos(r)

        resumen_tipos[tipo] += 1
        resumen_productividad[productividad] += 1
        repeticiones[nombre] += 1
        minutos_por_actividad[nombre] += minutos

        if productividad == "productivo":
            minutos_productivos += minutos
            cantidad_actividades_productivas += 1
        elif productividad == "necesario":
            minutos_necesarios += minutos
        elif productividad == "perdida_tiempo":
            minutos_perdidos += minutos
            cantidad_actividades_perdida += 1
        else:
            minutos_neutros += minutos

        if es_actividad_de_redes(r):
            minutos_redes += minutos

    candidatas_perdida = []

    for nombre, total_min in minutos_por_actividad.items():
        if total_min <= 0:
            continue

        apariciones = 0
        apariciones_perdida = 0

        for r in registros:
            nombre_r = normalizar_nombre_actividad(r)
            productividad = (r.get("productividad") or "neutro").lower()

            if nombre_r == nombre:
                apariciones += 1
                if productividad == "perdida_tiempo":
                    apariciones_perdida += 1

        if apariciones > 0 and apariciones_perdida >= 1:
            candidatas_perdida.append({
                "actividad": nombre,
                "minutos": total_min,
                "apariciones": apariciones,
                "apariciones_perdida": apariciones_perdida,
            })

    candidatas_perdida.sort(key=lambda x: x["minutos"], reverse=True)
    malversadores_tiempo = candidatas_perdida[:5]

    actividad_mas_repetida = None
    if repeticiones:
        nombre_top, veces_top = repeticiones.most_common(1)[0]
        actividad_mas_repetida = {
            "actividad": nombre_top,
            "veces": veces_top,
            "minutos_totales": minutos_por_actividad.get(nombre_top, 0)
        }

    if minutos_redes >= UMBRAL_REDES_DIA:
        alertas.append(f"Uso elevado de redes: {minutos_redes} minutos.")

    if minutos_perdidos > minutos_productivos and minutos_perdidos >= UMBRAL_TIEMPO_PERDIDO_DIA:
        alertas.append("Hoy el tiempo perdido supera al tiempo productivo.")

    if cantidad_actividades_perdida >= 3:
        alertas.append("Hubo varias actividades clasificadas como pérdida de tiempo.")

    if minutos_productivos == 0 and len(registros) >= 3:
        if es_exigente:
            alertas.append("Todavía no registraste tiempo productivo real hoy, aunque el contexto indica que fue un día exigente.")
        else:
            alertas.append("Todavía no registraste tiempo productivo real hoy.")

    if minutos_redes >= UMBRAL_REDES_DIA:
        recomendaciones.append("Poné un límite concreto a redes sociales, por ejemplo 20 o 30 minutos por bloque.")

    if minutos_perdidos > UMBRAL_TIEMPO_PERDIDO_SEMANA:
        recomendaciones.append("Conviene cortar las distracciones largas y volver a bloques de trabajo de 25 a 40 minutos.")

    if minutos_productivos < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        if es_exigente:
            recomendaciones.append("Día exigente. Intentá rescatar aunque sea un bloque corto útil.")
        elif tipo_dia == "libre":
            recomendaciones.append("Día libre con baja productividad. Necesitás meter una tarea importante.")
        else:
            recomendaciones.append("Falta un bloque productivo fuerte. Prioridad: tarea clave.")

    if minutos_productivos >= UMBRAL_PRODUCTIVO_MUY_BUENO:
        recomendaciones.append("Buen avance productivo. Conviene cerrar el día con una tarea breve y concreta.")

    if cantidad_actividades_productivas >= 2 and minutos_perdidos < 60:
        recomendaciones.append("Vas bien. Mantené el foco y evitá abrir redes sin objetivo.")

    if not recomendaciones:
        recomendaciones.append("El día viene equilibrado. Seguí registrando para detectar patrones más claros.")

    if minutos_productivos < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        if es_exigente:
            prioridades.append("Hacer aunque sea 1 bloque útil corto antes de cerrar el día.")
        elif tipo_dia == "libre":
            prioridades.append("Hacer 1 bloque productivo importante antes de cerrar el día.")
        else:
            prioridades.append("Meter una tarea concreta y útil antes de cerrar el día.")

    if minutos_redes >= UMBRAL_REDES_DIA:
        prioridades.append("Reducir redes sociales el resto del día.")

    if minutos_perdidos > UMBRAL_TIEMPO_PERDIDO_SEMANA:
        prioridades.append("Evitar tareas dispersas y volver a una sola tarea principal.")

    if not prioridades:
        prioridades.append("Mantener el ritmo actual y cerrar una tarea concreta.")

    return {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "cantidad_registros": len(registros),
        "mensaje": "Análisis del día generado correctamente.",
        "resumen_tipos": dict(resumen_tipos),
        "resumen_productividad": dict(resumen_productividad),
        "minutos_productivos": minutos_productivos,
        "minutos_necesarios": minutos_necesarios,
        "minutos_perdidos": minutos_perdidos,
        "minutos_neutros": minutos_neutros,
        "minutos_redes": minutos_redes,
        "malversadores_tiempo": malversadores_tiempo,
        "alertas": alertas,
        "prioridades": prioridades,
        "recomendaciones": recomendaciones,
        "actividad_mas_repetida": actividad_mas_repetida,
    }


def generar_texto_modo_dueno() -> str:
    data = analizar_dia()

    if data["cantidad_registros"] == 0:
        return "Todavía no hay registros hoy para analizar."

    lineas = []
    lineas.append("📊 MODO DUEÑO")
    lineas.append(f"Fecha: {data['fecha']}")
    lineas.append(f"Registros del día: {data['cantidad_registros']}")
    if data.get("contexto"):
        lineas.append(f"Tipo de día: {data['contexto'].get('tipo_dia', 'normal')}")

    if data.get("contexto"):
        lineas.append(f"Tipo de día: {data['contexto'].get('tipo_dia', 'normal')}")
    lineas.append("")
    lineas.append("⏱ Tiempo del día:")
    lineas.append(f"- Productivo: {data['minutos_productivos']} min")
    lineas.append(f"- Necesario: {data['minutos_necesarios']} min")
    lineas.append(f"- Perdido: {data['minutos_perdidos']} min")
    lineas.append(f"- Neutro: {data['minutos_neutros']} min")
    lineas.append("")

    if data["actividad_mas_repetida"]:
        top = data["actividad_mas_repetida"]
        lineas.append("🔁 Actividad más repetida:")
        lineas.append(f"- {top['actividad']} ({top['veces']} veces, {top['minutos_totales']} min)")
        lineas.append("")

    if data["malversadores_tiempo"]:
        lineas.append("🚨 Malversadores de tiempo:")
        for item in data["malversadores_tiempo"]:
            lineas.append(f"- {item['actividad']}: {item['minutos']} min ({item['apariciones']} registros)")
        lineas.append("")

    if data["alertas"]:
        lineas.append("⚠ Alertas:")
        for alerta in data["alertas"]:
            lineas.append(f"- {alerta}")
        lineas.append("")

    lineas.append("🎯 Prioridades sugeridas:")
    for p in data["prioridades"]:
        lineas.append(f"- {p}")
    lineas.append("")

    lineas.append("🧠 Recomendaciones:")
    for r in data["recomendaciones"]:
        lineas.append(f"- {r}")

    return "\n".join(lineas)


def generar_texto_tiempo_perdido() -> str:
    data = analizar_dia()
    return f"Hoy llevás {data['minutos_perdidos']} minutos clasificados como pérdida de tiempo."


def generar_texto_tiempo_productivo() -> str:
    data = analizar_dia()
    return f"Hoy llevás {data['minutos_productivos']} minutos de tiempo productivo."


def generar_texto_prioridades() -> str:
    data = analizar_dia()

    if not data["prioridades"]:
        return "Por ahora no detecté prioridades claras."

    texto = "🎯 Prioridades sugeridas para hoy:\n"
    for p in data["prioridades"]:
        texto += f"- {p}\n"
    return texto.strip()


def generar_texto_malversadores() -> str:
    data = analizar_dia()

    if not data["malversadores_tiempo"]:
        return "Hoy no detecté malversadores de tiempo claros."

    texto = "🚨 Lo que más te está quitando tiempo hoy:\n"
    for item in data["malversadores_tiempo"]:
        texto += f"- {item['actividad']}: {item['minutos']} min\n"
    return texto.strip()




def es_consulta_modo_dueno(texto: str) -> bool:
    texto = (texto or "").strip().lower()

    disparadores = [
        "modo dueño",
        "modo dueno",
        "como vengo hoy",
        "cómo vengo hoy",
        "analiza mi dia",
        "analiza mi día",
        "analizar mi dia",
        "analizar mi día",
        "resumen inteligente",
        "estado del dia",
        "estado del día",
        "que deberia priorizar",
        "qué debería priorizar",
        "que me hace perder tiempo",
        "qué me hace perder tiempo",
        "tiempo perdido hoy",
        "tiempo productivo hoy",
    ]

    return any(d in texto for d in disparadores)


def responder_consulta_inteligente(texto: str) -> str | None:
    texto = (texto or "").strip().lower()

    if "tiempo perdido" in texto:
        return generar_texto_tiempo_perdido()

    if "tiempo productivo" in texto:
        return generar_texto_tiempo_productivo()

    if "priorizar" in texto:
        return generar_texto_prioridades()

    if "perder tiempo" in texto or "malversador" in texto:
        return generar_texto_malversadores()

    if "resumen semana" in texto or "resumen semanal" in texto:
            return generar_texto_patrones(7)

    if "patrones" in texto or "mis patrones" in texto:
        return generar_texto_patrones(7)

    if "redes esta semana" in texto or "cuanto use redes esta semana" in texto or "cuánto usé redes esta semana" in texto:
        data = analizar_patrones(7)
        return f"En los últimos 7 días registraste {data['minutos_redes']} minutos asociados a redes."

    if "en que pierdo tiempo" in texto or "en qué pierdo tiempo" in texto:
        data = analizar_patrones(7)
        return (
            f"En los últimos 7 días llevás {data['minutos_perdidos']} minutos de tiempo perdido "
            f"y {data['minutos_redes']} minutos ligados a redes."
        )
    
    if "que hago ahora" in texto or "qué hago ahora" in texto:
            return generar_texto_accion_concreta()

    if "cual es mi foco" in texto or "cuál es mi foco" in texto or "mi foco" in texto:
        return generar_texto_foco_actual()

    if "estoy disperso" in texto:
        return generar_texto_estado_actual()

    if "dame una accion concreta" in texto or "dame una acción concreta" in texto:
        return generar_texto_accion_concreta()

    if "como estoy ahora" in texto or "cómo estoy ahora" in texto:
        return generar_texto_estado_actual()

    if "estoy mejorando" in texto:
        return generar_texto_mejora_actual()

    if "como vengo comparado con antes" in texto or "cómo vengo comparado con antes" in texto:
        return generar_texto_tendencia_semanal()

    if "mi productividad mejoro" in texto or "mi productividad mejoró" in texto:
        return generar_texto_tendencia_semanal()

    if "estoy empeorando" in texto:
        return generar_texto_mejora_actual()

    if "comparacion semanal" in texto or "comparación semanal" in texto:
        return generar_texto_tendencia_semanal()

    if "tengo alertas" in texto or "alertas de la semana" in texto:
        return generar_texto_alertas()

    if "estoy en recaida" in texto or "estoy en recaída" in texto:
        return generar_texto_recaida()

    if "que me preocupa hoy" in texto or "qué me preocupa hoy" in texto:
        return generar_texto_preocupacion_actual()

    if "que corrijo primero" in texto or "qué corrijo primero" in texto:
        return generar_texto_plan_correccion()

    if "cual es mi prioridad real" in texto or "cuál es mi prioridad real" in texto:
        return generar_texto_prioridad_real()

    if "por donde empiezo" in texto or "por dónde empiezo" in texto:
        return generar_texto_por_donde_empezar()

    if "que deberia atacar ahora" in texto or "qué debería atacar ahora" in texto:
        return generar_texto_plan_correccion()

    if "que rutina me conviene hoy" in texto or "qué rutina me conviene hoy" in texto:
        return generar_texto_rutina_sugerida()

    if "armame un plan para hoy" in texto or "armame un plan hoy" in texto:
        return generar_texto_rutina_sugerida()

    if "como organizo lo que queda del dia" in texto or "cómo organizo lo que queda del día" in texto:
        return generar_texto_resto_del_dia()

    if "que hago el resto del dia" in texto or "qué hago el resto del día" in texto:
        return generar_texto_resto_del_dia()
    
    if "objetivos del dia" in texto or "objetivos del día" in texto:
        return generar_texto_objetivos_del_dia()

    if "que me falta hoy" in texto or "qué me falta hoy" in texto:
        return generar_texto_que_falta_hoy()

    if "como viene mi dia" in texto or "cómo viene mi día" in texto:
        return generar_texto_estado_del_dia()

    if "que importante falta hoy" in texto or "qué importante falta hoy" in texto:
        return generar_texto_importante_ausente()

    if "mi dia esta incompleto" in texto or "mi día está incompleto" in texto:
        return generar_texto_estado_del_dia()
    
    if "hoy estudie algo importante" in texto or "hoy estudié algo importante" in texto:
        return generar_texto_importante_ausente_detallado()

    if "mi dia se fue en cosas secundarias" in texto or "mi día se fue en cosas secundarias" in texto:
        return generar_texto_dia_secundario()

    if "cual fue mi actividad principal hoy" in texto or "cuál fue mi actividad principal hoy" in texto:
        return generar_texto_actividad_principal_hoy()

    if "hice algo importante hoy" in texto:
        return generar_texto_importante_ausente_detallado()

    if "que habito estoy formando" in texto or "qué hábito estoy formando" in texto:
        return generar_texto_habitos_reales()

    if "que habitos tengo" in texto or "qué hábitos tengo" in texto:
        return generar_texto_habitos_reales()

    if "tengo constancia en algo" in texto:
        return generar_texto_constancia()

    if "que habito perdi" in texto or "qué hábito perdí" in texto:
        return generar_texto_habitos_en_caida()

    if "memoria de habitos" in texto or "memoria de hábitos" in texto:
        return generar_texto_memoria_habitos()

    if "que habitos me ayudan" in texto or "qué hábitos me ayudan" in texto:
        return generar_texto_relaciones_habitos()

    if "las redes me estan sacando foco" in texto or "las redes me están sacando foco" in texto:
        return generar_texto_relacion_redes_foco()

    if "que horario me hace rendir mejor" in texto or "qué horario me hace rendir mejor" in texto:
        return generar_texto_relacion_horarios()

    if "cual es mi gatillo principal" in texto or "cuál es mi gatillo principal" in texto:
        return generar_texto_gatillo_principal()
    
    if "como vienen mis tendencias" in texto or "cómo vienen mis tendencias" in texto:
        return generar_texto_tendencias_multisemana()

    if "estoy recuperandome" in texto or "estoy recuperándome" in texto:
        return generar_texto_recuperacion_o_deterioro()

    if "vengo empeorando hace semanas" in texto:
        return generar_texto_recuperacion_o_deterioro()

    if "como vienen mis gastos" in texto or "cómo vienen mis gastos" in texto:
        return generar_texto_tendencia_gastos()

    if "realmente estoy mejorando" in texto:
        return generar_texto_si_estas_mejorando()
    
    if "alertas avanzadas" in texto:
        return generar_texto_alertas_avanzadas()

    if "cual es mi alerta principal" in texto or "cuál es mi alerta principal" in texto:
        return generar_texto_prioridad_alerta()

    if "vengo en racha negativa" in texto:
        return generar_texto_si_hay_racha_negativa()

    if "perdi un habito importante" in texto or "perdí un hábito importante" in texto:
        return generar_texto_habito_perdido()

    if "cual es mi problema dominante" in texto or "cuál es mi problema dominante" in texto:
        return generar_texto_problema_dominante()

    if "que tan grave estoy" in texto or "qué tan grave estoy" in texto:
        return generar_texto_gravedad_actual()

    if "decime que decision tomar ahora" in texto or "decime qué decisión tomar ahora" in texto:
        return generar_texto_decision_contextual()

    if "cual es mi mejor accion segun el contexto" in texto or "cuál es mi mejor acción según el contexto" in texto:
        return generar_texto_mejor_accion_contextual()

    if "que haria un dueño ahora" in texto or "qué haría un dueño ahora" in texto:
        return generar_texto_que_haria_un_dueno()

    if "armame un microplan serio" in texto:
        return generar_texto_microplan_serio()

    if "dame un plan de rescate" in texto:
        return generar_texto_plan_rescate()

    if "como cierro bien el dia" in texto or "cómo cierro bien el día" in texto:
        return generar_texto_cierre_dia()

    if "que objetivos minimos me quedan" in texto or "qué objetivos mínimos me quedan" in texto:
        return generar_texto_objetivos_minimos()

    if "que plan me conviene segun como vengo" in texto or "qué plan me conviene según cómo vengo" in texto:
        return generar_texto_plan_según_estado()

    if "como vienen mis finanzas" in texto or "cómo vienen mis finanzas" in texto:
        return generar_texto_finanzas_semanales()

    if "cual es mi gasto problematico" in texto or "cuál es mi gasto problemático" in texto:
        return generar_texto_gasto_problematico()

    if "gasto y desorden tienen relacion" in texto or "gasto y desorden tienen relación" in texto:
        return generar_texto_relacion_gasto_desorden()

    if "modo dueño economico" in texto or "modo dueño económico" in texto:
        return generar_texto_modo_dueno_economico()

    if "que tipo de dia fue hoy" in texto or "qué tipo de día fue hoy" in texto:
        return generar_texto_contexto_del_dia()

    if "hoy era un dia exigente" in texto or "hoy era un día exigente" in texto:
        return generar_texto_dia_exigente()

    if "mi dia fue normal o pesado" in texto or "mi día fue normal o pesado" in texto:
        return generar_texto_contexto_del_dia()

    if "ajusta el analisis por contexto" in texto or "ajusta el análisis por contexto" in texto:
        return generar_texto_lectura_contextual()

    if "como cambia el analisis si tuve facultad" in texto or "cómo cambia el análisis si tuve facultad" in texto:
        return generar_texto_lectura_contextual()

    if "como rindo segun el tipo de dia" in texto or "cómo rindo según el tipo de día" in texto:
        return generar_texto_rendimiento_por_tipo_dia()

    if "cual es mi promedio real" in texto or "cuál es mi promedio real" in texto:
        return generar_texto_memoria_historica()

    if "hoy estoy por encima o por debajo de mi nivel" in texto:
        return generar_texto_hoy_vs_mi_promedio()

    if "estoy raro respecto a mi patron" in texto or "estoy raro respecto a mi patrón" in texto:
        return generar_texto_anomalias_personales()

    if "como estoy respecto a mi base" in texto or "cómo estoy respecto a mi base" in texto:
        return generar_texto_lectura_historica_personal()

    if "como estoy respecto a mi promedio" in texto or "cómo estoy respecto a mi promedio" in texto:
        return generar_texto_hoy_vs_mi_promedio()

    if "estoy en riesgo de recaida" in texto or "estoy en riesgo de recaída" in texto:
        return generar_texto_riesgo_recaida()

    if "como puede terminar mi dia" in texto or "cómo puede terminar mi día" in texto:
        return generar_texto_cierre_probable()

    if "voy camino a un mal cierre" in texto:
        return generar_texto_cierre_probable()

    if "tengo riesgo de dispersarme" in texto:
        return generar_texto_riesgo_dispersion()

    if "que riesgo tengo ahora" in texto or "qué riesgo tengo ahora" in texto:
        return generar_texto_riesgo_actual()

    if "resumen natural" in texto or "hablame normal" in texto:
        return generar_resumen_natural_del_momento()

    if "modo dueño natural" in texto:
        return generar_respuesta_natural_modo_dueno()

    if "explicamelo simple" in texto or "explícamelo simple" in texto:
        return generar_respuesta_natural_de_estado()

    if "decimelo claro" in texto or "decímelo claro" in texto:
        return generar_respuesta_natural_de_foco()

    if "que tengo que corregir en serio" in texto or "qué tengo que corregir en serio" in texto:
        return generar_respuesta_natural_de_correccion()

    if es_consulta_modo_dueno(texto):
        return generar_texto_modo_dueno()

    return None

def obtener_registros_ultimos_dias(dias: int = 7) -> List[dict]:
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            fecha,
            texto_original,
            tipo,
            categoria,
            detalle,
            monto,
            cantidad,
            unidad,
            respuesta,
            productividad,
            duracion_minutos
        FROM registros
        WHERE fecha >= datetime('now', 'localtime', ?)
        ORDER BY fecha ASC
    """, (f"-{dias} days",))

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def analizar_patrones(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "dias_analizados": dias,
            "cantidad_registros": 0,
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "actividad_mas_repetida": None,
            "categoria_gasto_top": None,
            "minutos_productivos": 0,
            "minutos_perdidos": 0,
            "minutos_redes": 0,
            "dias_con_actividad": 0,
            "alertas": [],
            "recomendaciones": [],
        }

    repeticiones = Counter()
    gastos_por_categoria = defaultdict(float)

    minutos_productivos = 0
    minutos_perdidos = 0
    minutos_redes = 0
    fechas_con_actividad = set()

    for r in registros:
        nombre = normalizar_nombre_actividad(r)
        repeticiones[nombre] += 1

        fecha = str(r.get("fecha") or "")[:10]
        if fecha:
            fechas_con_actividad.add(fecha)

        tipo = (r.get("tipo") or "").lower()
        productividad = (r.get("productividad") or "neutro").lower()
        minutos = obtener_minutos(r)

        if tipo == "gasto":
            categoria = (r.get("categoria") or "sin_categoria").lower()
            monto = r.get("monto") or 0
            try:
                gastos_por_categoria[categoria] += float(monto)
            except Exception:
                pass

        if productividad == "productivo":
            minutos_productivos += minutos
        elif productividad == "perdida_tiempo":
            minutos_perdidos += minutos

        if es_actividad_de_redes(r):
            minutos_redes += minutos

    actividad_mas_repetida = None
    if repeticiones:
        nombre_top, veces_top = repeticiones.most_common(1)[0]
        actividad_mas_repetida = {
            "actividad": nombre_top,
            "veces": veces_top
        }

    categoria_gasto_top = None
    if gastos_por_categoria:
        categoria_top = max(gastos_por_categoria, key=gastos_por_categoria.get)
        categoria_gasto_top = {
            "categoria": categoria_top,
            "total": round(gastos_por_categoria[categoria_top], 2)
        }

    alertas = []
    recomendaciones = []

    if minutos_redes >= UMBRAL_REDES_SEMANA:
        alertas.append(f"Uso alto de redes en los últimos {dias} días: {minutos_redes} minutos.")

    if minutos_perdidos > minutos_productivos and minutos_perdidos >= UMBRAL_TIEMPO_PERDIDO_DIA:
        alertas.append("En esta etapa reciente, el tiempo perdido supera al productivo.")

    if categoria_gasto_top and categoria_gasto_top["total"] > 0:
        alertas.append(
            f"La categoría con más gasto fue {categoria_gasto_top['categoria']} (${categoria_gasto_top['total']})."
        )

    if minutos_redes >= UMBRAL_REDES_SEMANA:
        recomendaciones.append("Te conviene poner límites más concretos al uso de redes durante la semana.")

    if minutos_productivos < (UMBRAL_BLOQUE_PRODUCTIVO_MINIMO * 3):
        recomendaciones.append("Tu tiempo productivo semanal todavía es bajo. Conviene planear bloques fijos por día.")

    if minutos_perdidos > minutos_productivos:
        recomendaciones.append("Necesitás reducir distracciones repetidas y priorizar una tarea principal por bloque.")

    if len(fechas_con_actividad) >= 5:
        recomendaciones.append("Venís registrando bastante. Ya se empiezan a ver patrones útiles.")
    else:
        recomendaciones.append("Registrá más días seguidos para detectar patrones más precisos.")

    return {
        "dias_analizados": dias,
        "cantidad_registros": len(registros),
        "mensaje": f"Patrones analizados correctamente en los últimos {dias} días.",
        "actividad_mas_repetida": actividad_mas_repetida,
        "categoria_gasto_top": categoria_gasto_top,
        "minutos_productivos": minutos_productivos,
        "minutos_perdidos": minutos_perdidos,
        "minutos_redes": minutos_redes,
        "dias_con_actividad": len(fechas_con_actividad),
        "alertas": alertas,
        "recomendaciones": recomendaciones,
    }


def generar_texto_patrones(dias: int = 7) -> str:
    data = analizar_patrones(dias)

    if data["cantidad_registros"] == 0:
        return data["mensaje"]

    lineas = []
    lineas.append(f"📈 PATRONES DE LOS ÚLTIMOS {dias} DÍAS")
    lineas.append(f"Registros analizados: {data['cantidad_registros']}")
    lineas.append(f"Días con actividad: {data['dias_con_actividad']}")
    lineas.append("")

    if data["actividad_mas_repetida"]:
        lineas.append("🔁 Actividad más repetida:")
        lineas.append(
            f"- {data['actividad_mas_repetida']['actividad']} ({data['actividad_mas_repetida']['veces']} veces)"
        )
        lineas.append("")

    if data["categoria_gasto_top"]:
        lineas.append("💸 Categoría con más gasto:")
        lineas.append(
            f"- {data['categoria_gasto_top']['categoria']}: ${data['categoria_gasto_top']['total']}"
        )
        lineas.append("")

    lineas.append("⏱ Tiempo acumulado:")
    lineas.append(f"- Productivo: {data['minutos_productivos']} min")
    lineas.append(f"- Perdido: {data['minutos_perdidos']} min")
    lineas.append(f"- Redes: {data['minutos_redes']} min")
    lineas.append("")

    if data["alertas"]:
        lineas.append("⚠ Alertas:")
        for alerta in data["alertas"]:
            lineas.append(f"- {alerta}")
        lineas.append("")

    lineas.append("🧠 Recomendaciones:")
    for r in data["recomendaciones"]:
        lineas.append(f"- {r}")

    return "\n".join(lineas)

def generar_diagnostico_actual() -> Dict[str, Any]:
    contexto = detectar_contexto_desde_registros(obtener_registros_hoy())
    tipo_dia = contexto["tipo_dia"]
    es_exigente = contexto["es_exigente"]
    hoy = analizar_dia()
    semana = analizar_patrones(7)

    if hoy["cantidad_registros"] == 0:
        return {
            "estado": "sin_datos",
            "foco": "Todavía no hay suficiente información hoy.",
            "problema_principal": "Falta de registros.",
            "accion_concreta": "Empezá registrando lo primero importante que hagas hoy.",
            "mensaje_corto": "Todavía no tengo datos suficientes de hoy."
        }

    estado = "estable"
    problema_principal = "Sin problema dominante detectado."
    foco = "Mantener el ritmo."
    accion_concreta = "Seguí con una tarea concreta."
    mensaje_corto = "Venís bastante equilibrado."

    minutos_productivos = hoy["minutos_productivos"]
    minutos_perdidos = hoy["minutos_perdidos"]
    minutos_redes = hoy["minutos_redes"]

    if minutos_productivos == 0 and hoy["cantidad_registros"] >= 3:
        if es_exigente:
            estado = "esperable_por_contexto"
            mensaje_corto = "Día exigente, bajo rendimiento esperado."
        else:
            estado = "sin_foco"
            mensaje_corto = "Hoy no arrancaste fuerte."

    elif minutos_perdidos > minutos_productivos and minutos_perdidos >= 45:
        estado = "disperso"
        problema_principal = "El tiempo perdido está superando al productivo."
        foco = "Recuperar control del día."
        accion_concreta = "Cortá distracciones y elegí una sola tarea para los próximos 30 minutos."
        mensaje_corto = "Hoy estás algo disperso."

    elif minutos_redes >= 45:
        estado = "interrumpido"
        problema_principal = "Las redes están consumiendo demasiado tiempo."
        foco = "Bajar interrupciones."
        accion_concreta = "No abras redes en el próximo bloque y cerrá una tarea concreta."
        mensaje_corto = "Las redes te están sacando foco."

    elif minutos_productivos >= 90 and minutos_perdidos < 45:
        estado = "bien_encaminado"
        problema_principal = "No se detecta una traba principal."
        foco = "Consolidar el avance."
        accion_concreta = "Terminá una tarea concreta antes de cambiar de actividad."
        mensaje_corto = "Hoy venís bien encaminado."

    elif semana["minutos_perdidos"] > semana["minutos_productivos"] and semana["cantidad_registros"] > 0:
        estado = "patron_negativo"
        problema_principal = "En la semana se repite más tiempo perdido que productivo."
        foco = "Romper el patrón semanal."
        accion_concreta = "Planificá 1 bloque fijo por día para una tarea clave."
        mensaje_corto = "Ya se ve un patrón semanal que conviene corregir."

    return {
        "estado": estado,
        "foco": foco,
        "problema_principal": problema_principal,
        "accion_concreta": accion_concreta,
        "mensaje_corto": mensaje_corto
    }


def generar_texto_foco_actual() -> str:
    data = generar_diagnostico_actual()

    return (
        f"🎯 FOCO ACTUAL\n"
        f"Estado: {data['estado']}\n"
        f"Foco: {data['foco']}\n"
        f"Problema principal: {data['problema_principal']}\n"
        f"Acción concreta: {data['accion_concreta']}"
    )


def generar_texto_accion_concreta() -> str:
    data = generar_diagnostico_actual()
    return f"Tu mejor acción ahora es: {data['accion_concreta']}"


def generar_texto_estado_actual() -> str:
    data = generar_diagnostico_actual()
    return f"{data['mensaje_corto']} Problema principal: {data['problema_principal']}"

def obtener_franja_horaria(fecha_texto: str) -> str:
    """
    Divide el día en franjas simples.
    """
    try:
        dt = datetime.fromisoformat(str(fecha_texto).replace("Z", ""))
        hora = dt.hour
    except Exception:
        return "sin_horario"

    if 5 <= hora < 12:
        return "mañana"
    if 12 <= hora < 18:
        return "tarde"
    if 18 <= hora < 24:
        return "noche"
    return "madrugada"


def analizar_franjas_horarias(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "dias_analizados": dias,
            "cantidad_registros": 0,
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "franja_mas_productiva": None,
            "franja_mas_perdida": None,
            "franja_mas_redes": None,
            "detalle_franjas": {},
        }

    detalle_franjas = {
        "mañana": {"productivo": 0, "perdida_tiempo": 0, "redes": 0, "registros": 0},
        "tarde": {"productivo": 0, "perdida_tiempo": 0, "redes": 0, "registros": 0},
        "noche": {"productivo": 0, "perdida_tiempo": 0, "redes": 0, "registros": 0},
        "madrugada": {"productivo": 0, "perdida_tiempo": 0, "redes": 0, "registros": 0},
        "sin_horario": {"productivo": 0, "perdida_tiempo": 0, "redes": 0, "registros": 0},
    }

    for r in registros:
        franja = obtener_franja_horaria(r.get("fecha"))
        productividad = (r.get("productividad") or "neutro").lower()
        minutos = obtener_minutos(r)

        detalle_franjas[franja]["registros"] += 1

        if productividad == "productivo":
            detalle_franjas[franja]["productivo"] += minutos

        if productividad == "perdida_tiempo":
            detalle_franjas[franja]["perdida_tiempo"] += minutos

        if es_actividad_de_redes(r):
            detalle_franjas[franja]["redes"] += minutos

    franjas_validas = ["mañana", "tarde", "noche", "madrugada"]

    franja_mas_productiva = max(
        franjas_validas,
        key=lambda f: detalle_franjas[f]["productivo"]
    )

    franja_mas_perdida = max(
        franjas_validas,
        key=lambda f: detalle_franjas[f]["perdida_tiempo"]
    )

    franja_mas_redes = max(
        franjas_validas,
        key=lambda f: detalle_franjas[f]["redes"]
    )

    if detalle_franjas[franja_mas_productiva]["productivo"] == 0:
        franja_mas_productiva = None

    if detalle_franjas[franja_mas_perdida]["perdida_tiempo"] == 0:
        franja_mas_perdida = None

    if detalle_franjas[franja_mas_redes]["redes"] == 0:
        franja_mas_redes = None

    return {
        "dias_analizados": dias,
        "cantidad_registros": len(registros),
        "mensaje": "Franjas horarias analizadas correctamente.",
        "franja_mas_productiva": franja_mas_productiva,
        "franja_mas_perdida": franja_mas_perdida,
        "franja_mas_redes": franja_mas_redes,
        "detalle_franjas": detalle_franjas,
    }


def generar_texto_franjas_horarias(dias: int = 7) -> str:
    data = analizar_franjas_horarias(dias)

    if data["cantidad_registros"] == 0:
        return data["mensaje"]

    lineas = []
    lineas.append(f"🕒 RENDIMIENTO POR HORARIO ({dias} días)")
    lineas.append(f"Registros analizados: {data['cantidad_registros']}")
    lineas.append("")

    if data["franja_mas_productiva"]:
        lineas.append(f"✅ Franja más productiva: {data['franja_mas_productiva']}")

    if data["franja_mas_perdida"]:
        lineas.append(f"⚠ Franja con más tiempo perdido: {data['franja_mas_perdida']}")

    if data["franja_mas_redes"]:
        lineas.append(f"📱 Franja con más uso de redes: {data['franja_mas_redes']}")

    lineas.append("")
    lineas.append("Detalle por franja:")

    for franja in ["mañana", "tarde", "noche", "madrugada"]:
        info = data["detalle_franjas"][franja]
        lineas.append(
            f"- {franja}: productivo {info['productivo']} min | "
            f"perdido {info['perdida_tiempo']} min | "
            f"redes {info['redes']} min | "
            f"registros {info['registros']}"
        )

    return "\n".join(lineas)


def generar_texto_mejor_horario() -> str:
    data = analizar_franjas_horarias(7)

    if not data["franja_mas_productiva"]:
        return "Todavía no detecté una franja productiva clara."

    return f"Tu franja más productiva en los últimos 7 días fue: {data['franja_mas_productiva']}."


def generar_texto_peor_horario() -> str:
    data = analizar_franjas_horarias(7)

    if not data["franja_mas_perdida"]:
        return "Todavía no detecté una franja clara de tiempo perdido."

    return f"La franja donde más perdés tiempo es: {data['franja_mas_perdida']}."


def generar_texto_redes_noche() -> str:
    data = analizar_franjas_horarias(7)
    noche = data["detalle_franjas"].get("noche", {})

    minutos_redes_noche = noche.get("redes", 0)
    return f"En los últimos 7 días registraste {minutos_redes_noche} minutos de redes durante la noche."

def obtener_registros_rango_dias(desde_hace: int, hasta_hace: int) -> List[dict]:
    """
    Ejemplo:
    - desde_hace=7, hasta_hace=0  -> últimos 7 días
    - desde_hace=14, hasta_hace=7 -> semana anterior
    """
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            fecha,
            texto_original,
            tipo,
            categoria,
            detalle,
            monto,
            cantidad,
            unidad,
            respuesta,
            productividad,
            duracion_minutos
        FROM registros
        WHERE fecha >= datetime('now', 'localtime', ?)
          AND fecha < datetime('now', 'localtime', ?)
        ORDER BY fecha ASC
    """, (f"-{desde_hace} days", f"-{hasta_hace} days"))

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def obtener_bloques_semanales(cantidad_semanas: int = 3) -> List[Dict[str, Any]]:
    bloques = []

    for i in range(cantidad_semanas):
        desde_hace = (i + 1) * 7
        hasta_hace = i * 7

        registros = obtener_registros_rango_dias(desde_hace, hasta_hace)
        resumen = resumir_periodo(registros)

        bloques.append({
            "semana_indice": i,
            "desde_hace": desde_hace,
            "hasta_hace": hasta_hace,
            "registros": registros,
            "resumen": resumen,
        })

    return list(reversed(bloques))

def agrupar_registros_por_dia(registros: List[dict]) -> Dict[str, List[dict]]:
    agrupados = defaultdict(list)

    for r in registros:
        fecha = str(r.get("fecha") or "")[:10]
        if fecha:
            agrupados[fecha].append(r)

    return dict(agrupados)

def calcular_promedios_por_dia(registros: List[dict]) -> Dict[str, float]:
    if not registros:
        return {
            "promedio_productivo": 0.0,
            "promedio_perdido": 0.0,
            "promedio_redes": 0.0,
            "promedio_registros": 0.0,
            "dias_con_datos": 0,
        }

    agrupados = agrupar_registros_por_dia(registros)

    if not agrupados:
        return {
            "promedio_productivo": 0.0,
            "promedio_perdido": 0.0,
            "promedio_redes": 0.0,
            "promedio_registros": 0.0,
            "dias_con_datos": 0,
        }

    total_productivo = 0
    total_perdido = 0
    total_redes = 0
    total_registros = 0

    for _, regs in agrupados.items():
        resumen = resumir_dia_desde_registros(regs)
        total_productivo += resumen["productivo"]
        total_perdido += resumen["perdido"]
        total_redes += resumen["redes"]
        total_registros += resumen["cantidad_registros"]

    dias = len(agrupados)

    return {
        "promedio_productivo": round(total_productivo / dias, 2),
        "promedio_perdido": round(total_perdido / dias, 2),
        "promedio_redes": round(total_redes / dias, 2),
        "promedio_registros": round(total_registros / dias, 2),
        "dias_con_datos": dias,
    }

def resumir_dia_desde_registros(registros_dia: List[dict]) -> Dict[str, int]:
    tiempos = resumir_tiempos(registros_dia)

    return {
        "productivo": tiempos["productivo"],
        "necesario": tiempos["necesario"],
        "perdido": tiempos["perdido"],
        "neutro": tiempos["neutro"],
        "redes": tiempos["redes"],
        "cantidad_registros": len(registros_dia),    
    }

def clasificar_estado_dia_desde_registros(registros_dia: List[dict]) -> str:
    resumen = resumir_dia_desde_registros(registros_dia)

    if resumen["cantidad_registros"] == 0:
        return "sin_datos"

    if resumen["productivo"] >= UMBRAL_BLOQUE_PRODUCTIVO_MINIMO and resumen["perdido"] <= resumen["productivo"]:
        return "bueno"

    if resumen["perdido"] > resumen["productivo"] or resumen["redes"] >= UMBRAL_REDES_DIA:
        return "malo"

    return "neutro"

def resumir_periodo(registros: List[dict]) -> Dict[str, int]:

    minutos_productivos = 0
    minutos_perdidos = 0
    minutos_redes = 0

    for r in registros:
        productividad = (r.get("productividad") or "neutro").lower()
        minutos = obtener_minutos(r)

        if productividad == "productivo":
            minutos_productivos += minutos
        elif productividad == "perdida_tiempo":
            minutos_perdidos += minutos

        if es_actividad_de_redes(r):
            minutos_redes += minutos

    return {
        "productivo": minutos_productivos,
        "perdido": minutos_perdidos,
        "redes": minutos_redes,
    }


def analizar_tendencia_semanal() -> Dict[str, Any]:
    semana_reciente = obtener_registros_rango_dias(7, 0)
    semana_anterior = obtener_registros_rango_dias(14, 7)

    resumen_reciente = resumir_periodo(semana_reciente)
    resumen_anterior = resumir_periodo(semana_anterior)

    diff_productivo = resumen_reciente["productivo"] - resumen_anterior["productivo"]
    diff_perdido = resumen_reciente["perdido"] - resumen_anterior["perdido"]
    diff_redes = resumen_reciente["redes"] - resumen_anterior["redes"]

    diagnostico = []
    conclusion = "estable"

    if diff_productivo > 0:
        diagnostico.append(f"Tu tiempo productivo subió {diff_productivo} minutos.")
    elif diff_productivo < 0:
        diagnostico.append(f"Tu tiempo productivo bajó {abs(diff_productivo)} minutos.")

    if diff_perdido > 0:
        diagnostico.append(f"Tu tiempo perdido subió {diff_perdido} minutos.")
    elif diff_perdido < 0:
        diagnostico.append(f"Tu tiempo perdido bajó {abs(diff_perdido)} minutos.")

    if diff_redes > 0:
        diagnostico.append(f"El uso de redes subió {diff_redes} minutos.")
    elif diff_redes < 0:
        diagnostico.append(f"El uso de redes bajó {abs(diff_redes)} minutos.")

    if diff_productivo > 0 and diff_perdido <= 0:
        conclusion = "mejorando"
    elif diff_productivo < 0 and diff_perdido > 0:
        conclusion = "empeorando"
    elif diff_productivo == 0 and diff_perdido == 0 and diff_redes == 0:
        conclusion = "sin_cambios"

    recomendacion = "Seguí registrando para consolidar el análisis."
    if conclusion == "mejorando":
        recomendacion = "Vas mejor que la semana anterior. Conviene sostener el horario o rutina que más te funcionó."
    elif conclusion == "empeorando":
        recomendacion = "Conviene corregir esta semana con una tarea principal por día y menos distracciones."
    elif diff_redes > 0:
        recomendacion = "Se nota más consumo de redes. Ahí puede estar parte de la caída de foco."

    return {
        "conclusion": conclusion,
        "semana_reciente": resumen_reciente,
        "semana_anterior": resumen_anterior,
        "diagnostico": diagnostico,
        "recomendacion": recomendacion,
    }

def analizar_tendencias_multisemana(cantidad_semanas: int = 3) -> Dict[str, Any]:
    bloques = obtener_bloques_semanales(cantidad_semanas)

    if not bloques:
        return {
            "mensaje": "No hay datos suficientes.",
            "productividad": "sin_datos",
            "tiempo_perdido": "sin_datos",
            "redes": "sin_datos",
            "detalle": [],
        }

    detalle = []
    productivos = []
    perdidos = []
    redes = []

    for bloque in bloques:
        resumen = bloque["resumen"]
        productivos.append(resumen["productivo"])
        perdidos.append(resumen["perdido"])
        redes.append(resumen["redes"])

        detalle.append({
            "semana": f"hace {bloque['desde_hace']} a {bloque['hasta_hace']} días",
            "productivo": resumen["productivo"],
            "perdido": resumen["perdido"],
            "redes": resumen["redes"],
        })

    def clasificar_tendencia_serie(serie: List[int], invertida: bool = False) -> str:
        if len(serie) < 2:
            return "sin_datos"

        sube = serie[-1] - serie[0]

        if abs(sube) < UMBRAL_CAMBIO_RELEVANTE_MIN:
            return "estable"

        if not invertida:
            return "mejorando" if sube > 0 else "empeorando"
        else:
            return "mejorando" if sube < 0 else "empeorando"

    tendencia_productividad = clasificar_tendencia_serie(productivos, invertida=False)
    tendencia_perdido = clasificar_tendencia_serie(perdidos, invertida=True)
    tendencia_redes = clasificar_tendencia_serie(redes, invertida=True)

    return {
        "mensaje": "Tendencias multi-semana analizadas.",
        "productividad": tendencia_productividad,
        "tiempo_perdido": tendencia_perdido,
        "redes": tendencia_redes,
        "detalle": detalle,
    }

def analizar_recuperacion_o_deterioro() -> Dict[str, Any]:
    data = analizar_tendencias_multisemana(3)

    productividad = data["productividad"]
    perdido = data["tiempo_perdido"]
    redes = data["redes"]

    estado_general = "mixto"
    mensaje = "Hay señales mezcladas entre mejora y empeoramiento."

    if productividad == "mejorando" and perdido == "mejorando" and redes == "mejorando":
        estado_general = "recuperacion_sostenida"
        mensaje = "Se ve una recuperación sostenida en las últimas semanas."

    elif productividad == "empeorando" and (perdido == "empeorando" or redes == "empeorando"):
        estado_general = "deterioro_sostenido"
        mensaje = "Se ve un deterioro sostenido en las últimas semanas."

    elif productividad == "mejorando" and (perdido == "estable" or perdido == "mejorando"):
        estado_general = "mejora_parcial"
        mensaje = "Hay una mejora parcial, sobre todo en productividad."

    elif productividad == "estable" and perdido == "estable" and redes == "estable":
        estado_general = "estable"
        mensaje = "El patrón general viene bastante estable."

    return {
        "estado_general": estado_general,
        "mensaje": mensaje,
        "detalle": data,
    }

def analizar_tendencias_por_categoria_gasto() -> Dict[str, Any]:
    semana_reciente = obtener_registros_rango_dias(7, 0)
    semana_anterior = obtener_registros_rango_dias(14, 7)

    recientes = defaultdict(float)
    anteriores = defaultdict(float)

    for r in semana_reciente:
        if (r.get("tipo") or "").lower() == "gasto":
            categoria = (r.get("categoria") or "sin_categoria").lower()
            monto = r.get("monto") or 0
            try:
                recientes[categoria] += float(monto)
            except Exception:
                pass

    for r in semana_anterior:
        if (r.get("tipo") or "").lower() == "gasto":
            categoria = (r.get("categoria") or "sin_categoria").lower()
            monto = r.get("monto") or 0
            try:
                anteriores[categoria] += float(monto)
            except Exception:
                pass

    cambios = []

    categorias = set(recientes.keys()) | set(anteriores.keys())

    for categoria in categorias:
        actual = recientes.get(categoria, 0)
        anterior = anteriores.get(categoria, 0)
        diferencia = actual - anterior

        if abs(diferencia) >= UMBRAL_CAMBIO_RELEVANTE_MIN:
            cambios.append({
                "categoria": categoria,
                "anterior": anterior,
                "actual": actual,
                "diferencia": diferencia,
            })

    cambios.sort(key=lambda x: abs(x["diferencia"]), reverse=True)

    return {
        "cambios": cambios
    }

def generar_texto_tendencias_multisemana() -> str:
    data = analizar_tendencias_multisemana(3)

    lineas = []
    lineas.append("📈 TENDENCIAS MULTI-SEMANA")
    lineas.append(f"- Productividad: {data['productividad']}")
    lineas.append(f"- Tiempo perdido: {data['tiempo_perdido']}")
    lineas.append(f"- Redes: {data['redes']}")
    lineas.append("")
    lineas.append("Detalle por semana:")

    for item in data["detalle"]:
        lineas.append(
            f"- {item['semana']}: productivo {item['productivo']} | "
            f"perdido {item['perdido']} | redes {item['redes']}"
        )

    return "\n".join(lineas)


def generar_texto_recuperacion_o_deterioro() -> str:
    data = analizar_recuperacion_o_deterioro()

    return (
        f"📊 Estado general: {data['estado_general']}\n"
        f"{data['mensaje']}"
    )


def generar_texto_tendencia_gastos() -> str:
    data = analizar_tendencias_por_categoria_gasto()

    if not data["cambios"]:
        return "No detecto cambios fuertes en gastos entre la semana actual y la anterior."

    lineas = []
    lineas.append("💸 TENDENCIA DE GASTOS")
    lineas.append("")

    for item in data["cambios"][:5]:
        direccion = "subió" if item["diferencia"] > 0 else "bajó"
        lineas.append(
            f"- {item['categoria']}: {direccion} ${abs(item['diferencia'])} "
            f"(antes {item['anterior']}, ahora {item['actual']})"
        )

    return "\n".join(lineas)


def generar_texto_si_estas_mejorando() -> str:
    data = analizar_recuperacion_o_deterioro()

    if data["estado_general"] in ["recuperacion_sostenida", "mejora_parcial"]:
        return "Sí, hay señales de mejora en las últimas semanas."

    if data["estado_general"] == "deterioro_sostenido":
        return "No, en las últimas semanas se ve un deterioro bastante claro."

    if data["estado_general"] == "estable":
        return "Por ahora venís bastante estable, sin grandes cambios."

    return "Hay cambios mezclados: algunas cosas mejoran y otras no."

def analizar_habitos_en_caida() -> Dict[str, Any]:
    semana_reciente = obtener_registros_rango_dias(7, 0)
    semana_anterior = obtener_registros_rango_dias(14, 7)

    recientes = Counter()
    anteriores = Counter()

    for r in semana_reciente:
        productividad = (r.get("productividad") or "neutro").lower()
        if productividad == "productivo":
            nombre = normalizar_nombre_actividad(r)
            if nombre and nombre != "sin_detalle":
                recientes[nombre] += 1

    for r in semana_anterior:
        productividad = (r.get("productividad") or "neutro").lower()
        if productividad == "productivo":
            nombre = normalizar_nombre_actividad(r)
            if nombre and nombre != "sin_detalle":
                anteriores[nombre] += 1

    en_caida = []

    for nombre, veces_antes in anteriores.items():
        veces_ahora = recientes.get(nombre, 0)

        if veces_antes >= UMBRAL_HABITO_FORMACION and veces_ahora < veces_antes:
            en_caida.append({
                "actividad": nombre,
                "antes": veces_antes,
                "ahora": veces_ahora
            })

    en_caida.sort(key=lambda x: (x["antes"] - x["ahora"]), reverse=True)

    return {
        "habitos_en_caida": en_caida
    }


def generar_texto_habitos_en_caida() -> str:
    data = analizar_habitos_en_caida()

    if not data["habitos_en_caida"]:
        return "No detecto hábitos productivos en caída por ahora."

    lineas = []
    lineas.append("📉 HÁBITOS EN CAÍDA")
    lineas.append("")

    for item in data["habitos_en_caida"][:5]:
        lineas.append(
            f"- {item['actividad']}: pasó de {item['antes']} a {item['ahora']} registros"
        )

    return "\n".join(lineas)


def generar_texto_tendencia_semanal() -> str:
    data = analizar_tendencia_semanal()

    lineas = []
    lineas.append("📊 COMPARACIÓN SEMANAL")
    lineas.append("")
    lineas.append("Semana reciente:")
    lineas.append(f"- Productivo: {data['semana_reciente']['productivo']} min")
    lineas.append(f"- Perdido: {data['semana_reciente']['perdido']} min")
    lineas.append(f"- Redes: {data['semana_reciente']['redes']} min")
    lineas.append("")
    lineas.append("Semana anterior:")
    lineas.append(f"- Productivo: {data['semana_anterior']['productivo']} min")
    lineas.append(f"- Perdido: {data['semana_anterior']['perdido']} min")
    lineas.append(f"- Redes: {data['semana_anterior']['redes']} min")
    lineas.append("")
    lineas.append(f"Conclusión: {data['conclusion']}")

    if data["diagnostico"]:
        lineas.append("")
        lineas.append("Cambios detectados:")
        for item in data["diagnostico"]:
            lineas.append(f"- {item}")

    lineas.append("")
    lineas.append(f"Recomendación: {data['recomendacion']}")

    return "\n".join(lineas)


def generar_texto_mejora_actual() -> str:
    data = analizar_tendencia_semanal()

    if data["conclusion"] == "mejorando":
        return "Sí, venís mejorando respecto a la semana anterior."
    if data["conclusion"] == "empeorando":
        return "No, esta semana venís peor que la anterior."
    if data["conclusion"] == "sin_cambios":
        return "Por ahora no hay cambios fuertes respecto a la semana anterior."

    return "Hay cambios mezclados: algunas cosas mejoraron y otras empeoraron."

def analizar_alertas_automaticas() -> Dict[str, Any]:
    hoy = analizar_dia()
    semana = analizar_patrones(7)
    tendencia = analizar_tendencia_semanal()

    alertas = []
    nivel = "normal"

    if hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        alertas.append("Hoy todavía no registraste un bloque productivo real.")

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        alertas.append("Hoy el tiempo perdido supera al productivo.")

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        alertas.append("Hoy hay un uso alto de redes.")

    if semana["minutos_redes"] >= UMBRAL_REDES_SEMANA:
        alertas.append("Esta semana las redes vienen ocupando demasiado tiempo.")

    if semana["minutos_perdidos"] > semana["minutos_productivos"] and semana["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_SEMANA:
        alertas.append("En la semana se acumula más tiempo perdido que productivo.")

    if tendencia["conclusion"] == "empeorando":
        alertas.append("La tendencia semanal muestra empeoramiento.")

    if len(alertas) >= 4:
        nivel = "alto"
    elif len(alertas) >= 2:
        nivel = "medio"

    return {
        "nivel": nivel,
        "cantidad_alertas": len(alertas),
        "alertas": alertas,
    }


def detectar_recaida() -> Dict[str, Any]:
    hoy = analizar_dia()
    tendencia = analizar_tendencia_semanal()
    semana = analizar_patrones(7)

    en_recaida = False
    motivos = []

    if tendencia["conclusion"] == "empeorando":
        en_recaida = True
        motivos.append("La semana actual está peor que la anterior.")

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        en_recaida = True
        motivos.append("Hoy el tiempo perdido supera al productivo.")

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        en_recaida = True
        motivos.append("Hoy las redes están sacando foco.")

    if semana["minutos_redes"] >= UMBRAL_REDES_SEMANA:
        en_recaida = True
        motivos.append("En la semana hay exceso de tiempo en redes.")

    return {
        "en_recaida": en_recaida,
        "motivos": motivos
    }
    

def analizar_habitos_reales(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "habitos_formacion": [],
            "habitos_consolidados": [],
            "habitos_negativos": [],
        }

    contador_total = Counter()
    contador_productivos = Counter()
    contador_perdida = Counter()

    for r in registros:
        nombre = normalizar_nombre_actividad(r)
        productividad = (r.get("productividad") or "neutro").lower()

        if not nombre or nombre == "sin_detalle":
            continue

        contador_total[nombre] += 1

        if productividad == "productivo":
            contador_productivos[nombre] += 1
        elif productividad == "perdida_tiempo":
            contador_perdida[nombre] += 1

    habitos_formacion = []
    habitos_consolidados = []
    habitos_negativos = []

    for nombre, veces in contador_productivos.items():
        if veces >= UMBRAL_HABITO_CONSOLIDADO:
            habitos_consolidados.append({
                "actividad": nombre,
                "veces": veces,
                "tipo": "productivo"
            })
        elif veces >= UMBRAL_HABITO_FORMACION:
            habitos_formacion.append({
                "actividad": nombre,
                "veces": veces,
                "tipo": "productivo"
            })

    for nombre, veces in contador_perdida.items():
        if veces >= UMBRAL_HABITO_FORMACION:
            habitos_negativos.append({
                "actividad": nombre,
                "veces": veces,
                "tipo": "perdida_tiempo"
            })

    habitos_formacion.sort(key=lambda x: x["veces"], reverse=True)
    habitos_consolidados.sort(key=lambda x: x["veces"], reverse=True)
    habitos_negativos.sort(key=lambda x: x["veces"], reverse=True)

    return {
        "mensaje": "Hábitos analizados correctamente.",
        "habitos_formacion": habitos_formacion,
        "habitos_consolidados": habitos_consolidados,
        "habitos_negativos": habitos_negativos,
    }

def analizar_constancia_habitos(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "constancias": []
        }

    agrupados = agrupar_registros_por_dia(registros)
    apariciones_por_actividad = defaultdict(set)

    for fecha, regs in agrupados.items():
        vistos_en_ese_dia = set()

        for r in regs:
            nombre = normalizar_nombre_actividad(r)
            productividad = (r.get("productividad") or "neutro").lower()

            if productividad != "productivo":
                continue

            if nombre and nombre != "sin_detalle":
                vistos_en_ese_dia.add(nombre)

        for nombre in vistos_en_ese_dia:
            apariciones_por_actividad[nombre].add(fecha)

    constancias = []

    for nombre, fechas in apariciones_por_actividad.items():
        dias_aparece = len(fechas)
        if dias_aparece >= UMBRAL_DIAS_CONSTANCIA:
            constancias.append({
                "actividad": nombre,
                "dias": dias_aparece
            })

    constancias.sort(key=lambda x: x["dias"], reverse=True)

    return {
        "mensaje": "Constancia analizada correctamente.",
        "constancias": constancias
    }

def generar_texto_memoria_habitos() -> str:
    habitos = analizar_habitos_reales(7)
    constancia = analizar_constancia_habitos(7)
    caida = analizar_habitos_en_caida()

    lineas = []
    lineas.append("🧠 MEMORIA DE HÁBITOS")
    lineas.append("")

    if habitos["habitos_consolidados"]:
        top = habitos["habitos_consolidados"][0]
        lineas.append(f"Hábito consolidado más fuerte: {top['actividad']} ({top['veces']} veces)")
    elif habitos["habitos_formacion"]:
        top = habitos["habitos_formacion"][0]
        lineas.append(f"Hábito en formación más claro: {top['actividad']} ({top['veces']} veces)")
    else:
        lineas.append("Todavía no hay un hábito productivo fuerte.")

    if habitos["habitos_negativos"]:
        top_neg = habitos["habitos_negativos"][0]
        lineas.append(f"Hábito negativo más repetido: {top_neg['actividad']} ({top_neg['veces']} veces)")

    if constancia["constancias"]:
        top_const = constancia["constancias"][0]
        lineas.append(f"Mayor constancia: {top_const['actividad']} en {top_const['dias']} días")

    if caida["habitos_en_caida"]:
        top_caida = caida["habitos_en_caida"][0]
        lineas.append(
            f"Hábito en caída: {top_caida['actividad']} (antes {top_caida['antes']}, ahora {top_caida['ahora']})"
        )

    return "\n".join(lineas)


def generar_texto_constancia() -> str:
    data = analizar_constancia_habitos(7)

    if not data["constancias"]:
        return "Todavía no detecto constancia suficiente en hábitos productivos."

    lineas = []
    lineas.append("📅 CONSTANCIA")
    lineas.append("")

    for item in data["constancias"][:5]:
        lineas.append(f"- {item['actividad']}: apareció en {item['dias']} días")

    return "\n".join(lineas)

def generar_texto_habitos_reales() -> str:
    data = analizar_habitos_reales(7)

    lineas = []
    lineas.append("🧠 HÁBITOS DETECTADOS")
    lineas.append("")

    if data["habitos_consolidados"]:
        lineas.append("✅ Hábitos consolidados:")
        for item in data["habitos_consolidados"][:5]:
            lineas.append(f"- {item['actividad']} ({item['veces']} veces)")
        lineas.append("")

    if data["habitos_formacion"]:
        lineas.append("🌱 Hábitos en formación:")
        for item in data["habitos_formacion"][:5]:
            lineas.append(f"- {item['actividad']} ({item['veces']} veces)")
        lineas.append("")

    if data["habitos_negativos"]:
        lineas.append("⚠ Hábitos negativos repetidos:")
        for item in data["habitos_negativos"][:5]:
            lineas.append(f"- {item['actividad']} ({item['veces']} veces)")
        lineas.append("")

    if (
        not data["habitos_consolidados"]
        and not data["habitos_formacion"]
        and not data["habitos_negativos"]
    ):
        return "Todavía no detecto hábitos suficientemente repetidos."

    return "\n".join(lineas).strip()

def generar_texto_alertas() -> str:
    data = analizar_alertas_automaticas()

    if not data["alertas"]:
        return "No detecté alertas importantes por ahora."

    lineas = []
    lineas.append(f"🚨 ALERTAS ({data['nivel']})")
    lineas.append("")

    for alerta in data["alertas"]:
        lineas.append(f"- {alerta}")

    return "\n".join(lineas)


def generar_texto_recaida() -> str:
    data = detectar_recaida()

    if not data["en_recaida"]:
        return "No detecto una recaída clara por ahora."

    texto = "⚠ Detecto señales de recaída:\n"
    for motivo in data["motivos"]:
        texto += f"- {motivo}\n"
    return texto.strip()


def generar_texto_preocupacion_actual() -> str:
    alertas = analizar_alertas_automaticas()

    if not alertas["alertas"]:
        return "Por ahora no veo una preocupación fuerte. El estado general está bastante estable."

    return f"La principal preocupación actual es: {alertas['alertas'][0]}"

def generar_plan_correccion() -> Dict[str, Any]:
    hoy = analizar_dia()
    semana = analizar_patrones(7)
    alertas = analizar_alertas_automaticas()
    tendencia = analizar_tendencia_semanal()

    prioridad = "Mantener el ritmo actual."
    motivo = "No se detecta una falla dominante."
    accion = "Seguí con una tarea concreta y evitá interrupciones."
    nivel = "normal"

    if hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        prioridad = "Generar un bloque productivo real hoy."
        motivo = "Todavía no hubo foco productivo concreto."
        accion = "Hacé ahora 25 a 40 minutos de una sola tarea importante."
        nivel = "alta"

    elif hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        prioridad = "Bajar el consumo de redes."
        motivo = "Las redes están sacando foco hoy."
        accion = "Cerrá redes y no las abras durante el próximo bloque."
        nivel = "alta"

    elif hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        prioridad = "Recuperar control del día."
        motivo = "El tiempo perdido ya supera al productivo."
        accion = "Elegí una sola tarea y hacela sin cambiar de contexto."
        nivel = "alta"

    elif tendencia["conclusion"] == "empeorando":
        prioridad = "Cortar el empeoramiento semanal."
        motivo = "La semana actual viene peor que la anterior."
        accion = "Definí una tarea principal fija por día durante los próximos días."
        nivel = "media"

    elif semana["minutos_redes"] >= UMBRAL_REDES_SEMANA:
        prioridad = "Corregir el patrón semanal de redes."
        motivo = "Se está acumulando demasiado tiempo en redes."
        accion = "Poné un límite diario concreto para redes y respetalo."
        nivel = "media"

    elif alertas["nivel"] == "alto":
        prioridad = "Bajar el nivel general de alertas."
        motivo = "Hay varias señales de desorden al mismo tiempo."
        accion = "No intentes corregir todo: resolvé una sola fuente principal de dispersión."
        nivel = "alta"

    return {
        "prioridad": prioridad,
        "motivo": motivo,
        "accion": accion,
        "nivel": nivel,
    }


def generar_texto_plan_correccion() -> str:
    data = generar_plan_correccion()

    return (
        f"🛠 PLAN DE CORRECCIÓN\n"
        f"Nivel: {data['nivel']}\n"
        f"Prioridad: {data['prioridad']}\n"
        f"Motivo: {data['motivo']}\n"
        f"Acción recomendada: {data['accion']}"
    )


def generar_texto_prioridad_real() -> str:
    data = generar_plan_correccion()
    return f"Tu prioridad real ahora es: {data['prioridad']}"


def generar_texto_por_donde_empezar() -> str:
    data = generar_plan_correccion()
    return f"Empezá por esto: {data['accion']}"

def generar_rutina_sugerida() -> Dict[str, Any]:
    hoy = analizar_dia()
    diagnostico = generar_diagnostico_actual()
    correccion = generar_plan_correccion()
    alertas = analizar_alertas_automaticas()

    bloques = []
    enfoque = "equilibrado"

    if hoy["cantidad_registros"] == 0:
        bloques = [
            "Registrar la primera actividad importante del día.",
            "Hacer 1 bloque productivo de 25 a 40 minutos.",
            "Evitar redes hasta terminar ese bloque.",
        ]
        enfoque = "inicio"
    elif diagnostico["estado"] == "sin_foco":
        bloques = [
            "Hacer ahora 1 bloque productivo corto de 25 a 40 minutos.",
            "No abrir redes durante ese bloque.",
            "Después registrar cómo te fue.",
        ]
        enfoque = "arranque"
    elif diagnostico["estado"] == "disperso":
        bloques = [
            "Elegir una sola tarea concreta.",
            "Trabajar 30 minutos sin cambiar de contexto.",
            "Tomar una pausa corta de 5 minutos.",
            "Recién después decidir la siguiente acción.",
        ]
        enfoque = "recuperar_foco"
    elif diagnostico["estado"] == "interrumpido":
        bloques = [
            "Cerrar redes y dejar solo la tarea principal abierta.",
            "Hacer 1 bloque productivo.",
            "Registrar el resultado antes de volver a otra actividad.",
        ]
        enfoque = "bajar_interrupciones"
    elif diagnostico["estado"] == "bien_encaminado":
        bloques = [
            "Cerrar una tarea concreta antes de cambiar de actividad.",
            "Hacer una pausa breve.",
            "Meter un segundo bloque útil si todavía tenés energía.",
        ]
        enfoque = "consolidar"
    else:
        bloques = [
            "Elegir la tarea más importante del día.",
            "Hacer un bloque productivo sin interrupciones.",
            "Evitar multitarea.",
            "Registrar el cierre del bloque.",
        ]
        enfoque = "general"

    if alertas["nivel"] == "alto":
        bloques.append("No intentes corregir todo hoy: resolvé un solo problema principal.")

    return {
        "enfoque": enfoque,
        "prioridad": correccion["prioridad"],
        "accion_principal": correccion["accion"],
        "bloques": bloques,
    }


def generar_texto_rutina_sugerida() -> str:
    data = generar_rutina_sugerida()

    lineas = []
    lineas.append("📋 RUTINA SUGERIDA")
    lineas.append(f"Enfoque: {data['enfoque']}")
    lineas.append(f"Prioridad: {data['prioridad']}")
    lineas.append(f"Acción principal: {data['accion_principal']}")
    lineas.append("")
    lineas.append("Plan sugerido:")

    for i, bloque in enumerate(data["bloques"], start=1):
        lineas.append(f"{i}. {bloque}")

    return "\n".join(lineas)


def generar_texto_resto_del_dia() -> str:
    data = generar_rutina_sugerida()

    texto = "Para lo que queda del día te conviene esto:\n"
    for i, bloque in enumerate(data["bloques"], start=1):
        texto += f"{i}. {bloque}\n"

    return texto.strip()

def analizar_objetivos_del_dia() -> Dict[str, Any]:
    hoy = analizar_dia()
    importante = detectar_importante_ausente_hoy()

    objetivos_cumplidos = []
    objetivos_pendientes = []
    alertas_objetivos = []
    estado_dia = "neutro"

    minutos_productivos = hoy["minutos_productivos"]
    minutos_perdidos = hoy["minutos_perdidos"]
    minutos_redes = hoy["minutos_redes"]
    cantidad_registros = hoy["cantidad_registros"]

    # -----------------------------
    # Objetivo 1: hubo bloque productivo
    # -----------------------------
    if minutos_productivos >= UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        objetivos_cumplidos.append("Hubo al menos un bloque productivo real.")
    else:
        objetivos_pendientes.append("Todavía falta un bloque productivo real.")

    # -----------------------------
    # Objetivo 2: hubo bloque fuerte
    # -----------------------------
    if minutos_productivos >= UMBRAL_BLOQUE_PRODUCTIVO_FUERTE:
        objetivos_cumplidos.append("El día ya tiene un bloque productivo fuerte.")
    else:
        objetivos_pendientes.append("Todavía no aparece un bloque productivo fuerte.")

    # -----------------------------
    # Objetivo 3: no dejar que redes dominen
    # -----------------------------
    if minutos_redes < UMBRAL_REDES_DIA:
        objetivos_cumplidos.append("Las redes no dominaron el día.")
    else:
        objetivos_pendientes.append("Las redes están ocupando demasiado lugar hoy.")
        alertas_objetivos.append("El día puede desviarse por exceso de redes.")

    # -----------------------------
    # Objetivo 4: que el tiempo perdido no gane
    # -----------------------------
    if minutos_perdidos <= minutos_productivos:
        objetivos_cumplidos.append("El tiempo perdido no supera al productivo.")
    else:
        objetivos_pendientes.append("El tiempo perdido está ganando terreno.")
        alertas_objetivos.append("Hay dispersión fuerte en el día.")

    # -----------------------------
    # Objetivo 5: evitar día lleno de movimiento pero sin foco
    # -----------------------------
    if importante["dia_secundario"]:
        alertas_objetivos.append("Hubo bastante movimiento, pero sin foco productivo claro.")
        objetivos_pendientes.append("El día tiene actividad, pero todavía no una tarea importante cerrada.")

    # -----------------------------
    # Estado general del día
    # -----------------------------
    if minutos_productivos >= UMBRAL_BLOQUE_PRODUCTIVO_FUERTE and minutos_perdidos < UMBRAL_TIEMPO_PERDIDO_DIA:
        estado_dia = "bien_encaminado"
    elif minutos_productivos >= UMBRAL_BLOQUE_PRODUCTIVO_MINIMO and minutos_perdidos <= minutos_productivos:
        estado_dia = "rescatable"
    elif cantidad_registros == 0:
        estado_dia = "sin_movimiento"
    elif minutos_productivos == 0 and cantidad_registros >= 3:
        estado_dia = "incompleto"
    elif minutos_perdidos > minutos_productivos:
        estado_dia = "desordenado"
    else:
        estado_dia = "neutro"

    return {
        "estado_dia": estado_dia,
        "objetivos_cumplidos": objetivos_cumplidos,
        "objetivos_pendientes": objetivos_pendientes,
        "alertas_objetivos": alertas_objetivos,
    }

def detectar_importante_ausente_hoy() -> Dict[str, Any]:
    registros = obtener_registros_hoy()

    if not registros:
        return {
            "hay_importante": False,
            "actividad_productiva_principal": None,
            "mensaje": "Todavía no hay registros hoy.",
            "dia_secundario": False,
        }

    actividades_productivas = Counter()
    minutos_productivos = 0
    minutos_perdidos = 0
    minutos_redes = 0

    for r in registros:
        productividad = (r.get("productividad") or "neutro").lower()
        nombre = normalizar_nombre_actividad(r)
        minutos = obtener_minutos(r)

        if productividad == "productivo":
            actividades_productivas[nombre] += 1
            minutos_productivos += minutos
        elif productividad == "perdida_tiempo":
            minutos_perdidos += minutos

        if es_actividad_de_redes(r):
            minutos_redes += minutos

    actividad_productiva_principal = None
    if actividades_productivas:
        nombre_top, veces_top = actividades_productivas.most_common(1)[0]
        actividad_productiva_principal = {
            "actividad": nombre_top,
            "veces": veces_top
        }

    hay_importante = minutos_productivos >= UMBRAL_BLOQUE_PRODUCTIVO_MINIMO
    dia_secundario = (
        len(registros) >= UMBRAL_DIA_CON_MUCHOS_REGISTROS and
        minutos_productivos < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO and
        (minutos_perdidos > 0 or minutos_redes >= UMBRAL_REDES_DIA)
    )

    if not hay_importante and not actividad_productiva_principal:
        mensaje = "Hoy todavía no aparece una actividad productiva principal."
    elif not hay_importante and actividad_productiva_principal:
        mensaje = (
            f"Hay señales de actividad útil en {actividad_productiva_principal['actividad']}, "
            f"pero todavía no alcanza como bloque importante."
        )
    else:
        mensaje = "Hoy sí aparece una actividad productiva principal."

    return {
        "hay_importante": hay_importante,
        "actividad_productiva_principal": actividad_productiva_principal,
        "mensaje": mensaje,
        "dia_secundario": dia_secundario,
        "minutos_productivos": minutos_productivos,
        "minutos_perdidos": minutos_perdidos,
        "minutos_redes": minutos_redes,
    }

def generar_texto_importante_ausente_detallado() -> str:
    data = detectar_importante_ausente_hoy()

    if data["hay_importante"]:
        if data["actividad_productiva_principal"]:
            return (
                f"Hoy sí aparece algo importante: {data['actividad_productiva_principal']['actividad']}."
            )
        return "Hoy sí aparece una actividad importante."

    return data["mensaje"]


def generar_texto_dia_secundario() -> str:
    data = detectar_importante_ausente_hoy()

    if data["dia_secundario"]:
        return (
            "Sí, hoy hay señales de un día dominado por cosas secundarias: "
            "hubo movimiento, pero todavía no un bloque importante claro."
        )

    return "No veo un día dominado por cosas secundarias por ahora."


def generar_texto_actividad_principal_hoy() -> str:
    data = detectar_importante_ausente_hoy()

    if not data["actividad_productiva_principal"]:
        return "Todavía no detecto una actividad productiva principal hoy."

    act = data["actividad_productiva_principal"]
    return f"La actividad productiva más fuerte de hoy es: {act['actividad']} ({act['veces']} registros)."

def generar_texto_objetivos_del_dia() -> str:
    data = analizar_objetivos_del_dia()

    lineas = []
    lineas.append("🎯 OBJETIVOS DEL DÍA")
    lineas.append(f"Estado: {data['estado_dia']}")
    lineas.append("")

    if data["objetivos_cumplidos"]:
        lineas.append("✅ Cumplidos:")
        for item in data["objetivos_cumplidos"]:
            lineas.append(f"- {item}")
        lineas.append("")

    if data["objetivos_pendientes"]:
        lineas.append("🕒 Pendientes:")
        for item in data["objetivos_pendientes"]:
            lineas.append(f"- {item}")
        lineas.append("")

    if data["alertas_objetivos"]:
        lineas.append("⚠ Alertas:")
        for item in data["alertas_objetivos"]:
            lineas.append(f"- {item}")

    return "\n".join(lineas)


def generar_texto_que_falta_hoy() -> str:
    data = analizar_objetivos_del_dia()

    if not data["objetivos_pendientes"]:
        return "Por ahora no veo pendientes importantes. El día viene bastante cubierto."

    return f"Lo más importante que falta hoy es: {data['objetivos_pendientes'][0]}"


def generar_texto_estado_del_dia() -> str:
    data = analizar_objetivos_del_dia()

    mensajes = {
        "bien_encaminado": "Hoy el día viene bien encaminado.",
        "rescatable": "El día todavía está bastante rescatable.",
        "sin_movimiento": "Todavía no hay movimiento suficiente para evaluar el día.",
        "incompleto": "Hoy hubo actividad, pero el día sigue incompleto.",
        "desordenado": "Hoy el día viene bastante desordenado.",
        "neutro": "Hoy el día está en un punto intermedio.",
    }

    return mensajes.get(data["estado_dia"], "No pude determinar bien el estado del día.")


def generar_texto_importante_ausente() -> str:
    data = analizar_objetivos_del_dia()

    for item in data["objetivos_pendientes"]:
        if "bloque productivo" in item.lower():
            return f"Lo importante que está faltando hoy es: {item}"

    if data["objetivos_pendientes"]:
        return f"Lo importante que está faltando hoy es: {data['objetivos_pendientes'][0]}"

    return "No detecto algo importante ausente por ahora."

def analizar_relacion_habitos_y_rendimiento(dias: int = 14) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "relaciones_positivas": [],
            "relaciones_negativas": [],
        }

    agrupados = agrupar_registros_por_dia(registros)

    stats_por_actividad = defaultdict(lambda: {
        "dias_aparece": 0,
        "dias_buenos": 0,
        "dias_malos": 0,
    })

    for fecha, regs in agrupados.items():
        resumen = resumir_dia_desde_registros(regs)

        dia_bueno = resumen["productivo"] >= UMBRAL_BLOQUE_PRODUCTIVO_MINIMO and resumen["perdido"] <= resumen["productivo"]
        dia_malo = resumen["perdido"] > resumen["productivo"] or resumen["redes"] >= UMBRAL_REDES_DIA

        actividades_productivas_del_dia = set()

        for r in regs:
            productividad = (r.get("productividad") or "neutro").lower()
            nombre = normalizar_nombre_actividad(r)

            if productividad == "productivo" and nombre and nombre != "sin_detalle":
                actividades_productivas_del_dia.add(nombre)

        for actividad in actividades_productivas_del_dia:
            stats_por_actividad[actividad]["dias_aparece"] += 1
            if dia_bueno:
                stats_por_actividad[actividad]["dias_buenos"] += 1
            if dia_malo:
                stats_por_actividad[actividad]["dias_malos"] += 1

    relaciones_positivas = []
    relaciones_negativas = []

    for actividad, stats in stats_por_actividad.items():
        if stats["dias_aparece"] < UMBRAL_MIN_DIAS_RELACION:
            continue

        if stats["dias_buenos"] > stats["dias_malos"]:
            relaciones_positivas.append({
                "actividad": actividad,
                "dias_aparece": stats["dias_aparece"],
                "dias_buenos": stats["dias_buenos"],
                "dias_malos": stats["dias_malos"],
            })
        elif stats["dias_malos"] > stats["dias_buenos"]:
            relaciones_negativas.append({
                "actividad": actividad,
                "dias_aparece": stats["dias_aparece"],
                "dias_buenos": stats["dias_buenos"],
                "dias_malos": stats["dias_malos"],
            })

    relaciones_positivas.sort(key=lambda x: (x["dias_buenos"] - x["dias_malos"], x["dias_aparece"]), reverse=True)
    relaciones_negativas.sort(key=lambda x: (x["dias_malos"] - x["dias_buenos"], x["dias_aparece"]), reverse=True)

    return {
        "mensaje": "Relaciones hábito-rendimiento analizadas.",
        "relaciones_positivas": relaciones_positivas,
        "relaciones_negativas": relaciones_negativas,
    }

def analizar_relacion_redes_y_foco(dias: int = 14) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "dias_con_redes_altas": 0,
            "dias_con_redes_altas_y_bajo_foco": 0,
            "conclusion": "Sin datos suficientes."
        }

    agrupados = agrupar_registros_por_dia(registros)

    dias_con_redes_altas = 0
    dias_con_redes_altas_y_bajo_foco = 0

    for fecha, regs in agrupados.items():
        resumen = resumir_dia_desde_registros(regs)

        redes_altas = resumen["redes"] >= UMBRAL_REDES_DIA
        bajo_foco = resumen["productivo"] < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO or resumen["perdido"] > resumen["productivo"]

        if redes_altas:
            dias_con_redes_altas += 1
            if bajo_foco:
                dias_con_redes_altas_y_bajo_foco += 1

    conclusion = "No detecto una relación fuerte todavía."
    if dias_con_redes_altas >= UMBRAL_MIN_DIAS_RELACION:
        if dias_con_redes_altas_y_bajo_foco == dias_con_redes_altas:
            conclusion = "Cada vez que suben las redes, también cae el foco."
        elif dias_con_redes_altas_y_bajo_foco >= UMBRAL_MIN_DIAS_RELACION:
            conclusion = "Hay una relación bastante clara entre redes altas y bajo foco."

    return {
        "mensaje": "Relación redes-foco analizada.",
        "dias_con_redes_altas": dias_con_redes_altas,
        "dias_con_redes_altas_y_bajo_foco": dias_con_redes_altas_y_bajo_foco,
        "conclusion": conclusion,
    }

def analizar_relacion_horario_rendimiento(dias: int = 14) -> Dict[str, Any]:
    data = analizar_franjas_horarias(dias)

    if data["cantidad_registros"] == 0:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "mejor_franja": None,
            "peor_franja": None,
        }

    mejor_franja = None
    peor_franja = None
    mejor_balance = None
    peor_balance = None

    for franja in ["mañana", "tarde", "noche", "madrugada"]:
        info = data["detalle_franjas"][franja]
        balance = info["productivo"] - info["perdida_tiempo"]

        if mejor_balance is None or balance > mejor_balance:
            mejor_balance = balance
            mejor_franja = franja

        if peor_balance is None or balance < peor_balance:
            peor_balance = balance
            peor_franja = franja

    return {
        "mensaje": "Relación horario-rendimiento analizada.",
        "mejor_franja": mejor_franja,
        "peor_franja": peor_franja,
        "mejor_balance": mejor_balance,
        "peor_balance": peor_balance,
    }

def generar_texto_relaciones_habitos() -> str:
    data = analizar_relacion_habitos_y_rendimiento(14)

    if not data["relaciones_positivas"] and not data["relaciones_negativas"]:
        return "Todavía no detecto relaciones claras entre hábitos y rendimiento."

    lineas = []
    lineas.append("🔗 RELACIONES ENTRE HÁBITOS Y RENDIMIENTO")
    lineas.append("")

    if data["relaciones_positivas"]:
        lineas.append("✅ Relaciones positivas:")
        for item in data["relaciones_positivas"][:5]:
            lineas.append(
                f"- {item['actividad']}: apareció en {item['dias_buenos']} días buenos y {item['dias_malos']} malos"
            )
        lineas.append("")

    if data["relaciones_negativas"]:
        lineas.append("⚠ Relaciones negativas:")
        for item in data["relaciones_negativas"][:5]:
            lineas.append(
                f"- {item['actividad']}: apareció en {item['dias_malos']} días malos y {item['dias_buenos']} buenos"
            )

    return "\n".join(lineas).strip()


def generar_texto_relacion_redes_foco() -> str:
    data = analizar_relacion_redes_y_foco(14)

    return (
        f"📱 Redes y foco:\n"
        f"- Días con redes altas: {data['dias_con_redes_altas']}\n"
        f"- De esos, días con bajo foco: {data['dias_con_redes_altas_y_bajo_foco']}\n"
        f"- Conclusión: {data['conclusion']}"
    )


def generar_texto_relacion_horarios() -> str:
    data = analizar_relacion_horario_rendimiento(14)

    if not data["mejor_franja"] or not data["peor_franja"]:
        return "Todavía no detecto una relación clara entre horario y rendimiento."

    return (
        f"🕒 Relación horario-rendimiento:\n"
        f"- Mejor franja: {data['mejor_franja']}\n"
        f"- Peor franja: {data['peor_franja']}"
    )


def generar_texto_gatillo_principal() -> str:
    redes = analizar_relacion_redes_y_foco(14)
    horarios = analizar_relacion_horario_rendimiento(14)

    if "clara" in redes["conclusion"].lower() or "cada vez" in redes["conclusion"].lower():
        return "El gatillo principal que detecto es el exceso de redes asociado a pérdida de foco."

    if horarios["peor_franja"]:
        return f"El momento más delicado del día parece ser: {horarios['peor_franja']}."

    return "Todavía no detecto un gatillo dominante claro."

def analizar_dias_malos_seguidos(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "dias_malos_seguidos": 0,
            "hay_alerta": False,
            "fechas": []
        }

    agrupados = agrupar_registros_por_dia(registros)
    fechas_ordenadas = sorted(agrupados.keys())

    racha_actual = 0
    peor_racha = 0
    fechas_racha = []
    fechas_actuales = []

    for fecha in fechas_ordenadas:
        estado = clasificar_estado_dia_desde_registros(agrupados[fecha])

        if estado == "malo":
            racha_actual += 1
            fechas_actuales.append(fecha)
            if racha_actual > peor_racha:
                peor_racha = racha_actual
                fechas_racha = fechas_actuales.copy()
        else:
            racha_actual = 0
            fechas_actuales = []

    return {
        "dias_malos_seguidos": peor_racha,
        "hay_alerta": peor_racha >= UMBRAL_DIAS_MALOS_SEGUIDOS,
        "fechas": fechas_racha
    }

def analizar_redes_repetidas(dias: int = 7) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "dias_con_redes_altas": 0,
            "hay_alerta": False,
            "fechas": []
        }

    agrupados = agrupar_registros_por_dia(registros)
    fechas_con_redes = []

    for fecha, regs in sorted(agrupados.items()):
        resumen = resumir_dia_desde_registros(regs)
        if resumen["redes"] >= UMBRAL_REDES_DIA:
            fechas_con_redes.append(fecha)

    return {
        "dias_con_redes_altas": len(fechas_con_redes),
        "hay_alerta": len(fechas_con_redes) >= UMBRAL_DIAS_REDES_SEGUIDOS,
        "fechas": fechas_con_redes
    }

def analizar_desaparicion_habito_importante() -> Dict[str, Any]:
    memoria = analizar_habitos_reales(14)
    semana_reciente = obtener_registros_rango_dias(7, 0)

    habito_importante = None

    if memoria["habitos_consolidados"]:
        habito_importante = memoria["habitos_consolidados"][0]["actividad"]
    elif memoria["habitos_formacion"]:
        habito_importante = memoria["habitos_formacion"][0]["actividad"]

    if not habito_importante:
        return {
            "hay_alerta": False,
            "habito": None,
            "mensaje": "No hay un hábito importante identificado todavía."
        }

    apariciones_recientes = 0

    for r in semana_reciente:
        productividad = (r.get("productividad") or "neutro").lower()
        nombre = normalizar_nombre_actividad(r)

        if productividad == "productivo" and nombre == habito_importante:
            apariciones_recientes += 1

    if apariciones_recientes == 0:
        return {
            "hay_alerta": True,
            "habito": habito_importante,
            "mensaje": f"Desapareció por completo el hábito importante: {habito_importante}."
        }

    if apariciones_recientes < UMBRAL_HABITO_FORMACION:
        return {
            "hay_alerta": True,
            "habito": habito_importante,
            "mensaje": f"El hábito importante {habito_importante} cayó bastante en la semana reciente."
        }

    return {
        "hay_alerta": False,
        "habito": habito_importante,
        "mensaje": f"El hábito importante {habito_importante} sigue presente."
    }

def analizar_alertas_avanzadas() -> Dict[str, Any]:
    hoy = analizar_dia()
    semana = analizar_patrones(7)
    tendencia = analizar_recuperacion_o_deterioro()
    dias_malos = analizar_dias_malos_seguidos(7)
    redes_rep = analizar_redes_repetidas(7)
    habito = analizar_desaparicion_habito_importante()

    alertas = []

    if dias_malos["hay_alerta"]:
        alertas.append({
            "tipo": "dias_malos_seguidos",
            "nivel": "alta",
            "mensaje": f"Se detectó una racha de {dias_malos['dias_malos_seguidos']} días malos seguidos."
        })

    if redes_rep["hay_alerta"]:
        alertas.append({
            "tipo": "redes_repetidas",
            "nivel": "alta" if redes_rep["dias_con_redes_altas"] >= 4 else "media",
            "mensaje": f"Las redes aparecieron altas en {redes_rep['dias_con_redes_altas']} días recientes."
        })

    if habito["hay_alerta"]:
        alertas.append({
            "tipo": "habito_importante",
            "nivel": "alta",
            "mensaje": habito["mensaje"]
        })

    if tendencia["estado_general"] == "deterioro_sostenido":
        alertas.append({
            "tipo": "deterioro_sostenido",
            "nivel": "alta",
            "mensaje": "La tendencia general muestra deterioro sostenido."
        })

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        alertas.append({
            "tipo": "hoy_desordenado",
            "nivel": "media",
            "mensaje": "Hoy el tiempo perdido supera al productivo."
        })

    if semana["minutos_redes"] >= UMBRAL_REDES_SEMANA:
        alertas.append({
            "tipo": "redes_semana",
            "nivel": "media",
            "mensaje": "Esta semana las redes están ocupando demasiado tiempo."
        })

    puntaje = 0
    for alerta in alertas:
        if alerta["nivel"] == "alta":
            puntaje += 2
        elif alerta["nivel"] == "media":
            puntaje += 1

    nivel_general = "normal"
    if puntaje >= UMBRAL_ALERTA_ALTA_PUNTAJE:
        nivel_general = "alto"
    elif puntaje >= UMBRAL_ALERTA_MEDIA_PUNTAJE:
        nivel_general = "medio"

    alertas.sort(key=lambda x: 0 if x["nivel"] == "alta" else 1)

    prioridad_principal = alertas[0]["mensaje"] if alertas else "No detecto alertas avanzadas importantes."

    return {
        "nivel_general": nivel_general,
        "puntaje": puntaje,
        "cantidad": len(alertas),
        "prioridad_principal": prioridad_principal,
        "alertas": alertas
    }

def generar_texto_alertas_avanzadas() -> str:
    data = analizar_alertas_avanzadas()

    if not data["alertas"]:
        return "No detecto alertas avanzadas importantes por ahora."

    lineas = []
    lineas.append(f"🚨 ALERTAS AVANZADAS ({data['nivel_general']})")
    lineas.append("")
    lineas.append(f"Prioridad principal: {data['prioridad_principal']}")
    lineas.append("")

    for alerta in data["alertas"]:
        lineas.append(f"- [{alerta['nivel']}] {alerta['mensaje']}")

    return "\n".join(lineas)


def generar_texto_prioridad_alerta() -> str:
    data = analizar_alertas_avanzadas()
    return f"La alerta más importante ahora es: {data['prioridad_principal']}"


def generar_texto_si_hay_racha_negativa() -> str:
    data = analizar_dias_malos_seguidos(7)

    if not data["hay_alerta"]:
        return "No detecto una racha negativa fuerte por ahora."

    return f"Sí, detecto una racha de {data['dias_malos_seguidos']} días malos seguidos."


def generar_texto_habito_perdido() -> str:
    data = analizar_desaparicion_habito_importante()
    return data["mensaje"]

def detectar_problema_dominante() -> Dict[str, Any]:
    hoy = analizar_dia()
    semana = analizar_patrones(7)
    tendencia = analizar_recuperacion_o_deterioro()
    alertas = analizar_alertas_avanzadas()
    objetivos = analizar_objetivos_del_dia()

    candidatos = []

    if hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        candidatos.append({
            "problema": "falta_foco_real",
            "peso": 5,
            "mensaje": "Todavía no hubo un bloque productivo real."
        })

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        candidatos.append({
            "problema": "exceso_redes",
            "peso": 4,
            "mensaje": "Las redes están ocupando demasiado lugar hoy."
        })

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        candidatos.append({
            "problema": "tiempo_perdido_dominante",
            "peso": 4,
            "mensaje": "El tiempo perdido ya supera al productivo."
        })

    if semana["minutos_redes"] >= UMBRAL_REDES_SEMANA:
        candidatos.append({
            "problema": "patron_redes",
            "peso": 3,
            "mensaje": "Se está consolidando un patrón semanal de redes."
        })

    if tendencia["estado_general"] == "deterioro_sostenido":
        candidatos.append({
            "problema": "deterioro_sostenido",
            "peso": 5,
            "mensaje": "Las últimas semanas muestran deterioro sostenido."
        })

    if objetivos["estado_dia"] == "incompleto":
        candidatos.append({
            "problema": "dia_incompleto",
            "peso": 3,
            "mensaje": "El día tiene movimiento, pero todavía no algo importante."
        })

    if alertas["nivel_general"] == "alto":
        candidatos.append({
            "problema": "acumulacion_alertas",
            "peso": 4,
            "mensaje": "Hay demasiadas señales negativas al mismo tiempo."
        })

    if not candidatos:
        return {
            "problema": "sin_problema_dominante",
            "peso": 0,
            "mensaje": "No detecto un problema dominante fuerte por ahora."
        }

    candidatos.sort(key=lambda x: x["peso"], reverse=True)
    return candidatos[0]

def analizar_gravedad_actual() -> Dict[str, Any]:
    hoy = analizar_dia()
    alertas = analizar_alertas_avanzadas()
    tendencia = analizar_recuperacion_o_deterioro()

    puntaje = 0

    if hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        puntaje += 2

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        puntaje += 1

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        puntaje += 1

    if alertas["nivel_general"] == "alto":
        puntaje += 2
    elif alertas["nivel_general"] == "medio":
        puntaje += 1

    if tendencia["estado_general"] == "deterioro_sostenido":
        puntaje += 2
    elif tendencia["estado_general"] == "mejora_parcial":
        puntaje -= 1

    if puntaje >= UMBRAL_GRAVEDAD_ALTA:
        gravedad = "alta"
    elif puntaje >= UMBRAL_GRAVEDAD_MEDIA:
        gravedad = "media"
    else:
        gravedad = "baja"

    return {
        "gravedad": gravedad,
        "puntaje": puntaje
    }

def generar_decision_contextual() -> Dict[str, Any]:
    problema = detectar_problema_dominante()
    gravedad = analizar_gravedad_actual()
    diagnostico = generar_diagnostico_actual()
    horarios = analizar_relacion_horario_rendimiento(14)

    accion = "Seguí con una tarea concreta."
    estrategia = "sostener"
    justificacion = problema["mensaje"]

    if problema["problema"] == "falta_foco_real":
        accion = "Hacé ahora un bloque productivo corto y no abras redes hasta terminarlo."
        estrategia = "rescatar_dia"

    elif problema["problema"] == "exceso_redes":
        accion = "Cerrá redes y dejá solo la tarea principal abierta durante el próximo bloque."
        estrategia = "cortar_interrupciones"

    elif problema["problema"] == "tiempo_perdido_dominante":
        accion = "Volvé a una sola tarea concreta y evitá cambiar de contexto."
        estrategia = "recuperar_control"

    elif problema["problema"] == "patron_redes":
        accion = "Poné un límite explícito a redes durante los próximos días."
        estrategia = "corregir_patron"

    elif problema["problema"] == "deterioro_sostenido":
        accion = "Bajá la exigencia y definí una sola tarea principal por día hasta recuperar ritmo."
        estrategia = "frenar_caida"

    elif problema["problema"] == "dia_incompleto":
        accion = "Convertí el día en rescatable cerrando una tarea importante antes de terminar."
        estrategia = "cerrar_dia"

    elif diagnostico["estado"] == "bien_encaminado":
        accion = "Aprovechá el impulso y cerrá una tarea concreta antes de pasar a otra."
        estrategia = "consolidar"

    if gravedad["gravedad"] == "alta":
        accion += " No intentes resolver todo hoy: corregí solo lo principal."

    if horarios["mejor_franja"]:
        recomendacion_horaria = f" Tu mejor franja suele ser: {horarios['mejor_franja']}."
    else:
        recomendacion_horaria = ""

    return {
        "problema_dominante": problema["problema"],
        "mensaje_problema": problema["mensaje"],
        "gravedad": gravedad["gravedad"],
        "estrategia": estrategia,
        "accion": accion + recomendacion_horaria,
    }

def generar_texto_problema_dominante() -> str:
    data = detectar_problema_dominante()
    return f"El problema dominante ahora es: {data['mensaje']}"


def generar_texto_gravedad_actual() -> str:
    data = analizar_gravedad_actual()
    return f"La gravedad actual del momento es: {data['gravedad']}."


def generar_texto_decision_contextual() -> str:
    data = generar_decision_contextual()

    return (
        f"🧭 DECISIÓN ACTUAL\n"
        f"Problema dominante: {data['mensaje_problema']}\n"
        f"Gravedad: {data['gravedad']}\n"
        f"Estrategia: {data['estrategia']}\n"
        f"Acción: {data['accion']}"
    )


def generar_texto_mejor_accion_contextual() -> str:
    data = generar_decision_contextual()
    return f"La mejor acción ahora es: {data['accion']}"


def generar_texto_que_haria_un_dueno() -> str:
    data = generar_decision_contextual()

    return (
        f"Si lo mirás en modo dueño, no deberías atacar todo junto. "
        f"Tu foco ahora tiene que ser esto: {data['accion']}"
    )

def generar_objetivos_minimos_dia() -> Dict[str, Any]:
    hoy = analizar_dia()
    objetivos = []

    if hoy["minutos_productivos"] < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        objetivos.append("Hacer al menos un bloque productivo real.")

    if hoy["minutos_productivos"] < UMBRAL_BLOQUE_PRODUCTIVO_FUERTE:
        objetivos.append("Intentar cerrar una tarea importante antes de terminar el día.")

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        objetivos.append("No sumar más tiempo de redes salvo que sea necesario.")

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"]:
        objetivos.append("Evitar cambiar de contexto innecesariamente.")

    if not objetivos:
        objetivos.append("Mantener el foco y cerrar bien el día.")

    return {
        "objetivos": objetivos
    }

def generar_microplan_diario_serio() -> Dict[str, Any]:
    hoy = analizar_dia()
    diagnostico = generar_diagnostico_actual()
    decision = generar_decision_contextual()
    gravedad = analizar_gravedad_actual()

    tipo_plan = "general"
    bloques = []

    if gravedad["gravedad"] == "alta":
        tipo_plan = "rescate"
        bloques = [
            "Elegir una sola tarea importante.",
            "Trabajar 25 a 40 minutos sin redes ni multitarea.",
            "Tomar una pausa breve.",
            "Registrar cómo terminó ese bloque.",
            "No intentar arreglar todo hoy: solo rescatar el día."
        ]

    elif diagnostico["estado"] == "disperso":
        tipo_plan = "recuperar_foco"
        bloques = [
            "Cerrar todas las distracciones visibles.",
            "Definir una tarea concreta y acotada.",
            "Hacer un bloque corto con foco total.",
            "Evitar abrir otra tarea antes de cerrar esa."
        ]

    elif diagnostico["estado"] == "interrumpido":
        tipo_plan = "bajar_interrupciones"
        bloques = [
            "Dejar solo una ventana o tarea principal abierta.",
            "No abrir redes en el próximo bloque.",
            "Terminar una acción útil antes de revisar otra cosa."
        ]

    elif hoy["minutos_productivos"] >= UMBRAL_PLAN_CONSOLIDACION and hoy["minutos_perdidos"] < UMBRAL_TIEMPO_PERDIDO_DIA:
        tipo_plan = "consolidacion"
        bloques = [
            "Cerrar una tarea concreta importante.",
            "Tomar una pausa breve.",
            "Evaluar si queda energía para un segundo bloque útil.",
            "No regalar el cierre del día en redes."
        ]

    elif hoy["cantidad_registros"] == 0:
        tipo_plan = "inicio"
        bloques = [
            "Registrar la primera actividad importante del día.",
            "Hacer un bloque productivo corto.",
            "Evitar redes hasta completar ese bloque."
        ]

    else:
        tipo_plan = "general"
        bloques = [
            "Elegir la tarea más importante que te quede.",
            "Hacer un bloque de foco sin interrupciones.",
            "No cambiar de tarea hasta terminar una parte concreta.",
            "Cerrar el día con algo útil, aunque sea pequeño."
        ]

    return {
        "tipo_plan": tipo_plan,
        "decision_base": decision["accion"],
        "bloques": bloques,
    }

def generar_plan_cierre_dia() -> Dict[str, Any]:
    hoy = analizar_dia()

    pasos = []

    if hoy["minutos_productivos"] < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        pasos.append("Intentar un último bloque productivo corto antes de cerrar el día.")

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        pasos.append("Evitar más redes en el cierre del día.")

    pasos.append("Cerrar una tarea concreta o dejar definido el próximo paso.")
    pasos.append("Registrar cómo terminó el día.")
    pasos.append("No extender el día en cosas secundarias si ya estás cansado.")

    return {
        "pasos": pasos
    }

def generar_texto_microplan_serio() -> str:
    data = generar_microplan_diario_serio()

    lineas = []
    lineas.append("🗂 MICROPLAN DEL DÍA")
    lineas.append(f"Tipo de plan: {data['tipo_plan']}")
    lineas.append(f"Base de decisión: {data['decision_base']}")
    lineas.append("")
    lineas.append("Pasos:")

    for i, bloque in enumerate(data["bloques"], start=1):
        lineas.append(f"{i}. {bloque}")

    return "\n".join(lineas)


def generar_texto_objetivos_minimos() -> str:
    data = generar_objetivos_minimos_dia()

    lineas = []
    lineas.append("🎯 OBJETIVOS MÍNIMOS DEL DÍA")
    lineas.append("")

    for i, obj in enumerate(data["objetivos"], start=1):
        lineas.append(f"{i}. {obj}")

    return "\n".join(lineas)


def generar_texto_plan_rescate() -> str:
    data = generar_microplan_diario_serio()

    if data["tipo_plan"] != "rescate":
        return "No detecto que haga falta un plan de rescate fuerte ahora. Pero este sería tu mejor enfoque actual:\n" + "\n".join(
            [f"{i+1}. {p}" for i, p in enumerate(data["bloques"][:4])]
        )

    texto = "🛟 PLAN DE RESCATE\n"
    for i, paso in enumerate(data["bloques"], start=1):
        texto += f"{i}. {paso}\n"
    return texto.strip()


def generar_texto_cierre_dia() -> str:
    data = generar_plan_cierre_dia()

    texto = "🌙 CIERRE DEL DÍA\n"
    for i, paso in enumerate(data["pasos"], start=1):
        texto += f"{i}. {paso}\n"
    return texto.strip()


def generar_texto_plan_según_estado() -> str:
    data = generar_microplan_diario_serio()
    return generar_texto_microplan_serio()

def analizar_finanzas_semanales() -> Dict[str, Any]:
    semana_reciente = obtener_registros_rango_dias(7, 0)
    semana_anterior = obtener_registros_rango_dias(14, 7)

    resumen_reciente = resumir_gastos(semana_reciente)
    resumen_anterior = resumir_gastos(semana_anterior)

    diferencia_total = resumen_reciente["total_gastos"] - resumen_anterior["total_gastos"]

    estado = "estable"
    if diferencia_total >= UMBRAL_AUMENTO_GASTO_RELEVANTE:
        estado = "subiendo"
    elif diferencia_total <= -UMBRAL_AUMENTO_GASTO_RELEVANTE:
        estado = "bajando"

    return {
        "estado": estado,
        "semana_reciente": resumen_reciente,
        "semana_anterior": resumen_anterior,
        "diferencia_total": round(diferencia_total, 2),
    }

def detectar_gasto_problematico_recurrente(dias: int = 14) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    conteo_categorias = Counter()
    monto_categorias = defaultdict(float)

    for r in registros:
        if (r.get("tipo") or "").lower() != "gasto":
            continue

        categoria = (r.get("categoria") or "sin_categoria").lower()
        monto = r.get("monto") or 0

        try:
            monto = float(monto)
        except Exception:
            monto = 0

        conteo_categorias[categoria] += 1
        monto_categorias[categoria] += monto

    recurrentes = []

    for categoria, veces in conteo_categorias.items():
        total = monto_categorias[categoria]

        if veces >= UMBRAL_GASTO_REPETIDO or total >= UMBRAL_GASTO_RELEVANTE:
            recurrentes.append({
                "categoria": categoria,
                "veces": veces,
                "total": round(total, 2),
            })

    recurrentes.sort(key=lambda x: (x["total"], x["veces"]), reverse=True)

    return {
        "recurrentes": recurrentes
    }

def analizar_relacion_desorden_y_gasto(dias: int = 14) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "dias_desordenados_con_gasto": 0,
            "dias_desordenados": 0,
            "conclusion": "Sin datos suficientes."
        }

    agrupados = agrupar_registros_por_dia(registros)

    dias_desordenados = 0
    dias_desordenados_con_gasto = 0

    for fecha, regs in agrupados.items():
        resumen_tiempo = resumir_dia_desde_registros(regs)
        resumen_gasto = resumir_gastos(regs)

        desordenado = (
            resumen_tiempo["perdido"] > resumen_tiempo["productivo"]
            or resumen_tiempo["redes"] >= UMBRAL_REDES_DIA
        )

        if desordenado:
            dias_desordenados += 1
            if resumen_gasto["total_gastos"] > 0:
                dias_desordenados_con_gasto += 1

    conclusion = "No detecto una relación fuerte todavía."
    if dias_desordenados >= UMBRAL_MIN_DIAS_RELACION:
        if dias_desordenados_con_gasto == dias_desordenados:
            conclusion = "Cada día desordenado reciente también tuvo gasto registrado."
        elif dias_desordenados_con_gasto >= UMBRAL_MIN_DIAS_RELACION:
            conclusion = "Hay una relación bastante clara entre desorden y gasto."

    return {
        "dias_desordenados_con_gasto": dias_desordenados_con_gasto,
        "dias_desordenados": dias_desordenados,
        "conclusion": conclusion
    }

def generar_modo_dueno_economico() -> Dict[str, Any]:
    hoy = obtener_registros_hoy()
    semana = obtener_registros_ultimos_dias(7)

    gastos_hoy = resumir_gastos(hoy)
    gastos_semana = resumir_gastos(semana)
    finanzas = analizar_finanzas_semanales()
    recurrentes = detectar_gasto_problematico_recurrente(14)
    relacion = analizar_relacion_desorden_y_gasto(14)

    diagnostico = []
    prioridad = "Mantener control."
    accion = "Seguí registrando con criterio."

    if gastos_hoy["total_gastos"] > 0:
        diagnostico.append(f"Hoy llevás ${gastos_hoy['total_gastos']} en gastos.")

    if gastos_semana["categoria_top"]:
        diagnostico.append(
            f"La categoría dominante de la semana es {gastos_semana['categoria_top']['categoria']} "
            f"con ${gastos_semana['categoria_top']['total']}."
        )

    if finanzas["estado"] == "subiendo":
        diagnostico.append("El gasto semanal subió respecto a la semana anterior.")
        prioridad = "Frenar el aumento de gasto."
        accion = "Revisá primero la categoría que más creció."
    elif finanzas["estado"] == "bajando":
        diagnostico.append("El gasto semanal bajó respecto a la semana anterior.")

    if recurrentes["recurrentes"]:
        top = recurrentes["recurrentes"][0]
        diagnostico.append(
            f"El gasto más repetido/problema actual parece ser {top['categoria']} "
            f"({top['veces']} veces, ${top['total']})."
        )

    if "clara" in relacion["conclusion"].lower() or "cada día" in relacion["conclusion"].lower():
        diagnostico.append("Hay relación entre días desordenados y gastos registrados.")
        prioridad = "Cortar el desorden antes del gasto impulsivo."
        accion = "Cuando el día se desordene, evitá decisiones de gasto innecesarias."

    return {
        "diagnostico": diagnostico,
        "prioridad": prioridad,
        "accion": accion
    }

def generar_texto_finanzas_semanales() -> str:
    data = analizar_finanzas_semanales()

    return (
        f"💰 FINANZAS SEMANALES\n"
        f"- Semana reciente: ${data['semana_reciente']['total_gastos']}\n"
        f"- Semana anterior: ${data['semana_anterior']['total_gastos']}\n"
        f"- Diferencia: ${data['diferencia_total']}\n"
        f"- Estado: {data['estado']}"
    )


def generar_texto_gasto_problematico() -> str:
    data = detectar_gasto_problematico_recurrente(14)

    if not data["recurrentes"]:
        return "No detecto un gasto problemático recurrente claro por ahora."

    top = data["recurrentes"][0]
    return (
        f"El gasto más problemático/repetido parece ser {top['categoria']}, "
        f"con {top['veces']} apariciones y ${top['total']} acumulados."
    )


def generar_texto_relacion_gasto_desorden() -> str:
    data = analizar_relacion_desorden_y_gasto(14)

    return (
        f"🧾 Relación gasto-desorden:\n"
        f"- Días desordenados: {data['dias_desordenados']}\n"
        f"- Días desordenados con gasto: {data['dias_desordenados_con_gasto']}\n"
        f"- Conclusión: {data['conclusion']}"
    )


def generar_texto_modo_dueno_economico() -> str:
    data = generar_modo_dueno_economico()

    lineas = []
    lineas.append("🏦 MODO DUEÑO ECONÓMICO")
    lineas.append("")

    for item in data["diagnostico"]:
        lineas.append(f"- {item}")

    lineas.append("")
    lineas.append(f"Prioridad: {data['prioridad']}")
    lineas.append(f"Acción: {data['accion']}")

    return "\n".join(lineas)

def analizar_contexto_del_dia() -> Dict[str, Any]:
    registros_hoy = obtener_registros_hoy()
    hoy = analizar_dia()

    contexto = detectar_contexto_desde_registros(registros_hoy)

    tipo_dia = contexto["tipo_dia"]
    es_exigente = contexto["es_exigente"]

    lectura = "día normal"
    ajuste = "Evaluación estándar."
    mensaje = "No hace falta ajustar demasiado el análisis."

    if tipo_dia == "facultad":
        lectura = "día de facultad"
        ajuste = "La productividad esperable puede ser menor si hubo cursada o traslados."
        mensaje = "Si hubo menos tiempo útil hoy, no necesariamente significa mal día."

    elif tipo_dia == "trabajo":
        lectura = "día de trabajo"
        ajuste = "El análisis debería valorar más los bloques útiles cortos."
        mensaje = "En un día de trabajo, un bloque productivo corto ya tiene bastante valor."

    elif tipo_dia in {"bomberos", "guardia"}:
        lectura = "día de bomberos/guardia"
        ajuste = "El día puede ser irregular y con interrupciones externas."
        mensaje = "No conviene medir este día igual que un día libre."

    elif tipo_dia == "mixto":
        lectura = "día exigente mixto"
        ajuste = "Hubo varias exigencias en el mismo día."
        mensaje = "El análisis tiene que ser más flexible porque el contexto fue pesado."

    elif tipo_dia == "normal":
        lectura = "día normal"
        ajuste = "Se mantiene una evaluación estándar."
        mensaje = "Hoy el análisis puede ser bastante directo."

    if es_exigente and hoy["minutos_productivos"] < UMBRAL_BLOQUE_PRODUCTIVO_MINIMO:
        mensaje += " Aun así, el bajo tiempo productivo puede ser entendible por contexto."

    return {
        "tipo_dia": tipo_dia,
        "contextos_detectados": contexto["contextos_detectados"],
        "es_exigente": es_exigente,
        "lectura": lectura,
        "ajuste": ajuste,
        "mensaje": mensaje,
    }

def generar_lectura_contextual_del_dia() -> Dict[str, Any]:
    hoy = analizar_dia()
    contexto = analizar_contexto_del_dia()

    conclusion = "lectura_normal"
    interpretacion = "El día puede evaluarse de forma estándar."

    if contexto["es_exigente"]:
        if hoy["minutos_productivos"] >= UMBRAL_PLAN_MINIMO_PRODUCTIVO:
            conclusion = "buen_rendimiento_en_dia_exigente"
            interpretacion = (
                "Aunque fue un día exigente, lograste meter tiempo útil. "
                "Eso vale más que en un día normal."
            )
        elif hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
            conclusion = "dia_exigente_con_poco_foco"
            interpretacion = (
                "El día fue exigente y hubo poco foco productivo. "
                "No necesariamente es una falla grave, pero sí conviene rescatar algo útil."
            )
        else:
            conclusion = "dia_exigente_aceptable"
            interpretacion = (
                "Fue un día exigente. El rendimiento no debería medirse igual que un día libre."
            )
    else:
        if hoy["minutos_productivos"] >= UMBRAL_BLOQUE_PRODUCTIVO_FUERTE:
            conclusion = "buen_dia_normal"
            interpretacion = "Fue un buen día en términos normales."
        elif hoy["minutos_perdidos"] > hoy["minutos_productivos"]:
            conclusion = "dia_normal_desordenado"
            interpretacion = "Para un día normal, hubo bastante desorden o dispersión."
        else:
            conclusion = "dia_normal_intermedio"
            interpretacion = "Fue un día relativamente normal, sin extremos fuertes."

    return {
        "conclusion": conclusion,
        "interpretacion": interpretacion,
        "contexto": contexto,
    }

def analizar_rendimiento_por_tipo_de_dia(dias: int = 14) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "por_tipo": {}
        }

    agrupados = agrupar_registros_por_dia(registros)
    acumulado = defaultdict(lambda: {
        "dias": 0,
        "productivo": 0,
        "perdido": 0,
        "redes": 0,
    })

    for fecha, regs in agrupados.items():
        contexto = detectar_contexto_desde_registros(regs)
        tipo_dia = contexto["tipo_dia"]
        resumen = resumir_dia_desde_registros(regs)

        acumulado[tipo_dia]["dias"] += 1
        acumulado[tipo_dia]["productivo"] += resumen["productivo"]
        acumulado[tipo_dia]["perdido"] += resumen["perdido"]
        acumulado[tipo_dia]["redes"] += resumen["redes"]

    resultado = {}

    for tipo_dia, info in acumulado.items():
        dias_count = info["dias"] or 1
        resultado[tipo_dia] = {
            "dias": info["dias"],
            "promedio_productivo": round(info["productivo"] / dias_count, 2),
            "promedio_perdido": round(info["perdido"] / dias_count, 2),
            "promedio_redes": round(info["redes"] / dias_count, 2),
        }

    return {
        "mensaje": "Rendimiento por tipo de día analizado.",
        "por_tipo": dict(resultado)
    }

def generar_texto_contexto_del_dia() -> str:
    data = analizar_contexto_del_dia()

    lineas = []
    lineas.append("🗓 CONTEXTO DEL DÍA")
    lineas.append(f"Tipo de día: {data['tipo_dia']}")
    lineas.append(f"Lectura: {data['lectura']}")
    lineas.append(f"Ajuste: {data['ajuste']}")
    lineas.append(f"Mensaje: {data['mensaje']}")

    if data["contextos_detectados"]:
        lineas.append(f"Contextos detectados: {', '.join(data['contextos_detectados'])}")

    return "\n".join(lineas)


def generar_texto_dia_exigente() -> str:
    data = analizar_contexto_del_dia()

    if data["es_exigente"]:
        return f"Sí, hoy se detecta como un día exigente ({data['tipo_dia']})."

    return "No, hoy no parece un día especialmente exigente."


def generar_texto_lectura_contextual() -> str:
    data = generar_lectura_contextual_del_dia()

    return (
        f"🧠 LECTURA CONTEXTUAL\n"
        f"{data['interpretacion']}\n"
        f"Tipo de día: {data['contexto']['tipo_dia']}"
    )


def generar_texto_rendimiento_por_tipo_dia() -> str:
    data = analizar_rendimiento_por_tipo_de_dia(14)

    if not data["por_tipo"]:
        return "Todavía no hay suficiente información para comparar tipos de día."

    lineas = []
    lineas.append("📊 RENDIMIENTO SEGÚN TIPO DE DÍA")
    lineas.append("")

    for tipo_dia, info in data["por_tipo"].items():
        lineas.append(
            f"- {tipo_dia}: {info['dias']} días | "
            f"promedio productivo {info['promedio_productivo']} min | "
            f"promedio perdido {info['promedio_perdido']} min | "
            f"promedio redes {info['promedio_redes']} min"
        )

    return "\n".join(lineas)

def analizar_memoria_historica_base(dias: int = DIAS_MEMORIA_HISTORICA) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "base": {
                "promedio_productivo": 0.0,
                "promedio_perdido": 0.0,
                "promedio_redes": 0.0,
                "promedio_registros": 0.0,
                "dias_con_datos": 0,
            }
        }

    base = calcular_promedios_por_dia(registros)

    return {
        "mensaje": "Base histórica calculada correctamente.",
        "base": base
    }

def comparar_hoy_con_mi_base() -> Dict[str, Any]:
    hoy_regs = obtener_registros_hoy()
    base = analizar_memoria_historica_base(DIAS_MEMORIA_HISTORICA)["base"]

    resumen_hoy = resumir_dia_desde_registros(hoy_regs) if hoy_regs else {
        "productivo": 0,
        "perdido": 0,
        "redes": 0,
        "cantidad_registros": 0,
    }

    diff_productivo = resumen_hoy["productivo"] - base["promedio_productivo"]
    diff_perdido = resumen_hoy["perdido"] - base["promedio_perdido"]
    diff_redes = resumen_hoy["redes"] - base["promedio_redes"]

    lectura = []

    if diff_productivo >= UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy estás por encima de tu promedio productivo.")
    elif diff_productivo <= -UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy estás por debajo de tu promedio productivo.")

    if diff_perdido >= UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy el tiempo perdido está por encima de tu nivel habitual.")
    elif diff_perdido <= -UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy el tiempo perdido está por debajo de tu nivel habitual.")

    if diff_redes >= UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy el uso de redes está por encima de tu promedio.")
    elif diff_redes <= -UMBRAL_DESVIO_RELEVANTE:
        lectura.append("Hoy el uso de redes está por debajo de tu promedio.")

    if not lectura:
        lectura.append("Hoy viene bastante parecido a tu patrón normal.")

    return {
        "resumen_hoy": resumen_hoy,
        "base": base,
        "diff_productivo": round(diff_productivo, 2),
        "diff_perdido": round(diff_perdido, 2),
        "diff_redes": round(diff_redes, 2),
        "lectura": lectura,
    }

def detectar_anomalias_personales() -> Dict[str, Any]:
    comp = comparar_hoy_con_mi_base()
    anomalias = []

    if comp["diff_productivo"] <= -UMBRAL_DESVIO_RELEVANTE:
        anomalias.append("Productividad anormalmente baja respecto a tu promedio.")

    if comp["diff_perdido"] >= UMBRAL_DESVIO_RELEVANTE:
        anomalias.append("Tiempo perdido anormalmente alto respecto a tu promedio.")

    if comp["diff_redes"] >= UMBRAL_DESVIO_RELEVANTE:
        anomalias.append("Uso de redes anormalmente alto respecto a tu promedio.")

    if comp["diff_productivo"] >= UMBRAL_DESVIO_RELEVANTE:
        anomalias.append("Productividad por encima de lo habitual.")

    return {
        "hay_anomalias": len(anomalias) > 0,
        "anomalias": anomalias
    }

def analizar_memoria_por_franja(dias: int = DIAS_MEMORIA_HISTORICA) -> Dict[str, Any]:
    registros = obtener_registros_ultimos_dias(dias)

    if not registros:
        return {
            "mensaje": f"No hay registros en los últimos {dias} días.",
            "franjas": {}
        }

    acumulado = defaultdict(lambda: {
        "productivo": 0,
        "perdido": 0,
        "redes": 0,
        "registros": 0,
    })

    for r in registros:
        franja = obtener_franja_horaria(r.get("fecha"))
        minutos = obtener_minutos(r)
        productividad = (r.get("productividad") or "neutro").lower()

        acumulado[franja]["registros"] += 1

        if productividad == "productivo":
            acumulado[franja]["productivo"] += minutos
        elif productividad == "perdida_tiempo":
            acumulado[franja]["perdido"] += minutos

        if es_actividad_de_redes(r):
            acumulado[franja]["redes"] += minutos

    return {
        "mensaje": "Memoria por franja calculada.",
        "franjas": dict(acumulado)
    }

def generar_lectura_historica_personal() -> Dict[str, Any]:
    base = analizar_memoria_historica_base(DIAS_MEMORIA_HISTORICA)["base"]
    hoy = comparar_hoy_con_mi_base()
    anomalias = detectar_anomalias_personales()

    conclusion = "estable"
    mensaje = "Hoy estás dentro de un rango bastante normal para vos."

    if anomalias["hay_anomalias"]:
        if any("Productividad anormalmente baja" in a for a in anomalias["anomalias"]):
            conclusion = "por_debajo_de_tu_base"
            mensaje = "Hoy estás rindiendo por debajo de tu estándar personal."
        elif any("Tiempo perdido anormalmente alto" in a for a in anomalias["anomalias"]):
            conclusion = "desviado_por_distraccion"
            mensaje = "Hoy te estás desviando por encima de tu nivel normal de distracción."
        elif any("Productividad por encima" in a for a in anomalias["anomalias"]):
            conclusion = "por_encima_de_tu_base"
            mensaje = "Hoy venís mejor que tu estándar habitual."

    return {
        "conclusion": conclusion,
        "mensaje": mensaje,
        "base": base,
        "comparacion_hoy": hoy,
        "anomalias": anomalias,
    }

def generar_texto_memoria_historica() -> str:
    data = analizar_memoria_historica_base(DIAS_MEMORIA_HISTORICA)
    base = data["base"]

    return (
        f"🧠 MEMORIA HISTÓRICA\n"
        f"- Días con datos: {base['dias_con_datos']}\n"
        f"- Promedio productivo: {base['promedio_productivo']} min\n"
        f"- Promedio perdido: {base['promedio_perdido']} min\n"
        f"- Promedio redes: {base['promedio_redes']} min\n"
        f"- Promedio de registros: {base['promedio_registros']}"
    )


def generar_texto_hoy_vs_mi_promedio() -> str:
    data = comparar_hoy_con_mi_base()

    lineas = []
    lineas.append("📊 HOY VS TU PROMEDIO")
    lineas.append(f"- Diferencia productiva: {data['diff_productivo']} min")
    lineas.append(f"- Diferencia tiempo perdido: {data['diff_perdido']} min")
    lineas.append(f"- Diferencia redes: {data['diff_redes']} min")
    lineas.append("")

    for item in data["lectura"]:
        lineas.append(f"- {item}")

    return "\n".join(lineas)


def generar_texto_anomalias_personales() -> str:
    data = detectar_anomalias_personales()

    if not data["hay_anomalias"]:
        return "No detecto anomalías fuertes respecto a tu promedio personal."

    texto = "⚠ ANOMALÍAS PERSONALES\n"
    for item in data["anomalias"]:
        texto += f"- {item}\n"
    return texto.strip()


def generar_texto_lectura_historica_personal() -> str:
    data = generar_lectura_historica_personal()

    return (
        f"📌 LECTURA PERSONAL\n"
        f"{data['mensaje']}\n"
        f"Conclusión: {data['conclusion']}"
    )

def predecir_riesgo_recaida() -> Dict[str, Any]:
    hoy = analizar_dia()
    tendencia = analizar_recuperacion_o_deterioro()
    alertas = analizar_alertas_avanzadas()
    memoria = comparar_hoy_con_mi_base()

    puntaje = 0
    motivos = []

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        puntaje += 1
        motivos.append("Hoy ya hay exceso de redes.")

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_perdidos"] >= UMBRAL_TIEMPO_PERDIDO_DIA:
        puntaje += 1
        motivos.append("Hoy el tiempo perdido supera al productivo.")

    if tendencia["estado_general"] == "deterioro_sostenido":
        puntaje += 2
        motivos.append("Venís en deterioro sostenido.")

    if alertas["nivel_general"] == "alto":
        puntaje += 1
        motivos.append("Hay acumulación fuerte de alertas.")

    if memoria["diff_redes"] >= UMBRAL_DESVIO_RELEVANTE:
        puntaje += 1
        motivos.append("Hoy el uso de redes está por encima de tu promedio.")

    if puntaje >= UMBRAL_RIESGO_ALTO:
        riesgo = "alto"
    elif puntaje >= UMBRAL_RIESGO_MEDIO:
        riesgo = "medio"
    else:
        riesgo = "bajo"

    return {
        "riesgo": riesgo,
        "puntaje": puntaje,
        "motivos": motivos
    }

def predecir_cierre_del_dia() -> Dict[str, Any]:
    hoy = analizar_dia()
    contexto = analizar_contexto_del_dia()
    memoria = comparar_hoy_con_mi_base()

    estado_probable = "intermedio"
    mensaje = "El día todavía está abierto y puede inclinarse para cualquiera de los dos lados."

    if hoy["minutos_productivos"] >= UMBRAL_BLOQUE_PRODUCTIVO_FUERTE and hoy["minutos_perdidos"] < UMBRAL_TIEMPO_PERDIDO_DIA:
        estado_probable = "buen_cierre"
        mensaje = "Si sostenés el foco, el día tiene buenas chances de cerrar bien."

    elif hoy["minutos_perdidos"] > hoy["minutos_productivos"] and hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        estado_probable = "cierre_desordenado"
        mensaje = "Si seguís igual, el día probablemente cierre desordenado."

    elif hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        estado_probable = "cierre_flojo"
        mensaje = "Si no aparece un bloque útil pronto, el día puede terminar flojo."

    elif contexto["es_exigente"] and hoy["minutos_productivos"] >= UMBRAL_PLAN_MINIMO_PRODUCTIVO:
        estado_probable = "cierre_aceptable"
        mensaje = "Para un día exigente, todavía puede cerrar aceptablemente."

    elif memoria["diff_productivo"] <= -UMBRAL_DESVIO_RELEVANTE:
        estado_probable = "por_debajo_de_lo_habitual"
        mensaje = "Hoy viene por debajo de tu nivel habitual y eso puede afectar el cierre."

    return {
        "estado_probable": estado_probable,
        "mensaje": mensaje
    }

def predecir_riesgo_dispersion() -> Dict[str, Any]:
    hoy = analizar_dia()
    decision = generar_decision_contextual()
    memoria = comparar_hoy_con_mi_base()

    puntaje = 0
    motivos = []

    if hoy["minutos_redes"] >= UMBRAL_REDES_DIA:
        puntaje += 1
        motivos.append("Hay redes altas hoy.")

    if hoy["minutos_perdidos"] > hoy["minutos_productivos"]:
        puntaje += 1
        motivos.append("El tiempo perdido va ganando.")

    if memoria["diff_redes"] >= UMBRAL_DESVIO_RELEVANTE:
        puntaje += 1
        motivos.append("Las redes hoy están por encima de tu patrón habitual.")

    if decision["problema_dominante"] in {"exceso_redes", "tiempo_perdido_dominante", "acumulacion_alertas"}:
        puntaje += 1
        motivos.append("El problema dominante actual favorece la dispersión.")

    if puntaje >= UMBRAL_RIESGO_ALTO:
        riesgo = "alto"
    elif puntaje >= UMBRAL_RIESGO_MEDIO:
        riesgo = "medio"
    else:
        riesgo = "bajo"

    return {
        "riesgo": riesgo,
        "puntaje": puntaje,
        "motivos": motivos
    }

def generar_lectura_predictiva() -> Dict[str, Any]:
    recaida = predecir_riesgo_recaida()
    cierre = predecir_cierre_del_dia()
    dispersion = predecir_riesgo_dispersion()

    foco_principal = "sostener"
    mensaje = "El escenario actual es bastante manejable."

    if recaida["riesgo"] == "alto":
        foco_principal = "evitar_recaida"
        mensaje = "Ahora mismo la prioridad es no profundizar una recaída."

    elif dispersion["riesgo"] == "alto":
        foco_principal = "evitar_dispersion"
        mensaje = "Hay bastante riesgo de dispersión si no cerrás el contexto."

    elif cierre["estado_probable"] == "cierre_desordenado":
        foco_principal = "rescatar_cierre"
        mensaje = "Conviene rescatar el cierre del día antes de que se desordene más."

    elif cierre["estado_probable"] == "buen_cierre":
        foco_principal = "consolidar"
        mensaje = "Si sostenés un poco más el foco, el día puede cerrar bien."

    return {
        "foco_principal": foco_principal,
        "mensaje": mensaje,
        "recaida": recaida,
        "cierre": cierre,
        "dispersion": dispersion,
    }

def generar_texto_riesgo_recaida() -> str:
    data = predecir_riesgo_recaida()

    lineas = []
    lineas.append(f"🔮 Riesgo de recaída: {data['riesgo']}")
    if data["motivos"]:
        lineas.append("Motivos:")
        for m in data["motivos"]:
            lineas.append(f"- {m}")

    return "\n".join(lineas)


def generar_texto_cierre_probable() -> str:
    data = predecir_cierre_del_dia()

    return (
        f"🌙 Cierre probable del día: {data['estado_probable']}\n"
        f"{data['mensaje']}"
    )


def generar_texto_riesgo_dispersion() -> str:
    data = predecir_riesgo_dispersion()

    lineas = []
    lineas.append(f"🌀 Riesgo de dispersión: {data['riesgo']}")
    if data["motivos"]:
        lineas.append("Motivos:")
        for m in data["motivos"]:
            lineas.append(f"- {m}")

    return "\n".join(lineas)


def generar_texto_riesgo_actual() -> str:
    data = generar_lectura_predictiva()

    return (
        f"📍 Riesgo actual\n"
        f"Foco principal: {data['foco_principal']}\n"
        f"{data['mensaje']}"
    )

def generar_resumen_natural_del_momento() -> str:
    diagnostico = generar_diagnostico_actual()
    decision = generar_decision_contextual()
    riesgo = generar_lectura_predictiva()

    mensaje_principal = diagnostico["mensaje_corto"]
    detalle = f"Problema dominante: {decision['mensaje_problema']}"
    sugerencia = decision["accion"]

    return construir_respuesta_natural(
        mensaje_principal=mensaje_principal,
        detalle=detalle,
        sugerencia=sugerencia,
    )


def generar_respuesta_natural_modo_dueno() -> str:
    contexto = analizar_contexto_del_dia()
    decision = generar_decision_contextual()
    riesgo = generar_lectura_predictiva()

    mensaje_principal = (
        f"El foco ahora no es resolver todo, sino atacar lo que más pesa: {decision['mensaje_problema']}"
    )

    detalle = (
        f"Tipo de día: {contexto['tipo_dia']}. "
        f"Riesgo actual: {riesgo['foco_principal']}."
    )

    sugerencia = decision["accion"]

    return construir_respuesta_natural(
        mensaje_principal=mensaje_principal,
        detalle=detalle,
        sugerencia=sugerencia,
        tono="ejecutivo",
    )


def generar_respuesta_natural_de_estado() -> str:
    lectura = generar_lectura_historica_personal()
    cierre = predecir_cierre_del_dia()

    mensaje_principal = lectura["mensaje"]
    detalle = f"Cierre probable: {cierre['estado_probable']}."
    sugerencia = cierre["mensaje"]

    return construir_respuesta_natural(
        mensaje_principal=mensaje_principal,
        detalle=detalle,
        sugerencia=sugerencia,
    )

def generar_respuesta_natural_de_foco() -> str:
    decision = generar_decision_contextual()

    return construir_respuesta_natural(
        mensaje_principal=f"Tu foco real ahora debería ser: {decision['estrategia']}.",
        detalle=f"Problema dominante: {decision['mensaje_problema']}",
        sugerencia=decision["accion"],
    )


def generar_respuesta_natural_de_correccion() -> str:
    correccion = generar_plan_correccion()

    return construir_respuesta_natural(
        mensaje_principal=f"La prioridad es corregir esto: {correccion['prioridad']}",
        detalle=correccion["motivo"],
        sugerencia=correccion["accion"],
        tono="correctivo" if correccion["nivel"] == "alta" else None,
    )

def generar_lectura_con_contexto_externo(contexto: Dict[str, Any]) -> Dict[str, Any]:
    hoy = analizar_dia()

    tipo_dia = contexto.get("tipo_dia", "normal")
    eventos = contexto.get("eventos", [])
    es_exigente = contexto.get("es_exigente", False)

    lectura = "Evaluación estándar."
    ajuste = "Sin ajuste especial."
    mensaje = "El día puede leerse con criterios normales."

    if tipo_dia == "facultad":
        lectura = "Día de facultad."
        ajuste = "La productividad esperable puede ser menor por cursada o traslados."
        mensaje = "Si hoy hubo menos tiempo útil, no necesariamente significa mal rendimiento."

    elif tipo_dia == "trabajo":
        lectura = "Día de trabajo."
        ajuste = "Conviene valorar más los bloques útiles cortos."
        mensaje = "En un día de trabajo, un bloque corto de foco ya tiene valor."

    elif tipo_dia in {"bomberos", "guardia"}:
        lectura = "Día de guardia o bomberos."
        ajuste = "Puede haber interrupciones externas y menos control del tiempo."
        mensaje = "Este día no conviene medirlo igual que un día libre."

    elif tipo_dia == "mixto":
        lectura = "Día mixto o exigente."
        ajuste = "Hubo más de una exigencia importante."
        mensaje = "El análisis debe ser más flexible por el contexto."

    if es_exigente and hoy["minutos_productivos"] >= UMBRAL_PLAN_MINIMO_PRODUCTIVO:
        mensaje += " Aun así, lograste sostener algo útil."

    if es_exigente and hoy["minutos_productivos"] == 0 and hoy["cantidad_registros"] >= 3:
        mensaje += " Hoy faltó foco, pero el contexto también pesó."

    return {
        "tipo_dia": tipo_dia,
        "eventos": eventos,
        "es_exigente": es_exigente,
        "lectura": lectura,
        "ajuste": ajuste,
        "mensaje": mensaje,
    }

def generar_texto_con_contexto_externo(contexto: Dict[str, Any]) -> str:
    data = generar_lectura_con_contexto_externo(contexto)

    lineas = []
    lineas.append("🌐 CONTEXTO EXTERNO")
    lineas.append(f"Tipo de día: {data['tipo_dia']}")
    lineas.append(f"Lectura: {data['lectura']}")
    lineas.append(f"Ajuste: {data['ajuste']}")
    lineas.append(f"Mensaje: {data['mensaje']}")

    if data["eventos"]:
        lineas.append("Eventos:")
        for evento in data["eventos"]:
            lineas.append(f"- {evento}")

    return "\n".join(lineas)