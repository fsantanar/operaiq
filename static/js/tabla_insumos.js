// Función para agregar una nueva fila interactiva a la tabla
function agregarFila(trabajoPorDefecto = "", insumoPorDefecto = "", cantidadPorDefecto = 1, porcentajePorDefecto = 100) {
    var tabla = document.getElementById('tabla-insumos');
    var tbody = tabla.querySelector('tbody');

    var nuevaFila = document.createElement('tr');

    var celdaTrabajo = document.createElement('td');
    var celdaInsumo = document.createElement('td');
    var celdaCantidad = document.createElement('td');
    var celdaPorcentaje = document.createElement('td');
    var celdaAccion = document.createElement('td');

    // Dropdown para trabajo
    var selectTrabajo = document.createElement('select');
    selectTrabajo.name = "trabajo[]";
    selectTrabajo.required = true;
    var optionTrabajoDefault = document.createElement('option');
    optionTrabajoDefault.value = "";
    optionTrabajoDefault.disabled = true;
    optionTrabajoDefault.selected = true;
    optionTrabajoDefault.textContent = "Seleccione un Trabajo";
    selectTrabajo.appendChild(optionTrabajoDefault);

    info_tipos_trabajos.forEach(function(trabajo) {
        var option = document.createElement('option');
        option.value = trabajo.id_tipo_trabajo;
        option.textContent = trabajo.nombre_trabajo;
        if (trabajoPorDefecto && option.value == trabajoPorDefecto) {
            option.selected = true;
        }
        selectTrabajo.appendChild(option);
    });
    celdaTrabajo.appendChild(selectTrabajo);

    // Dropdown para insumo
    var selectInsumo = document.createElement('select');
    selectInsumo.name = "nombre_insumo[]";
    selectInsumo.required = true;
    var optionDefault = document.createElement('option');
    optionDefault.value = "";
    optionDefault.disabled = true;
    optionDefault.selected = true;
    optionDefault.textContent = "Seleccione un Insumo";
    selectInsumo.appendChild(optionDefault);

    insumos.forEach(function(insumo) {
        var option = document.createElement('option');
        option.value = insumo.nombre;
        option.textContent = insumo.nombre;
        option.setAttribute('data-reutilizable', insumo.reutilizable);
        if (insumoPorDefecto && option.value == insumoPorDefecto) {
            option.selected = true;
        }
        selectInsumo.appendChild(option);
    });
    celdaInsumo.appendChild(selectInsumo);

    // Inputs para cantidad y porcentaje
    var inputCantidad = document.createElement('input');
    inputCantidad.type = 'number';
    inputCantidad.name = 'cantidad_requerida[]';
    inputCantidad.required = true;
    inputCantidad.min = 1;
    inputCantidad.value = cantidadPorDefecto;

    var inputPorcentaje = document.createElement('input');
    inputPorcentaje.type = 'number';
    inputPorcentaje.name = 'porcentaje_uso[]';
    inputPorcentaje.required = true;
    inputPorcentaje.min = 0;
    inputPorcentaje.max = 100;
    inputPorcentaje.value = porcentajePorDefecto;

    celdaCantidad.appendChild(inputCantidad);
    celdaPorcentaje.appendChild(inputPorcentaje);

    // Botón eliminar fila
    var btnEliminar = document.createElement('button');
    btnEliminar.type = 'button';
    btnEliminar.textContent = 'Eliminar';
    btnEliminar.classList.add('eliminar-fila');
    btnEliminar.addEventListener('click', function() {
        tabla.deleteRow(nuevaFila.rowIndex);
    });
    celdaAccion.appendChild(btnEliminar);

    // Agregar todas las celdas a la fila
    nuevaFila.appendChild(celdaTrabajo);
    nuevaFila.appendChild(celdaInsumo);
    nuevaFila.appendChild(celdaCantidad);
    nuevaFila.appendChild(celdaPorcentaje);
    nuevaFila.appendChild(celdaAccion);
    tbody.appendChild(nuevaFila);

    // Listener para comportamiento de reutilizable
    selectInsumo.addEventListener('change', function() {
        var reutilizable = selectInsumo.selectedOptions[0].getAttribute('data-reutilizable') === 'true';
        if (!reutilizable) {
            inputPorcentaje.value = 100;
            inputPorcentaje.setAttribute('readonly', true);
            inputCantidad.setAttribute('step', 'any');
        } else {
            inputPorcentaje.removeAttribute('readonly');
            inputPorcentaje.value = '';
            inputCantidad.setAttribute('step', '1');
        }
    });

    // Si hay valor por defecto, aplicamos inmediatamente la lógica de reutilizable
    if (insumoPorDefecto) {
        var selectedOption = selectInsumo.querySelector('option[value="' + insumoPorDefecto + '"]');
        if (selectedOption) {
            var reutilizable = selectedOption.getAttribute('data-reutilizable') === 'true';
            if (!reutilizable) {
                inputPorcentaje.value = 100;
                inputPorcentaje.setAttribute('readonly', true);
                inputCantidad.setAttribute('step', 'any');
            } else {
                inputCantidad.setAttribute('step', '1');
            }
        }
    }
}

// Al cargar la página, agregar una fila vacía
document.addEventListener('DOMContentLoaded', function() {
    agregarFila();  // Fila inicial vacía

    // Botón para agregar una fila manualmente
    document.getElementById('agregar-insumo').addEventListener('click', function() {
        agregarFila();  // Agrega una nueva fila vacía
    });

    // Botón para agregar los requerimientos de referencia
    document.getElementById('agregar_requerimientos_referencia').addEventListener('click', function() {
        if (requerimientosMaterialesReferencia && Array.isArray(requerimientosMaterialesReferencia)) {
            requerimientosMaterialesReferencia.forEach(function(material) {
                agregarFila(
                    material['id_tipo_trabajo'],
                    material['nombre_insumo'],
                    material['cantidad_requerida'],
                    material['porcentaje_de_uso']
                );
            });
        }
    });
});

console.log("Fin del archivo tabla_insumos.js");
