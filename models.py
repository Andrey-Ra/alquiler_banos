from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
 
db = SQLAlchemy()
 
# ─────────────────────────────────────────
#  CLIENTE
# ─────────────────────────────────────────
class Cliente(db.Model):
    __tablename__ = 'cliente'
 
    id             = db.Column(db.Integer, primary_key=True)
    nombre         = db.Column(db.String(100), nullable=False)
    email          = db.Column(db.String(100), nullable=False, default='')
    telefono       = db.Column(db.String(20),  nullable=False)
    direccion      = db.Column(db.String(200), default='')
    ruc_ci         = db.Column(db.String(20),  unique=True, nullable=False)
    tipo           = db.Column(db.String(20),  nullable=False, default='particular')  # particular | empresa
    fecha_registro = db.Column(db.DateTime,    default=datetime.utcnow)
    activo         = db.Column(db.Boolean,     default=True)
 
    # Relaciones
    alquileres = db.relationship('Alquiler', backref='cliente', lazy=True)
 
 
# ─────────────────────────────────────────
#  BAÑO PORTÁTIL
# ─────────────────────────────────────────
class BanoPortatil(db.Model):
    __tablename__ = 'bano_portatil'
 
    id            = db.Column(db.Integer, primary_key=True)
    codigo        = db.Column(db.String(20),    unique=True, nullable=False)
    tipo          = db.Column(db.String(50),    nullable=False)   # standard | vip | accesible
    estado        = db.Column(db.String(20),    nullable=False, default='disponible')  # disponible | alquilado | mantenimiento
    precio_dia    = db.Column(db.Float,         nullable=False)
    capacidad     = db.Column(db.Integer)
    fecha_compra  = db.Column(db.Date)
    activo        = db.Column(db.Boolean,       default=True)
    observaciones = db.Column(db.Text)
 
    # Relaciones
    detalles      = db.relationship('DetalleAlquiler', backref='bano', lazy=True)
    mantenimientos = db.relationship('Mantenimiento',  backref='bano', lazy=True)
 
 
# ─────────────────────────────────────────
#  USUARIO
# ─────────────────────────────────────────
class Usuario(db.Model):
    __tablename__ = 'usuario'
 
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50),  unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    rol           = db.Column(db.String(20),  nullable=False, default='operador')  # administrador | operador | consultor
    nombre        = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(100), nullable=False)
    activo        = db.Column(db.Boolean,     default=True)
    ultimo_acceso = db.Column(db.DateTime)
 
    # Relaciones
    alquileres    = db.relationship('Alquiler',     backref='usuario',       lazy=True)
    mantenimientos = db.relationship('Mantenimiento', backref='usuario',      lazy=True)
 
 
# ─────────────────────────────────────────
#  ALQUILER
# ─────────────────────────────────────────
class Alquiler(db.Model):
    __tablename__ = 'alquiler'
 
    id             = db.Column(db.Integer, primary_key=True)
    cliente_id     = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    usuario_id     = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    fecha_inicio   = db.Column(db.DateTime, nullable=False)
    fecha_fin      = db.Column(db.DateTime, nullable=False)
    total          = db.Column(db.Float,    nullable=False, default=0.0)
    estado         = db.Column(db.String(20), nullable=False, default='activo')  # pendiente | activo | finalizado | cancelado
    deposito       = db.Column(db.Float,    default=0.0)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    observaciones  = db.Column(db.Text)
 
    # Relaciones
    detalles = db.relationship('DetalleAlquiler', backref='alquiler', lazy=True, cascade='all, delete-orphan')
    pagos    = db.relationship('Pago',            backref='alquiler', lazy=True, cascade='all, delete-orphan')
 
 
# ─────────────────────────────────────────
#  DETALLE ALQUILER  (tabla puente)
# ─────────────────────────────────────────
class DetalleAlquiler(db.Model):
    __tablename__ = 'detalle_alquiler'
 
    id          = db.Column(db.Integer, primary_key=True)
    alquiler_id = db.Column(db.Integer, db.ForeignKey('alquiler.id'), nullable=False)
    bano_id     = db.Column(db.Integer, db.ForeignKey('bano_portatil.id'), nullable=False)
    cantidad    = db.Column(db.Integer, nullable=False, default=1)
    subtotal    = db.Column(db.Float,   nullable=False, default=0.0)
 
 
# ─────────────────────────────────────────
#  PAGO
# ─────────────────────────────────────────
class Pago(db.Model):
    __tablename__ = 'pago'
 
    id          = db.Column(db.Integer, primary_key=True)
    alquiler_id = db.Column(db.Integer, db.ForeignKey('alquiler.id'), nullable=False)
    monto       = db.Column(db.Float,   nullable=False)
    fecha_pago  = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_pago   = db.Column(db.String(30), nullable=False)  # efectivo | transferencia | tarjeta | deposito
    referencia  = db.Column(db.String(50))
    observaciones = db.Column(db.Text)
    estado      = db.Column(db.String(20), nullable=False, default='completado')  # completado | pendiente | reembolsado
 
 
# ─────────────────────────────────────────
#  MANTENIMIENTO
# ─────────────────────────────────────────
class Mantenimiento(db.Model):
    __tablename__ = 'mantenimiento'
 
    id           = db.Column(db.Integer, primary_key=True)
    bano_id      = db.Column(db.Integer, db.ForeignKey('bano_portatil.id'), nullable=False)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'),       nullable=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin    = db.Column(db.DateTime)
    tipo_mant    = db.Column(db.String(50), nullable=False)  # limpieza | reparacion | revision_general
    costo        = db.Column(db.Float,      default=0.0)
    observaciones = db.Column(db.Text)
    estado       = db.Column(db.String(20), nullable=False, default='en_proceso')  # en_proceso | completado | pendiente