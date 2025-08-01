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
import traceback
from werkzeug.utils import secure_filename

### IMPORTANTE
### Hay que revisar bien el calculo de los insumos a consumir y comprar. Primero esta el problema
### de que automaticamente los requisitos materiales son los mismos para todas las maquinas
### ademas *estaba* el problema que para cada maquina se usaban los requisitos de todos los servicios
### y en servicios no simulados pueden aparecer consumos de insumos que no han llegado que antes
### podia generar cantidades disponibles negativas



# Cargar la configuración desde el archivo YAML
# Usa la variable de entorno CONFIG_FILE si existe, si no usa la ruta por defecto
config_path = os.getenv('CONFIG_FILE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')))

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

str_fecha_inicio_empresa = config['csvs']['fecha_inicio_empresa']
fechahora_inicio_empresa =  datetime.strptime(str_fecha_inicio_empresa, '%Y/%m/%d')

def calcula_compras_y_consumos_servicio(df_insumos_servicio, df_consumos_servicio,asignaciones_servicio,
                                        req_materiales, id_insumo_actual, n_maquinas, fechahora_solicitud):
    df_insumos_a_usar = df_insumos_servicio.copy()
    df_consumos_a_usar = df_consumos_servicio.copy()
    df_comprar_servicio = pd.DataFrame([])
    df_consumir_servicio = pd.DataFrame([])

    for n_maquina in range(1,n_maquinas+1):
        asignaciones_atencion = asignaciones_servicio[asignaciones_servicio['n_maquina']==n_maquina]
        inicio_trabajos = min(asignaciones_atencion['fechahora_inicio_ventana']).to_pydatetime()
        fin_trabajos = max(asignaciones_atencion['fechahora_fin_ventana']).to_pydatetime()
        ids_tipo_trabajo_con_asignaciones = list(set(asignaciones_atencion['id_tipo_trabajo']))
        (df_comprar_atencion, df_consumir_atencion
         ) = calcula_compras_y_consumos_atencion(df_insumos_a_usar, df_consumos_a_usar,inicio_trabajos,
                                                 fin_trabajos, req_materiales, id_insumo_actual,
                                                 fechahora_solicitud,ids_tipo_trabajo_con_asignaciones)
        
        # Ahora apendizamos el resultado al df a usar excluyendo el numero de la maquina
        if len(df_comprar_atencion)>0:
            df_insumos_a_usar = pd.concat([df_insumos_a_usar, df_comprar_atencion.iloc[:,:-1]],ignore_index=True)
        if len(df_consumir_atencion)>0:
            df_consumos_a_usar = pd.concat([df_consumos_a_usar, df_consumir_atencion.iloc[:,:-1]],ignore_index=True)
        # Luego actualizamos la id actual de la tabla insumos
        id_insumo_actual += len(df_comprar_atencion)
        # Y finalmente anexamos los resultados incluyendo el numero de la maquina al output
        df_consumir_atencion['n_maquina']=n_maquina
        df_comprar_atencion['n_maquina']=n_maquina
        if len(df_comprar_atencion)>0:
            df_comprar_servicio = pd.concat([df_comprar_servicio,df_comprar_atencion],ignore_index=True)
        if len(df_consumir_atencion)>0:
            df_consumir_servicio = pd.concat([df_consumir_servicio,df_consumir_atencion],ignore_index=True)

    return df_comprar_servicio, df_consumir_servicio


def calcula_compras_y_consumos_atencion(df_insumos, df_consumos,inicio_trabajos,
                                        fin_trabajos, req_materiales, id_insumo_actual, fechahora_solicitud,
                                        ids_tipo_trabajo_con_asignaciones):
    """ Calcula las compras y consumos necesarios para una atención en función de los requerimientos materiales
    los insumos que existen, los consumos y el periodo de trabajo
    """

    tipos_insumo = sorted(list(set(req_materiales['id_tipo_insumo'])))
    df_insumos_filtrado, df_consumos_filtrado = filtra_dfs_insumo_consumo(tipos_insumo, df_insumos,df_consumos,
                                                                          inicio_trabajos,fin_trabajos,'atencion')
    # Para el calculo de disponibilidad solo se cuentan los insumos que ya han llegado (porque los otros no se si me sirven)
    # pero se cuentan todos los consumos porque ya estan reservados para otros servicios
    # Esto significa que no pueden existir en las tablas consumos de insumos que no han llegado
    # porque eso estropea la cuenta

    datos_comprar = []
    datos_consumir = []

    ids_tipo_trabajo_con_requerimientos = req_materiales['id_tipo_trabajo']
    ids_tipo_trabajo = sorted(list( set(ids_tipo_trabajo_con_requerimientos)
                                   & set(ids_tipo_trabajo_con_asignaciones)))
    for id_tipo_trabajo in ids_tipo_trabajo:
        req_materiales_trabajo = req_materiales[req_materiales['id_tipo_trabajo']==id_tipo_trabajo]
        for _,row_material in req_materiales_trabajo.iterrows():
            _, id_tipo_insumo, _, cantidad_requerida, porcentaje_requerido, cantidad_ponderada, reutilizable, seguimiento_automatizado = row_material
            # Primero calculo la cantidad total de insumos
            (n_disponibles, porcentaje_disponibilidad, disponibilidad_por_id
             ) = calcula_disponibilidad_insumo_y_por_id_detallado(df_insumos_filtrado, df_consumos_filtrado,
                                                                  id_tipo_insumo, reutilizable,
                                                                  seguimiento_automatizado)
            # Ahora que tengo las disponibilidades calculo cuanto tengo que comprar y cuanto tengo que consumir de lo existente
            n_a_comprar = int(max([0, np.ceil((cantidad_ponderada-n_disponibles*porcentaje_disponibilidad/100))]))


            # Por cada material a comprar agendamos la compra en datos_comprar y actualizamos df_insumos_filtrado
            # para considerarlo disponible para el proximo trabajo
            ids_insumos_nuevos = []
            # guardo las ids de los insumos nuevos para despues ponerles disponibilidad 100% en df_nuevos_disponibles
            if n_a_comprar > 0:
                fila_df_insumos = {'id': id_insumo_actual,
                                   'id_tipo_insumo': id_tipo_insumo,
                                   'cantidad': n_a_comprar,
                                   'fechahora_adquisicion_actualizacion': fechahora_inicio_empresa}
                ids_insumos_nuevos.append(id_insumo_actual)
                if len(df_insumos_filtrado)==0:
                    df_insumos_filtrado = pd.DataFrame([fila_df_insumos])
                else:
                    indice_df = df_insumos_filtrado.index.max() + 1
                    df_insumos_filtrado.loc[indice_df] = fila_df_insumos
                fecha_real_llegada_insumo = calcula_tiempo_entrega(TiposInsumo, [id_tipo_insumo], fechahora_solicitud)
                datos_comprar.append([id_insumo_actual, id_tipo_insumo,n_a_comprar, fecha_real_llegada_insumo, id_tipo_trabajo])
                # Agregamos la nueva fila correspondiente al nuevo insumo que va a estar disponible para los otros trabajos
                id_insumo_actual += 1
            #
            #  
            # Ahora que tenemos df_insumos_filtrado actualizado por las compras necesarias podemos
            # calcular los consumos correspondientes a este material para este trabajo
            #
            #Pero esto solo se hace para insumos con seguimiento automatizado porque para los otros es muy dificil
            #rastrear el consumo real entonces en ese caso simplemente vamos al siguiente insumo
            if not seguimiento_automatizado:
                continue
            #
            # Primero determinamos las filas del material actual que incluye las nuevas compras y que por construccion
            # tiene todo lo necesario para cumplir el requerimiento y le agregamos la informacion de que tan disponible esta cada insumo
            # Este df incluye las compras necesarias entonces nunca deberia estar vacio por eso puedo hacer seleccion
            df_nuevo_disponible = df_insumos_filtrado[df_insumos_filtrado['id_tipo_insumo']==id_tipo_insumo].sort_values('id',kind="mergesort")
            df_nuevo_disponible['porcentaje_de_disponibilidad'] = 0.0

            # Ahora lleno las disponibilidades de cada id de insumo
            for id_insumo in ids_insumos_nuevos:
                df_nuevo_disponible.loc[df_nuevo_disponible[df_nuevo_disponible['id']==id_insumo].index,'porcentaje_de_disponibilidad']=100.0
            ids_insumos_antiguos = sorted(list(disponibilidad_por_id.keys()))
            for id_insumo in ids_insumos_antiguos:
                disponibilidad = disponibilidad_por_id[id_insumo][1]
                df_nuevo_disponible.loc[df_nuevo_disponible[df_nuevo_disponible['id']==id_insumo].index,'porcentaje_de_disponibilidad']=disponibilidad

            # Ahora filtro el df con los insumos del tipo correspondiente para que solo tenga insumos realmente disponibles
            df_nuevo_disponible = df_nuevo_disponible[(df_nuevo_disponible['cantidad']>1e-9) &
                                                    (df_nuevo_disponible['porcentaje_de_disponibilidad']>1e-9)]
            df_nuevo_disponible = df_nuevo_disponible.reset_index(drop=True)
            # Esto es la cantidad real de uso requerido que antes del for es todo faltante por cumplir
            cantidad_ponderada_faltante = cantidad_ponderada
            iloc_df = 0
            while cantidad_ponderada_faltante>1e-9:
                fila_df = df_nuevo_disponible.iloc[iloc_df]
                id_insumo, _ , n_insumos, _, porc_disponibilidad = fila_df
                cantidad_disponible = n_insumos * porc_disponibilidad/100
                
                # Si es desechable el porcentaje de uso es 100 y la cantidad a usar
                # el minimo entre lo disponible y lo necesario
                if not reutilizable:
                    cantidad_a_usar = min([cantidad_requerida, n_insumos])
                    porcentaje_a_usar = 100
                else:
                    # Si es reutilizable uso siempre todos los que hay
                    cantidad_a_usar = n_insumos
                    # Si el insumo no alcanza para cumplir el requisito
                    # se usa el maximo porcentaje posible (lo que queda disponible)
                    if cantidad_ponderada_faltante>cantidad_disponible:
                        porcentaje_a_usar = porc_disponibilidad
                    # Si el insumo alcanza para cumplir uso lo que me falta para cumplir el requerimiento
                    else:
                        porcentaje_a_usar = 100*cantidad_ponderada_faltante/cantidad_a_usar
                # Aqui guardamos la info del consumo
                datos_consumir.append([id_tipo_insumo, cantidad_a_usar, round(porcentaje_a_usar,9),
                                       round(cantidad_a_usar*porcentaje_a_usar/100,9), inicio_trabajos,
                                       fin_trabajos, id_insumo, reutilizable, id_tipo_trabajo])
                fila_a_agregar = {'id_tipo_insumo': id_tipo_insumo,
                                 'cantidad': cantidad_a_usar,
                                 'porcentaje_uso': round(porcentaje_a_usar,9),
                                 'uso_ponderado': round(cantidad_a_usar*porcentaje_a_usar/100,9),
                                 'fechahora_inicio_uso': inicio_trabajos,
                                 'fechahora_fin_uso': fin_trabajos,
                                 'id_insumo_si_aplica': id_insumo,
                                 'insumo_reutilizable': reutilizable}
                
                if len(df_consumos_filtrado)==0:
                    df_consumos_filtrado = pd.DataFrame([fila_a_agregar])
                else:
                    indice_df = df_consumos_filtrado.index.max() + 1            
                    # Agregamos la nueva fila correspondiente al nuevo consumo para que se considere por otros trabajos de la atencion
                    df_consumos_filtrado.loc[indice_df] = fila_a_agregar
                #Aqui actualizamos la info si hay que seguir buscando insumos
                cantidad_ponderada_faltante -= cantidad_a_usar*porcentaje_a_usar/100
                # Si es reutilizable disminuimos el porcentaje requerido
                if reutilizable:
                    porcentaje_requerido = cantidad_ponderada_faltante*100/cantidad_requerida
                # Si es desechable disminuimos la cantidad requerida
                else:
                    cantidad_requerida -= cantidad_a_usar
                # Seguimos el loop si quedan insumos por completar
                iloc_df += 1

    df_comprar = pd.DataFrame(datos_comprar,
                              columns=['id','id_tipo_insumo','cantidad',
                                       'fechahora_adquisicion_actualizacion','id_tipo_trabajo'])
    df_consumir = pd.DataFrame(datos_consumir,
                               columns=['id_tipo_insumo', 'cantidad', 'porcentaje_uso',
                                         'uso_ponderado', 'fechahora_inicio_uso', 'fechahora_fin_uso',
                                         'id_insumo_si_aplica', 'insumo_reutilizable','id_tipo_trabajo'])
    return df_comprar, df_consumir



def filtra_dfs_insumo_consumo(ids_tipos_insumo, df_insumos,df_consumos,inicio_trabajos,fin_trabajos,tipo_filtro):
    """ filtra los dataframes de insumo y consumo para una atención o servicio para que solo tengan
    las ids de tipos de insumo y los periodos relevantes de insumo y consumo.
    """
    assert tipo_filtro in ('atencion', 'servicio'), f"tipo debe ser 'atencion' o 'servicio', no '{tipo_filtro}'"
    
    # Si no hay insumos tampoco hay consumos
    if len(df_insumos)==0:
        return pd.DataFrame([]),pd.DataFrame([])
    # Si es para una atencion en particular solo me sirven los insumos que ya han llegado al momento del inicio de los trabajos
    if tipo_filtro == 'atencion':
        df_insumos_filtrado_original = df_insumos[(df_insumos['fechahora_adquisicion_actualizacion']<=inicio_trabajos) &
                                                  (df_insumos['id_tipo_insumo'].isin(ids_tipos_insumo))]
    # Si es para todas las atenciones del servicio filtro los insumos que llegan en algún momento del intervalo total
    else: # o sea tipo_filtro == 'servicio'
        df_insumos_filtrado_original = df_insumos[(df_insumos['fechahora_adquisicion_actualizacion']<=fin_trabajos) &
                                                  (df_insumos['id_tipo_insumo'].isin(ids_tipos_insumo))]

    ids_insumos_filtrados = sorted(list(set(df_insumos_filtrado_original['id'])))
    df_insumos_filtrado = df_insumos_filtrado_original.copy()
    # Si no hay consumos devolvemos solo el de insumos
    if len(df_consumos)==0:
        return df_insumos_filtrado,pd.DataFrame([])
    # OJO
    # quitamos la condicion de que los consumos sean de insumos que ya llegaron porque no sabemos de que insumo es cada consumo
    # esto puede producir discrepancia en casos muy extraños, para que se de tiene que ser un insumo desechable
    # que llegue despues del inicio de los trabajos (y por tanto el insumo no se cuenta) pero que tiene un consumo
    # programado que no deberia contarse tampoco pero se va a contar. Además en varios de esos casos la cantidad de insumo
    # va a ser 0 y por tanto la cantidad disponible también va a ser 0 y por tanto no vamos a estar contando ese consumo 
    # Ademas id_insumo_si_aplica parece estar mal asignado
    #
    #cond_id_insumo = df_consumos['id_insumo_si_aplica'].isin(ids_insumos_filtrados)
    #
    cond_desechable = ~df_consumos['insumo_reutilizable']
    cond_reutilizable = ((df_consumos['insumo_reutilizable']) & ((df_consumos['fechahora_inicio_uso']<fin_trabajos) &
                                                            (df_consumos['fechahora_fin_uso']>inicio_trabajos)))
    df_consumos_filtrado_original = df_consumos[cond_desechable | cond_reutilizable]
    
    df_consumos_filtrado = df_consumos_filtrado_original.copy()
    return df_insumos_filtrado, df_consumos_filtrado


def calcula_disponibilidad_insumo_y_por_id_detallado(df_insumos_filtrado, df_consumos_filtrado,id_tipo_insumo,
                                                     es_reutilizable,seguimiento_automatizado):
    """Calcula disponibilidad global y por cada id_insumo en el instante de máximo consumo"""
    disponibilidad_por_id = {}

    # Lo primero es que si no hay insumos todo lo disponible es 0
    if len(df_insumos_filtrado)==0 or id_tipo_insumo not in set(df_insumos_filtrado['id_tipo_insumo']):
        return 0, 0.0, disponibilidad_por_id
    
    # Si hay insumos entonces calculamos la disponibilidad
    else:
        df_insumos_tipo = df_insumos_filtrado[df_insumos_filtrado['id_tipo_insumo']==id_tipo_insumo].sort_values('id',kind="mergesort")
        n_insumos = sum(df_insumos_tipo['cantidad'])

        # Si no hay consumos o no hay seguimiento automatizado asumimos que todos los insumos estan disponibles
        if not seguimiento_automatizado or len(df_consumos_filtrado)==0 or id_tipo_insumo not in set(df_consumos_filtrado['id_tipo_insumo']):
            for _, row in df_insumos_tipo.iterrows():
                disponibilidad_por_id[row['id']] = (row['cantidad'], 100.0)
            return n_insumos, 100.0, disponibilidad_por_id


        # Si hay consumos y seguimiento entonces calculamos el consumo para determinar cuanto está disponible
        else:
            rows_consumo = df_consumos_filtrado[df_consumos_filtrado['id_tipo_insumo']==id_tipo_insumo]
            
            # Si es reutilizable calculo lo disponible (global y por id_insumo) como lo libre en el momento
            # de mayor consumo
            if es_reutilizable:
                # Gardamos cada inicio o fin de un consumo como un evento aumento o disminución del uso ponderado respectivamente
                eventos = []
                for _, row in rows_consumo.iterrows():
                    eventos.append((row['fechahora_inicio_uso'], +row['uso_ponderado']))
                    eventos.append((row['fechahora_fin_uso'], -row['uso_ponderado']))
                eventos.sort()
                # Luego recorro los eventos y sus deltas de uso para calcular el momento de mayor consumo y el consumo asociado
                uso_actual = 0
                uso_max = 0
                tiempo_max = None
                for tiempo, delta in eventos:
                    uso_actual += delta
                    if uso_actual > uso_max:
                        uso_max = uso_actual
                        tiempo_max = tiempo

                # Filtrar consumos activos en el momento de uso maximo
                activos = rows_consumo[
                    (rows_consumo['fechahora_inicio_uso'] < tiempo_max) &
                    (rows_consumo['fechahora_fin_uso'] > tiempo_max)]

                # Finalmente calculamos la disponibilidad por id y la global
                for _, row in df_insumos_tipo.iterrows():
                    id_insumo = row['id']
                    cantidad_total = row['cantidad']
                    cantidad_en_uso = activos[activos['id_insumo_si_aplica'] == id_insumo]['uso_ponderado'].sum()
                    porcentaje_disponible = round(100 * (cantidad_total - cantidad_en_uso) / cantidad_total, 9)
                    disponibilidad_por_id[id_insumo] = (cantidad_total, porcentaje_disponible)
                # En insumos desechables ajustamos el porcentaje de disponibilidad segun consumo
                # asegurandonos que no sea menor que 0 (si hay consumos de insumos que no hayn llegado)
                porcentaje_global = max(0, round(100 * (n_insumos - uso_max) / n_insumos, 9))
                return n_insumos, porcentaje_global, disponibilidad_por_id

            # Si es desechable simplemente resto los consumos que son por definicion al 100%
            else:
                usados_por_id = rows_consumo.groupby('id_insumo_si_aplica')['cantidad'].sum().to_dict()
                for _, row in df_insumos_tipo.iterrows():
                    usados = usados_por_id.get(row['id'], 0)
                    disponibles = row['cantidad'] - usados
                    n_insumos -= usados
                    disponibilidad_por_id[row['id']] = (disponibles, 100)
                # En insumos reutilizables ajustamos el numero de insumos segun consumo
                # asegurandonos que no sea menor que 0 (si hay consumos de insumos que no hayn llegado)
                n_insumos = max(0,n_insumos)
                return n_insumos, 100, disponibilidad_por_id


def calcula_tiempo_entrega(TiposInsumo, tipos_insumo_a_comprar, fechahora_partida):
    """ Calcula el momento en que llegan todos los insumos requeridos"""
    
    # Si no hay insumos que comprar la fecha de llegada es igual a la de partida y terminamos
    if len(tipos_insumo_a_comprar)==0:
        return fechahora_partida
    
    query_tiempos_insumos = (TiposInsumo.select(TiposInsumo.dias_entrega_referencia,
                                                TiposInsumo.entrega_dias_inhabiles)
                            .where(TiposInsumo.id.in_(tipos_insumo_a_comprar))
                            .order_by(TiposInsumo.id))
    df_tiempos_insumos = pd.DataFrame(list(query_tiempos_insumos.dicts()))
    # Por defecto establecemos como que la demora es 0 en que lleguen los insumos
    # y aumentamos desde ahí
    fechahora_entrega = fechahora_partida
    fecha_entrega, hora_entrega = fechahora_partida.date(), fechahora_partida.time()

    tiempos_dias_habiles = df_tiempos_insumos[~df_tiempos_insumos['entrega_dias_inhabiles']]
    if len(tiempos_dias_habiles)>0:
        fecha_entrega = desplazar_dias_habiles(fecha_entrega, int(max(tiempos_dias_habiles['dias_entrega_referencia'])))
        fechahora_entrega = datetime.combine(fecha_entrega, hora_entrega)

    tiempos_dias_corridos = df_tiempos_insumos[df_tiempos_insumos['entrega_dias_inhabiles']]
    if len(tiempos_dias_corridos)>0:
        fechahora_entrega = max([fechahora_entrega, fechahora_partida
                                + timedelta(days=max(tiempos_dias_corridos['dias_entrega_referencia']))])
    return fechahora_entrega



def desplazar_dias_habiles(fecha, n_dias):
    dias_enteros = int(n_dias)
    fraccion = n_dias - dias_enteros
    fecha_actual = fecha

    # Avanzar los días hábiles enteros
    while dias_enteros > 0:
        fecha_actual += timedelta(days=1)
        if fecha_actual.weekday() < 5:
            dias_enteros -= 1

    # Sumar la fracción como días reales
    if fraccion > 0:
        fecha_actual += timedelta(days=fraccion)
        # Si cae en sábado (5) o domingo (6), ajustar al lunes siguiente
        dia_semana = fecha_actual.weekday()
        if dia_semana >= 5:  # sábado o domingo
            fecha_actual += timedelta(days=7-dia_semana)
    return fecha_actual


def id_actual_modelo(Modelo):
    """Obtiene la mayor id registrada en el modelo"""
    df_tabla = pd.DataFrame(list(Modelo.select(Modelo.id).dicts()))
    if len(df_tabla)==0:
        id_actual = 0
    else:
        id_actual = max(df_tabla['id'])
    return int(id_actual)


def crea_dataframes_variables(Insumos, Consumos, ids_trabajo_con_asignaciones):
    """Crea los dataframes que cambian de servicio a servicio"""

    # Esta vez agrego la condición de que filtre los consumos del mismo servicio analizado porque en la app
    # se agregan los consumos apenas se define el servicio
    query_consumos = (Consumos
                      .select(Consumos.id_tipo_insumo,
                              Consumos.cantidad,
                              Consumos.porcentaje_de_uso.alias('porcentaje_uso'),
                              Consumos.uso_ponderado,
                              Consumos.fechahora_inicio_uso,
                              Consumos.fechahora_fin_uso,
                              Consumos.id_insumo_si_aplica,
                              TiposInsumo.reutilizable.alias('insumo_reutilizable'))
                      .join(TiposInsumo, on=(Consumos.id_tipo_insumo == TiposInsumo.id))
                      .where(~Consumos.id_trabajo_si_aplica.in_(ids_trabajo_con_asignaciones))
                      .order_by(Consumos.id))
    df_consumos = pd.DataFrame(list(query_consumos.dicts()))

    if df_consumos.empty:
    # Si el dataframe está vacío entonces le damos el mismo formato que los de la tabla
        df_consumos = pd.DataFrame({
            'id_tipo_insumo': pd.Series(dtype='int'),
            'cantidad': pd.Series(dtype='int'),
            'porcentaje_uso': pd.Series(dtype='float'),
            'uso_ponderado': pd.Series(dtype='float'),
            'fechahora_inicio_uso': pd.Series(dtype='datetime64[ns]'),
            'fechahora_fin_uso': pd.Series(dtype='datetime64[ns]'),
            'id_insumo_si_aplica': pd.Series(dtype='int'),
            'insumo_reutilizable': pd.Series(dtype='boolean')
        })


    query_insumos = (Insumos.select(Insumos.id, Insumos.id_tipo_insumo, Insumos.cantidad,
                                   Insumos.fechahora_adquisicion_actualizacion)
                     .order_by(Insumos.id))
    df_insumos = pd.DataFrame(list(query_insumos.dicts()))

    if df_insumos.empty:
    # Si el dataframe está vacío entonces le damos el mismo formato que los de la tabla
        df_insumos = pd.DataFrame({
            'id': pd.Series(dtype='int'),
            'id_tipo_insumo': pd.Series(dtype='int'),
            'cantidad': pd.Series(dtype='int'),
            'fechahora_adquisicion_actualizacion': pd.Series(dtype='datetime64[ns]')
        })

    return df_insumos, df_consumos

def calcula_estado(avances):
    if all(x == 100 for x in avances):
        return 'finalizado'
    elif all(x == 0 for x in avances):
        return 'confirmado'
    else:
        return 'en curso'





administrar_servicio_bp = Blueprint('administrar_servicio', __name__)

@administrar_servicio_bp.route('/administrar_servicio', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            info_cliente = request.form['info_cliente']
            id_cliente, nombre_cliente = info_cliente.split('|')

            query_servicios = (Servicios
                               .select(Servicios.id,Servicios.estado,Servicios.fecha_solicitud,
                                       Servicios.unidad_tipo_servicio, Servicios.fecha_inicio_trabajos,
                                       Servicios.fecha_fin_trabajos,Servicios.total_precio_ot,
                                       TiposServicio.nombre.alias('nombre_servicio'))
                               .join(Proyectos, on=(Servicios.id_proyecto==Proyectos.id))
                               .join(TiposServicio, on=(Servicios.ids_tipo_servicio.cast('int')==TiposServicio.id))
                               .where(Proyectos.id_cliente == id_cliente)
                               .order_by(Servicios.fecha_solicitud.desc()))
            servicios = list(query_servicios.dicts())

            query_ntrabajos = (Servicios
                               .select(Servicios.id, fn.COUNT(Trabajos.id).alias('n_trabajos'))
                               .join(Trabajos, on=(Servicios.id == Trabajos.id_servicio))
                               .group_by(Servicios.id))
            n_trabajos_list = list(query_ntrabajos.dicts())
            n_trabajos_dict = {el['id']:el['n_trabajos'] for el in n_trabajos_list}

            for ind_servicio in range(len(servicios)):
                id_servicio = servicios[ind_servicio]['id']
                servicios[ind_servicio]['n_trabajos'] = n_trabajos_dict.get(id_servicio, 0)

            session['servicios'] = servicios
            session['id_cliente'] = id_cliente
            session['nombre_cliente'] = nombre_cliente
            return redirect(request.url)

        except Exception as e:
            flash(f"❌ Error: {e}", "danger")
            return redirect(url_for('administrar_servicio.index'))

    clientes = Clientes.select(Clientes.id, Clientes.nombre).order_by(Clientes.nombre).dicts()
    return render_template('administrar_servicio.html', clientes=clientes)



@administrar_servicio_bp.route('/gestion_servicio/<int:id_servicio>', methods=['GET', 'POST'])
def gestion_servicio(id_servicio):
    try:
        query_servicios = (Servicios
                           .select(Clientes.nombre.alias('nombre_cliente'),
                                   Proyectos.nombre.alias('nombre_proyecto'),
                                   Servicios.id, TiposServicio.nombre.alias('nombre_servicio'),
                                   Servicios.unidad_tipo_servicio, Servicios.estado,
                                   Servicios.fecha_actualizacion_estado, Servicios.fecha_solicitud,
                                   Servicios.fecha_inicio_trabajos, Servicios.fecha_fin_trabajos,
                                   Servicios.total_precio_ot, Servicios.demora_pago_dias)
                           .join(TiposServicio, on=(Servicios.ids_tipo_servicio.cast('int') == TiposServicio.id))
                           .join(Proyectos, on=(Servicios.id_proyecto == Proyectos.id))
                           .join(Clientes, on=(Proyectos.id_cliente == Clientes.id))
                           .where(Servicios.id == id_servicio))
        dict_servicio = list(query_servicios.dicts())[0]

        query_asignaciones = (Asignaciones
                              .select(Trabajos.n_maquina,
                                      TiposTrabajo.nombre.alias('nombre_trabajo'),
                                      Trabajadores.nombre.alias('nombre_trabajador'),
                                      Roles.nombre.alias('nombre_rol'), Asignaciones.id,
                                      Asignaciones.horas_hombre_asignadas,
                                      Asignaciones.fechahora_inicio_ventana,
                                      Asignaciones.fechahora_fin_ventana,
                                      Asignaciones.horas_trabajadas_total,
                                      Asignaciones.porcentaje_de_avance,
                                      Asignaciones.observaciones)
                              .join(Trabajos, on=(Asignaciones.id_trabajo == Trabajos.id))
                              .join(Servicios, on=(Trabajos.id_servicio == Servicios.id))
                              .join(TiposTrabajo, on=(Trabajos.id_tipo_trabajo == TiposTrabajo.id))
                              .join(Trabajadores, on=(Asignaciones.id_trabajador == Trabajadores.id))
                              .join(Roles, on=(Trabajadores.id_rol == Roles.id))
                              .where(Servicios.id == id_servicio)
                              .order_by(Asignaciones.fechahora_inicio_ventana, Asignaciones.fechahora_fin_ventana))
        dict_asignaciones = list(query_asignaciones.dicts())

        query_req_materiales = (
            Consumos
            .select(
                TiposTrabajo.id.alias('id_tipo_trabajo'),
                TiposInsumo.id.alias('id_tipo_insumo'),
                fn.MIN(TiposInsumo.nombre).alias('nombre'),
                fn.AVG(Consumos.cantidad).alias('cantidad_requerida'),
                fn.AVG(Consumos.porcentaje_de_uso).alias('porcentaje_de_uso'),
                fn.AVG(Consumos.uso_ponderado).alias('cantidad_ponderada'),
                fn.BOOL_OR(TiposInsumo.reutilizable).alias('reutilizable'),
                fn.BOOL_OR(TiposInsumo.seguimiento_automatizado).alias('seguimiento_automatizado')
            )
            .join(Trabajos, on=(Consumos.id_trabajo_si_aplica == Trabajos.id))
            .join(TiposTrabajo, on=(Trabajos.id_tipo_trabajo == TiposTrabajo.id))
            .join(TiposInsumo, on=(Consumos.id_tipo_insumo == TiposInsumo.id))
            .where(Trabajos.id_servicio == dict_servicio['id'])
            .group_by(TiposTrabajo.id, TiposInsumo.id))
        
        req_materiales = pd.DataFrame(list(query_req_materiales.dicts()))

        query_asignaciones_servicio = (Asignaciones
                                       .select(Asignaciones.id_trabajador,
                                               Asignaciones.fechahora_inicio_ventana,
                                               Asignaciones.fechahora_fin_ventana,
                                               Asignaciones.horas_hombre_asignadas,
                                               Trabajadores.id_rol, Trabajos.id_tipo_trabajo,
                                               Trabajos.estacionamiento,Trabajos.n_maquina)
                                       .join(Trabajadores, on=(Asignaciones.id_trabajador == Trabajadores.id))
                                       .join(Trabajos, on=(Asignaciones.id_trabajo == Trabajos.id))
                                       .where(Trabajos.id_servicio == dict_servicio['id']))
        asignaciones_servicio = pd.DataFrame(list(query_asignaciones_servicio.dicts()))
        
        query_trabajos_servicio = list(Trabajos.select(Trabajos.id).where(Trabajos.id_servicio==dict_servicio['id']).dicts())
        ids_trabajos_servicio = sorted(list(set([el['id'] for el in query_trabajos_servicio])))

        df_insumos, df_consumos = crea_dataframes_variables(Insumos, Consumos, ids_trabajos_servicio)
        ids_tipos_insumo = sorted(list(set(req_materiales['id_tipo_insumo'])))
        inicio_trabajos = min(asignaciones_servicio['fechahora_inicio_ventana']).to_pydatetime()
        fin_trabajos = max(asignaciones_servicio['fechahora_fin_ventana']).to_pydatetime()
    
        df_insumos_servicio, df_consumos_servicio = filtra_dfs_insumo_consumo(ids_tipos_insumo, df_insumos,df_consumos
                                                                              ,inicio_trabajos,fin_trabajos,'servicio')

        n_maquinas = dict_servicio['unidad_tipo_servicio']
        fechahora_solicitud = dict_servicio['fecha_solicitud']
        id_insumo_actual = id_actual_modelo(Insumos)
        df_comprar_servicio, df_consumir_servicio = calcula_compras_y_consumos_servicio(df_insumos_servicio, df_consumos_servicio,
                                                                                        asignaciones_servicio, req_materiales,
                                                                                        id_insumo_actual, n_maquinas, fechahora_solicitud)
        ids_tipos_insumo_a_comprar = list(set(df_comprar_servicio['id_tipo_insumo']))
        dict_comprar_servicio = []
        for id_tipo_insumo_a_comprar in ids_tipos_insumo_a_comprar:
            rows = df_comprar_servicio[df_comprar_servicio['id_tipo_insumo']==id_tipo_insumo_a_comprar]
            n_a_comprar = sum(rows['cantidad'])
            tipo_insumo = TiposInsumo.get(TiposInsumo.id == id_tipo_insumo_a_comprar)
            nombre_insumo = tipo_insumo.nombre
            dict_comprar_servicio.append({'nombre':nombre_insumo,'cantidad':n_a_comprar})

        query_consumos = (Consumos
                          .select(TiposInsumo.nombre.alias('nombre_insumo'),TiposInsumo.reutilizable,
                                  Consumos.cantidad,Consumos.porcentaje_de_uso,Consumos.uso_ponderado,
                                  Consumos.fechahora_inicio_uso,Consumos.fechahora_fin_uso,
                                  Trabajos.n_maquina,TiposTrabajo.nombre.alias('nombre_trabajo'),
                                  Trabajos.estacionamiento)
                          .join(Trabajos, on=(Consumos.id_trabajo_si_aplica == Trabajos.id))
                          .join(TiposInsumo, on=(Consumos.id_tipo_insumo == TiposInsumo.id))
                          .join(TiposTrabajo, on=(Trabajos.id_tipo_trabajo == TiposTrabajo.id))
                          .where(Trabajos.id_servicio == dict_servicio['id'])
                          .order_by(TiposInsumo.nombre, Trabajos.n_maquina, TiposTrabajo.nombre))

        df_consumir = pd.DataFrame(list(query_consumos.dicts()))
        if len(df_consumir)>0:
            insumos_desechables = sorted(list(set(df_consumir[~df_consumir['reutilizable']]['nombre_insumo'])))
        else:
            insumos_desechables = []
        info_insumos_desechables = dict()

        for nombre_insumo in insumos_desechables:
            rows_insumo = df_consumir[df_consumir['nombre_insumo']==nombre_insumo]
            uso_insumo = sum(rows_insumo['cantidad'])
            info_insumos_desechables[nombre_insumo]=uso_insumo        
        df_insumos_reutilizables = df_consumir[df_consumir['reutilizable']]
        info_insumos_reutilizables = df_insumos_reutilizables.to_dict(orient='records')



        if request.method == 'POST':
            # Actualizar porcentaje de avance
            for asignacion in dict_asignaciones:
                id_asignacion = asignacion['id']
                nuevo_porcentaje = request.form.get(f'porcentaje_avance_{id_asignacion}')
                nuevas_horas_trabajadas = request.form.get(f'horas_trabajadas_{id_asignacion}')
                nuevo_inicio = request.form.get(f'inicio_asignacion_{id_asignacion}')
                nuevo_fin = request.form.get(f'fin_asignacion_{id_asignacion}')
                nueva_observacion = request.form.get(f'observaciones_{id_asignacion}')
                if nuevo_porcentaje and nuevas_horas_trabajadas:
                    # Actualizar en la base de datos el porcentaje de avance y las horas_trabajadas_totales
                    (Asignaciones.update(porcentaje_de_avance=nuevo_porcentaje,
                                         horas_trabajadas_total=nuevas_horas_trabajadas)
                                 .where(Asignaciones.id == id_asignacion)
                                 .execute())
                if nuevo_inicio and nuevo_fin:
                    nuevo_inicio_dt = datetime.strptime(nuevo_inicio, '%Y-%m-%dT%H:%M')
                    nuevo_fin_dt = datetime.strptime(nuevo_fin, '%Y-%m-%dT%H:%M')
                    # Actualizar en la base de datos el porcentaje de avance
                    (Asignaciones.update(fechahora_inicio_ventana=nuevo_inicio_dt,
                                         fechahora_fin_ventana=nuevo_fin_dt,)
                                 .where(Asignaciones.id == id_asignacion)
                                 .execute())

                # Actualizar las observaciones para entregar mensaje al cliente
                (Asignaciones.update(observaciones=nueva_observacion)
                                .where(Asignaciones.id == id_asignacion)
                                .execute())


            # Una vez que se cambiaron todos los porcentajes de avance reviso si hay que
            # actualizar el estado del servicio
            query_avances_nuevos = (Asignaciones
                                    .select(Asignaciones.porcentaje_de_avance)
                                    .join(Trabajos, on=(Asignaciones.id_trabajo==Trabajos.id))
                                    .where(Trabajos.id_servicio==dict_servicio['id']))
            lista_avances_nuevos = list(query_avances_nuevos.dicts())
            avances_nuevos = [el['porcentaje_de_avance'] for el in lista_avances_nuevos]
            estado_actual = dict_servicio['estado']
            estado_segun_avances = calcula_estado(avances_nuevos)
            # Si el estado actual es uno que depende de los avances de los trabajos
            # y ademas el estado no correpsonde con los nuevos avances entonces actualizamos el estado del servicio
            if estado_actual in ['confirmado','en curso','finalizado'] and estado_actual!=estado_segun_avances:
                (Servicios
                 .update(estado=estado_segun_avances)
                 .where(Servicios.id == dict_servicio['id'])
                 .execute())


            flash("✅ Cambios en Progresos Actualizadas Correctamente", "success")
            return redirect(url_for('administrar_servicio.gestion_servicio', id_servicio=id_servicio))

        return render_template('gestion_servicio.html', servicio=dict_servicio,
                               asignaciones=dict_asignaciones,
                               dict_comprar_servicio=dict_comprar_servicio,
                               info_insumos_desechables=info_insumos_desechables,
                               info_insumos_reutilizables=info_insumos_reutilizables)

    except Exception as e:
        error_trace = traceback.format_exc()
        flash(f"❌ Error: {e}\nTraceback: {error_trace}", "danger")
        return redirect(url_for('administrar_servicio.index'))


