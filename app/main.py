from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from starlette.middleware.sessions import SessionMiddleware
from fastapi import HTTPException
from datetime import date, datetime, timedelta

from app.database import SessionLocal, engine, Base
from app.models import (
    Usuario,
    Producto,
    Inventario,
    Produccion,
    Venta,
    Salida,
    Gasto,
    Bitacora,
    ConfiguracionSemana,
    CorteHistorico,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Huevos Alak POS")
app.add_middleware(SessionMiddleware, secret_key="huevos-alak-clave-secreta-2026")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def registrar_bitacora(db: Session, usuario: str, accion: str, detalle: str):
    item = Bitacora(usuario=usuario, accion=accion, detalle=detalle)
    db.add(item)
    db.commit()

def obtener_usuario_actual(request: Request, db: Session):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    return db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.activo == True).first()


def requerir_login(request: Request, db: Session):
    usuario = obtener_usuario_actual(request, db)
    if not usuario:
        raise HTTPException(status_code=401, detail="No autenticado")
    return usuario


def requerir_admin(request: Request, db: Session):
    usuario = requerir_login(request, db)
    if usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario


def crear_admin(db: Session):
    existe = db.query(Usuario).filter(Usuario.usuario == "admin").first()
    if not existe:
        db.add(Usuario(
            nombre="Administrador",
            usuario="admin",
            password="1234",
            rol="admin"
        ))
        db.commit()


def crear_inventario_inicial(db: Session):
    tipos = ["Ponedoras", "Ponedoras de afuera", "Jolota"]
    for tipo in tipos:
        existe = db.query(Inventario).filter(Inventario.tipo_huevo == tipo).first()
        if not existe:
            db.add(Inventario(tipo_huevo=tipo, cantidad=0))
    db.commit()


def crear_configuracion_semana_inicial(db: Session):
    existe = db.query(ConfiguracionSemana).first()

    if not existe:
        config = ConfiguracionSemana(
            caja_inicial=0,
            ponedoras_inicial=0,
            ponedoras_afuera_inicial=0,
            jolota_inicial=0
        )
        db.add(config)
        db.commit()


@app.on_event("startup")
def startup():
    db = SessionLocal()
    crear_admin(db)
    crear_inventario_inicial(db)
    crear_configuracion_semana_inicial(db)
    db.close()


@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": ""}
    )


@app.post("/login")
def login(
    request: Request,
    usuario: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(Usuario).filter(
        Usuario.usuario == usuario,
        Usuario.password == password,
        Usuario.activo == True
    ).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Usuario o contraseña incorrectos"}
        )

    request.session["usuario_id"] = user.id
    request.session["usuario_nombre"] = user.nombre
    request.session["usuario_rol"] = user.rol

    registrar_bitacora(db, user.nombre, "Inicio de sesión", "Entró al sistema")

    if user.debe_cambiar_password:
        return RedirectResponse(url="/mi-cuenta/forzar-cambio", status_code=303)

    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/mi-cuenta")
def mi_cuenta_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)

    return templates.TemplateResponse(
        request=request,
        name="mi_cuenta.html",
        context={
            "usuario": usuario,
            "mensaje": "",
            "error": ""
        }
    )


@app.post("/mi-cuenta/cambiar-password")
def cambiar_password(
    request: Request,
    password_actual: str = Form(...),
    password_nueva: str = Form(...),
    password_confirmacion: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    if usuario.password != password_actual:
        return templates.TemplateResponse(
            request=request,
            name="mi_cuenta.html",
            context={
                "usuario": usuario,
                "mensaje": "",
                "error": "La contraseña actual no es correcta"
            }
        )

    if password_nueva != password_confirmacion:
        return templates.TemplateResponse(
            request=request,
            name="mi_cuenta.html",
            context={
                "usuario": usuario,
                "mensaje": "",
                "error": "La nueva contraseña y la confirmación no coinciden"
            }
        )

    usuario.password = password_nueva
    db.commit()

    registrar_bitacora(
        db,
        usuario.nombre,
        "Cambio de contraseña",
        "Actualizó su contraseña personal"
    )

    return templates.TemplateResponse(
        request=request,
        name="mi_cuenta.html",
        context={
            "usuario": usuario,
            "mensaje": "Contraseña actualizada correctamente",
            "error": ""
        }
    )

@app.get("/mi-cuenta/forzar-cambio")
def forzar_cambio_password_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)

    return templates.TemplateResponse(
        request=request,
        name="forzar_cambio_password.html",
        context={
            "usuario": usuario,
            "error": "",
            "mensaje": ""
        }
    )


@app.post("/mi-cuenta/forzar-cambio")
def forzar_cambio_password(
    request: Request,
    password_actual: str = Form(...),
    password_nueva: str = Form(...),
    password_confirmacion: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    if usuario.password != password_actual:
        return templates.TemplateResponse(
            request=request,
            name="forzar_cambio_password.html",
            context={
                "usuario": usuario,
                "mensaje": "",
                "error": "La contraseña actual no es correcta"
            }
        )

    if password_nueva != password_confirmacion:
        return templates.TemplateResponse(
            request=request,
            name="forzar_cambio_password.html",
            context={
                "usuario": usuario,
                "mensaje": "",
                "error": "La nueva contraseña y la confirmación no coinciden"
            }
        )

    usuario.password = password_nueva
    usuario.debe_cambiar_password = False
    usuario.password_modificada_por_admin = False
    db.commit()

    registrar_bitacora(
        db,
        usuario.nombre,
        "Cambio obligatorio de contraseña",
        "Actualizó su contraseña después de un cambio administrativo"
    )

    return RedirectResponse(url="/dashboard", status_code=303)



@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)

    inventario = db.query(Inventario).all()
    alertas_bajas = [
    item for item in inventario
    if item.tipo_huevo == "Ponedoras" and item.cantidad < 30
]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "usuario": usuario,
            "inventario": inventario,
            "alertas_bajas": alertas_bajas
        }
    )


@app.get("/usuarios")
def usuarios_page(request: Request, db: Session = Depends(get_db)):
    usuario_actual = requerir_admin(request, db)
    usuarios = db.query(Usuario).order_by(Usuario.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="usuarios.html",
        context={
            "usuario": usuario_actual,
            "usuarios": usuarios
        }
    )


@app.post("/usuarios")
def crear_usuario(
    request: Request,
    nombre: str = Form(...),
    usuario: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_actual = requerir_admin(request, db)

    existe = db.query(Usuario).filter(Usuario.usuario == usuario).first()
    if existe:
        usuarios = db.query(Usuario).order_by(Usuario.id.desc()).all()
        return templates.TemplateResponse(
            request=request,
            name="usuarios.html",
            context={
                "usuario": usuario_actual,
                "usuarios": usuarios,
                "error": "Ese nombre de usuario ya existe"
            }
        )

    nuevo_usuario = Usuario(
        nombre=nombre,
        usuario=usuario,
        password=password,
        rol=rol,
        activo=True
    )
    db.add(nuevo_usuario)
    db.commit()

    registrar_bitacora(
        db,
        usuario_actual.nombre,
        "Crear usuario",
        f"Creó al usuario {usuario} con rol {rol}"
    )

    return RedirectResponse(url="/usuarios", status_code=303)


@app.get("/usuarios/toggle/{usuario_id}")
def toggle_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    usuario_actual = requerir_admin(request, db)

    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if user:
        user.activo = not user.activo
        db.commit()

        estado = "activó" if user.activo else "desactivó"
        registrar_bitacora(
            db,
            usuario_actual.nombre,
            "Cambiar estado usuario",
            f"{estado} al usuario {user.usuario}"
        )

    return RedirectResponse(url="/usuarios", status_code=303)


@app.get("/usuarios/editar/{usuario_id}")
def editar_usuario_page(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    usuario_actual = requerir_admin(request, db)
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not user:
        return RedirectResponse(url="/usuarios", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="editar_usuario.html",
        context={
            "usuario": usuario_actual,
            "user": user,
            "error": ""
        }
    )


@app.post("/usuarios/editar/{usuario_id}")
def editar_usuario(
    usuario_id: int,
    request: Request,
    nombre: str = Form(...),
    usuario_login: str = Form(...),
    rol: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_actual = requerir_admin(request, db)
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not user:
        return RedirectResponse(url="/usuarios", status_code=303)

    existe = db.query(Usuario).filter(
        Usuario.usuario == usuario_login,
        Usuario.id != usuario_id
    ).first()

    if existe:
        return templates.TemplateResponse(
            request=request,
            name="editar_usuario.html",
            context={
                "usuario": usuario_actual,
                "user": user,
                "error": "Ese nombre de usuario ya está en uso"
            }
        )

    user.nombre = nombre
    user.usuario = usuario_login
    user.rol = rol
    db.commit()

    registrar_bitacora(
        db,
        usuario_actual.nombre,
        "Editar usuario",
        f"Editó al usuario {user.usuario}"
    )

    return RedirectResponse(url="/usuarios", status_code=303)


@app.get("/usuarios/eliminar/{usuario_id}")
def eliminar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    usuario_actual = requerir_admin(request, db)
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not user:
        return RedirectResponse(url="/usuarios", status_code=303)

    if user.usuario == "admin":
        return RedirectResponse(url="/usuarios", status_code=303)

    db.delete(user)
    db.commit()

    registrar_bitacora(
        db,
        usuario_actual.nombre,
        "Eliminar usuario",
        f"Eliminó al usuario {user.usuario}"
    )

    return RedirectResponse(url="/usuarios", status_code=303)

@app.get("/usuarios/reset-password/{usuario_id}")
def reset_password_page(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_actual = requerir_admin(request, db)
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not user:
        return RedirectResponse(url="/usuarios", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="reset_password_usuario.html",
        context={
            "usuario": usuario_actual,
            "user": user,
            "error": "",
            "mensaje": ""
        }
    )


@app.post("/usuarios/reset-password/{usuario_id}")
def reset_password_usuario(
    usuario_id: int,
    request: Request,
    nueva_password: str = Form(...),
    confirmar_password: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_actual = requerir_admin(request, db)
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not user:
        return RedirectResponse(url="/usuarios", status_code=303)

    if nueva_password != confirmar_password:
        return templates.TemplateResponse(
            request=request,
            name="reset_password_usuario.html",
            context={
                "usuario": usuario_actual,
                "user": user,
                "error": "Las contraseñas no coinciden",
                "mensaje": ""
            }
        )

    user.password = nueva_password
    user.debe_cambiar_password = True
    user.password_modificada_por_admin = True
    db.commit()

    registrar_bitacora(
        db,
        usuario_actual.nombre,
        "Reset de contraseña",
        f"Restableció la contraseña del usuario {user.usuario}"
    )

    return templates.TemplateResponse(
        request=request,
        name="reset_password_usuario.html",
        context={
            "usuario": usuario_actual,
            "user": user,
            "error": "",
            "mensaje": "Contraseña restablecida correctamente. El usuario deberá cambiarla al iniciar sesión."
        }
    )

@app.get("/productos")
def productos_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_admin(request, db)
    productos = db.query(Producto).order_by(Producto.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="productos.html",
        context={
            "productos": productos,
            "usuario": usuario
        }
    )


@app.post("/productos")
def guardar_producto(
    request: Request,
    nombre: str = Form(...),
    precio: float = Form(...),
    unidades_por_presentacion: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_admin(request, db)

    db.add(Producto(
        nombre=nombre,
        precio=precio,
        unidades_por_presentacion=unidades_por_presentacion
    ))
    db.commit()

    registrar_bitacora(
        db,
        usuario.nombre,
        "Producto",
        f"Agregó producto {nombre}"
    )

    return RedirectResponse(url="/productos", status_code=303)



@app.get("/inventario")
def inventario_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    inventario = db.query(Inventario).all()

    return templates.TemplateResponse(
        request=request,
        name="inventario.html",
        context={
            "inventario": inventario,
            "usuario": usuario
        }
    )


@app.get("/produccion")
def produccion_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    registros = db.query(Produccion).order_by(Produccion.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="produccion.html",
        context={
            "registros": registros,
            "usuario": usuario
        }
    )


@app.post("/produccion")
def guardar_produccion(
    request: Request,
    tipo_huevo: str = Form(...),
    cantidad: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    nuevo = Produccion(
        tipo_huevo=tipo_huevo,
        cantidad=cantidad,
        responsable=usuario.nombre
    )
    db.add(nuevo)

    inventario = db.query(Inventario).filter(Inventario.tipo_huevo == tipo_huevo).first()
    inventario.cantidad += cantidad
    db.commit()
    db.refresh(nuevo)

    registrar_bitacora(db, usuario.nombre, "Producción", f"{cantidad} huevos de {tipo_huevo}")

    return RedirectResponse(url=f"/confirmacion/produccion/{nuevo.id}", status_code=303)


@app.get("/ventas")
def ventas_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)

    productos = db.query(Producto).all()

    ventas = db.query(Venta, Producto)\
        .join(Producto, Venta.producto_id == Producto.id)\
        .order_by(Venta.id.desc())\
        .all()

    return templates.TemplateResponse(
        request=request,
        name="ventas.html",
        context={
            "productos": productos,
            "ventas": ventas,
            "usuario": usuario
        }
    )

@app.post("/ventas")
def guardar_venta(
    request: Request,
    producto_id: int = Form(...),
    cantidad_presentaciones: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    inventario = db.query(Inventario).filter(Inventario.tipo_huevo == "Ponedoras").first()

    huevos_reales = cantidad_presentaciones * producto.unidades_por_presentacion

    if huevos_reales > inventario.cantidad:
        return RedirectResponse(url="/ventas", status_code=303)

    total = cantidad_presentaciones * producto.precio

    venta = Venta(
        producto_id=producto.id,
        tipo_huevo_origen="Ponedoras",
        cantidad_presentaciones=cantidad_presentaciones,
        huevos_reales=huevos_reales,
        total=total,
        responsable=usuario.nombre
    )

    inventario.cantidad -= huevos_reales
    db.add(venta)
    db.commit()
    db.refresh(venta)

    registrar_bitacora(db, usuario.nombre, "Venta", f"{cantidad_presentaciones} de {producto.nombre}")

    return RedirectResponse(url=f"/ticket/{venta.id}", status_code=303)

@app.get("/ticket/{venta_id}")
def ver_ticket(venta_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)

    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    producto = db.query(Producto).filter(Producto.id == venta.producto_id).first() if venta else None

    return templates.TemplateResponse(
        request=request,
        name="ticket.html",
        context={
            "venta": venta,
            "producto": producto,
            "usuario": usuario
        }
    )


@app.get("/salidas")
def salidas_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    salidas = db.query(Salida).order_by(Salida.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="salidas.html",
        context={
            "salidas": salidas,
            "usuario": usuario
        }
    )


@app.post("/salidas")
def guardar_salida(
    request: Request,
    tipo_huevo: str = Form(...),
    motivo: str = Form(...),
    cantidad: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    if tipo_huevo == "Ponedoras" and motivo not in ["Roto", "Pequeño"]:
        return RedirectResponse(url="/salidas", status_code=303)

    if tipo_huevo in ["Ponedoras de afuera", "Jolota"] and motivo not in ["Incubadora", "Roto"]:
        return RedirectResponse(url="/salidas", status_code=303)

    inventario = db.query(Inventario).filter(Inventario.tipo_huevo == tipo_huevo).first()

    if cantidad > inventario.cantidad:
        return RedirectResponse(url="/salidas", status_code=303)

    nueva_salida = Salida(
        tipo_huevo=tipo_huevo,
        motivo=motivo,
        cantidad=cantidad,
        responsable=usuario.nombre
    )

    inventario.cantidad -= cantidad
    db.add(nueva_salida)
    db.commit()
    db.refresh(nueva_salida)

    registrar_bitacora(db, usuario.nombre, "Salida", f"{cantidad} huevos - {tipo_huevo} - {motivo}")

    return RedirectResponse(url=f"/confirmacion/salida/{nueva_salida.id}", status_code=303)


@app.get("/gastos")
def gastos_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    gastos = db.query(Gasto).order_by(Gasto.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="gastos.html",
        context={
            "gastos": gastos,
            "usuario": usuario
        }
    )

@app.post("/gastos")
def guardar_gasto(
    request: Request,
    concepto: str = Form(...),
    monto: float = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_login(request, db)

    nuevo_gasto = Gasto(
        concepto=concepto,
        monto=monto,
        responsable=usuario.nombre
    )
    db.add(nuevo_gasto)
    db.commit()
    db.refresh(nuevo_gasto)

    registrar_bitacora(db, usuario.nombre, "Gasto", f"{concepto} - ${monto}")

    return RedirectResponse(url=f"/confirmacion/gasto/{nuevo_gasto.id}", status_code=303)


@app.get("/cortes")
def cortes_page(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    filtro_rapido: str = "",
    db: Session = Depends(get_db)
):
    usuario = requerir_admin(request, db)

    hoy = date.today()

    if filtro_rapido == "semana":
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        fecha_inicio = inicio_semana.isoformat()
        fecha_fin = hoy.isoformat()

    elif filtro_rapido == "mes":
        inicio_mes = hoy.replace(day=1)
        fecha_inicio = inicio_mes.isoformat()
        fecha_fin = hoy.isoformat()

    elif filtro_rapido == "anio":
        inicio_anio = hoy.replace(month=1, day=1)
        fecha_inicio = inicio_anio.isoformat()
        fecha_fin = hoy.isoformat()

    producido_ponedoras = db.query(func.sum(Produccion.cantidad)).filter(
        Produccion.tipo_huevo == "Ponedoras"
    ).scalar() or 0

    producido_afuera = db.query(func.sum(Produccion.cantidad)).filter(
        Produccion.tipo_huevo == "Ponedoras de afuera"
    ).scalar() or 0

    producido_jolota = db.query(func.sum(Produccion.cantidad)).filter(
        Produccion.tipo_huevo == "Jolota"
    ).scalar() or 0

    total_producido = producido_ponedoras + producido_afuera + producido_jolota
    total_vendido = db.query(func.sum(Venta.total)).scalar() or 0
    total_gastos = db.query(func.sum(Gasto.monto)).scalar() or 0
    utilidad = total_vendido - total_gastos

    inventario = db.query(Inventario).all()
    config = db.query(ConfiguracionSemana).first()

    query = db.query(CorteHistorico)

    if fecha_inicio:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        query = query.filter(CorteHistorico.fecha_corte >= fecha_inicio_dt)

    if fecha_fin:
        fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(CorteHistorico.fecha_corte < fecha_fin_dt)

    historico = query.order_by(CorteHistorico.id.desc()).all()

    labels_historico = [str(h.fecha_corte.date()) for h in historico[::-1]]
    ventas_historico = [float(h.total_vendido) for h in historico[::-1]]
    gastos_historico = [float(h.total_gastos) for h in historico[::-1]]
    utilidad_historico = [float(h.utilidad) for h in historico[::-1]]

    producido_ponedoras_hist = [int(h.producido_ponedoras or 0) for h in historico[::-1]]
    producido_afuera_hist = [int(h.producido_afuera or 0) for h in historico[::-1]]
    producido_jolota_hist = [int(h.producido_jolota or 0) for h in historico[::-1]]

    inventario_labels = [i.tipo_huevo for i in inventario]
    inventario_data = [i.cantidad for i in inventario]

    return templates.TemplateResponse(
        request=request,
        name="cortes.html",
        context={
            "usuario": usuario,
            "total_producido": total_producido,
            "producido_ponedoras": producido_ponedoras,
            "producido_afuera": producido_afuera,
            "producido_jolota": producido_jolota,
            "total_vendido": total_vendido,
            "total_gastos": total_gastos,
            "utilidad": utilidad,
            "inventario": inventario,
            "config": config,
            "historico": historico,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "filtro_rapido": filtro_rapido,
            "labels_historico": labels_historico,
            "ventas_historico": ventas_historico,
            "gastos_historico": gastos_historico,
            "utilidad_historico": utilidad_historico,
            "producido_ponedoras_hist": producido_ponedoras_hist,
            "producido_afuera_hist": producido_afuera_hist,
            "producido_jolota_hist": producido_jolota_hist,
            "inventario_labels": inventario_labels,
            "inventario_data": inventario_data
        }
    )


@app.post("/cortes/generar")
def generar_corte(
    request: Request,
    caja_inicial_nueva: float = Form(...),
    ponedoras_nueva: int = Form(...),
    ponedoras_afuera_nueva: int = Form(...),
    jolota_nueva: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = requerir_admin(request, db)

    total_producido = db.query(func.sum(Produccion.cantidad)).scalar() or 0
    total_vendido = db.query(func.sum(Venta.total)).scalar() or 0
    total_gastos = db.query(func.sum(Gasto.monto)).scalar() or 0
    utilidad = total_vendido - total_gastos

    config = db.query(ConfiguracionSemana).first()

    inv_ponedoras = db.query(Inventario).filter(Inventario.tipo_huevo == "Ponedoras").first()
    inv_afuera = db.query(Inventario).filter(Inventario.tipo_huevo == "Ponedoras de afuera").first()
    inv_jolota = db.query(Inventario).filter(Inventario.tipo_huevo == "Jolota").first()

    caja_final = (config.caja_inicial if config else 0) + utilidad

    corte = CorteHistorico(
        caja_inicial_semana=config.caja_inicial if config else 0,
        caja_final_semana=caja_final,
        ponedoras_inicial_semana=config.ponedoras_inicial if config else 0,
        ponedoras_afuera_inicial_semana=config.ponedoras_afuera_inicial if config else 0,
        jolota_inicial_semana=config.jolota_inicial if config else 0,
        ponedoras_final_semana=inv_ponedoras.cantidad if inv_ponedoras else 0,
        ponedoras_afuera_final_semana=inv_afuera.cantidad if inv_afuera else 0,
        jolota_final_semana=inv_jolota.cantidad if inv_jolota else 0,
        total_producido=total_producido,
        total_vendido=total_vendido,
        total_gastos=total_gastos,
        utilidad=utilidad
    )

    db.add(corte)
    db.commit()

    db.query(Produccion).delete()
    db.query(Venta).delete()
    db.query(Salida).delete()
    db.query(Gasto).delete()
    db.commit()

    if inv_ponedoras:
        inv_ponedoras.cantidad = ponedoras_nueva
    if inv_afuera:
        inv_afuera.cantidad = ponedoras_afuera_nueva
    if inv_jolota:
        inv_jolota.cantidad = jolota_nueva

    if config:
        config.caja_inicial = caja_inicial_nueva
        config.ponedoras_inicial = ponedoras_nueva
        config.ponedoras_afuera_inicial = ponedoras_afuera_nueva
        config.jolota_inicial = jolota_nueva

    db.commit()

    registrar_bitacora(
        db,
        usuario.nombre,
        "Corte semanal",
        f"Se realizó corte semanal. Nueva caja inicial: {caja_inicial_nueva}. Nuevos inventarios: Ponedoras={ponedoras_nueva}, Ponedoras de afuera={ponedoras_afuera_nueva}, Jolota={jolota_nueva}"
    )

    return RedirectResponse(url="/cortes", status_code=303)

@app.get("/cortes/pdf/{corte_id}")
def descargar_corte_pdf(corte_id: int, db: Session = Depends(get_db)):
    corte = db.query(CorteHistorico).filter(CorteHistorico.id == corte_id).first()

    if not corte:
        return {"error": "Corte no encontrado"}

    carpeta = "temp_pdfs"
    os.makedirs(carpeta, exist_ok=True)

    archivo_pdf = os.path.join(carpeta, f"corte_{corte_id}.pdf")

    c = canvas.Canvas(archivo_pdf, pagesize=letter)
    width, height = letter

    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Corte histórico #{corte.id}")
    y -= 30

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Fecha de corte: {corte.fecha_corte}")
    y -= 25

    c.drawString(50, y, f"Caja inicial: ${corte.caja_inicial_semana}")
    y -= 20
    c.drawString(50, y, f"Caja final: ${corte.caja_final_semana}")
    y -= 20
    c.drawString(50, y, f"Total producido: {corte.total_producido}")
    y -= 20
    c.drawString(50, y, f"Total vendido: ${corte.total_vendido}")
    y -= 20
    c.drawString(50, y, f"Total gastos: ${corte.total_gastos}")
    y -= 20
    c.drawString(50, y, f"Utilidad: ${corte.utilidad}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Inventario inicial")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Ponedoras: {corte.ponedoras_inicial_semana}")
    y -= 20
    c.drawString(50, y, f"Ponedoras de afuera: {corte.ponedoras_afuera_inicial_semana}")
    y -= 20
    c.drawString(50, y, f"Jolota: {corte.jolota_inicial_semana}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Inventario final")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Ponedoras: {corte.ponedoras_final_semana}")
    y -= 20
    c.drawString(50, y, f"Ponedoras de afuera: {corte.ponedoras_afuera_final_semana}")
    y -= 20
    c.drawString(50, y, f"Jolota: {corte.jolota_final_semana}")
    y -= 40

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, "Huevos Alak POS - Reporte generado por el sistema")

    c.save()

    return FileResponse(
        path=archivo_pdf,
        filename=f"corte_{corte_id}.pdf",
        media_type="application/pdf"
    )

@app.get("/bitacora")
def bitacora_page(request: Request, db: Session = Depends(get_db)):
    usuario = requerir_admin(request, db)
    movimientos = db.query(Bitacora).order_by(Bitacora.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="bitacora.html",
        context={
            "movimientos": movimientos,
            "usuario": usuario
        }
    )

@app.get("/confirmacion/produccion/{registro_id}")
def confirmacion_produccion(registro_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    registro = db.query(Produccion).filter(Produccion.id == registro_id).first()

    return templates.TemplateResponse(
        request=request,
        name="confirmacion_produccion.html",
        context={
            "usuario": usuario,
            "registro": registro
        }
    )


@app.get("/confirmacion/salida/{salida_id}")
def confirmacion_salida(salida_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    salida = db.query(Salida).filter(Salida.id == salida_id).first()

    return templates.TemplateResponse(
        request=request,
        name="confirmacion_salida.html",
        context={
            "usuario": usuario,
            "salida": salida
        }
    )


@app.get("/confirmacion/gasto/{gasto_id}")
def confirmacion_gasto(gasto_id: int, request: Request, db: Session = Depends(get_db)):
    usuario = requerir_login(request, db)
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()

    return templates.TemplateResponse(
        request=request,
        name="confirmacion_gasto.html",
        context={
            "usuario": usuario,
            "gasto": gasto
        }
    )