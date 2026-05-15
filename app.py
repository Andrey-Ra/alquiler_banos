from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from config import Config
from models import Usuario, db, Cliente, BanoPortatil
from flask_pymongo import PyMongo
from models import Alquiler, DetalleAlquiler
from models import Pago
from models import Mantenimiento
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies, unset_jwt_cookies
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
mongo = PyMongo(app)
jwt = JWTManager(app)

#Ayuda a iniciar sesión con el rol
@jwt.unauthorized_loader
def unauthorized_callback(callback):

    flash("Debes iniciar sesión.", "warning")

    return redirect(url_for('login'))

#Ayuda a cerrar sesión
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):

    flash(
        "Tu sesión expiró. Inicia sesión nuevamente.",
        "warning"
    )

    response = redirect(
        url_for('login')
    )

    unset_jwt_cookies(
        response
    )

    return response

# ══════════════════════════════════════════
#  USUARIO DISPONIBLE EN TODOS LOS TEMPLATES
# ══════════════════════════════════════════
@app.context_processor
def inject_user():

    try:

        current_user_id = get_jwt_identity()

        if current_user_id:

            user = Usuario.query.get(
                current_user_id
            )

            return dict(
                current_user=user
            )

    except:
        pass

    return dict(
        current_user=None
    )

# ══════════════════════════════════════════
#  MANEJO DE ERRORES JWT
# ══════════════════════════════════════════
@jwt.unauthorized_loader
def token_faltante(callback):
    flash("Debes iniciar sesión para continuar.", "warning")
    return redirect(url_for('login'))


@jwt.expired_token_loader
def token_expirado(jwt_header, jwt_payload):
    flash("Tu sesión ha expirado.", "warning")
    return redirect(url_for('login'))


@jwt.invalid_token_loader
def token_invalido(callback):
    flash("Sesión inválida.", "danger")
    return redirect(url_for('login'))

# ══════════════════════════════════════════
#  DECORADOR DE ROLES
# ══════════════════════════════════════════
def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = Usuario.query.get(current_user_id)
        if not user or user.rol != 'admin':
            flash("Acceso denegado: Se requieren permisos de administrador.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ══════════════════════════════════════════
#  DECORADORES DE SEGURIDAD (JWT + RBAC)
# ══════════════════════════════════════════
def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):

        current_user_id = get_jwt_identity()
        user = Usuario.query.get(current_user_id)

        if not user or user.rol != 'admin':
            flash(
                "Acceso denegado: Se requieren permisos de administrador.",
                "danger"
            )
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


def roles_required(*roles_permitidos):
    """
    Permite restringir rutas según rol.

    Ejemplo:
    @roles_required('admin', 'operador')
    """

    def decorator(f):

        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):

            current_user_id = get_jwt_identity()
            user = Usuario.query.get(current_user_id)

            if not user:
                flash(
                    "Usuario no encontrado.",
                    "danger"
                )
                return redirect(url_for('login'))

            if user.rol not in roles_permitidos:
                flash(
                    "No tienes permisos para realizar esta acción.",
                    "danger"
                )
                return redirect(url_for('index'))

            return f(*args, **kwargs)

        return decorated_function

    return decorator

# ══════════════════════════════════════════
#  LOG DE ACTIVIDAD (MongoDB)
# ══════════════════════════════════════════
def registrar_log(accion, modulo, descripcion, datos_extra=None):

    usuario_actual = None


    try:

        user_id = get_jwt_identity()

        if user_id:

            usuario_actual = Usuario.query.get(
                int(user_id)
            )

    except:

        pass


    log = {

        'accion'      : accion,
        'modulo'      : modulo,
        'descripcion' : descripcion,
        'fecha'       : datetime.utcnow(),

        'usuario'     : usuario_actual.nombre if usuario_actual else 'Sistema',

        'email'       : usuario_actual.email if usuario_actual else 'sistema',

        'rol'         : usuario_actual.rol if usuario_actual else 'sistema',

        'datos_extra' : datos_extra or {}

    }


    try:

        mongo.db.logs.insert_one(
            log
        )

    except Exception as e:

        print(
            "MongoDB no disponible:",
            e
        )

# ══════════════════════════════════════════
#  INICIO
# ══════════════════════════════════════════
@app.route('/')
@jwt_required()
def index():
    # Baños
    total_banos      = BanoPortatil.query.filter_by(activo=True).count()
    disponibles      = BanoPortatil.query.filter_by(activo=True, estado='disponible').count()
    alquilados       = BanoPortatil.query.filter_by(activo=True, estado='alquilado').count()
    en_mantenimiento = BanoPortatil.query.filter_by(activo=True, estado='mantenimiento').count()

    # Clientes
    total_clientes = Cliente.query.filter_by(activo=True).count()

    # Alquileres
    alquileres_activos  = Alquiler.query.filter_by(estado='activo').count()
    alquileres_recientes = Alquiler.query.order_by(Alquiler.fecha_registro.desc()).limit(5).all()

    # Ingresos totales
    ingreso_total = db.session.query(
        func.sum(Alquiler.total)
    ).filter(Alquiler.estado.in_(['activo', 'finalizado'])).scalar() or 0

    # Últimos 5 eventos de MongoDB
    logs_recientes = list(mongo.db.logs.find().sort('fecha', -1).limit(5))
    for log in logs_recientes:
        log['_id'] = str(log['_id'])

    return render_template('index.html',
        total_banos         = total_banos,
        disponibles         = disponibles,
        alquilados          = alquilados,
        en_mantenimiento    = en_mantenimiento,
        total_clientes      = total_clientes,
        alquileres_activos  = alquileres_activos,
        alquileres_recientes = alquileres_recientes,
        ingreso_total       = ingreso_total,
        logs_recientes      = logs_recientes
    )

# ══════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Usuario.query.filter_by(email=email).first()

        if user and user.check_password(password):
            access_token = create_access_token(identity=str(user.id))
            response = redirect(url_for('index'))
            set_access_cookies(response, access_token)
            flash(f"Bienvenido de nuevo, {user.nombre}", "success")
            return response
        
        flash("Credenciales inválidas", "danger")
    return render_template('login.html')

# ══════════════════════════════════════════
#  REGISTRO DE USUARIOS
# ══════════════════════════════════════════
@app.route('/registro', methods=['GET', 'POST'])
def registro():

    if request.method == 'POST':

        email = request.form.get('email')
        username = request.form.get('username')
        nombre = request.form.get('nombre')
        password = request.form.get('password')

        # Validar duplicados
        existe = Usuario.query.filter_by(email=email).first()

        if existe:
            flash("Ya existe un usuario con ese correo.", "danger")
            return render_template('registro.html')

        # Crear usuario
        usuario = Usuario(
            email=email,
            username=username,
            nombre=nombre,
            rol='consultor'
        )

        # Hash seguro
        usuario.set_password(password)

        db.session.add(usuario)
        db.session.commit()

        flash("Usuario registrado correctamente.", "success")

        return redirect(url_for('login'))

    return render_template('registro.html')

# ══════════════════════════════════════════
#  CLIENTES
# ══════════════════════════════════════════
@app.route('/clientes')
@jwt_required()
def clientes():
    lista = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    return render_template('clientes.html', clientes=lista)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def nuevo_cliente():
    if request.method == 'POST':
        # Verificar RUC/CI duplicado
        existente = Cliente.query.filter_by(ruc_ci=request.form['ruc_ci']).first()
        if existente:
            flash('Ya existe un cliente con ese RUC/CI.', 'error')
            return render_template('nuevo_cliente.html')

        cliente = Cliente(
            nombre    = request.form['nombre'],
            email     = request.form['email'],
            telefono  = request.form['telefono'],
            direccion = request.form['direccion'],
            ruc_ci    = request.form['ruc_ci'],
            tipo      = request.form['tipo']
        )
        db.session.add(cliente)
        registrar_log(
            accion      = 'crear',
            modulo      = 'clientes',
            descripcion = f'Cliente "{cliente.nombre}" registrado',
            datos_extra = {'ruc_ci': cliente.ruc_ci, 'tipo': cliente.tipo}
     )
        db.session.commit()
        flash('Cliente registrado correctamente.', 'ok')
        return redirect(url_for('clientes'))

    return render_template('nuevo_cliente.html')


@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == 'POST':
        # Verificar RUC/CI duplicado (excluyendo al propio cliente)
        existente = Cliente.query.filter(
            Cliente.ruc_ci == request.form['ruc_ci'],
            Cliente.id != id
        ).first()
        if existente:
            flash('Ya existe otro cliente con ese RUC/CI.', 'error')
            return render_template('editar_cliente.html', cliente=cliente)

        cliente.nombre    = request.form['nombre']
        cliente.email     = request.form['email']
        cliente.telefono  = request.form['telefono']
        cliente.direccion = request.form['direccion']
        cliente.ruc_ci    = request.form['ruc_ci']
        cliente.tipo      = request.form['tipo']
        registrar_log(
            accion      = 'editar',
            modulo      = 'clientes',
            descripcion = f'Cliente "{cliente.nombre}" actualizado',
            datos_extra = {'id': cliente.id}
        )
        db.session.commit()
        flash('Cliente actualizado correctamente.', 'ok')
        return redirect(url_for('clientes'))

    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/clientes/eliminar/<int:id>')
@roles_required('admin')
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    # Baja lógica: simplemente marcamos como inactivo
    registrar_log(
        accion      = 'eliminar',
        modulo      = 'clientes',
        descripcion = f'Cliente "{cliente.nombre}" eliminado',
        datos_extra = {'id': cliente.id}
    )
    cliente.activo = False
    db.session.commit()
    flash('Cliente eliminado correctamente.', 'ok')
    return redirect(url_for('clientes'))


# ══════════════════════════════════════════
#  BAÑOS PORTÁTILES
# ══════════════════════════════════════════
@app.route('/banos')
@jwt_required()
def banos():
    lista = BanoPortatil.query.filter_by(activo=True).order_by(BanoPortatil.codigo).all()
    return render_template('banos.html', banos=lista)


@app.route('/banos/nuevo', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def nuevo_bano():
    if request.method == 'POST':
        # Verificar código duplicado
        existente = BanoPortatil.query.filter_by(codigo=request.form['codigo']).first()
        if existente:
            flash('Ya existe un baño con ese código.', 'error')
            return render_template('nuevo_bano.html')

        bano = BanoPortatil(
            codigo        = request.form['codigo'],
            tipo          = request.form['tipo'],
            estado        = request.form['estado'],
            precio_dia    = float(request.form['precio_dia']),
            capacidad     = int(request.form['capacidad']) if request.form['capacidad'] else None,
            observaciones = request.form['observaciones']
        )
        db.session.add(bano)
        registrar_log(
            accion      = 'crear',
            modulo      = 'banos',
            descripcion = f'Baño "{bano.codigo}" registrado en inventario',
            datos_extra = {'tipo': bano.tipo, 'precio_dia': bano.precio_dia}
        )
        db.session.commit()
        flash('Baño registrado correctamente.', 'ok')
        return redirect(url_for('banos'))

    return render_template('nuevo_bano.html')


@app.route('/banos/editar/<int:id>', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def editar_bano(id):
    bano = BanoPortatil.query.get_or_404(id)

    if request.method == 'POST':
        # Verificar código duplicado (excluyendo al propio baño)
        existente = BanoPortatil.query.filter(
            BanoPortatil.codigo == request.form['codigo'],
            BanoPortatil.id != id
        ).first()
        if existente:
            flash('Ya existe otro baño con ese código.', 'error')
            return render_template('editar_bano.html', bano=bano)

        bano.codigo        = request.form['codigo']
        bano.tipo          = request.form['tipo']
        bano.estado        = request.form['estado']
        bano.precio_dia    = float(request.form['precio_dia'])
        bano.capacidad     = int(request.form['capacidad']) if request.form['capacidad'] else None
        bano.observaciones = request.form['observaciones']
        registrar_log(
            accion      = 'editar',
            modulo      = 'banos',
            descripcion = f'Baño "{bano.codigo}" actualizado',
            datos_extra = {'id': bano.id, 'estado': bano.estado}
        )
        db.session.commit()
        flash('Baño actualizado correctamente.', 'ok')
        return redirect(url_for('banos'))

    return render_template('editar_bano.html', bano=bano)


@app.route('/banos/eliminar/<int:id>')
@roles_required('admin')
def eliminar_bano(id):
    bano = BanoPortatil.query.get_or_404(id)
    # Baja lógica
    bano.activo = False
    db.session.commit()
    flash('Baño eliminado correctamente.', 'ok')
    return redirect(url_for('banos'))

# ══════════════════════════════════════════
#  ALQUILERES
# ══════════════════════════════════════════
@app.route('/alquileres')
@jwt_required()
def alquileres():
    lista = Alquiler.query.order_by(Alquiler.fecha_registro.desc()).all()
    return render_template('alquileres.html', alquileres=lista)


@app.route('/alquileres/nuevo', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def nuevo_alquiler():
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    banos    = BanoPortatil.query.filter_by(activo=True, estado='disponible').all()

    if request.method == 'POST':
        cliente_id   = int(request.form['cliente_id'])
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin    = datetime.strptime(request.form['fecha_fin'],    '%Y-%m-%d')
        deposito     = float(request.form.get('deposito', 0))
        observaciones = request.form.get('observaciones', '')

        # Validar fechas
        if fecha_fin <= fecha_inicio:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'error')
            return render_template('nuevo_alquiler.html', clientes=clientes, banos=banos)

        dias = (fecha_fin - fecha_inicio).days

        # Recoger baños seleccionados del formulario
        banos_seleccionados = request.form.getlist('bano_ids')
        if not banos_seleccionados:
            flash('Debes seleccionar al menos un baño.', 'error')
            return render_template('nuevo_alquiler.html', clientes=clientes, banos=banos)

        # Calcular total
        total = 0
        detalles_data = []
        for bano_id in banos_seleccionados:
            bano     = BanoPortatil.query.get(int(bano_id))
            cantidad = int(request.form.get(f'cantidad_{bano_id}', 1))
            subtotal = bano.precio_dia * cantidad * dias
            total   += subtotal
            detalles_data.append({'bano': bano, 'cantidad': cantidad, 'subtotal': subtotal})

        # Crear alquiler
        alquiler = Alquiler(
            cliente_id    = cliente_id,
            fecha_inicio  = fecha_inicio,
            fecha_fin     = fecha_fin,
            total         = total,
            deposito      = deposito,
            observaciones = observaciones,
            estado        = 'activo'
        )
        db.session.add(alquiler)
        db.session.flush()  # para obtener el ID del alquiler

        # Crear detalles y marcar baños como alquilados
        for d in detalles_data:
            detalle = DetalleAlquiler(
                alquiler_id = alquiler.id,
                bano_id     = d['bano'].id,
                cantidad    = d['cantidad'],
                subtotal    = d['subtotal']
            )
            db.session.add(detalle)
            d['bano'].estado = 'alquilado'  # cambiar estado del baño

        registrar_log(
            accion      = 'crear',
            modulo      = 'alquileres',
            descripcion = f'Alquiler #{alquiler.id} creado para cliente_id {cliente_id}',
            datos_extra = {
                'cliente_id'  : cliente_id,
                'fecha_inicio': str(fecha_inicio.date()),
                'fecha_fin'   : str(fecha_fin.date()),
                'total'       : total,
                'dias'        : dias
           }
        )
        db.session.commit()
        flash(f'Alquiler #{alquiler.id} registrado. Total: ${total:.2f}', 'ok')
        return redirect(url_for('alquileres'))

    return render_template('nuevo_alquiler.html', clientes=clientes, banos=banos)

@app.route('/clientes/<int:id>')
def detalle_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # Alquileres del cliente desde SQLite
    alquileres = Alquiler.query.filter_by(
        cliente_id=id
    ).order_by(Alquiler.fecha_registro.desc()).all()

    # Total gastado
    total_gastado = sum(a.total for a in alquileres if a.estado in ['activo', 'finalizado'])

    # Logs del cliente desde MongoDB
    logs = list(mongo.db.logs.find({
        'modulo': 'clientes',
        'descripcion': {'$regex': f'"{cliente.nombre}"'}
    }).sort('fecha', -1))
    for log in logs:
        log['_id'] = str(log['_id'])

    return render_template('detalle_cliente.html',
        cliente       = cliente,
        alquileres    = alquileres,
        total_gastado = total_gastado,
        logs          = logs
    )

@app.route('/alquileres/<int:id>')
def detalle_alquiler(id):
    alquiler = Alquiler.query.get_or_404(id)

    logs = list(mongo.db.logs.find({
        'modulo': 'alquileres',
        'descripcion': {'$regex': f'#{id}'}
    }).sort('fecha', -1))

    for log in logs:
        log['_id'] = str(log['_id'])

    return render_template('detalle_alquiler.html', alquiler=alquiler, logs=logs)

@app.route('/alquileres/<int:id>/finalizar', methods=['POST'])
@roles_required('admin', 'operador')
def finalizar_alquiler(id):
    alquiler = Alquiler.query.get_or_404(id)

    if alquiler.estado != 'activo':
        flash('Este alquiler no está activo.', 'error')
        return redirect(url_for('detalle_alquiler', id=id))

    # Devolver baños a disponible
    for detalle in alquiler.detalles:
        detalle.bano.estado = 'disponible'

    alquiler.estado = 'finalizado'
    registrar_log(
        accion      = 'finalizar',
        modulo      = 'alquileres',
        descripcion = f'Alquiler #{alquiler.id} finalizado',
        datos_extra = {'cliente': alquiler.cliente.nombre, 'total': alquiler.total}
    ) 
    db.session.commit()
    flash(f'Alquiler #{alquiler.id} finalizado. Baños devueltos al inventario.', 'ok')
    return redirect(url_for('alquileres'))

# ══════════════════════════════════════════
#  PAGOS
# ══════════════════════════════════════════
@app.route('/pagos')
@jwt_required()
def pagos():
    lista = Pago.query.order_by(Pago.fecha_pago.desc()).all()
    return render_template('pagos.html', pagos=lista)


@app.route('/pagos/nuevo/<int:alquiler_id>', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def nuevo_pago(alquiler_id):
    alquiler = Alquiler.query.get_or_404(alquiler_id)

    # Calcular cuánto se ha pagado ya
    pagado = sum(p.monto for p in alquiler.pagos if p.estado == 'completado')
    pendiente = alquiler.total - pagado

    if request.method == 'POST':
        monto = float(request.form['monto'])

        if monto <= 0:
            flash('El monto debe ser mayor a cero.', 'error')
            return render_template('nuevo_pago.html', alquiler=alquiler,
                                   pagado=pagado, pendiente=pendiente)

        pago = Pago(
            alquiler_id   = alquiler.id,
            monto         = monto,
            tipo_pago     = request.form['tipo_pago'],
            referencia    = request.form.get('referencia', ''),
            observaciones = request.form.get('observaciones', ''),
            estado        = 'completado'
        )
        db.session.add(pago)
        registrar_log(
            accion      = 'crear',
            modulo      = 'pagos',
            descripcion = f'Pago de ${monto:.2f} registrado para alquiler #{alquiler_id}',
            datos_extra = {'tipo_pago': pago.tipo_pago, 'monto': monto}
        )
        db.session.commit()
        flash(f'Pago de ${monto:.2f} registrado correctamente.', 'ok')
        return redirect(url_for('detalle_alquiler', id=alquiler_id))

    return render_template('nuevo_pago.html', alquiler=alquiler,
                           pagado=pagado, pendiente=pendiente)


@app.route('/pagos/anular/<int:pago_id>')
@roles_required('admin')
def anular_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    pago.estado = 'reembolsado'
    db.session.commit()
    flash('Pago anulado correctamente.', 'ok')
    return redirect(url_for('detalle_alquiler', id=pago.alquiler_id))

# ══════════════════════════════════════════
#  MANTENIMIENTO
# ══════════════════════════════════════════
@app.route('/mantenimiento')
@jwt_required()
def mantenimiento():
    lista = Mantenimiento.query.order_by(Mantenimiento.fecha_inicio.desc()).all()
    return render_template('mantenimiento.html', registros=lista)


@app.route('/mantenimiento/nuevo', methods=['GET', 'POST'])
@roles_required('admin', 'operador')
def nuevo_mantenimiento():
    banos = BanoPortatil.query.filter_by(activo=True).all()

    if request.method == 'POST':
        bano_id      = int(request.form['bano_id'])
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin_str = request.form.get('fecha_fin', '').strip()
        fecha_fin    = datetime.strptime(fecha_fin_str, '%Y-%m-%d') if fecha_fin_str else None
        costo        = float(request.form.get('costo', 0) or 0)

        mantenimiento = Mantenimiento(
            bano_id       = bano_id,
            fecha_inicio  = fecha_inicio,
            fecha_fin     = fecha_fin,
            tipo_mant     = request.form['tipo_mant'],
            costo         = costo,
            observaciones = request.form.get('observaciones', ''),
            estado        = 'en_proceso'
        )
        db.session.add(mantenimiento)

        # Cambiar estado del baño a mantenimiento
        bano = BanoPortatil.query.get(bano_id)
        bano.estado = 'mantenimiento'
        registrar_log(
            accion      = 'crear',
            modulo      = 'mantenimiento',
            descripcion = f'Mantenimiento registrado para baño {bano.codigo}',
            datos_extra = {'tipo': request.form["tipo_mant"], 'costo': costo}
        )
        db.session.commit()
        flash(f'Mantenimiento registrado para el baño {bano.codigo}.', 'ok')
        return redirect(url_for('mantenimiento'))

    return render_template('nuevo_mantenimiento.html', banos=banos)


@app.route('/mantenimiento/<int:id>/completar', methods=['POST'])
@roles_required('admin', 'operador')
def completar_mantenimiento(id):
    registro = Mantenimiento.query.get_or_404(id)

    if registro.estado == 'completado':
        flash('Este mantenimiento ya fue completado.', 'error')
        return redirect(url_for('mantenimiento'))

    registro.estado   = 'completado'
    registro.fecha_fin = datetime.utcnow()

    # Devolver el baño a disponible
    registro.bano.estado = 'disponible'
    registrar_log(
        accion      = 'completar',
        modulo      = 'mantenimiento',
        descripcion = f'Mantenimiento completado para baño {registro.bano.codigo}',
        datos_extra = {'costo': registro.costo, 'tipo': registro.tipo_mant}
    )
    db.session.commit()
    flash(f'Mantenimiento completado. Baño {registro.bano.codigo} disponible nuevamente.', 'ok')
    return redirect(url_for('mantenimiento'))

# ══════════════════════════════════════════
#  REPORTES
# ══════════════════════════════════════════
@app.route('/reportes')
@admin_required
def reportes():
    # ── Alquileres activos
    alquileres_activos = Alquiler.query.filter_by(estado='activo').all()

    # ── Ingresos por mes (últimos 6 meses)
    ingresos_mes = db.session.query(
        func.strftime('%Y-%m', Alquiler.fecha_registro).label('mes'),
        func.sum(Alquiler.total).label('total')
    ).filter(
        Alquiler.estado.in_(['activo', 'finalizado'])
    ).group_by('mes').order_by('mes').limit(6).all()

    # ── Estado del inventario
    total_banos      = BanoPortatil.query.filter_by(activo=True).count()
    disponibles      = BanoPortatil.query.filter_by(activo=True, estado='disponible').count()
    alquilados       = BanoPortatil.query.filter_by(activo=True, estado='alquilado').count()
    en_mantenimiento = BanoPortatil.query.filter_by(activo=True, estado='mantenimiento').count()

    # ── Clientes con más alquileres
    top_clientes = db.session.query(
        Cliente.nombre,
        func.count(Alquiler.id).label('total_alquileres'),
        func.sum(Alquiler.total).label('total_pagado')
    ).join(Alquiler).group_by(Cliente.id).order_by(
        func.count(Alquiler.id).desc()
    ).limit(5).all()

    # ── Ingresos totales
    ingreso_total = db.session.query(
        func.sum(Alquiler.total)
    ).filter(Alquiler.estado.in_(['activo', 'finalizado'])).scalar() or 0

    # ── Baños en mantenimiento activo
    banos_mantenimiento = Mantenimiento.query.filter_by(estado='en_proceso').all()

    return render_template('reportes.html',
        alquileres_activos  = alquileres_activos,
        ingresos_mes        = ingresos_mes,
        total_banos         = total_banos,
        disponibles         = disponibles,
        alquilados          = alquilados,
        en_mantenimiento    = en_mantenimiento,
        top_clientes        = top_clientes,
        ingreso_total       = ingreso_total,
        banos_mantenimiento = banos_mantenimiento
    )

# ══════════════════════════════════════════
#  ACTIVIDAD (MongoDB)
# ══════════════════════════════════════════
@app.route('/actividad')
@admin_required
def actividad():
    modulo = request.args.get('modulo', 'todos')

    # Filtrar por módulo si se selecciona uno
    filtro = {} if modulo == 'todos' else {'modulo': modulo}

    # Traer los últimos 50 eventos de MongoDB
    logs = list(mongo.db.logs.find(filtro).sort('fecha', -1).limit(50))

    # Convertir ObjectId a string para que Jinja pueda usarlo
    for log in logs:
        log['_id'] = str(log['_id'])

    return render_template('actividad.html', logs=logs, modulo_activo=modulo)

# Detalle de baño con logs relacionados
@app.route('/banos/<int:id>')
def detalle_bano(id):
    bano = BanoPortatil.query.get_or_404(id)

    # Traer eventos de este baño desde MongoDB
    logs = list(mongo.db.logs.find({
        'modulo': {'$in': ['banos', 'mantenimiento']},
        'descripcion': {'$regex': bano.codigo}
    }).sort('fecha', -1))

    for log in logs:
        log['_id'] = str(log['_id'])

    return render_template('detalle_bano.html', bano=bano, logs=logs)

# ══════════════════════════════════════════
#  ARRANQUE
# ══════════════════════════════════════════
if __name__ == '__main__':

    with app.app_context():

        db.create_all()

        usuarios_iniciales = [

            {
                'username': 'admin',
                'nombre': 'Administrador',
                'email': 'admin@admin.com',
                'password': '123456',
                'rol': 'admin'
            },

            {
                'username': 'operador',
                'nombre': 'Usuario Operador',
                'email': 'operador@admin.com',
                'password': '123456',
                'rol': 'operador'
            },

            {
                'username': 'consultor',
                'nombre': 'Usuario Consultor',
                'email': 'consultor@admin.com',
                'password': '123456',
                'rol': 'consultor'
            }
        ]


        for datos in usuarios_iniciales:

            existe = Usuario.query.filter_by(
                email=datos['email']
            ).first()

            if not existe:

                usuario = Usuario(
                    username=datos['username'],
                    nombre=datos['nombre'],
                    email=datos['email'],
                    rol=datos['rol']
                )

                usuario.set_password(
                    datos['password']
                )

                db.session.add(usuario)

        db.session.commit()

    app.run(
        debug=True,
        use_reloader=False
    )