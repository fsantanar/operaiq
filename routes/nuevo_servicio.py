# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import (db, Servicios, Clientes, Proyectos, TiposServicio, TiposServicioATiposTrabajo,
                       RequerimientosMateriales, TiposInsumo, TiposTrabajo, RequerimientosTrabajadores,
                       Roles, Trabajadores, Trabajos, Asignaciones, Consumos)
from datetime import datetime, date
import yaml
import os
from peewee import fn
from collections import defaultdict



# Usa la variable de entorno CONFIG_FILE si existe, si no usa la ruta por defecto
config_path = os.getenv('CONFIG_FILE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')))

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

solo_trabajadores_fijos = config['frontend']['solo_trabajadores_fijos']
fecha_hoy = datetime.now().date()


def id_actual_modelo(Modelo):
    ultimo = Modelo.select(fn.MAX(Modelo.id)).scalar()
    return ultimo or 0


def actualiza_tablas_servicio_aprobado(db, session, Servicios, Trabajos, Asignaciones, Consumos,
                                       RequerimientosMateriales, RequerimientosTrabajadores,
                                       TiposTrabajo):


    id_actual_trabajos = id_actual_modelo(Trabajos)
    id_actual_asignaciones = id_actual_modelo(Asignaciones)
    id_actual_consumos = id_actual_modelo(Consumos)

    asignaciones = session['asignaciones_laborales']
    inicio_trabajos = min(a['fecha_hora_inicio'] for a in asignaciones)
    fin_trabajos = max(a['fecha_hora_fin'] for a in asignaciones)

    numero_maquinas = session['unidad_tipo_servicio']
    ids_tipo_trabajo = [el['id_tipo_trabajo'] for el in session['info_tipos_trabajos']]
    requerimientos_materiales = session['requerimientos_materiales_seleccionados']

    # Agrupar info por (id_tipo_trabajo, numero_maquina)
    info_trabajos = {}
    for a in asignaciones:
        key = (a['id_tipo_trabajo'], a['numero_maquina'])
        if key not in info_trabajos:
            info_trabajos[key] = {
                'horas': 0,
                'estacionamiento': a['estacionamiento'],
                'inicio': a['fecha_hora_inicio'],
                'fin': a['fecha_hora_fin']
            }
        info = info_trabajos[key]
        info['horas'] += a['horas_asignadas']
        info['inicio'] = min(info['inicio'], a['fecha_hora_inicio'])
        info['fin'] = max(info['fin'], a['fecha_hora_fin'])

    # Asignar IDs a trabajos
    for i, key in enumerate(info_trabajos.keys(), start=1):
        info_trabajos[key]['id_trabajo'] = id_actual_trabajos + i

    # Crear asignaciones
    datos_insertar_asignaciones = []
    for i, a in enumerate(asignaciones, start=1):
        key = (a['id_tipo_trabajo'], a['numero_maquina'])
        trabajo_info = info_trabajos[key]
        id_trabajo = trabajo_info['id_trabajo']
        horas_trabajo = trabajo_info['horas']
        porcentaje_de_trabajo = 100 * (a['horas_asignadas'] / horas_trabajo)

        datos_insertar_asignaciones.append({
            'id': id_actual_asignaciones + i,
            'id_trabajo': id_trabajo,
            'id_trabajador': a['id_trabajador'],
            'fechahora_inicio_ventana': a['fecha_hora_inicio'],
            'fechahora_fin_ventana': a['fecha_hora_fin'],
            'horas_hombre_asignadas': a['horas_asignadas'],
            'horas_trabajadas_total': 0,
            'horas_trabajadas_extra': 0.0,
            'porcentaje_de_trabajo': porcentaje_de_trabajo,
            'porcentaje_de_avance': 0.0,
            'observaciones': 'Asignacion por App',
            'anuladas': False
        })

    # Tipos de trabajo como dict
    tipos_trabajo = {
        row.id: {'nombre': row.nombre, 'descripcion': row.descripcion}
        for row in TiposTrabajo.select(TiposTrabajo.id, TiposTrabajo.nombre, TiposTrabajo.descripcion)
    }

    # Agrupar requerimientos materiales por id_tipo_trabajo
    req_materiales_por_trabajo = defaultdict(list)
    for r in requerimientos_materiales:
        req_materiales_por_trabajo[r['id_tipo_trabajo']].append(r)

    datos_insertar_trabajos = []
    datos_insertar_consumos = []
    id_consumo = id_actual_consumos

    for (id_tipo_trabajo, n_maquina), info in info_trabajos.items():
        id_trabajo = info['id_trabajo']
        nombre = tipos_trabajo[id_tipo_trabajo]['nombre']
        descripcion = tipos_trabajo[id_tipo_trabajo]['descripcion']

        datos_insertar_trabajos.append({
            'id': id_trabajo,
            'nombre': nombre,
            'id_tipo_trabajo': id_tipo_trabajo,
            'id_servicio': session['id_servicio'],
            'n_maquina': n_maquina,
            'estacionamiento': info['estacionamiento'],
            'orden_en_ot': id_trabajo - id_actual_trabajos,
            'descripcion': descripcion,
            'horas_hombre_asignadas': info['horas'],
            'fechahora_inicio': info['inicio'],
            'fechahora_fin': info['fin']
        })

        if id_tipo_trabajo not in req_materiales_por_trabajo:
            print(f'WARNING: Para el trabajo {nombre} no hay requerimientos materiales')

        for r in req_materiales_por_trabajo[id_tipo_trabajo]:
            id_consumo += 1
            uso_ponderado = (r['cantidad_requerida'] * r['porcentaje_uso']) / 100

            datos_insertar_consumos.append({
                'id': id_consumo,
                'id_tipo_insumo': r['id_tipo_insumo'],
                'item_especifico': None,
                'cantidad': r['cantidad_requerida'],
                'porcentaje_de_uso': r['porcentaje_uso'],
                'uso_ponderado': uso_ponderado,
                'fechahora_inicio_uso': info['inicio'],
                'fechahora_fin_uso': info['fin'],
                'validado': False,
                'id_trabajo_si_aplica': id_trabajo,
                'descontado_en_insumos': False,
                'id_insumo_si_aplica': None
            })

    # Insertar en base de datos
    with db.atomic():
        Servicios.create(
            id=session['id_servicio'],
            id_proyecto=session['id_proyecto'],
            ids_tipo_servicio=session['id_tipo_servicio'],
            unidad_tipo_servicio=session['unidad_tipo_servicio'],
            estado='confirmado',
            fecha_actualizacion_estado=datetime.now(),
            fecha_solicitud=session['fecha_solicitud'],
            fecha_esperada=session['fecha_esperada'],
            fecha_limite_planificacion=session['fecha_esperada'],
            fecha_inicio_trabajos=inicio_trabajos,
            fecha_fin_trabajos=fin_trabajos,
            demora_pago_dias=session['demora_pago_dias']
        )

        Trabajos.insert_many(datos_insertar_trabajos).execute()
        Asignaciones.insert_many(datos_insertar_asignaciones).execute()
        Consumos.insert_many(datos_insertar_consumos).execute()







nuevo_servicio_bp = Blueprint('nuevo_servicio', __name__)

@nuevo_servicio_bp.route('/nuevo_servicio', methods=['GET', 'POST'])
def crear_servicio():
    session.permanent = True  # Hacer que la sesión sea permanente
    session.modified = True  # Forzar la escritura de la sesión si se modifica

    if request.method == 'POST':
        # Verificar si 'paso' existe, si no, inicializarlo
        if 'paso' not in session:
            session['paso'] = 1
        if session['paso'] == 1:
            try:
                # Guardamos los datos de la sesión
                session['id_cliente'] = request.form['id_cliente']
                session['id_proyecto'] = request.form['id_proyecto']
                info_tipo_servicio = request.form['id_tipo_servicio']
                id_tipo_servicio, nombre_tipo_servicio = info_tipo_servicio.split('|')
                session['id_tipo_servicio'] = id_tipo_servicio
                session['nombre_tipo_servicio'] =nombre_tipo_servicio
                session['unidad_tipo_servicio'] = int(request.form['unidad_tipo_servicio'])
                session['fecha_solicitud'] = request.form['fecha_solicitud']
                session['fecha_esperada'] = request.form['fecha_esperada']
                session['demora_pago_dias'] = int(request.form['demora_pago_dias'])

                # Verificar la fecha en el backend (después de recibir los datos del formulario)
                fecha_solicitud = datetime.strptime(request.form['fecha_solicitud'], '%Y-%m-%d').date()
                fecha_esperada = datetime.strptime(request.form['fecha_esperada'], '%Y-%m-%d').date()

                if fecha_solicitud > fecha_esperada:
                    flash("La fecha de solicitud no puede ser mayor que la fecha esperada.", "danger")
                    return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirige si hay un error



                # Guardamos el nombre del cliente y del proyecto
                cliente = Clientes.get(Clientes.id == session['id_cliente'])
                proyecto = Proyectos.get(Proyectos.id == session['id_proyecto'])


                id_tipo_servicio = int(session['id_tipo_servicio'])
                query_tipos_servicio = (TiposServicio
                                        .select(TiposServicio.nombre.alias('nombre_servicio'),
                                                TiposServicioATiposTrabajo.id_tipo_trabajo,
                                                TiposTrabajo.nombre.alias('nombre_trabajo'))
                                        .join(TiposServicioATiposTrabajo, on=(TiposServicio.id==TiposServicioATiposTrabajo.id_tipo_servicio))
                                        .join(TiposTrabajo, on=(TiposServicioATiposTrabajo.id_tipo_trabajo==TiposTrabajo.id))
                                        .where(TiposServicio.id==id_tipo_servicio)
                                        .order_by(TiposTrabajo.nombre))
                res_tipo_servicio = list(query_tipos_servicio.dicts())
                ids_tipo_trabajo = [el['id_tipo_trabajo'] for el in res_tipo_servicio]
                # Aprovechamos de guardar las ids de los trabajos involucrados
                session['info_tipos_trabajos'] = res_tipo_servicio
                
                

                query_req_materiales = (RequerimientosMateriales
                                        .select(RequerimientosMateriales.id_tipo_trabajo,
                                                TiposInsumo.id.alias('id_tipo_insumo'),
                                                TiposInsumo.nombre.alias('nombre_insumo'),
                                                RequerimientosMateriales.cantidad_requerida,
                                                RequerimientosMateriales.porcentaje_de_uso,
                                                TiposInsumo.reutilizable,
                                                TiposTrabajo.nombre.alias('nombre_trabajo'))
                                        .where((RequerimientosMateriales.id_tipo_trabajo.in_(ids_tipo_trabajo)) &
                                               (RequerimientosMateriales.id_trabajo_si_aplica.is_null()))
                                        .join(TiposTrabajo,on=(RequerimientosMateriales.id_tipo_trabajo==TiposTrabajo.id))
                                        .join(TiposInsumo,on=(RequerimientosMateriales.id_tipo_insumo==TiposInsumo.id))
                                        .order_by(TiposTrabajo.nombre))
                req_materiales_referencia = list(query_req_materiales.dicts())


                session['nombre_cliente'] = cliente.nombre
                session['nombre_proyecto'] = proyecto.nombre

                session['requerimientos_materiales_referencia'] = req_materiales_referencia  # Guardamos en la sesión

                query_req_laborales = (RequerimientosTrabajadores
                                    .select(TiposTrabajo.id,TiposTrabajo.nombre.alias('trabajo'),
                                            Roles.nombre.alias('rol'),
                                            RequerimientosTrabajadores.horas_hombre_requeridas)
                                    .join(TiposTrabajo, on=(RequerimientosTrabajadores.id_tipo_trabajo==TiposTrabajo.id))
                                    .join(Roles, on=(RequerimientosTrabajadores.id_rol==Roles.id))
                                    .where(RequerimientosTrabajadores.id_tipo_trabajo.in_(ids_tipo_trabajo))
                                    .order_by(TiposTrabajo.nombre,Roles.nombre))
                req_laborales_referencia = list(query_req_laborales.dicts())
                session['requerimientos_laborales_referencia'] = req_laborales_referencia


                # Generamos la ID del servicio y la guardamos en la sesión
                session['id_servicio'] = (Servicios.select(Servicios.id).order_by(Servicios.id.desc()).first().id or 0) + 1

                session['paso'] = 2  # Avanzamos al siguiente paso
                session.modified = True
                return redirect(url_for('nuevo_servicio.crear_servicio'))

            except Exception as e:
                flash(f"❌ Error en el paso 1: {e}", "danger")
                return redirect(url_for('nuevo_servicio.crear_servicio'))

        if session['paso'] == 2:
            try:
                # Obtener los valores de insumos, cantidades y porcentajes
                id_tipo_trabajo = request.form.getlist('trabajo[]')
                nombre_insumo = request.form.getlist('nombre_insumo[]')
                cantidad_requerida = request.form.getlist('cantidad_requerida[]')
                porcentaje_uso = request.form.getlist('porcentaje_uso[]')

                # Crear una lista de diccionarios para guardar en la sesión
                requerimientos_materiales_seleccionados = []


                # Validación: Verificar que el porcentaje de uso sea 100 para insumos no reutilizables
                for i in range(len(nombre_insumo)):
                    
                    # Consultar si el insumo es reutilizable en la base de datos
                    insumo = TiposInsumo.get(TiposInsumo.nombre == nombre_insumo[i])
                    tipo_trabajo = TiposTrabajo.get(TiposTrabajo.id == int(id_tipo_trabajo[i]))
                    

                    # Aqui revisamos que cualquier insumo no tenga porcentaje de uso o cantidad requerida menor o igual a 0
                    # Revisar que cantidad_requerida y porcentaje_uso no sean 0 o negativos
                    if float(cantidad_requerida[i]) <= 0:
                        flash(f"El insumo '{nombre_insumo[i]}' debe tener una cantidad requerida mayor a 0", 'error')
                        return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir a la misma página con el error

                    if float(porcentaje_uso[i]) <= 0:
                        flash(f"El insumo '{nombre_insumo[i]}' debe tener un porcentaje de uso mayor a 0", 'error')
                        return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir a la misma página con el error


                    # Aqui revisamos que insumos no reutilizables (desechables) tengan porcentaje de uso igual a 100
                    if not insumo.reutilizable and float(porcentaje_uso[i]) != 100:
                        # Si el insumo no es reutilizable y el porcentaje no es 100, devolver un error
                        flash(f"El insumo '{nombre_insumo[i]}' debe tener un porcentaje de uso de 100 porque no es reutilizable.", 'error')
                        return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir a la misma página con el error

                    # Aqui revisamos que insumos reutilizables tengan cantidad requerida que sea un número entero
                    if insumo.reutilizable and not float(cantidad_requerida[i]).is_integer():
                        # Si el insumo no es reutilizable y el porcentaje no es 100, devolver un error
                        flash(f"El insumo '{nombre_insumo[i]}' debe tener una cantidad requerida que sea un número entero porque es reutilizable.", 'error')
                        return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir a la misma página con el error


                    requerimientos_materiales_seleccionados.append({
                        'nombre_trabajo': tipo_trabajo.nombre,
                        'id_tipo_trabajo': int(id_tipo_trabajo[i]),
                        'nombre_insumo': nombre_insumo[i],
                        'id_tipo_insumo': insumo.id,
                        'cantidad_requerida': float(cantidad_requerida[i]),
                        'porcentaje_uso': float(porcentaje_uso[i]),
                        'reutilizable': insumo.reutilizable
                    })

                requerimientos_materiales_seleccionados_ord = sorted(
                    requerimientos_materiales_seleccionados,
                    key=lambda x: (x['nombre_trabajo'], x['nombre_insumo']))


                # Guardar la lista de requerimientos materiales seleccionados en la sesión
                session['requerimientos_materiales_seleccionados'] = requerimientos_materiales_seleccionados_ord

                session['paso'] = 3  # Avanzamos al siguiente paso
                session.modified = True
                return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigimos al siguiente paso
            except Exception as e:
                flash(f"❌ Error en el paso 2: {e}", "danger")
                return redirect(url_for('nuevo_servicio.crear_servicio'))  # Volvemos al paso 2 si hay error

        if session['paso'] == 3:
            try:
                # Obtener los valores del formulario
                id_tipo_trabajo = request.form.getlist('trabajo[]')
                numero_maquina = request.form.getlist('numero_maquina[]')
                id_trabajador = request.form.getlist('trabajador[]')
                fecha_inicio_ventana = request.form.getlist('fecha_inicio[]')
                hora_inicio_ventana = request.form.getlist('hora_inicio[]')
                fecha_fin_ventana = request.form.getlist('fecha_fin[]')
                hora_fin_ventana = request.form.getlist('hora_fin[]')
                horas_asignadas = request.form.getlist('horas_asignadas[]')
                estacionamiento = request.form.getlist('estacionamiento[]')

                # Diccionario para validar combinaciones únicas id_trabajo|numero_maquina con estacionamientos asignados
                combinaciones_estacionamiento = {}

                # Crear una lista de diccionarios para guardar en la sesión
                asignaciones_laborales = []
                for i in range(len(id_trabajador)):
                    # Convertir las fechas y horas de string a datetime
                    inicio_str = f"{fecha_inicio_ventana[i]} {hora_inicio_ventana[i]}"
                    fin_str = f"{fecha_fin_ventana[i]} {hora_fin_ventana[i]}"

                    # Convertir los strings a objetos datetime
                    fecha_hora_inicio = datetime.strptime(inicio_str, '%Y-%m-%d %H:%M')
                    fecha_hora_fin = datetime.strptime(fin_str, '%Y-%m-%d %H:%M')


                    # Verificar si la fecha/hora final es anterior a la de inicio
                    if fecha_hora_fin < fecha_hora_inicio:

                        flash(f"La fecha y hora de fin no pueden ser anteriores a la de inicio en la asignación {i+1}.", 'error')
                        return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir al formulario con el error

                    # Crear combinación de id_trabajo|numero_maquina
                    combinacion = f"{id_tipo_trabajo[i]}|{numero_maquina[i]}"
                    tipo_trabajo = TiposTrabajo.get(TiposTrabajo.id == int(id_tipo_trabajo[i]))
                    
                    # Verificar si ya existe esa combinación en el diccionario
                    if combinacion in combinaciones_estacionamiento:
                        # Si ya existe, verificar si el estacionamiento es diferente
                        if combinaciones_estacionamiento[combinacion] != estacionamiento[i]:
                            flash(f"El trabajo '{tipo_trabajo.nombre}' para la máquina '{numero_maquina[i]}' "
                                  f"no puede tener diferentes estacionamientos asignados.", 'error')
                            return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir al formulario con el error
                    else:
                        # Si no existe, agregar la combinación con el estacionamiento asignado
                        combinaciones_estacionamiento[combinacion] = estacionamiento[i]

                    # Agregar la asignación a la lista
                    
                    query_trabajador = (Trabajadores
                                        .select(Trabajadores.nombre.alias('trabajador'),Roles.nombre.alias('rol'))
                                        .join(Roles, on=(Trabajadores.id_rol==Roles.id))
                                        .where(Trabajadores.id==int(id_trabajador[i])))
                    info_trabajador = list(query_trabajador.dicts())[0]


                    asignaciones_laborales.append({
                        'nombre_trabajo': tipo_trabajo.nombre,
                        'id_tipo_trabajo': int(id_tipo_trabajo[i]),
                        'numero_maquina': int(numero_maquina[i]),
                        'id_trabajador': int(id_trabajador[i]),
                        'nombre_trabajador': info_trabajador['trabajador'],
                        'rol': info_trabajador['rol'],
                        'fecha_hora_inicio': fecha_hora_inicio,
                        'fecha_hora_fin': fecha_hora_fin,
                        'horas_asignadas': float(horas_asignadas[i]),
                        'estacionamiento': estacionamiento[i]
                    })
                

                asignaciones_laborales_ord = sorted(
                    asignaciones_laborales,
                    key=lambda x: (x['numero_maquina'], x['nombre_trabajo'], x['fecha_hora_inicio']))

                # Guardar la lista de asignaciones laborales en la sesión
                session['asignaciones_laborales'] = asignaciones_laborales_ord


                session['paso'] = 4  # Avanzamos al siguiente paso
                session.modified = True
                return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigimos al siguiente paso

            except Exception as e:
                flash(f"❌ Error en el paso 3: {e}", "danger")
                return redirect(url_for('nuevo_servicio.crear_servicio'))  # Volvemos al paso 3 si hay error

    if 'paso' not in session:
        session['paso'] = 1
        session.modified = True


    if session.get('paso') == 1:
        # Cargar clientes, proyectos y tipos de servicio
        clientes = Clientes.select(Clientes.id,Clientes.nombre).order_by(Clientes.nombre).dicts()
        proyectos = Proyectos.select(Proyectos.id, Proyectos.nombre, Proyectos.id_cliente).order_by(Proyectos.nombre).dicts()
        tipos_servicio = TiposServicio.select(TiposServicio.id, TiposServicio.nombre).order_by(TiposServicio.nombre).dicts()
        hoy = date.today().isoformat()  # formato 'YYYY-MM-DD'
        return render_template('nuevo_servicio_paso1.html', clientes=clientes, proyectos=proyectos,
                               tipos_servicio=tipos_servicio, fecha_hoy=hoy)
    
    elif session.get('paso') == 2:
        insumos = list(TiposInsumo.select(TiposInsumo.id, TiposInsumo.nombre, TiposInsumo.reutilizable).order_by(TiposInsumo.nombre).dicts())
        info_tipos_trabajos = session['info_tipos_trabajos']
        return render_template('nuevo_servicio_paso2.html',insumos=insumos, info_tipos_trabajos=info_tipos_trabajos)

    elif session.get('paso') == 3:
        if solo_trabajadores_fijos is True:
            condicion = ((Trabajadores.modalidad_contrato == 'fijo') & (Trabajadores.iniciacion<=fecha_hoy)
                        & (Trabajadores.termino.is_null(True)))
        else:
            condicion = ( (Trabajadores.iniciacion<=fecha_hoy) & (Trabajadores.termino.is_null(True)) )

        query_trabajadores = (Trabajadores
                            .select(Trabajadores.id,Trabajadores.nombre,Roles.nombre.alias('rol'))
                            .join(Roles, on=(Trabajadores.id_rol==Roles.id))
                            .where(condicion)
                            .order_by(Trabajadores.nombre))
        trabajadores = list(query_trabajadores.dicts())

        id_tipo_servicio = int(session['id_tipo_servicio'])
        query_modo_servicio = TiposServicio.select(TiposServicio.lugar_atencion,TiposServicio.tipo_maquinaria).where(TiposServicio.id==id_tipo_servicio)
        modo_servicio = list(query_modo_servicio.dicts())
        lugar_atencion, tipo_maquinaria = modo_servicio[0]['lugar_atencion'], modo_servicio[0]['tipo_maquinaria']
        if lugar_atencion == 'terreno':
            estacionamientos_posibles = ['terreno']
        elif lugar_atencion == 'taller':
            info_estacionamientos = config['instancias']['estacionamientos']
            n_estacionamientos = info_estacionamientos[tipo_maquinaria]
            estacionamientos_posibles = [tipo_maquinaria+str(n_estacionamiento) for n_estacionamiento in range(1,n_estacionamientos+1)]

        asignaciones_existentes = list(Asignaciones
                                       .select(Asignaciones.id_trabajador,
                                       Asignaciones.fechahora_inicio_ventana,
                                       Asignaciones.fechahora_fin_ventana)
                                       .dicts())

        hoy = date.today().isoformat()  # formato 'YYYY-MM-DD'
        return render_template('nuevo_servicio_paso3.html',trabajadores=trabajadores,
                               estacionamientos_posibles=estacionamientos_posibles,
                               numero_maquinas=session['unidad_tipo_servicio'],
                               asignaciones_existentes=asignaciones_existentes, fecha_hoy=hoy)

    elif session.get('paso') == 4:
        lista_trabajos = sorted(list(set([el['nombre_trabajo'] for el in session['info_tipos_trabajos']])))
        return render_template('nuevo_servicio_confirmacion.html',lista_trabajos=lista_trabajos)

    return redirect(url_for('nuevo_servicio.crear_servicio'))  # Redirigir si algo está mal con la sesión





@nuevo_servicio_bp.route('/confirmar_servicio', methods=['GET', 'POST'])
def confirmar_servicio():

    if request.method == 'POST':

        try:
            # Imprimir los valores que estamos a punto de guardar
            print("Datos del servicio a guardar:")
            print(f"Cliente: {session['id_cliente']}")
            print(f"Proyecto: {session['id_proyecto']}")
            print(f"ID Tipo de Servicio: {session['id_tipo_servicio']}")
            print(f"Nombre Tipo de Servicio: {session['nombre_tipo_servicio']}")
            print(f"Número de máquinas: {session['unidad_tipo_servicio']}")
            print(f"Fecha solicitud: {session['fecha_solicitud']}")
            print(f"Fecha esperada: {session['fecha_esperada']}")
            print(f"Demora en el pago: {session['demora_pago_dias']}")


            actualiza_tablas_servicio_aprobado(db, session, Servicios, Trabajos, Asignaciones, Consumos,
                                                RequerimientosMateriales, RequerimientosTrabajadores,
                                                TiposTrabajo)

            print("Servicio confirmado y guardado en la base de datos.")  # Confirmamos que el servicio se guardó correctamente
            flash("✅ Servicio confirmado y registrado exitosamente", "success")
            usuario_actual = session['usuario']
            tipo_usuario_actual = session['tipo']

            session.clear()  # Limpiar la sesión después de confirmar el servicio pero mantiene la info del usuario
            session['usuario'] = usuario_actual
            session['tipo'] = tipo_usuario_actual
            return redirect(url_for('nuevo_servicio.servicio_confirmado'))


        except Exception as e:
            print(f"Error al guardar el servicio: {e}")  # Imprimimos el error si ocurre
            flash(f"❌ Error al confirmar el servicio: {e}", "danger")
            return redirect(url_for('nuevo_servicio.crear_servicio'))  # Volver a intentar

    return render_template('nuevo_servicio_confirmacion.html', session=session)


@nuevo_servicio_bp.route('/servicio_confirmado')
def servicio_confirmado():
    return render_template('nuevo_servicio_confirmado.html')
