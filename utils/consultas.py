from models.db import Servicios, Trabajadores, Asignaciones, DisponibilidadesTrabajadores, MovimientosFinancieros
import pandas as pd
import os
import yaml
import datetime
from peewee import fn

# Ruta absoluta o relativa a config.yml
ruta_config = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')

# Cargar configuración desde config.yml
with open(ruta_config, 'r') as file:
    config = yaml.safe_load(file)

solo_trabajadores_fijos = config['instancias']['solo_trabajadores_fijos']
str_fecha_inicio_empresa = config['csvs']['fecha_inicio_empresa']
fecha_inicio = datetime.datetime.strptime(str_fecha_inicio_empresa, '%Y/%m/%d').date()
str_fecha_cierre = config['csvs']['fecha_cierre']
fecha_cierre = datetime.datetime.strptime(str_fecha_cierre, '%Y/%m/%d').date()
fecha_hoy = datetime.datetime.now().date()
roles_para_disponibilidad = config['frontend']['roles_para_disponibilidad']
lista_tipos_inversion = config['frontend'].get('tipos_inversion', ['inyección de capital'])

def calcula_horas_totales(df_disponibilidades_por_dia,fecha_in,fecha_final):
    horas_totales = 0
    for dia_semana in range(1,5+1):
        disponibilidades_dia = df_disponibilidades_por_dia[df_disponibilidades_por_dia['dia_semana']==dia_semana]
        if len(disponibilidades_dia)>0:
            horas_por_dia = disponibilidades_dia['hora_fin'].values[0] - disponibilidades_dia['hora_inicio'].values[0]
        else:
            horas_por_dia=0
        horas_totales += horas_por_dia * contar_dias_semana(fecha_in, fecha_final, dia_semana)
    return horas_totales


def contar_dias_semana(fecha_inicio, fecha_fin, dia_semana) -> int:
    """
    Cuenta cuántas veces aparece un día de la semana entre dos fechas (inclusive).

    Parámetros:
    - fecha_inicio, fecha_fin: objetos datetime.date
    - dia_semana: int de 1 (lunes) a 7 (domingo)

    Retorna:
    - número de ocurrencias del día indicado
    """
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    # Día de la semana de la fecha de inicio
    dia_inicio = fecha_inicio.weekday()

    # Días hasta el primer día deseado (puede ser 0 si ya cae en ese día)
    dias_hasta_deseado = (dia_semana - 1 - dia_inicio) % 7
    primera_ocurrencia = fecha_inicio + datetime.timedelta(days=dias_hasta_deseado)

    if primera_ocurrencia > fecha_fin:
        return 0

    total_dias = (fecha_fin - primera_ocurrencia).days
    return 1 + total_dias // 7



def calcula_resumen_finanzas(MovimientosFinancieros):
    """Escribe el resumen del balance financiero en el log"""

    query_movimientos = (MovimientosFinancieros
                         .select(MovimientosFinancieros.tipo, MovimientosFinancieros.categoria,
                                 MovimientosFinancieros.monto ))
    df_movimientos = pd.DataFrame(list(query_movimientos.dicts()))
    df_inversion = df_movimientos[df_movimientos['tipo'].isin(lista_tipos_inversion)]
    df_ingresos = df_movimientos[(df_movimientos['categoria'] == 'ingreso') &
                                 (~df_movimientos['tipo'].isin(lista_tipos_inversion))]
    df_egresos = df_movimientos[df_movimientos['categoria']=='egreso']

    total_inversion = sum(df_inversion['monto'])
    total_ingresos = sum(df_ingresos['monto'])
    total_egresos = sum(df_egresos['monto'])
    total_ganancia = total_ingresos - total_egresos

    info_inversion = f'${total_inversion:,.0f}'
    info_ingresos = f'${total_ingresos:,.0f}'
    info_egresos = f'${total_egresos:,.0f}'
    info_ganancia = f'${total_ganancia:,.0f}'

    return {'inversion': info_inversion, 'ingresos': info_ingresos, 'egresos': info_egresos, 'ganancia': info_ganancia}



def obtener_resumen():
    n_servicios = Servicios.select(Servicios.id).count()

    n_servicios_finalizados = (Servicios
                               .select(Servicios.id)
                               .where(Servicios.estado == 'finalizado')
                               .count())
    porcentaje_servicios_finalizados = 100 * n_servicios_finalizados / n_servicios
    info_servicios_finalizados = f'{n_servicios_finalizados} de {n_servicios} totales ({porcentaje_servicios_finalizados:.1f}%)'

    resultado = (Asignaciones
        .select(
            fn.MAX(Asignaciones.fechahora_fin_ventana).alias('ultima'),
            fn.SUM(Asignaciones.horas_trabajadas_total).alias('suma')
        )
        .dicts()
        .get())

    ultima_asignacion = resultado['ultima'].date()
    horas_trabajadas_totales = resultado['suma'] or 0
    fecha_fin = max([fecha_cierre, ultima_asignacion, fecha_hoy])


    if solo_trabajadores_fijos is True:
        condicion_fijos = (Trabajadores.modalidad_contrato == 'fijo')
    else:
        condicion_fijos = True

    condicion_roles = Trabajadores.id_rol.in_(roles_para_disponibilidad)

    query_disponibilidades = (
        DisponibilidadesTrabajadores
        .select(
            Trabajadores.id.alias('id_trabajador'),
            Trabajadores.id_rol,
            Trabajadores.iniciacion,
            Trabajadores.termino,

            DisponibilidadesTrabajadores.dia_semana,
            DisponibilidadesTrabajadores.hora_inicio,
            DisponibilidadesTrabajadores.hora_fin
        )
        .join(Trabajadores, on=(DisponibilidadesTrabajadores.id_trabajador == Trabajadores.id))
        .where( (DisponibilidadesTrabajadores.feriado == False) & condicion_fijos & condicion_roles))

    df_disponibilidades = pd.DataFrame(list(query_disponibilidades.dicts()))
    ids_trabajadores = sorted(list(set(df_disponibilidades['id_trabajador'])))
    horas_disponibles_totales = 0
    for id_trabajador in ids_trabajadores:
        df_disponibilidades_trabajador = df_disponibilidades[df_disponibilidades['id_trabajador']==id_trabajador]
        inicio = df_disponibilidades_trabajador['iniciacion'].values[0]
        fin = df_disponibilidades_trabajador['termino'].values[0] if df_disponibilidades_trabajador['termino'].values[0] is not None else fecha_fin
        inicio_disponibilidad = max(fecha_inicio, inicio)
        fin_disponibilidad = min(fecha_fin, fin)


        horas_disponibles_trabajador = calcula_horas_totales(df_disponibilidades_trabajador,inicio_disponibilidad,fin_disponibilidad)
        horas_disponibles_totales += horas_disponibles_trabajador


    
    porcentaje_horas_trabajadas_totales = 100*horas_trabajadas_totales/horas_disponibles_totales
    info_horas_trabajadas = f'{horas_trabajadas_totales:.1f} de {horas_disponibles_totales:.1f} disponibles ({porcentaje_horas_trabajadas_totales:.1f}%)'
    info_periodo_actividad = f'Del {fecha_inicio.strftime("%d/%m/%Y")} al {fecha_fin.strftime("%d/%m/%Y")}'
    info_finanzas = calcula_resumen_finanzas(MovimientosFinancieros)
    return {'info_servicios_finalizados': info_servicios_finalizados,
            'info_horas_trabajadas': info_horas_trabajadas,
            'info_periodo_actividad': info_periodo_actividad,
            'info_finanzas': info_finanzas}


