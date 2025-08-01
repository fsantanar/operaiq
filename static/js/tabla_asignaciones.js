document.addEventListener('DOMContentLoaded', function() {
    const formulario = document.querySelector('form'); // Obtener el formulario
    const agregarAsignacionBtn = document.getElementById('agregar-asignacion');
    const tablaAsignaciones = document.getElementById('tabla-asignaciones').getElementsByTagName('tbody')[0];
    const errorMessage = document.getElementById('error-message');  // Elemento donde se mostrará el mensaje de error

    // Agregar una nueva fila a la tabla
    agregarAsignacionBtn.addEventListener('click', function() {
        const nuevaFila = tablaAsignaciones.insertRow();  // Insertar una nueva fila
        console.log("Índice de nueva fila en tabla_asignaciones:", nuevaFila.rowIndex);  // Ver el índice al agregar una fila

        // Crear celdas para la fila
        for (let i = 0; i < 9; i++) {  // Ahora tenemos 9 celdas
            const celda = nuevaFila.insertCell(i);

            if (i === 0) {  // Trabajo: Dropdown de trabajos
                const select = document.createElement('select');
                select.name = 'trabajo[]';
                select.required = true;
                const optionDefault = document.createElement('option');
                optionDefault.value = '';
                optionDefault.disabled = true;
                optionDefault.selected = true;
                optionDefault.textContent = 'Seleccione un Trabajo';
                select.appendChild(optionDefault);

                // Llenar con trabajos desde sessionData['requerimientos_laborales_referencia']
                sessionData['requerimientos_laborales_referencia'].forEach(function(req_laboral) {
                    const option = document.createElement('option');
                    option.value = req_laboral['id'];  // Llenar con la id del trabajo
                    option.textContent = req_laboral['trabajo'];
                    select.appendChild(option);
                });
                celda.appendChild(select);

            } else if (i === 1) {  // Máquina a Atender: Dropdown de máquinas
                const select = document.createElement('select');
                select.name = 'numero_maquina[]';
                select.required = true;
                const optionDefault = document.createElement('option');
                optionDefault.value = '';
                optionDefault.disabled = true;
                optionDefault.selected = true;
                optionDefault.textContent = 'Seleccione una Máquina';
                select.appendChild(optionDefault);

                // Crear las opciones del dropdown de máquinas
                for (let j = 1; j <= numero_maquinas; j++) {
                    const option = document.createElement('option');
                    option.value = j;  // Número de la máquina
                    option.textContent = `${j}`;  // Texto visible
                    select.appendChild(option);
                }
                celda.appendChild(select);

            } else if (i === 2) {  // Trabajador: Dropdown de trabajadores
                const select = document.createElement('select');
                select.name = 'trabajador[]';
                select.required = true;
                const optionDefault = document.createElement('option');
                optionDefault.value = '';
                optionDefault.disabled = true;
                optionDefault.selected = true;
                optionDefault.textContent = 'Seleccione un Trabajador';
                select.appendChild(optionDefault);

                // Llenar con trabajadores desde la variable trabajadores
                trabajadores.forEach(function(trabajador) {
                    const option = document.createElement('option');
                    option.value = trabajador.id;  // Usar id en lugar de nombre
                    option.textContent = `${trabajador.nombre} (${trabajador.rol})`;  // Nombre y rol
                    select.appendChild(option);
                });
                celda.appendChild(select);

            } else if (i === 3 || i === 5) {  // Fecha: Inputs de fecha
                const input = document.createElement('input');
                input.type = 'date';
                input.name = i === 3 ? 'fecha_inicio[]' : 'fecha_fin[]';
                input.required = true;
                // Asignar fecha actual por defecto
                const hoy = new Date().toISOString().split('T')[0];
                input.value = hoy;
                celda.appendChild(input);

            } else if (i === 4 || i === 6) {  // Hora: Inputs de hora
                const input = document.createElement('input');
                input.type = 'time';
                input.name = i === 4 ? 'hora_inicio[]' : 'hora_fin[]';
                input.required = true;
                // Asignar hora por defecto
                input.value = i === 4 ? '09:00' : '17:00';
                celda.appendChild(input);

            } else if (i === 7) {  // Horas Asignadas: Input numérico
                const input = document.createElement('input');
                input.type = 'number';
                input.name = 'horas_asignadas[]';
                input.required = true;
                input.min = 0;
                celda.appendChild(input);

            } else if (i === 8) {  // Estacionamiento: Dropdown de estacionamientos
                const select = document.createElement('select');
                select.name = 'estacionamiento[]';
                select.required = true;
                const optionDefault = document.createElement('option');
                optionDefault.value = '';
                optionDefault.disabled = true;
                optionDefault.selected = true;
                optionDefault.textContent = 'Seleccione un Estacionamiento';
                select.appendChild(optionDefault);

                // Llenar con estacionamientos posibles desde la variable estacionamientosPosibles
                estacionamientos_posibles.forEach(function(estacionamiento) {
                    const option = document.createElement('option');
                    option.value = estacionamiento;
                    option.textContent = estacionamiento;
                    select.appendChild(option);
                });
                celda.appendChild(select);
            }
        }

        // Crear el botón de eliminar fila
        const eliminarBtn = document.createElement('button');
        eliminarBtn.type = 'button';
        eliminarBtn.textContent = 'Eliminar';
        eliminarBtn.classList.add('eliminar-fila');
        eliminarBtn.addEventListener('click', function() {
            console.log("Eliminando fila directamente con remove()");
            const numeroMaquina = nuevaFila.querySelector('select[name="numero_maquina[]"]').value;
            nuevaFila.remove();  // Elimina la fila sin usar índices

            // Si se eliminó una fila, debemos actualizar la cantidad de asignaciones para la máquina
            if (numeroMaquina) {
                maquinasAsignadas[numeroMaquina]--;  // Decrementar el contador de asignaciones para esa máquina
            }
        });

        // Añadir el botón de eliminar en la última celda
        nuevaFila.insertCell(9).appendChild(eliminarBtn);
    });

    // Validación del formulario antes de enviarlo
    formulario.addEventListener('submit', function(event) {
        let validacionExitosa = true; // Bandera para verificar si todas las asignaciones son válidas
        const maquinasAsignadas = {}; // Objeto para registrar las asignaciones

        // Iteramos sobre las filas de la tabla y registramos las asignaciones
        const filas = tablaAsignaciones.getElementsByTagName('tr');
        for (let fila of filas) {
            const trabajadorId = fila.querySelector('select[name="trabajador[]"]').value;
            const fechaInicio = fila.querySelector('input[name="fecha_inicio[]"]').value;
            const horaInicio = fila.querySelector('input[name="hora_inicio[]"]').value;
            const fechaFin = fila.querySelector('input[name="fecha_fin[]"]').value;
            const horaFin = fila.querySelector('input[name="hora_fin[]"]').value;
            const numeroMaquina = fila.querySelector('select[name="numero_maquina[]"]').value;


            // 👷‍♂️ Vamos llenando el conteo de asignaciones por máquina
            if (numeroMaquina) {
                maquinasAsignadas[numeroMaquina] = (maquinasAsignadas[numeroMaquina] || 0) + 1;
            }

            if (trabajadorId && fechaInicio && horaInicio && fechaFin && horaFin) {
                const inicioNueva = new Date(`${fechaInicio}T${horaInicio}`);
                const finNueva = new Date(`${fechaFin}T${horaFin}`);

                // Revisar si traslapa con alguna asignación existente
                for (let asignacion of asignaciones_existentes) {
                    if (parseInt(asignacion.id_trabajador) === parseInt(trabajadorId)) {
                        const inicioExistente = new Date(asignacion.fechahora_inicio_ventana);
                        const finExistente = new Date(asignacion.fechahora_fin_ventana);

                        const traslapan = inicioNueva < finExistente && finNueva > inicioExistente;
                        if (traslapan) {
                            errorMessage.textContent = `El trabajador ya tiene una asignación que traslapa con el rango ingresado.`;
                            errorMessage.style.display = 'block';
                            event.preventDefault();
                            errorMessage.scrollIntoView({ behavior: 'smooth' });
                            return;
                        }
                    }
                }
            }
        }
        
        // 🧪 Validación de cobertura de máquinas
        console.log('maquinasAsignadas:', maquinasAsignadas);
        // Verificar que todas las máquinas tengan al menos una asignación
        for (let i = 1; i <= numero_maquinas; i++) {
            if (!maquinasAsignadas[i] || maquinasAsignadas[i] === 0) {
                errorMessage.textContent = 'Cada máquina debe tener al menos una asignación ';
                errorMessage.textContent += 'y no se ha asignado ningún trabajo para la máquina ' + i;
                errorMessage.style.display = 'block';  // Muestra el mensaje de error
                validacionExitosa = false;
                break;
            }
        }

        // Si alguna validación falló, evitamos el envío del formulario
        if (!validacionExitosa) {
            event.preventDefault();  // Evitar que el formulario se envíe
            errorMessage.scrollIntoView({ behavior: 'smooth' });
        }
    });
});
