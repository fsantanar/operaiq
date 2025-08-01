from flask import Blueprint, render_template, request, redirect, url_for, session
from models.db import Clientes
import pandas as pd
import os
from dotenv import load_dotenv


load_dotenv()
usuarios_internos = ['sad']
clave_interna = os.getenv('CLAVE_INTERNA')
clave_externa = os.getenv('CLAVE_EXTERNA')

login_bp = Blueprint('login', __name__, url_prefix='/')


def obtener_usuarios_externos():
    return sorted(set(
        cliente['nombre']
        for cliente in Clientes.select(Clientes.nombre).dicts()
    ))


@login_bp.route('/', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        entro = False

        if usuario in usuarios_internos:
            if clave == clave_interna:
                session['usuario'] = usuario
                session['tipo'] = 'interno'
                entro = True
                return redirect(url_for('dashboard.dashboard'))

        elif usuario in obtener_usuarios_externos():
            if clave == clave_externa:
                session['usuario'] = usuario
                session['tipo'] = 'externo'
                entro = True
                return redirect(url_for('externo.historial_servicios'))

        if not entro:
            error = 'Usuario o contraseña incorrectos'

    return render_template('login.html', error=error)

@login_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login.login'))
