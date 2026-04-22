from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from datetime import datetime
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    rol = Column(String, nullable=False)  # admin o operador
    activo = Column(Boolean, default=True)

    debe_cambiar_password = Column(Boolean, default=False)
    password_modificada_por_admin = Column(Boolean, default=False)


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    unidades_por_presentacion = Column(Integer, default=1)


class Inventario(Base):
    __tablename__ = "inventario"

    id = Column(Integer, primary_key=True, index=True)
    tipo_huevo = Column(String, unique=True, nullable=False)
    cantidad = Column(Integer, default=0)


class Produccion(Base):
    __tablename__ = "produccion"

    id = Column(Integer, primary_key=True, index=True)
    tipo_huevo = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    responsable = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.now)


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    tipo_huevo_origen = Column(String, nullable=False)
    cantidad_presentaciones = Column(Integer, nullable=False)
    huevos_reales = Column(Integer, nullable=False)
    total = Column(Float, default=0)
    responsable = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.now)


class Salida(Base):
    __tablename__ = "salidas"

    id = Column(Integer, primary_key=True, index=True)
    tipo_huevo = Column(String, nullable=False)
    motivo = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    responsable = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.now)


class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True, index=True)
    concepto = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    responsable = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.now)


class Bitacora(Base):
    __tablename__ = "bitacora"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String, nullable=False)
    accion = Column(String, nullable=False)
    detalle = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.now)


class ConfiguracionSemana(Base):
    __tablename__ = "configuracion_semana"

    id = Column(Integer, primary_key=True, index=True)
    fecha_inicio = Column(DateTime, default=datetime.now)
    caja_inicial = Column(Float, default=0)
    ponedoras_inicial = Column(Integer, default=0)
    ponedoras_afuera_inicial = Column(Integer, default=0)
    jolota_inicial = Column(Integer, default=0)


class CorteHistorico(Base):
    __tablename__ = "cortes_historicos"

    id = Column(Integer, primary_key=True, index=True)
    fecha_corte = Column(DateTime, default=datetime.now)

    caja_inicial_semana = Column(Float, default=0)
    caja_final_semana = Column(Float, default=0)

    ponedoras_inicial_semana = Column(Integer, default=0)
    ponedoras_afuera_inicial_semana = Column(Integer, default=0)
    jolota_inicial_semana = Column(Integer, default=0)

    ponedoras_final_semana = Column(Integer, default=0)
    ponedoras_afuera_final_semana = Column(Integer, default=0)
    jolota_final_semana = Column(Integer, default=0)

    total_producido = Column(Integer, default=0)
    total_vendido = Column(Float, default=0)
    total_gastos = Column(Float, default=0)
    utilidad = Column(Float, default=0)

    producido_ponedoras = Column(Integer, default=0)
    producido_afuera = Column(Integer, default=0)
    producido_jolota = Column(Integer, default=0)
    