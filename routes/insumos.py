# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import (db, Servicios, Clientes, Proyectos, TiposServicio, TiposServicioATiposTrabajo,
                       RequerimientosMateriales, TiposInsumo, TiposTrabajo, RequerimientosTrabajadores,
                       Roles, Trabajadores, Trabajos, Asignaciones, Consumos, Insumos)
from datetime import datetime, timedelta
import pandas as pd
import yaml
import os
from peewee import fn
import numpy as np

def calcula_maximo_consumo(df_consumos):

    eventos = []
    for _, row in df_consumos.iterrows():
        eventos.append((row['fechahora_inicio_uso'], +row['uso_ponderado']))
        eventos.append((row['fechahora_fin_uso'], -row['uso_ponderado']))
    eventos.sort()
    # Luego recorro los eventos y sus deltas de uso para calcular el momento de mayor consumo y el consumo asociado
    uso_actual = 0
    uso_max = 0
    tiempo_max_inicial = None
    tiempo_max_final = None
    for ind_evento in range(len(eventos)):
        tiempo, delta = eventos[ind_evento]
        uso_actual += delta
        if uso_actual > uso_max:
            uso_max = uso_actual
            tiempo_max_inicial = tiempo
            tiempo_max_final = eventos[ind_evento+1][0]
    if uso_max>0:
        res = f'El máximo consumo futuro es de {uso_max} entre {tiempo_max_inicial} y {tiempo_max_final}'
    else:
        res = 'No hay consumos planeados para este insumo'
    return res





insumos_bp = Blueprint('insumos', __name__, url_prefix='/insumos')

@insumos_bp.route('/')
def index():

    query_insumos = (Insumos
                     .select(TiposInsumo.id,
                             fn.MIN(TiposInsumo.nombre).alias('nombre_insumo'),
                             fn.BOOL_AND(TiposInsumo.reutilizable).alias('reutilizable'),
                             fn.SUM(Insumos.cantidad).alias('comprados'))
                     .join(TiposInsumo)
                     .group_by(TiposInsumo.id)
                     .order_by(TiposInsumo.nombre))
    df_insumos = pd.DataFrame(list(query_insumos.dicts()))

    info_consumos_desechables = dict()
    for _,row in df_insumos.iterrows():
        # Solo queremos informacion sobre los insumos desechables
        if row['reutilizable']:
            continue
        id, comprados = row['id'], row['comprados']
        if comprados==0:
            info = 'No se han realizado compras de este tipo de insumo'
        else:
            info = f'En total se han comprado {comprados} unidades de este insumo'
        info_consumos_desechables[id] = info

    query_consumos_desechables = (Consumos
                                  .select(TiposInsumo.id,
                                          fn.MIN(TiposInsumo.nombre).alias('nombre_insumo'),
                                          fn.SUM(Consumos.uso_ponderado).alias('consumo'))
                                          .join(TiposInsumo)
                                          .where(TiposInsumo.reutilizable == False)
                                          .group_by(TiposInsumo.id)
                                          .order_by(TiposInsumo.nombre))
    df_consumos_desechables = pd.DataFrame(list(query_consumos_desechables.dicts()))

    query_consumos_reutilizables = (Consumos
                                    .select(TiposInsumo.id, TiposInsumo.nombre, Consumos.cantidad,
                                            Consumos.porcentaje_de_uso, Consumos.uso_ponderado,
                                            Consumos.fechahora_inicio_uso,Consumos.fechahora_fin_uso)
                                    .join(TiposInsumo)
                                    .where((Consumos.fechahora_fin_uso > fn.NOW()) &
                                           (TiposInsumo.reutilizable == True)))
    df_consumos_reutilizables = pd.DataFrame(list(query_consumos_reutilizables.dicts()))
    if len(df_consumos_reutilizables)>0:
        ids_tipos_insumo_reutilizables = sorted(list(set(df_consumos_reutilizables['id'])))
    else:
        ids_tipos_insumo_reutilizables = []
    
    info_consumos_reutilizables = dict()
    for id_tipo_insumo in ids_tipos_insumo_reutilizables:
        df_consumos_insumo = df_consumos_reutilizables[df_consumos_reutilizables['id']==id_tipo_insumo]
        info_consumos_reutilizables[id_tipo_insumo] = calcula_maximo_consumo(df_consumos_insumo)
    
    ids_tipos_insumo = sorted(list(set(df_insumos['id'])))

    info_insumos_y_consumos = []
    for id_tipo_insumo in ids_tipos_insumo:
        row_insumo = df_insumos[df_insumos['id']==id_tipo_insumo].iloc[0]
        nombre_insumo, reutilizable, comprados = row_insumo['nombre_insumo'], row_insumo['reutilizable'], row_insumo['comprados']
        if reutilizable:
            disponibles = comprados

            info = info_consumos_reutilizables.get(id_tipo_insumo,'No hay consumos planeados para este insumo')
        # Si es desechable hay que descontar los consumos
        else:
            row_consumo = df_consumos_desechables[df_consumos_desechables['id']==id_tipo_insumo].iloc[0]
            disponibles = comprados - row_consumo['consumo']
            info = info_consumos_desechables[id_tipo_insumo]
        
        info_insumos_y_consumos.append({'id':id_tipo_insumo, 'nombre': nombre_insumo,
                                        'reutilizable':reutilizable, 'disponibles': disponibles,
                                        'info':info})


    return render_template('insumos.html',info_insumos_y_consumos=info_insumos_y_consumos)


