from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
import app.contexto as contexto_app
from app.database import init_db, get_connection
from app.parser import interpretar_texto, es_consulta, clasificar_productividad
from app.inteligencia import analizar_dia, generar_texto_modo_dueno, responder_consulta_inteligente
from app.responses import (
    responder_chat,
    resolver_consulta,
    obtener_historial_chat,
    generar_respuesta_registro,
)
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/modo-dueno")
def modo_dueno():
    return analizar_dia()


@app.get("/modo-dueno-texto")
def modo_dueno_texto():
    return {"respuesta": generar_texto_modo_dueno()}

@app.get("/contexto-prueba")
def contexto_prueba():
    contexto = contexto_app.construir_contexto_del_dia()

    from app.inteligencia import generar_texto_con_contexto_externo
    return {"respuesta": generar_texto_con_contexto_externo(contexto)}

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    historial = obtener_historial_chat(cursor)
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"mensajes": historial}
    )


@app.post("/api/chat")
def api_chat(texto: str = Form(...)):
    texto_limpio = texto.lower().strip()

    conn = get_connection()
    cursor = conn.cursor()

        # -------------------------------------------------
    # 0) Primero vemos si el mensaje define contexto manual
    # -------------------------------------------------
    from app.contexto import interpretar_contexto_manual_desde_texto

    contexto_manual = None
    if texto_limpio.startswith("hoy "):
        contexto_manual = interpretar_contexto_manual_desde_texto(texto_limpio)

    if contexto_manual:
        contexto_app.guardar_contexto_manual_hoy(
            tipo_dia=contexto_manual["tipo_dia"],
            eventos=contexto_manual.get("eventos", []),
            es_exigente=contexto_manual.get("es_exigente", False)
        )

        respuesta_contexto = (
            f"Perfecto. Tomo el día de hoy como '{contexto_manual['tipo_dia']}'"
        )

        if contexto_manual.get("eventos"):
            respuesta_contexto += f" con contexto: {', '.join(contexto_manual['eventos'])}."

        cursor.execute("""
            INSERT INTO registros (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            texto,
            "consulta",
            "contexto_manual",
            texto,
            None,
            None,
            None,
            respuesta_contexto,
            None,
            None,
        ))

        conn.commit()
        conn.close()

        return JSONResponse({
            "ok": True,
            "tipo": "consulta",
            "categoria": "contexto_manual",
            "mensaje_usuario": texto,
            "respuesta": respuesta_contexto
        })

    # -------------------------------------------------
    # 1) Primero vemos si es una consulta inteligente
    # -------------------------------------------------
    respuesta_inteligente = responder_consulta_inteligente(texto_limpio)

    if respuesta_inteligente:
        cursor.execute("""
            INSERT INTO registros (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            texto,
            "consulta",
            "inteligente",
            texto,
            None,
            None,
            None,
            respuesta_inteligente,
            None,
            None,
        ))

        conn.commit()
        conn.close()

        return JSONResponse({
            "ok": True,
            "tipo": "consulta",
            "categoria": "inteligente",
            "mensaje_usuario": texto,
            "respuesta": respuesta_inteligente
        })

    # -------------------------------------------------
    # 2) Si es consulta normal, sigue como antes
    # -------------------------------------------------
    if es_consulta(texto_limpio):
        respuesta = resolver_consulta(texto_limpio, cursor)

        cursor.execute("""
            INSERT INTO registros (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            texto,
            "consulta",
            "general",
            texto,
            None,
            None,
            None,
            respuesta,
            None,
            None,
        ))

        conn.commit()
        conn.close()

        return JSONResponse({
            "ok": True,
            "tipo": "consulta",
            "categoria": "general",
            "mensaje_usuario": texto,
            "respuesta": respuesta
        })

    # -------------------------------------------------
    # 3) Si no es consulta, se interpreta como registro
    # -------------------------------------------------
    datos = interpretar_texto(texto)
    productividad = clasificar_productividad(datos)
    respuesta_base = generar_respuesta_registro(datos)

    respuesta_final = responder_chat(
        texto_usuario=texto,
        datos=datos,
        respuesta_base=respuesta_base
    )

    cursor.execute("""
        INSERT INTO registros (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        texto,
        datos["tipo"],
        datos["categoria"],
        datos["detalle"],
        datos["monto"],
        datos["cantidad"],
        datos["unidad"],
        respuesta_final,
        productividad,
        datos.get("duracion_minutos"),
    ))

    conn.commit()
    conn.close()

    return JSONResponse({
        "ok": True,
        "tipo": datos["tipo"],
        "categoria": datos["categoria"],
        "mensaje_usuario": texto,
        "respuesta": respuesta_final
    })

@app.post("/procesar", response_class=HTMLResponse)

def procesar(request: Request, texto: str = Form(...)):
    texto_limpio = texto.lower().strip()

    conn = get_connection()
    cursor = conn.cursor()
    from app.contexto import interpretar_contexto_manual_desde_texto

    contexto_manual = None
    if texto_limpio.startswith("hoy "):
        contexto_manual = interpretar_contexto_manual_desde_texto(texto_limpio)

    if contexto_manual:
        contexto_app.guardar_contexto_manual_hoy(
        tipo_dia=contexto_manual["tipo_dia"],
        eventos=contexto_manual.get("eventos", []),
        es_exigente=contexto_manual.get("es_exigente", False)
    )

    # -------------------------------------------------
    # 1) CONSULTA INTELIGENTE
    # -------------------------------------------------
    respuesta_inteligente = responder_consulta_inteligente(texto_limpio)

    if respuesta_inteligente:
        cursor.execute("""
            INSERT INTO registros (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            texto,
            "consulta",
            "inteligente",
            texto,
            None,
            None,
            None,
            respuesta_inteligente,
            None,
            None,
        ))

        conn.commit()
        historial = obtener_historial_chat(cursor)
        conn.close()

        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={"mensajes": historial}
        )

    # -------------------------------------------------
    # 2) CONSULTA NORMAL
    # -------------------------------------------------
    if es_consulta(texto_limpio):
        respuesta = resolver_consulta(texto_limpio, cursor)

        cursor.execute("""
            INSERT INTO registros (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            texto,
            "consulta",
            "general",
            texto,
            None,
            None,
            None,
            respuesta,
            None,
            None,
        ))

        conn.commit()
        historial = obtener_historial_chat(cursor)
        conn.close()

        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={"mensajes": historial}
        )

    # -------------------------------------------------
    # 3) REGISTRO NORMAL
    # -------------------------------------------------
    datos = interpretar_texto(texto)
    productividad = clasificar_productividad(datos)
    respuesta_base = generar_respuesta_registro(datos)

    respuesta = responder_chat(
        texto_usuario=texto,
        datos=datos,
        respuesta_base=respuesta_base
    )

    cursor.execute("""
        INSERT INTO registros (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        texto,
        datos["tipo"],
        datos["categoria"],
        datos["detalle"],
        datos["monto"],
        datos["cantidad"],
        datos["unidad"],
        respuesta,
        productividad,
        datos.get("duracion_minutos"),
    ))

    conn.commit()
    historial = obtener_historial_chat(cursor)
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"mensajes": historial}
    )

@app.get("/historial", response_class=HTMLResponse)
def historial():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, fecha, tipo, categoria, detalle, monto, cantidad, unidad, productividad, duracion_minutos
        FROM registros
        ORDER BY id DESC
    """)
    registros = cursor.fetchall()
    conn.close()

    filas = ""
    for r in registros:
        registro_id, fecha, tipo, categoria, detalle, monto, cantidad, unidad, productividad, duracion_minutos = r
        filas += f"""
        <tr>
            <td>{fecha}</td>
            <td>{tipo}</td>
            <td>{categoria}</td>
            <td>{detalle}</td>
            <td>{monto if monto is not None else '-'}</td>
            <td>{cantidad if cantidad is not None else '-'}</td>
            <td>{unidad if unidad is not None else '-'}</td>
            <td>{productividad if productividad is not None else '-'}</td>
            <td>{duracion_minutos if duracion_minutos is not None else '-'}</td>
            <td class="acciones">
                <a href="/editar/{registro_id}">Editar</a>
                <form method="post" action="/borrar/{registro_id}" style="display:inline;">
                    <button type="submit">Borrar</button>
                </form>
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Historial</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1300px;
                margin: 40px auto;
                padding: 20px;
                background: #f3f4f6;
            }}
            .caja {{
                background: white;
                padding: 25px;
                border-radius: 14px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.08);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background: #e5e7eb;
            }}
            a {{
                display: inline-block;
                text-decoration: none;
                background: #2563eb;
                color: white;
                padding: 8px 12px;
                border-radius: 8px;
            }}
            .volver {{
                margin-top: 20px;
                padding: 10px 16px;
            }}
            .acciones button {{
                background: #dc2626;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 8px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="caja">
            <h1>Historial</h1>
            <table>
                <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Categoría</th>
                    <th>Detalle</th>
                    <th>Monto</th>
                    <th>Cantidad</th>
                    <th>Unidad</th>
                    <th>Productividad</th>
                    <th>Duración (min)</th>
                    <th>Acción</th>
                </tr>
                {filas}
            </table>
            <br>
            <a class="volver" href="/">Volver</a>
        </div>
    </body>
    </html>
    """


@app.post("/borrar/{registro_id}")
def borrar_registro(registro_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/historial", status_code=303)


@app.get("/editar/{registro_id}", response_class=HTMLResponse)
def editar_form(registro_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT detalle FROM registros WHERE id = ?", (registro_id,))
    registro = cursor.fetchone()
    conn.close()

    if not registro:
        return HTMLResponse("<h2>Registro no encontrado</h2>")

    texto_actual = registro[0]

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Editar registro</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 700px;
                margin: 40px auto;
                padding: 20px;
                background: #f3f4f6;
            }}
            .caja {{
                background: white;
                padding: 25px;
                border-radius: 14px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.08);
            }}
            textarea {{
                width: 100%;
                height: 120px;
                padding: 12px;
                font-size: 16px;
                border-radius: 10px;
                border: 1px solid #d1d5db;
                box-sizing: border-box;
            }}
            button, a {{
                display: inline-block;
                margin-top: 15px;
                text-decoration: none;
                background: #2563eb;
                color: white;
                padding: 10px 16px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="caja">
            <h1>Editar registro</h1>
            <form method="post" action="/editar/{registro_id}">
                <textarea name="texto">{texto_actual}</textarea><br>
                <button type="submit">Guardar cambios</button>
            </form>
            <a href="/historial">Volver</a>
        </div>
    </body>
    </html>
    """


@app.post("/editar/{registro_id}")
def editar_registro(registro_id: int, texto: str = Form(...)):
    datos = interpretar_texto(texto)
    productividad = clasificar_productividad(datos)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE registros
        SET texto_original = ?, tipo = ?, categoria = ?, detalle = ?, monto = ?, cantidad = ?, unidad = ?, respuesta = ?, productividad = ?, duracion_minutos = ?
        WHERE id = ?
    """, (
        texto,
        datos["tipo"],
        datos["categoria"],
        datos["detalle"],
        datos["monto"],
        datos["cantidad"],
        datos["unidad"],
        None,
        productividad,
        datos.get("duracion_minutos"),
        registro_id
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/historial", status_code=303)


@app.get("/resumen", response_class=HTMLResponse)
def resumen():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM registros WHERE tipo = 'gasto'")
    total_gastos = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM registros WHERE tipo = 'ingreso'")
    total_ingresos = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(cantidad), 0) FROM registros WHERE categoria = 'fumar'")
    total_fumar = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registros WHERE categoria = 'gimnasio'")
    total_gimnasio = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registros WHERE categoria = 'bomberos'")
    total_bomberos = cursor.fetchone()[0]

    cursor.execute("""
        SELECT categoria, COALESCE(SUM(monto), 0)
        FROM registros
        WHERE tipo = 'gasto'
        GROUP BY categoria
        ORDER BY SUM(monto) DESC
    """)
    gastos_por_categoria = cursor.fetchall()

    conn.close()

    balance = total_ingresos - total_gastos

    bloques_gastos = ""
    if gastos_por_categoria:
        for categoria, total in gastos_por_categoria:
            bloques_gastos += f"""
            <div class="item">
                <strong>{categoria.capitalize()}:</strong> ${total}
            </div>
            """
    else:
        bloques_gastos = """
        <div class="item">
            Todavía no hay gastos cargados.
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Resumen</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #f3f4f6;
            }}
            .caja {{
                background: white;
                padding: 25px;
                border-radius: 14px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.08);
            }}
            .item {{
                background: #f9fafb;
                padding: 15px;
                margin-bottom: 12px;
                border-radius: 10px;
            }}
            .seccion {{
                margin-top: 30px;
            }}
            a {{
                display: inline-block;
                margin-top: 20px;
                text-decoration: none;
                background: #2563eb;
                color: white;
                padding: 10px 16px;
                border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="caja">
            <h1>Resumen general</h1>

            <div class="item"><strong>Total gastos:</strong> ${total_gastos}</div>
            <div class="item"><strong>Total ingresos:</strong> ${total_ingresos}</div>
            <div class="item"><strong>Balance:</strong> ${balance}</div>
            <div class="item"><strong>Cigarrillos registrados:</strong> {total_fumar}</div>
            <div class="item"><strong>Registros de gimnasio:</strong> {total_gimnasio}</div>
            <div class="item"><strong>Registros de bomberos:</strong> {total_bomberos}</div>

            <div class="seccion">
                <h2>Gastos por categoría</h2>
                {bloques_gastos}
            </div>

            <a href="/">Volver</a>
        </div>
    </body>
    </html>
    """


@app.get("/exportar-excel")
def exportar_excel():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fecha, texto_original, tipo, categoria, detalle, monto, cantidad, unidad, respuesta, productividad, duracion_minutos
        FROM registros
        ORDER BY id ASC
    """)
    registros = cursor.fetchall()
    conn.close()

    wb = Workbook()

    ws = wb.active
    ws.title = "Registros"
    ws.append([
        "Fecha", "Texto original", "Tipo", "Categoria", "Detalle",
        "Monto", "Cantidad", "Unidad", "Respuesta", "Productividad", "Duracion_minutos"
    ])

    for fila in registros:
        ws.append(list(fila))

    ws2 = wb.create_sheet("Resumen")

    total_gastos = sum((fila[5] or 0) for fila in registros if fila[2] == "gasto")
    total_ingresos = sum((fila[5] or 0) for fila in registros if fila[2] == "ingreso")
    balance = total_ingresos - total_gastos

    total_productivo = sum(1 for fila in registros if fila[9] == "productivo")
    total_necesario = sum(1 for fila in registros if fila[9] == "necesario")
    total_perdida = sum(1 for fila in registros if fila[9] == "perdida_tiempo")
    total_neutro = sum(1 for fila in registros if fila[9] == "neutro")

    total_min_productivo = sum((fila[10] or 0) for fila in registros if fila[9] == "productivo")
    total_min_perdido = sum((fila[10] or 0) for fila in registros if fila[9] == "perdida_tiempo")

    ws2.append(["Métrica", "Valor"])
    ws2.append(["Total gastos", total_gastos])
    ws2.append(["Total ingresos", total_ingresos])
    ws2.append(["Balance", balance])
    ws2.append(["Registros productivos", total_productivo])
    ws2.append(["Registros necesarios", total_necesario])
    ws2.append(["Registros pérdida de tiempo", total_perdida])
    ws2.append(["Registros neutros", total_neutro])
    ws2.append(["Tiempo productivo (min)", total_min_productivo])
    ws2.append(["Tiempo perdido (min)", total_min_perdido])

    ruta_archivo = "agenda_exportada.xlsx"
    wb.save(ruta_archivo)

    return FileResponse(
        path=ruta_archivo,
        filename="agenda_exportada.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    try:
        mensaje = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        numero = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except:
        return {"ok": True}

    respuesta = responder_consulta_inteligente(mensaje.lower())

    if not respuesta:
        datos = interpretar_texto(mensaje)
        respuesta_base = generar_respuesta_registro(datos)
        respuesta = responder_chat(mensaje, datos, respuesta_base)

    print(f"Mensaje de {numero}: {mensaje}")
    print(f"Respuesta: {respuesta}")

    return {"ok": True}

def router_principal(texto):
    texto = texto.lower()

    if "gasto" in texto or "compre" in texto:
        datos = interpretar_texto(texto)
        return generar_respuesta_registro(datos)

    if "hoy" in texto:
        return responder_consulta_inteligente(texto)

    return responder_consulta_inteligente(texto) or "No entendí"