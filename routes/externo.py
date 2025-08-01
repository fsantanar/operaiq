from flask import Blueprint, render_template, session, redirect, url_for, request
from models.db import Clientes, Servicios, TiposServicio, Proyectos, Trabajos, Asignaciones, Trabajadores, Roles
from peewee import fn

externo_bp = Blueprint('externo', __name__, url_prefix='/externo')

@externo_bp.route('/', methods=['GET'])
def historial_servicios():
    if 'usuario' not in session or session.get('tipo') != 'externo':
        return redirect(url_for('login.login'))

    try:
        nombre_cliente = session.get('usuario')
        cliente = Clientes.get(Clientes.nombre == nombre_cliente)
        id_cliente, es_empresa = cliente.id, cliente.es_empresa

        # ⚡️ Solo calcular historial si no está en sesión
        if 'servicios_cliente' not in session:
            query_servicios = (
                Servicios
                .select(
                    Servicios.id, Servicios.estado, Servicios.fecha_solicitud,
                    Servicios.unidad_tipo_servicio, Servicios.fecha_inicio_trabajos,
                    Servicios.fecha_fin_trabajos, Servicios.total_precio_ot,
                    TiposServicio.nombre.alias('nombre_servicio')
                )
                .join(Proyectos, on=(Servicios.id_proyecto == Proyectos.id))
                .join(TiposServicio, on=(Servicios.ids_tipo_servicio.cast('int') == TiposServicio.id))
                .where(Proyectos.id_cliente == id_cliente)
                .order_by(Servicios.fecha_solicitud.desc())
            )
            servicios = list(query_servicios.dicts())

            query_ntrabajos = (
                Servicios
                .select(Servicios.id, fn.COUNT(Trabajos.id).alias('n_trabajos'))
                .join(Trabajos, on=(Servicios.id == Trabajos.id_servicio))
                .group_by(Servicios.id)
            )
            n_trabajos_dict = {el['id']: el['n_trabajos'] for el in query_ntrabajos.dicts()}
            for servicio in servicios:
                servicio['n_trabajos'] = n_trabajos_dict.get(servicio['id'], 0)

            # Guardar en sesión
            session['servicios_cliente'] = servicios
            session['es_empresa'] = es_empresa

        # ⚡️ Recuperar desde sesión
        servicios = session.get('servicios_cliente')
        es_empresa = session.get('es_empresa')

        # Si se seleccionó un servicio específico
        id_servicio = request.args.get('id_servicio')
        servicio_detalle = None
        if id_servicio:
            query_asignaciones = (Asignaciones
                                  .select(Trabajos.n_maquina, Trabajos.nombre.alias('nombre_trabajo'),
                                          Trabajadores.nombre.alias('nombre_trabajador'),
                                          Roles.nombre.alias('nombre_rol'),
                                          Asignaciones.fechahora_inicio_ventana,
                                          Asignaciones.fechahora_fin_ventana,
                                          Asignaciones.horas_hombre_asignadas,
                                          Asignaciones.horas_trabajadas_total,
                                          Asignaciones.porcentaje_de_avance,
                                          Asignaciones.observaciones)
                                  .join(Trabajos, on=(Asignaciones.id_trabajo==Trabajos.id))
                                  .join(Trabajadores, on=(Asignaciones.id_trabajador==Trabajadores.id))
                                  .join(Roles, on=(Trabajadores.id_rol==Roles.id))
                                  .where(Trabajos.id_servicio==int(id_servicio)))
            

            servicio_detalle = query_asignaciones.dicts()
        return render_template('externo.html',
                               servicios=servicios,
                               servicio_detalle=servicio_detalle,
                               es_empresa=es_empresa)

    except Exception as e:
        print(f"Error en historial_servicios: {e}")
        return redirect(url_for('login.login'))
