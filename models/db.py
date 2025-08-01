import psycopg2
from peewee import (
    Model, CharField, DateField, FloatField, AutoField, BooleanField, DateTimeField,
    IntegerField, TextField, PostgresqlDatabase, ForeignKeyField, Check, SQL, OperationalError
)
import yaml
import os
import time
from dotenv import load_dotenv




# Cargar variables de entorno desde .env (solo localmente)
load_dotenv()

# Cargar configuración desde config.yml (nombre de config ya fue definido antes)
ruta_config = os.getenv("CONFIG_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')))
with open(ruta_config, 'r') as file:
    config = yaml.safe_load(file)


# Obtener datos desde config.yml y variables de entorno
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')  # Se espera que esté definido en .env
db_port = int(os.getenv("DB_PORT", "5432"))


# Usar 'db_host' como variable de entorno si está disponible, si no usar 'localhost'
db_host = os.getenv('DB_HOST', 'localhost')

# Inicializar la base de datos
db = PostgresqlDatabase(db_name, user=db_user, password=db_password, host=db_host, port=db_port)


def resetear_tablas(base, modelos_a_crear, tiempo):
    print("⚠️  ADVERTENCIA: Esto eliminará TODAS las tablas y sus datos.")
    print("")
    print("Presiona Ctrl+C ahora si quieres cancelar.")
    print("")
    print(f"Esperando {tiempo} segundos antes de continuar...")

    try:
        time.sleep(tiempo)
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario.")
        return

    with base:
        base.drop_tables(modelos_a_crear)
        base.create_tables(modelos_a_crear)
        print("✅ Tablas eliminadas y recreadas con éxito.")




class BaseModel(Model):
    class Meta:
        database = db


class Roles(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=50, unique=True, null=False)
    descripcion = TextField(null=False)
    hh_en_uf_fijo = FloatField(null=False)
    hh_en_uf_honorario = FloatField(null=False)


class Trabajadores(BaseModel):
    id = IntegerField(primary_key=True)
    rut = TextField(null=False, unique=True)
    nombre = CharField(max_length=100, null=False)
    id_rol = ForeignKeyField(Roles, backref='trabajadores', on_delete='CASCADE',column_name='id_rol')
    iniciacion = DateField(null=False)
    termino = DateField(null=True)
    modalidad_contrato = TextField(null=False)


class DisponibilidadesTrabajadores(BaseModel):
    id = IntegerField(primary_key=True)
    id_trabajador = ForeignKeyField(Trabajadores, backref='disponibilidades_trabajadores', on_delete='CASCADE',column_name='id_trabajador')
    dia_semana = IntegerField(null=False)
    feriado = BooleanField(null=False)
    hora_inicio = FloatField(null=False)
    hora_fin = FloatField(null=False)
    horas_dia = FloatField(null=False)
    class Meta:
        table_name = 'disponibilidades_trabajadores'


class Clientes(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=100, null=False)
    rut = CharField(max_length=20, null=False, unique=True)
    correo = TextField(null=True)
    celular = TextField(null=True)
    es_empresa = BooleanField(null=False)
    expectativa_pago = FloatField(null=True)
    expectativa_tiempo = FloatField(null=True)


class Contactos(BaseModel):
    id = IntegerField(primary_key=True)
    id_cliente = ForeignKeyField(Clientes, backref='contactos', on_delete='CASCADE',column_name='id_cliente')
    nombre = TextField(unique=True)
    correo = TextField(null=True)
    celular = TextField(null=True)
    notas = TextField(null=True)

class TiposInsumo(BaseModel): # Los tipos de materiales que necesitamos
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=100, null=False)
    descripcion = TextField(null=True)
    unidad = CharField(max_length=20,null=True)
    categoria = CharField(max_length=50,null=True)
    reutilizable = BooleanField(null=False)
    retorno_en_n_trabajos = FloatField(null=False)
    seguimiento_automatizado = BooleanField(null=False,  constraints=[SQL('DEFAULT TRUE')])
    nivel_critico = IntegerField(null=True)
    dias_entrega_referencia = FloatField(null=False)
    entrega_dias_inhabiles = BooleanField(null=False)
    cobrable = BooleanField(null=False)
    class Meta:
        table_name = 'tipos_insumo'

class TiposTrabajo(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=100, unique=True, null=False)
    descripcion = TextField(null=True)
    horas_trabajo_estimados = FloatField(null=False)
    dias_totales_entrega_insumos = FloatField(null=True)
    dias_habiles_entrega_insumos = FloatField(null=True)
    precio_uf_estimado = FloatField(null=False)
    class Meta:
        table_name = 'tipos_trabajo'

class PreciosInsumos(BaseModel):
    id = IntegerField(primary_key=True)
    id_tipo_insumo = ForeignKeyField(TiposInsumo, backref='precios_insumos', on_delete='CASCADE',column_name='id_tipo_insumo')
    precio_por_paquete = IntegerField(null=False)
    unidades_por_paquete = IntegerField(null=False)
    minimo_paquetes_por_compra = IntegerField(null=True)
    fecha_precio = DateField(null=False)
    fecha_vigencia = DateField(null=True)
    observaciones = TextField(null=True)
    proveedor = TextField(null=True)  
    dias_entrega = FloatField(null=True)
    entrega_dias_inhabiles = BooleanField(null=True)
    class Meta:
        table_name = 'precios_insumos'

class PreciosTrabajos(BaseModel):
    id = IntegerField(primary_key=True)
    id_tipo_trabajo = ForeignKeyField(TiposTrabajo, backref='precios_trabajos', on_delete='CASCADE',column_name='id_tipo_trabajo')
    precio_por_trabajo = IntegerField(null=False)
    minimo_trabajos = IntegerField(null=False) # Minimo necesario para que aplique este precio unitario
    maximo_trabajos = IntegerField(null=True) # En caso que muchos trabajos hagan dificil nuestro servicio
    fecha_precio = DateField(null=False)
    fecha_vigencia = DateField(null=True)
    observaciones = TextField(null=True)
    class Meta:
        table_name = 'precios_trabajos'

class TiposServicio(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=100, unique=True, null=False)
    descripcion = TextField(null=True)
    horas_trabajo_estimados = FloatField(null=True)
    dias_totales_entrega_insumos = FloatField(null=True)
    dias_habiles_entrega_insumos = FloatField(null=True)
    precio_uf_estimado = FloatField(null=True)
    lugar_atencion = TextField(null=False)
    tipo_maquinaria = TextField(null=False)
    tipo_cliente = TextField(null=False)
    periodicidad_tipica_meses = FloatField(null=True)
    class Meta:
        table_name = 'tipos_servicio'

class Proyectos(BaseModel):
    id = IntegerField(primary_key=True)
    id_cliente = ForeignKeyField(Clientes, backref='proyectos', on_delete='CASCADE',column_name='id_cliente')
    nombre = TextField(null=False, unique=True)
    descripcion = TextField(null=True)
    duracion_meses_estimada = IntegerField(null=True)
    fecha_inicio = DateField(null=True)
    fecha_fin = DateField(null=True)


class MovimientosFinancieros(BaseModel):
    id = IntegerField(primary_key=True)
    fechahora_movimiento = DateTimeField(null=False)
    numero_mes_balance = IntegerField(null=True)
    numero_año_balance = IntegerField(null=True)
    categoria = CharField(constraints=[Check("categoria IN ('ingreso', 'egreso')")], null=False)
    tipo = CharField(max_length=20)
    monto = IntegerField(null=False)
    divisa = TextField(null=False)
    descripcion = TextField(null=True)
    incluye_iva = BooleanField(null=True)
    deducible = BooleanField(null=True)
    nombre_y_carpeta_archivo_boleta = TextField(null=True)
    lugar_fisico_boleta = TextField(null=True)
    id_gasto_recurrente_si_aplica = IntegerField(index=True,null=True)
    class Meta:
        table_name = 'movimientos_financieros'

class MovimientosRecurrentes(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = CharField(max_length=100, null=False)  # Ej: "Arriendo taller"
    descripcion = TextField(null=True)
    categoria = CharField(constraints=[Check("categoria IN ('ingreso', 'egreso')")], null=False)
    tipo = CharField(max_length=50, null=False)  # Ej: "arriendo", "servicios básicos", etc.
    divisa = CharField(max_length=10, null=False,  constraints=[SQL("DEFAULT 'CLP'")])  # CLP, UF, USD, etc.
    valor_periodo = IntegerField(null=False)
    unidad_periodo = CharField(constraints=[Check("unidad_periodo IN ('dias', 'semanas', 'meses', 'años')")], null=False)
    info_extra_recurrencia = TextField(null=True)
    modo_calculo_monto = TextField(null=False)
    valor_fijo = FloatField(null=True)
    valor_por_servicio = FloatField(null=True)
    fecha_inicio = DateField(null=False)
    fecha_fin = DateField(null=True)
    ultima_actualizacion = DateTimeField(null=True)  # Para saber cuándo fue modificado por última vez
    class Meta:
        table_name = 'movimientos_recurrentes'


class Insumos(BaseModel): # Lo que tenemos como materiales en stock
    id = IntegerField(primary_key=True)
    id_tipo_insumo = ForeignKeyField(TiposInsumo, backref='insumos', on_delete='CASCADE',column_name='id_tipo_insumo')
    cantidad = IntegerField(null=False)
    descripcion = TextField(null=True)
    fechahora_adquisicion_actualizacion = DateTimeField(null=False)
    fecha_caducidad = DateField(null=True)    
    id_movimiento_financiero_si_aplica = IntegerField(index=True, null=True)


class Consumos(BaseModel): # Los consumos de insumos en stock
    id = IntegerField(primary_key=True)
    id_tipo_insumo = ForeignKeyField(TiposInsumo, backref='consumos', on_delete='CASCADE',column_name='id_tipo_insumo')
    item_especifico = TextField(null=True)
    cantidad = FloatField(null=False)
    porcentaje_de_uso = FloatField(null=True,  constraints=[SQL('DEFAULT 100.0')])  # Nivel de uso
    uso_ponderado = FloatField(null=True) # igual a la cantidad por el porcentaje de uso /100
    fechahora_inicio_uso = DateTimeField(null=True)
    fechahora_fin_uso = DateTimeField(null=True)
    validado = BooleanField(null=False, constraints=[SQL('DEFAULT FALSE')])
    id_trabajo_si_aplica = IntegerField(index=True, null=True)
    descontado_en_insumos = BooleanField(null=False, constraints=[SQL('DEFAULT FALSE')])
    id_insumo_si_aplica = IntegerField(index=True, null=True)
    


class Servicios(BaseModel):
    id = IntegerField(primary_key=True)
    id_proyecto = ForeignKeyField(Proyectos, backref='servicios_proyectos', on_delete='CASCADE',column_name='id_proyecto')
    ids_tipo_servicio = TextField(index=True, null=False)
    unidad_tipo_servicio = IntegerField(null=True)
    estado = CharField(constraints=[Check("estado IN ('planificado', 'confirmado', 'en curso', 'rechazado', 'inviable', 'finalizado', 'cliente perdido')")], null=False)
    fecha_actualizacion_estado = DateTimeField(null=True)
    fecha_solicitud = DateTimeField(null=True)
    fecha_esperada = DateTimeField(null=True)
    fecha_propuesta = DateTimeField(null=True)
    fecha_limite_planificacion = DateField(null=False)
    nombre_orden_trabajo = TextField(null=True)
    fecha_inicio_trabajos = DateField(null=True)
    fecha_fin_trabajos = DateField(null=True)
    total_precio_ot = IntegerField(null=True)
    id_movimiento_financiero_si_aplica = IntegerField(index=True,null=True)
    demora_pago_dias = IntegerField(null=False)


class Cotizaciones(BaseModel):
    id = IntegerField(primary_key=True)
    id_servicio = ForeignKeyField(Servicios, backref='cotizaciones', on_delete='CASCADE',column_name='id_servicio')
    fecha_cotizacion = DateField(null=False)
    fecha_entrega = DateField(null=True)
    descripcion = TextField(null=True)
    total_estimado = IntegerField(null=False)
    nombre_archivo = TextField(null=False)
    estado = TextField(null=False)



class TiposServicioATiposTrabajo(BaseModel):
    id = IntegerField(primary_key=True)
    id_tipo_servicio = ForeignKeyField(TiposServicio, backref='tsatt_tipos_servicio', on_delete='CASCADE',column_name='id_tipo_servicio')
    id_tipo_trabajo = ForeignKeyField(TiposTrabajo, backref='tsatt_tipos_trabajo', on_delete='CASCADE',column_name='id_tipo_trabajo')
    class Meta:
        table_name = 'tipos_servicio_a_tipos_trabajo'

class Trabajos(BaseModel):
    id = IntegerField(primary_key=True)
    nombre = TextField(null=False)
    id_tipo_trabajo = ForeignKeyField(TiposTrabajo, backref='trabajos_tipos_trabajo', on_delete='CASCADE',column_name='id_tipo_trabajo')
    id_servicio = ForeignKeyField(Servicios, backref='trabajos_servicios', on_delete='CASCADE',column_name='id_servicio')
    n_maquina = IntegerField(null=False)
    estacionamiento = TextField(null=True)
    orden_en_ot = IntegerField(null=True)
    descripcion = TextField(null=True)
    horas_hombre_asignadas = FloatField(null=True) # Las asignadas inicialmente (las reales van a ser la suma de las asignaciones realizadas)
    fechahora_inicio = DateTimeField(null=True)
    fechahora_fin = DateTimeField(null=True)


class Asignaciones(BaseModel):
    id = IntegerField(primary_key=True)
    id_trabajo = ForeignKeyField(Trabajos, backref='asignaciones_trabajos', on_delete='CASCADE',column_name='id_trabajo')
    id_trabajador = ForeignKeyField(Trabajadores, backref='asignaciones_trabajadores', on_delete='CASCADE',column_name='id_trabajador')
    fechahora_inicio_ventana = DateTimeField(null=True)       # Fecha de inicio pactada que cambia a medida que se replantee
    fechahora_fin_ventana = DateTimeField(null=True)         # Fecha de fin pactada que cambia a medida que se replantee
    horas_hombre_asignadas = FloatField(null=False)     # Horas usadas para comunicar al cliente
    horas_trabajadas_total = FloatField(null=True)     # Horas usadas para registrar faltas del trabajador o cargas mayores a lo esperado
    horas_trabajadas_extra = FloatField(null=True)     # Horas usadas para registrar horas extra y calcular salarios
    porcentaje_de_trabajo = FloatField(null=True)  # Porcentaje de las HH que representa esta asignación de todo el trabajo
    porcentaje_de_avance = FloatField(null=True)   # Que tan listo está la contribución de este trabajador al trabajo (100 es listo)
    observaciones = TextField(null=True)  # Opcional: "Apoyo solo primer día", "Turno nocturno", etc.
    anuladas = BooleanField(constraints=[SQL('DEFAULT FALSE')]) # Para tener la posibilidad de registrar horas asignadas no trabajadas


class RequerimientosTrabajadores(BaseModel):
    id = IntegerField(primary_key=True)
    id_trabajo_si_aplica = IntegerField(index=True, null=True)
    id_tipo_trabajo = ForeignKeyField(TiposTrabajo, backref='requerimientos_trabajadores_tipos_trabajo', on_delete='CASCADE',column_name='id_tipo_trabajo')
    id_rol = ForeignKeyField(Roles, backref='requerimientos_trabajadores_roles', on_delete='CASCADE',column_name='id_rol')
    horas_hombre_requeridas = FloatField(null=False)
    asignar_feriados = BooleanField(null=False,  constraints=[SQL('DEFAULT FALSE')])
    class Meta:
        table_name = 'requerimientos_trabajadores'

class RequerimientosMateriales(BaseModel):
    id = IntegerField(primary_key=True)
    id_trabajo_si_aplica = IntegerField(index=True,null=True)
    id_tipo_trabajo = ForeignKeyField(TiposTrabajo, backref='requerimientos_materiales_tipos_trabajo', on_delete='CASCADE',column_name='id_tipo_trabajo')
    id_tipo_insumo = ForeignKeyField(TiposInsumo, backref='requerimientos_materiales_tipos_insumo', on_delete='CASCADE',column_name='id_tipo_insumo')
    cantidad_requerida = FloatField(null=False)
    porcentaje_de_uso = FloatField(constraints=[SQL('DEFAULT 100.0')])  # Nivel estimado de uso para planificación
    cantidad_ponderada = FloatField(null=False)
    observaciones = TextField(null=True)
    class Meta:
        table_name = 'requerimientos_materiales'




MAX_RETRIES = 10
for intento in range(MAX_RETRIES):
    try:
        db.connect()
        print("✔ Conectado a la base de datos")
        break
    except OperationalError as e:
        print(f"❌ Intento {intento + 1}/{MAX_RETRIES} - Error: {e}")
        print("⌛ Esperando que la base de datos esté lista...")
        time.sleep(2)
else:
    raise RuntimeError("🚫 No se pudo conectar a la base de datos después de varios intentos.")



modelos = [Roles, Trabajadores, DisponibilidadesTrabajadores, Clientes, Contactos, TiposInsumo, TiposTrabajo, PreciosInsumos,
           PreciosTrabajos, TiposServicio, Proyectos, MovimientosFinancieros, MovimientosRecurrentes,
           Insumos, Consumos, Servicios, Cotizaciones, TiposServicioATiposTrabajo, Trabajos,
           Asignaciones, RequerimientosTrabajadores, RequerimientosMateriales]

if __name__== '__main__':
    resetear_tablas(db, modelos, 0)

db.close()

