# -*- coding: utf-8 -*-
from flask import Blueprint, render_template
from models.db import Servicios, TiposServicio, Trabajos, TiposTrabajo
import pandas as pd
import plotly.graph_objs as go
import plotly.offline as pyo
from peewee import fn

resultados_bp = Blueprint('resultados', __name__, url_prefix='/resultados')

@resultados_bp.route('/')
def index():
    # Diccionario de meses en español
    meses_es = {
        '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr',
        '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Ago',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'
    }

    # Obtener y preparar los datos mínimos necesarios
    query_servicios = Servicios.select(
        Servicios.fecha_solicitud,
        Servicios.estado,
        Servicios.unidad_tipo_servicio
    )
    df = pd.DataFrame(query_servicios.dicts())
    if df.empty:
        return render_template(
            'resultados.html',
            grafico_servicios_html='',
            grafico_maquinas_html='',
            resumen_servicios=[],
            resumen_trabajos=[]
        )

    df['mes'] = df['fecha_solicitud'].dt.to_period('M').astype(str)

    etiquetas = ['Realizados', 'Pendientes', 'Rechazados', 'Inviables']
    estados = {
        'Realizados': ['finalizado'],
        'Rechazados': ['rechazado'],
        'Inviables': ['inviable', 'cliente perdido'],
        'Pendientes': ['en curso', 'planificado', 'confirmado']
    }
    colores = {
        'Realizados': '#1976d2',
        'Rechazados': '#90caf9',
        'Inviables': '#d3d3d3',
        'Pendientes': '#4db6ac'
    }

    # Crear base temporal uniforme
    meses_raw = sorted(df['mes'].unique())
    meses_mapeados = [f"{meses_es[m[-2:]]} {m[:4]}" for m in meses_raw]

    # ------------------ Gráfico 1: Servicios por mes ------------------
    conteos = {
        etiqueta: df[df['estado'].isin(estados[etiqueta])]
        .groupby('mes')
        .size()
        .reindex(meses_raw, fill_value=0)
        for etiqueta in etiquetas
    }

    barras_servicios = [
        go.Bar(
            x=meses_mapeados,
            y=conteos[etiqueta].values,
            name=etiqueta,
            marker_color=colores[etiqueta],
            hovertemplate='%{x}<br>' + etiqueta + ': %{y}<extra></extra>'
        )
        for etiqueta in etiquetas
    ]

    layout_servicios = go.Layout(
        barmode='stack',
        title=dict(text='Servicios por Mes', x=0.5),
        xaxis=dict(title='Fecha Solicitud', tickangle=-45, tickmode='array', tickvals=meses_mapeados[::4]),
        yaxis=dict(title='Cantidad de Servicios'),
        hovermode='x unified',
        height=450,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    fig_servicios = go.Figure(data=barras_servicios, layout=layout_servicios)
    grafico_servicios_html = pyo.plot(fig_servicios, output_type='div', include_plotlyjs='cdn')

    # ------------------ Gráfico 2: Máquinas por mes ------------------
    conteos_maquinas = {
        etiqueta: df[df['estado'].isin(estados[etiqueta])]
        .groupby('mes')['unidad_tipo_servicio']
        .sum()
        .reindex(meses_raw, fill_value=0)
        for etiqueta in etiquetas
    }

    barras_maquinas = [
        go.Bar(
            x=meses_mapeados,
            y=conteos_maquinas[etiqueta].values,
            name=etiqueta,
            marker_color=colores[etiqueta],
            hovertemplate='%{x}<br>' + etiqueta + ': %{y}<extra></extra>'
        )
        for etiqueta in etiquetas
    ]

    layout_maquinas = go.Layout(
        barmode='stack',
        title=dict(text='Máquinas por Mes', x=0.5),
        xaxis=dict(title='Fecha Solicitud', tickangle=-45, tickmode='array', tickvals=meses_mapeados[::4]),
        yaxis=dict(title='Cantidad de Máquinas'),
        hovermode='x unified',
        height=450,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    fig_maquinas = go.Figure(data=barras_maquinas, layout=layout_maquinas)
    grafico_maquinas_html = pyo.plot(fig_maquinas, output_type='div', include_plotlyjs=False)

    # ---- Tabla Tipos Servicio ----
    query_tipos_servicio = (
        Servicios
        .select(
            Servicios.ids_tipo_servicio,
            fn.MIN(TiposServicio.nombre).alias('nombre'),
            fn.COUNT(Servicios.id).alias('servicios_realizados'),
            fn.SUM(Servicios.unidad_tipo_servicio).alias('maquinas_atendidas'),
            (fn.SUM(Servicios.fecha_fin_trabajos - Servicios.fecha_inicio_trabajos).cast('float') / fn.COUNT(Servicios.id)).alias('dias_trabajo_por_servicio'),
            (fn.SUM(Servicios.fecha_fin_trabajos - Servicios.fecha_inicio_trabajos).cast('float') / fn.SUM(Servicios.unidad_tipo_servicio)).alias('dias_trabajo_por_maquina'),
            (fn.SUM(Servicios.total_precio_ot) / fn.COUNT(Servicios.id)).alias('precio_por_servicio'),
            (fn.SUM(Servicios.total_precio_ot) / fn.SUM(Servicios.unidad_tipo_servicio)).alias('precio_por_maquina'),
            fn.SUM(Servicios.total_precio_ot).alias('ingresos_totales')
        )
        .join(TiposServicio, on=(Servicios.ids_tipo_servicio.cast('int') == TiposServicio.id))
        .where(Servicios.estado == 'finalizado')
        .group_by(Servicios.ids_tipo_servicio)
        .order_by(Servicios.ids_tipo_servicio.cast('int'))
    )
    df_tipos_servicio = pd.DataFrame(query_tipos_servicio.dicts()).round(2)

    # ---- Tabla Tipos Trabajo ----
    query_tipos_trabajo = (
        Trabajos
        .select(
            Trabajos.id_tipo_trabajo,
            fn.MIN(TiposTrabajo.nombre).alias('nombre_trabajo'),
            fn.COUNT(Trabajos.id).alias('trabajos_realizados'),
            fn.SUM(Trabajos.horas_hombre_asignadas).alias('horas_trabajadas_totales'),
            (fn.SUM(Trabajos.horas_hombre_asignadas) / fn.COUNT(Trabajos.id)).alias('horas_trabajadas_promedio')
        )
        .join(TiposTrabajo, on=(Trabajos.id_tipo_trabajo == TiposTrabajo.id))
        .group_by(Trabajos.id_tipo_trabajo)
        .order_by(Trabajos.id_tipo_trabajo)
    )
    df_tipos_trabajo = pd.DataFrame(query_tipos_trabajo.dicts()).round(2)

    return render_template(
        'resultados.html',
        grafico_servicios_html=grafico_servicios_html,
        grafico_maquinas_html=grafico_maquinas_html,
        resumen_servicios=df_tipos_servicio.to_dict(orient='records'),
        resumen_trabajos = df_tipos_trabajo.to_dict(orient='records'))


