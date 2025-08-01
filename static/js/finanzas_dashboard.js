let chartInstance = null;
let ordenAscendente = false; // Empezamos con el orden descendente para "Fecha" al inicio

document.addEventListener('DOMContentLoaded', function () {
    const ingresosVal = document.getElementById('ingresos-val');
    const inversionesVal = document.getElementById('inversiones-val');
    const egresosVal = document.getElementById('egresos-val');
    const balanceVal = document.getElementById('balance-val');
    const btnFiltrar = document.getElementById('btn-filtrar');
    const fechaInicioInput = document.getElementById('fecha_inicio');
    const fechaFinInput = document.getElementById('fecha_fin');
    const ctx = document.getElementById('graficoFinanzas').getContext('2d');

    function obtenerTipos(clase) {
        return Array.from(document.querySelectorAll(clase + ':checked')).map(el => el.value);
    }

    function actualizarGrafico(fechaInicio = '', fechaFin = '') {
        const tiposIngreso = obtenerTipos('.tipo-ingreso');
        const tiposEgreso = obtenerTipos('.tipo-egreso');
        const tiposInversion = obtenerTipos('.tipo-inversion');

        fetch('/finanzas/datos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fecha_inicio: fechaInicio,
                fecha_fin: fechaFin,
                tipos_ingreso: tiposIngreso,
                tipos_egreso: tiposEgreso,
                tipos_inversion: tiposInversion
            })
        })
        .then(response => response.json())
        .then(data => {
            // Actualizar valores de resumen
            ingresosVal.textContent = '$' + data.total_ingresos.toLocaleString('es-CL');
            inversionesVal.textContent = '$' + data.total_inversiones.toLocaleString('es-CL');
            egresosVal.textContent = '$' + data.total_egresos.toLocaleString('es-CL');
            const signo = data.balance >= 0 ? '+' : '-';
            balanceVal.textContent = signo + '$' + Math.abs(data.balance).toLocaleString('es-CL');

            // Preparar datos para el gráfico
            const labels = data.data_grafico.map(d => {
                const fecha = new Date(d.mes);
                return `${fecha.getFullYear()}/${(fecha.getMonth() + 1).toString().padStart(2, '0')}/${fecha.getDate().toString().padStart(2, '0')}`;
            });
            const ingresos = data.data_grafico.map(d => d.ingresos);
            const egresos = data.data_grafico.map(d => d.egresos);
            const inversiones = data.data_grafico.map(d => d.inversiones);

            if (chartInstance) chartInstance.destroy();

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Ingresos', data: ingresos, borderWidth: 2, fill: false },
                        { label: 'Egresos', data: egresos, borderWidth: 2, fill: false },
                        { label: 'Inversiones', data: inversiones, borderWidth: 2, fill: false }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { labels: { font: { size: 16 } } }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                font: { size: 14 },
                                callback: value => '$' + value.toLocaleString('es-CL')
                            }
                        },
                        x: {
                            ticks: { font: { size: 14 } }
                        }
                    }
                }
            });

            // Actualizar tabla de movimientos
            const tbody = document.querySelector('#tabla-movimientos tbody');
            tbody.innerHTML = '';

            if (data.tabla_movimientos && data.tabla_movimientos.length > 0) {
                data.tabla_movimientos.forEach(mov => {
                    const fecha = new Date(mov.fechahora_movimiento);
                    const fechaFormateada = `${fecha.getFullYear()}/${(fecha.getMonth() + 1).toString().padStart(2, '0')}/${fecha.getDate().toString().padStart(2, '0')}`;

                    const fila = document.createElement('tr');
                    fila.innerHTML = `
                        <td>${fechaFormateada}</td>
                        <td>${mov.categoria_modificada}</td>
                        <td>${mov.tipo}</td>
                        <td>$${mov.monto.toLocaleString('es-CL')}</td>
                        <td>${mov.divisa || ''}</td>
                        <td>${mov.descripcion || ''}</td>
                        <td>
                            ${mov.nombre_y_carpeta_archivo_boleta ? `<a href="/static/${mov.nombre_y_carpeta_archivo_boleta}" target="_blank">Link</a>`: ''}
                        </td>
                    `;
                    tbody.appendChild(fila);
                });
            }
        });
    }

    // Función para ordenar la tabla
    function ordenarTabla(columna) {
        const tbody = document.querySelector('#tabla-movimientos tbody');
        const filas = Array.from(tbody.rows);
        
        let index;
        switch (columna) {
            case 'fecha': index = 0; break;
            case 'categoria': index = 1; break;
            case 'tipo': index = 2; break;
            case 'monto': index = 3; break;
            case 'divisa': index = 4; break;
            case 'descripcion': index = 5; break;
            default: index = 0; break;
        }

        const comparar = (filaA, filaB) => {
            const valorA = filaA.cells[index].textContent.trim();
            const valorB = filaB.cells[index].textContent.trim();

            if (columna === 'fecha') {
                const fechaA = new Date(valorA); 
                const fechaB = new Date(valorB); 
                return ordenAscendente ? fechaA - fechaB : fechaB - fechaA;
            } else if (columna === 'monto') {
                const montoA = parseFloat(valorA.replace('$', '').replace(/\./g, ''));
                const montoB = parseFloat(valorB.replace('$', '').replace(/\./g, ''));
                return ordenAscendente ? montoA - montoB : montoB - montoA;
            } else {
                return ordenAscendente ? valorA.localeCompare(valorB) : valorB.localeCompare(valorA);
            }
        };

        filas.sort(comparar);
        filas.forEach(fila => tbody.appendChild(fila));

        ordenAscendente = !ordenAscendente;

        actualizarFlechas(columna);
    }

    // Función para actualizar las flechas de ordenamiento
    function actualizarFlechas(columna) {
        const ths = document.querySelectorAll('th');
        ths.forEach((th, index) => {
            const flecha = th.querySelector('.flecha');
            
            if (flecha) {
                // Ignorar la columna "Archivo" (índice 6)
                if (index === 6) return; 

                if (th.id === `th-${columna}`) {
                    flecha.textContent = ordenAscendente ? ' ↑' : ' ↓';
                } else {
                    flecha.textContent = '';
                }
            }
        });
    }

    // Añadir manejadores de evento para los encabezados de la tabla
    const headers = document.querySelectorAll('#tabla-movimientos th');
    const columnas = ['fecha', 'categoria', 'tipo', 'monto', 'divisa', 'descripcion'];

    headers.forEach((header, index) => {
        if (index < columnas.length) {
            header.addEventListener('click', () => {
                ordenarTabla(columnas[index]);
            });
        }
    });

    // Pre-ordenar por fecha descendente al cargar la página
    actualizarGrafico(fechaInicioInput.value, fechaFinInput.value);

    // Inicializar tabla con la columna "Fecha" ordenada descendente al inicio
    ordenarTabla('fecha');

    btnFiltrar.addEventListener('click', () => {
        const fechaInicio = fechaInicioInput.value;
        const fechaFin = fechaFinInput.value;
        actualizarGrafico(fechaInicio, fechaFin);
    });
});
