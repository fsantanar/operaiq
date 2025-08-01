from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import Clientes, Servicios, Cotizaciones, Proyectos, TiposServicio, TiposInsumo, Consumos, Trabajos
from peewee import JOIN, fn
import os
from datetime import date, datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import pandas as pd
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader

import os


# Ruta al directorio donde se almacenan los archivos de cotizaciones
CARPETA_COTIZACIONES = os.path.join('static', 'cotizaciones')


def formato_finanza(string_numero):
    numero = float(string_numero)
    return f"${numero:,.0f}".replace(",", ".")

def id_actual_modelo(Modelo):
    """Obtiene la mayor id registrada en el modelo"""
    df_tabla = pd.DataFrame(list(Modelo.select(Modelo.id).dicts()))
    if len(df_tabla)==0:
        id_actual = 0
    else:
        id_actual = max(df_tabla['id'])
    return int(id_actual)

cotizaciones_bp = Blueprint('cotizaciones', __name__, url_prefix='/cotizaciones')


def generar_info_cliente_y_nombre_archivo(servicio_id):
    """
    Genera un nombre único para el archivo PDF de la cotización
    basándose en el servicio_id, agregando un numeral si el archivo ya existe.
    """
    query_cliente = (Servicios
                     .select(Clientes.nombre, Clientes.rut, Clientes.correo)
                     .join(Proyectos, on=(Servicios.id_proyecto==Proyectos.id))
                     .join(Clientes, on=(Proyectos.id_cliente==Clientes.id))
                     .where(Servicios.id==servicio_id))
    info_cliente  = list(query_cliente.dicts())[0]
    nombre_cliente = info_cliente['nombre']

    base_path = CARPETA_COTIZACIONES+'/'
    base_filename = f'cotizacion_cliente_{nombre_cliente}_servicio{servicio_id}'
    ext = '.pdf'
    i = 1

    # Comprobar si el archivo ya existe
    filename = f'{base_filename}_{i}{ext}'
    while os.path.exists(os.path.join(base_path, filename)):
        i += 1
        filename = f'{base_filename}_{i}{ext}'

    return info_cliente,filename

# Página principal de cotizaciones, ahora usando 'index'
@cotizaciones_bp.route('/', methods=['GET', 'POST'])
def index():
    cotizaciones = None
    servicios = None
    cliente_id = None

    if request.method == 'POST':
        try:
            cliente_id = request.form['cliente_id']

            # Obtener los servicios del cliente
            servicios_query = (Servicios
                               .select(Servicios.id,
                                       fn.MIN(Servicios.fecha_solicitud).alias('fecha_solicitud'),
                                       fn.MIN(TiposServicio.nombre).alias('nombre_servicio'),
                                       fn.COUNT(Cotizaciones.nombre_archivo).alias('n_cotizaciones'))
                               .join(TiposServicio, on=(Servicios.ids_tipo_servicio.cast('int') == TiposServicio.id))
                               .join(Proyectos, on=(Servicios.id_proyecto==Proyectos.id))
                               .join(Cotizaciones, on=(Servicios.id == Cotizaciones.id_servicio),
                                     join_type=JOIN.LEFT_OUTER)
                               .where(Proyectos.id_cliente==cliente_id)
                               .group_by(Servicios.id))

            servicios = list(servicios_query.dicts())  # Servicios disponibles

            # Filtrar servicios para marcar cuáles realmente tienen archivos asociados
            for servicio in servicios:
                servicio_id = servicio['id']
                # Buscar archivos cuyo nombre contenga "servicio[ID]"
                archivos_existentes = [f for f in os.listdir(CARPETA_COTIZACIONES) if f"servicio{servicio_id}" in f]
                servicio['cotizaciones_con_archivo'] = len(archivos_existentes) > 0

        except Exception as e:
            flash(f"❌ Error: {e}", "danger")

    clientes = Clientes.select(Clientes.id, Clientes.nombre).order_by(Clientes.nombre).dicts()
    
    return render_template('cotizaciones.html', clientes=clientes,
                           servicios=servicios, cliente_id=cliente_id)


@cotizaciones_bp.route('/formulario_crear', methods=['GET'])
def formulario_crear():
    servicio_id = request.args.get('servicio_id')
    mensaje_estado = request.args.get('mensaje_estado')  # Obtener el mensaje de estado desde la URL

    query_consumos = (Consumos
        .select(
            TiposInsumo.nombre,
            fn.BOOL_AND(TiposInsumo.reutilizable).alias('reutilizable'),
            fn.SUM(Consumos.uso_ponderado).alias('uso_ponderado')
        )
        .join(Trabajos, on=(Consumos.id_trabajo_si_aplica == Trabajos.id))
        .join(TiposInsumo, on=(Consumos.id_tipo_insumo == TiposInsumo.id))
        .where(Trabajos.id_servicio == int(servicio_id))
        .group_by(TiposInsumo.nombre)
        .dicts()
    )

    res_consumo = [
        {
            **row,
            'reutilizable': 'Sí' if row['reutilizable'] else 'No'
        }
        for row in query_consumos
    ]
    return render_template('crear_cotizacion.html', servicio_id=servicio_id, mensaje_estado=mensaje_estado,
                           res_consumo=res_consumo)


@cotizaciones_bp.route('/crear', methods=['POST'])
def crear_cotizacion():
    try:
        servicio_id = request.form['servicio_id']
        descripcion = request.form['descripcion']

        # Generar el nombre del PDF y ruta
        info_cliente, nombre_archivo = generar_info_cliente_y_nombre_archivo(servicio_id)
        nombre_cliente, rut_cliente, correo_cliente = info_cliente['nombre'],info_cliente['rut'],info_cliente['correo']
        ruta_pdf = f'{CARPETA_COTIZACIONES}/{nombre_archivo}'

        # Extraer datos del formulario
        lista_nombre = request.form.getlist('nombre[]')
        lista_reutilizable = request.form.getlist('reutilizable[]')
        lista_uso_ponderado = request.form.getlist('uso_ponderado[]')
        lista_precios_unitarios = request.form.getlist('precios_unitarios[]')

        # Preparar items para la tabla
        items = []
        total_precio = 0
        for i in range(len(lista_nombre)):
            nombre = lista_nombre[i]
            precio_unitario = int(lista_precios_unitarios[i])
            uso_ponderado = float(lista_uso_ponderado[i])
            subtotal = uso_ponderado * precio_unitario
            total_precio += subtotal

            items.append({
                'producto': nombre,
                'cantidad': uso_ponderado,
                'precio': formato_finanza(precio_unitario),
                'total': formato_finanza(subtotal)
            })

        # Calcular IVA y Total
        iva = total_precio * 0.19
        total_final = total_precio + iva

        # Preparar datos para el HTML
        fecha = datetime.today().strftime('%d/%m/%Y')

        datos_pdf = {
            'cliente': nombre_cliente,
            'fecha': fecha,
            'rut': rut_cliente,
            'correo': correo_cliente,
            'items': items,
            'total_neto': formato_finanza(total_precio),
            'iva': formato_finanza(iva),
            'total_final': formato_finanza(total_final),
            'descripcion': descripcion
        }

        # Renderizar plantilla HTML
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('cotizaciones_pdf.html')
        html_render = template.render(datos_pdf)

        # Generar PDF con WeasyPrint
        HTML(string=html_render, base_url='.').write_pdf(ruta_pdf, stylesheets=[CSS('static/css/cotizaciones_pdf.css')])

        # Guardar en la base de datos
        Cotizaciones.create(
            id=id_actual_modelo(Cotizaciones) + 1,
            id_servicio=servicio_id,
            fecha_cotizacion=date.today(),
            descripcion=descripcion,
            total_estimado=total_precio,
            nombre_archivo=nombre_archivo,
            estado="Pendiente"
        )

        mensaje_estado = 'success'

    except Exception as e:
        print('La excepcion es la siguiente')
        print(e)
        mensaje_estado = 'danger'

    return redirect(url_for('cotizaciones.formulario_crear', servicio_id=servicio_id, mensaje_estado=mensaje_estado))



# Ruta para ver las cotizaciones de un servicio específico
@cotizaciones_bp.route('/ver_cotizaciones_servicio_<int:servicio_id>', methods=['GET'])
def ver_cotizaciones_servicio(servicio_id):
    cotizaciones_query = (Cotizaciones
                         .select(Cotizaciones.id, Cotizaciones.fecha_cotizacion,
                                 Cotizaciones.total_estimado, Cotizaciones.nombre_archivo)
                         .where(Cotizaciones.id_servicio == servicio_id))
    cotizaciones = cotizaciones_query.dicts()

        # Filtrar solo las cotizaciones que tengan archivos realmente existentes
    cotizaciones_con_archivo = []
    for cot in cotizaciones:
        nombre_archivo = cot['nombre_archivo']
        if nombre_archivo and os.path.exists(os.path.join(CARPETA_COTIZACIONES, nombre_archivo)):
            cotizaciones_con_archivo.append(cot)
    return render_template('cotizaciones_servicio.html', cotizaciones=cotizaciones_con_archivo, servicio_id=servicio_id)




