# routes/dashboard.py
from flask import Blueprint, render_template, session, redirect, url_for
from utils.consultas import obtener_resumen

dashboard_bp = Blueprint('dashboard', __name__,url_prefix='/dashboard')

@dashboard_bp.route('/')
def dashboard():
    resumen = obtener_resumen()
    return render_template('dashboard.html', resumen=resumen)

