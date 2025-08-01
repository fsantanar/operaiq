from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from models.db import MovimientosFinancieros
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import os
import yaml
from werkzeug.utils import secure_filename
from peewee import fn

# Usa la variable de entorno CONFIG_FILE si existe, si no usa la ruta por defecto
config_path = os.getenv('CONFIG_FILE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')))

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

lista_tipos_inversion = config['frontend'].get('tipos_inversion', ['inyección de capital'])

finanzas_bp = Blueprint('finanzas', __name__, url_prefix='/finanzas')


def id_actual_modelo(Modelo):
    """Obtiene la mayor id registrada en el modelo"""
    df_tabla = pd.DataFrame(list(Modelo.select(Modelo.id).dicts()))
    if len(df_tabla)==0:
        id_actual = 0
    else:
        id_actual = max(df_tabla['id'])
    return int(id_actual)



@finanzas_bp.route('/')
def finanzas_dashboard():
    # Obtener tipos de ingreso (excluyendo tipos de inversión)
    tipos_ingreso_query = (MovimientosFinancieros
        .select(MovimientosFinancieros.tipo)
        .where(
            (MovimientosFinancieros.categoria == 'ingreso') &
            (~MovimientosFinancieros.tipo.in_(lista_tipos_inversion))
        )
        .distinct())

    tipos_ingreso = sorted({row.tipo for row in tipos_ingreso_query})

    # Obtener tipos de egreso
    tipos_egreso_query = (MovimientosFinancieros
        .select(MovimientosFinancieros.tipo)
        .where(MovimientosFinancieros.categoria == 'egreso')
        .distinct())

    tipos_egreso = sorted({row.tipo for row in tipos_egreso_query})

    # Obtener fechas mínima y máxima
    fechas_query = (MovimientosFinancieros
        .select(
            fn.MIN(MovimientosFinancieros.fechahora_movimiento).alias('min_fecha'),
            fn.MAX(MovimientosFinancieros.fechahora_movimiento).alias('max_fecha')
        )
        .dicts()
        .get())

    min_fecha = fechas_query['min_fecha'].date().isoformat() if fechas_query['min_fecha'] else ''
    max_fecha = fechas_query['max_fecha'].date().isoformat() if fechas_query['max_fecha'] else ''

    # Tipos de inversión vienen desde la config
    tipos_inversion = lista_tipos_inversion



    return render_template('finanzas_dashboard.html',
                           tipos_ingreso=tipos_ingreso,
                           tipos_egreso=tipos_egreso,
                           tipos_inversion=tipos_inversion,
                           min_fecha=min_fecha,
                           max_fecha=max_fecha)


@finanzas_bp.route('/datos', methods=['POST'])
def obtener_datos_financieros():
    data = request.get_json()
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipos_ingreso = data.get('tipos_ingreso', [])
    tipos_egreso = data.get('tipos_egreso', [])
    tipos_inversion = data.get('tipos_inversion', lista_tipos_inversion)

    # Parsear fechas
    fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d') if fecha_inicio else None
    fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1) if fecha_fin else None

    # Construir filtros
    filtros = []
    if fecha_inicio:
        filtros.append(MovimientosFinancieros.fechahora_movimiento >= fecha_inicio)
    if fecha_fin:
        filtros.append(MovimientosFinancieros.fechahora_movimiento <= fecha_fin)
    tipos_totales = tipos_ingreso + tipos_egreso + tipos_inversion
    if tipos_totales:
        filtros.append(MovimientosFinancieros.tipo.in_(tipos_totales))

    # Ejecutar consulta filtrada
    query_filtrada = (MovimientosFinancieros
        .select(
            MovimientosFinancieros.fechahora_movimiento,
            MovimientosFinancieros.tipo,
            MovimientosFinancieros.categoria,
            MovimientosFinancieros.monto,
            MovimientosFinancieros.divisa,
            MovimientosFinancieros.descripcion,
            MovimientosFinancieros.nombre_y_carpeta_archivo_boleta
        )
        .where(*filtros)
        .order_by(MovimientosFinancieros.fechahora_movimiento.desc())
        .dicts())

    # Inicializar acumuladores
    total_ingresos = total_egresos = total_inversiones = 0.0
    ingresos_mensuales = defaultdict(float)
    egresos_mensuales = defaultdict(float)
    inversiones_mensuales = defaultdict(float)
    tabla_movimientos = []

    # Procesar resultados
    for row in query_filtrada:
        tipo = row['tipo']
        monto = float(row['monto'])
        categoria = row['categoria']
        mes = row['fechahora_movimiento'].strftime('%Y-%m')

        # Clasificación para totales y gráfico
        if tipo in tipos_ingreso:
            total_ingresos += monto
            ingresos_mensuales[mes] += monto
            categoria_modificada = 'ingreso'
        elif tipo in tipos_egreso:
            total_egresos += monto
            egresos_mensuales[mes] += monto
            categoria_modificada = 'egreso'
        elif tipo in tipos_inversion:
            total_inversiones += monto
            inversiones_mensuales[mes] += monto
            categoria_modificada = 'inversion'
        else:
            categoria_modificada = categoria or 'desconocido'

        # Construir fila para la tabla
        fila = {
            'fechahora_movimiento': row['fechahora_movimiento'].isoformat(),
            'categoria_modificada': categoria_modificada,
            'tipo': tipo,
            'monto': monto,
            'divisa': row['divisa'],
            'descripcion': row['descripcion'],
            'nombre_y_carpeta_archivo_boleta': row['nombre_y_carpeta_archivo_boleta']
        }
        tabla_movimientos.append(fila)

    # Calcular balance
    balance = total_ingresos - total_egresos

    # Generar datos para gráfico mensual
    meses = sorted(set(ingresos_mensuales.keys()) |
                   set(egresos_mensuales.keys()) |
                   set(inversiones_mensuales.keys()))
    
    data_grafico_serializable = [
        {
            'mes': mes,
            'ingresos': ingresos_mensuales.get(mes, 0),
            'inversiones': inversiones_mensuales.get(mes, 0),
            'egresos': egresos_mensuales.get(mes, 0)
        }
        for mes in meses
    ]

    # Devolver JSON
    return jsonify({
        'total_ingresos': total_ingresos,
        'total_inversiones': total_inversiones,
        'total_egresos': total_egresos,
        'balance': balance,
        'data_grafico': data_grafico_serializable,
        'tabla_movimientos': tabla_movimientos})



@finanzas_bp.route('/registrar', methods=['POST'])
def registrar_movimiento():
    try:
        categoria = request.form['categoria']
        tipo = request.form['tipo']
        monto = float(request.form['monto'])
        divisa = request.form.get('divisa', '')
        descripcion = request.form.get('descripcion', '')
        fechahora = request.form.get('fechahora_movimiento')

        archivo_boleta = request.files.get('archivo_boleta')
        nombre_archivo = None

        # Calcular el próximo ID de forma segura
        id_movimiento = id_actual_modelo(MovimientosFinancieros) + 1

        if archivo_boleta and archivo_boleta.filename != '':
            filename_original = secure_filename(archivo_boleta.filename)
            carpeta_destino = os.path.join(current_app.root_path, 'static', 'movimientos_financieros')
            os.makedirs(carpeta_destino, exist_ok=True)

            # Separar nombre base y extensión
            nombre_base, extension = os.path.splitext(filename_original)
            filename = filename_original
            contador = 1

            # Buscar un nombre que no exista
            while os.path.exists(os.path.join(carpeta_destino, filename)):
                filename = f"{nombre_base}_{contador}{extension}"
                contador += 1

            ruta_completa = os.path.join(carpeta_destino, filename)
            archivo_boleta.save(ruta_completa)
            nombre_archivo = f'movimientos_financieros/{filename}'

        MovimientosFinancieros.create(
            id=id_movimiento,
            categoria=categoria,
            tipo=tipo,
            monto=monto,
            divisa=divisa,
            descripcion=descripcion,
            fechahora_movimiento=datetime.strptime(fechahora, '%Y-%m-%dT%H:%M'),
            nombre_y_carpeta_archivo_boleta=nombre_archivo
        )

        flash('✅ Movimiento registrado correctamente.', 'success')
    except Exception as e:
        flash(f'❌ Error al registrar movimiento: {str(e)}', 'danger')

    return redirect(url_for('finanzas.finanzas_dashboard'))
