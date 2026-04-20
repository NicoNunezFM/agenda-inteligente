import html

from app.parser import obtener_filtro_fecha


def generar_respuesta_registro(datos: dict):
    tipo = datos.get("tipo")
    categoria = datos.get("categoria")
    monto = datos.get("monto")
    cantidad = datos.get("cantidad")
    unidad = datos.get("unidad")
    duracion = datos.get("duracion_minutos")

    if tipo == "gasto":
        if monto is not None:
            return f"Anotado. Gastaste ${monto} en {categoria}."
        return f"Anotado. Registré un gasto en {categoria}."

    if tipo == "ingreso":
        if monto is not None:
            return f"Perfecto. Registré un ingreso de ${monto}."
        return "Perfecto. Registré un ingreso."

    if tipo == "habito":
        if duracion:
            horas = duracion // 60
            minutos = duracion % 60
            if horas > 0:
                return f"Registré tu hábito: {categoria} por {horas}h {minutos}min."
            return f"Registré tu hábito: {categoria} por {minutos} minutos."

        if cantidad is not None:
            return f"Registré tu hábito: {categoria}. Cantidad: {cantidad} {unidad or ''}".strip()

        return f"Registré tu hábito: {categoria}."

    if tipo == "actividad":
        if duracion:
            horas = duracion // 60
            minutos = duracion % 60
            if horas > 0:
                return f"Actividad registrada: {categoria} por {horas}h {minutos}min."
            return f"Actividad registrada: {categoria} por {minutos} minutos."

        if cantidad is not None:
            return f"Actividad registrada: {categoria}. Cantidad: {cantidad} {unidad or ''}".strip()

        return f"Actividad registrada: {categoria}."

    return "Nota guardada."


def generar_consejo_dueno(cursor):
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM registros
        WHERE tipo = 'ingreso'
    """)
    ingresos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM registros
        WHERE tipo = 'gasto'
    """)
    gastos = cursor.fetchone()[0] or 0

    balance = ingresos - gastos

    cursor.execute("""
        SELECT categoria, COALESCE(SUM(monto), 0) as total
        FROM registros
        WHERE tipo = 'gasto'
        GROUP BY categoria
        ORDER BY total DESC
        LIMIT 1
    """)
    mayor_gasto = cursor.fetchone()

    cursor.execute("""
        SELECT COALESCE(SUM(duracion_minutos), 0)
        FROM registros
        WHERE productividad = 'productivo'
    """)
    tiempo_productivo = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(duracion_minutos), 0)
        FROM registros
        WHERE productividad = 'perdida_tiempo'
    """)
    tiempo_perdido = cursor.fetchone()[0] or 0

    mensajes = []

    if ingresos == 0 and gastos > 0:
        mensajes.append("Todavía no registraste ingresos, pero sí gastos.")
    elif ingresos > 0 and gastos == 0:
        mensajes.append("Tenés ingresos registrados y ningún gasto cargado.")
    elif ingresos == 0 and gastos == 0:
        mensajes.append("Todavía no hay movimientos suficientes para analizar.")
    else:
        if balance > 0:
            mensajes.append(f"Tu balance actual es positivo: ${balance}.")
        elif balance < 0:
            mensajes.append(f"Atención: tu balance actual es negativo: ${balance}.")
        else:
            mensajes.append("Tu balance actual está en cero.")

    if mayor_gasto:
        categoria, total = mayor_gasto
        mensajes.append(f"Tu categoría con más gasto es {categoria}, con ${total}.")

    if gastos > ingresos and ingresos > 0:
        mensajes.append("Estás gastando más de lo que ingresás.")
    elif ingresos > gastos and gastos > 0:
        mensajes.append("Vas bien: tus ingresos superan a tus gastos.")

    hp = tiempo_productivo // 60
    mp = tiempo_productivo % 60
    hd = tiempo_perdido // 60
    md = tiempo_perdido % 60

    if tiempo_productivo > 0:
        mensajes.append(f"Llevás {hp}h {mp}min de tiempo productivo registrado.")

    if tiempo_perdido > 0:
        mensajes.append(f"Llevás {hd}h {md}min de tiempo perdido registrado.")

    if tiempo_perdido > tiempo_productivo and tiempo_perdido > 0:
        mensajes.append("Ojo: el tiempo perdido supera al productivo.")
    elif tiempo_productivo > tiempo_perdido and tiempo_productivo > 0:
        mensajes.append("Bien: tu tiempo productivo supera al tiempo perdido.")

    return "\n".join(mensajes)


def obtener_detalle_gastos(cursor, texto_limpio):
    fecha_filtro = obtener_filtro_fecha(texto_limpio)

    if fecha_filtro:
        cursor.execute("""
            SELECT categoria, COALESCE(SUM(monto), 0) as total
            FROM registros
            WHERE tipo = 'gasto' AND fecha >= ?
            GROUP BY categoria
            ORDER BY total DESC
        """, (fecha_filtro,))
    else:
        cursor.execute("""
            SELECT categoria, COALESCE(SUM(monto), 0) as total
            FROM registros
            WHERE tipo = 'gasto'
            GROUP BY categoria
            ORDER BY total DESC
        """)

    resultados = cursor.fetchall()

    if not resultados:
        return "No hay gastos registrados para ese período."

    total_general = sum(total for _, total in resultados)

    if "hoy" in texto_limpio:
        titulo = "Detalle de gastos de hoy:"
    elif "semana" in texto_limpio:
        titulo = "Detalle de gastos de esta semana:"
    elif "mes" in texto_limpio:
        titulo = "Detalle de gastos de este mes:"
    else:
        titulo = "Detalle de gastos:"

    detalle = ""
    for categoria, total in resultados:
        detalle += f"- {categoria}: ${total}\n"

    return f"{titulo}\n{detalle}\nTotal: ${total_general}"


def resolver_consulta(texto_limpio: str, cursor):
    if "modo dueño" in texto_limpio or "modo dueno" in texto_limpio or "analiza mi situacion" in texto_limpio or "analiza mi situación" in texto_limpio:
        return generar_consejo_dueno(cursor)

    if "detalle" in texto_limpio and "gasto" in texto_limpio:
        return obtener_detalle_gastos(cursor, texto_limpio)

    if "comida" in texto_limpio and ("cuanto" in texto_limpio or "cuánto" in texto_limpio):
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE tipo = 'gasto' AND categoria = 'comida'
        """)
        total = cursor.fetchone()[0] or 0
        return f"Gastaste ${total} en comida."

    if "transporte" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE categoria = 'transporte'
        """)
        total = cursor.fetchone()[0] or 0
        return f"Gastaste ${total} en transporte."

    if "fume" in texto_limpio or "fumé" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(cantidad), 0)
            FROM registros
            WHERE categoria = 'fumar'
        """)
        total = cursor.fetchone()[0] or 0
        return f"Tenés registrados {total} cigarrillos."

    if "gym" in texto_limpio or "gim" in texto_limpio:
        cursor.execute("""
            SELECT COUNT(*)
            FROM registros
            WHERE categoria = 'gimnasio'
        """)
        total = cursor.fetchone()[0] or 0
        return f"Fuiste al gimnasio {total} veces."

    if "balance" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE tipo = 'ingreso'
        """)
        ingresos = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE tipo = 'gasto'
        """)
        gastos = cursor.fetchone()[0] or 0

        return f"Tu balance actual es ${ingresos - gastos}."

    if "ingres" in texto_limpio:
        fecha_filtro = obtener_filtro_fecha(texto_limpio)

        if fecha_filtro:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0)
                FROM registros
                WHERE tipo = 'ingreso' AND fecha >= ?
            """, (fecha_filtro,))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0)
                FROM registros
                WHERE tipo = 'ingreso'
            """)

        total = cursor.fetchone()[0] or 0

        if "hoy" in texto_limpio:
            return f"Hoy ingresaste ${total}."
        if "semana" in texto_limpio:
            return f"Esta semana ingresaste ${total}."
        if "mes" in texto_limpio:
            return f"Este mes ingresaste ${total}."

        return f"En total ingresaste ${total}."

    if "gaste" in texto_limpio or "gasté" in texto_limpio:
        fecha_filtro = obtener_filtro_fecha(texto_limpio)

        if fecha_filtro:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0)
                FROM registros
                WHERE tipo = 'gasto' AND fecha >= ?
            """, (fecha_filtro,))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0)
                FROM registros
                WHERE tipo = 'gasto'
            """)

        total = cursor.fetchone()[0] or 0

        if "hoy" in texto_limpio:
            return f"Hoy gastaste ${total}."
        if "semana" in texto_limpio:
            return f"Esta semana gastaste ${total}."
        if "mes" in texto_limpio:
            return f"Este mes gastaste ${total}."

        return f"Gastaste ${total} en total."

    if "que hice hoy" in texto_limpio or "qué hice hoy" in texto_limpio:
        cursor.execute("""
            SELECT tipo, categoria, detalle
            FROM registros
            WHERE fecha >= date('now', 'localtime')
            ORDER BY id DESC
            LIMIT 20
        """)
        filas = cursor.fetchall()

        if not filas:
            return "Hoy todavía no registraste nada."

        respuesta = "Hoy registraste:\n"
        for tipo, categoria, detalle in filas:
            respuesta += f"- {tipo} | {categoria} | {detalle}\n"
        return respuesta

    if "horas productivas" in texto_limpio or "tiempo productivo" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(duracion_minutos), 0)
            FROM registros
            WHERE productividad = 'productivo'
        """)
        total_min = cursor.fetchone()[0] or 0

        horas = total_min // 60
        minutos = total_min % 60

        return f"Tiempo productivo registrado: {horas}h {minutos}min."

    if "tiempo perdido" in texto_limpio or "perdi tiempo" in texto_limpio or "perdí tiempo" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(duracion_minutos), 0)
            FROM registros
            WHERE productividad = 'perdida_tiempo'
        """)
        total_min = cursor.fetchone()[0] or 0

        horas = total_min // 60
        minutos = total_min % 60

        return f"Tiempo perdido registrado: {horas}h {minutos}min."

    if "como estuvo mi dia" in texto_limpio or "cómo estuvo mi día" in texto_limpio:
        cursor.execute("""
            SELECT productividad, COUNT(*), COALESCE(SUM(duracion_minutos), 0)
            FROM registros
            WHERE fecha >= date('now', 'localtime')
            GROUP BY productividad
        """)
        filas = cursor.fetchall()

        if not filas:
            return "Hoy todavía no registraste actividad suficiente."

        respuesta = "Resumen de tu día:\n"
        for prod, cantidad, minutos in filas:
            horas = minutos // 60
            resto = minutos % 60
            respuesta += f"- {prod}: {cantidad} registros | {horas}h {resto}min\n"

        return respuesta

    if "resumen" in texto_limpio:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE tipo = 'gasto'
        """)
        total_gastos = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM registros
            WHERE tipo = 'ingreso'
        """)
        total_ingresos = cursor.fetchone()[0] or 0

        balance = total_ingresos - total_gastos

        cursor.execute("""
            SELECT categoria, COALESCE(SUM(monto), 0) as total
            FROM registros
            WHERE tipo = 'gasto'
            GROUP BY categoria
            ORDER BY total DESC
        """)
        categorias = cursor.fetchall()

        detalle_categorias = ""
        if categorias:
            for categoria, total in categorias[:5]:
                detalle_categorias += f"- {categoria}: ${total}\n"
        else:
            detalle_categorias = "- No hay gastos registrados.\n"

        return (
            f"Resumen general:\n"
            f"Ingresos: ${total_ingresos}\n"
            f"Gastos: ${total_gastos}\n"
            f"Balance: ${balance}\n\n"
            f"Gastos por categoría:\n{detalle_categorias}"
        )

    return "No entendí la consulta."


def responder_chat(texto_usuario: str, datos: dict | None = None, respuesta_base: str | None = None) -> str:
    """
    Primero intenta responder consultas inteligentes.
    Si no corresponde, usa la respuesta normal del sistema.
    """

    from app.inteligencia import responder_consulta_inteligente

    respuesta_inteligente = responder_consulta_inteligente(texto_usuario)
    if respuesta_inteligente:
        return respuesta_inteligente

    if respuesta_base:
        return respuesta_base

    if not datos:
        return "No entendí el mensaje. Probá escribiendo un gasto, ingreso, actividad o una consulta."

    tipo = datos.get("tipo")
    categoria = datos.get("categoria")
    detalle = datos.get("detalle")
    monto = datos.get("monto")
    cantidad = datos.get("cantidad")
    unidad = datos.get("unidad")
    productividad = datos.get("productividad")

    if tipo == "gasto":
        return f"Gasto registrado: {detalle or categoria or 'sin detalle'} por ${monto}"

    if tipo == "ingreso":
        return f"Ingreso registrado: {detalle or categoria or 'sin detalle'} por ${monto}"

    if tipo == "habito":
        if cantidad and unidad:
            return f"Hábito registrado: {detalle or categoria or 'sin detalle'} - {cantidad} {unidad}"
        return f"Hábito registrado: {detalle or categoria or 'sin detalle'}"

    if tipo == "actividad":
        texto = f"Actividad registrada: {detalle or categoria or 'sin detalle'}"
        if cantidad and unidad:
            texto += f" - {cantidad} {unidad}"
        if productividad:
            texto += f" - {productividad}"
        return texto

    if tipo == "consulta":
        return "Consulta procesada."

    return "Registro guardado correctamente."


def obtener_historial_chat(cursor, limit=30):
    cursor.execute("""
        SELECT fecha, tipo, categoria, detalle, monto, respuesta
        FROM registros
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    registros = cursor.fetchall()
    registros.reverse()

    mensajes = ""

    for fecha, tipo, categoria, detalle, monto, respuesta in registros:
        texto_user = html.escape(str(detalle))

        mensajes += f"""
        <div class="fila user">
            <div class="burbuja user">
                {texto_user}
            </div>
        </div>
        """

        if tipo == "gasto":
            respuesta_bot = f"Anotado. Gastaste ${monto} en {categoria}."
            clase_bot = "bot-gasto"
            etiqueta = "Gasto"

        elif tipo == "ingreso":
            respuesta_bot = f"Perfecto. Registré un ingreso de ${monto}."
            clase_bot = "bot-ingreso"
            etiqueta = "Ingreso"

        elif tipo == "habito":
            respuesta_bot = respuesta if respuesta else f"Registré tu hábito: {categoria}."
            clase_bot = "bot-habito"
            etiqueta = "Hábito"

        elif tipo == "actividad":
            respuesta_bot = respuesta if respuesta else f"Actividad registrada: {categoria}."
            clase_bot = "bot-actividad"
            etiqueta = "Actividad"

        elif tipo == "consulta":
            respuesta_bot = respuesta if respuesta else "Consulta guardada."
            clase_bot = "bot-consulta"
            etiqueta = "Consulta"

        else:
            respuesta_bot = "Nota guardada."
            clase_bot = "bot-nota"
            etiqueta = "Nota"

        mensajes += f"""
        <div class="fila bot">
            <div class="burbuja bot {clase_bot}">
                <div class="etiqueta-tipo">{etiqueta}</div>
                {html.escape(str(respuesta_bot))}
            </div>
        </div>
        """

    return mensajes