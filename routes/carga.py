from flask import Blueprint, render_template, request, flash
from models.db import Trabajadores, Asignaciones
from datetime import datetime, timedelta
from peewee import fn


carga_bp = Blueprint('carga', __name__, url_prefix='/carga')


def contar_horas(Asignaciones, id_trabajador, periodo_meses, ahora):
    desde = ahora - timedelta(days=30 * periodo_meses)

    query = (Asignaciones
             .select(
                 fn.SUM(Asignaciones.horas_hombre_asignadas).alias('hh_asignadas'),
                 fn.SUM(fn.COALESCE(Asignaciones.horas_trabajadas_total, 0)).alias('hh_trabajadas')
             )
             .where(
                 (Asignaciones.id_trabajador == id_trabajador) &
                 (Asignaciones.fechahora_inicio_ventana >= desde) &
                 (Asignaciones.fechahora_inicio_ventana < ahora)
             )
             .dicts()
             .get())

    return query['hh_asignadas'] or 0, query['hh_trabajadas'] or 0


@carga_bp.route('/', methods=['GET', 'POST'])
def index():
    trabajadores = Trabajadores.select(Trabajadores.id, Trabajadores.nombre).order_by(Trabajadores.nombre).dicts()
    nombre_trabajador=None
    datos_horas = None
    asignaciones_pendientes = []

    if request.method == 'POST':
        try:
            id_trabajador = int(request.form['id_trabajador'])
            nombre_trabajador = Trabajadores.get(Trabajadores.id == int(id_trabajador)).nombre
            ahora = datetime.now()

            datos_horas = {
                '3m': contar_horas(Asignaciones, id_trabajador, 3, ahora),
                '6m': contar_horas(Asignaciones, id_trabajador, 6, ahora),
                '12m': contar_horas(Asignaciones, id_trabajador, 12, ahora),
            }

            asignaciones_pendientes = (Asignaciones
                                       .select(Asignaciones.fechahora_inicio_ventana,
                                               Asignaciones.fechahora_fin_ventana,
                                               Asignaciones.horas_hombre_asignadas)
                                       .where((Asignaciones.id_trabajador == id_trabajador) &
                                              (Asignaciones.porcentaje_de_avance < 100))
                                       .order_by(Asignaciones.fechahora_inicio_ventana)
                                       .dicts())
        except Exception as e:
            print("Error al procesar carga laboral:", e)
            flash("❌ Error al procesar la carga laboral. Intente nuevamente.")

    return render_template('carga.html',
                           trabajadores=trabajadores,
                           nombre_trabajador=nombre_trabajador,
                           datos_horas=datos_horas,
                           asignaciones_pendientes=asignaciones_pendientes)
