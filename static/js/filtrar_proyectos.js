document.addEventListener('DOMContentLoaded', function () {
    const clienteSelect = document.getElementById('id_cliente');
    const proyectoSelect = document.getElementById('id_proyecto');
    const todasLasOpciones = Array.from(proyectoSelect.options);

    function filtrarProyectos() {
        const clienteSeleccionado = clienteSelect.value;
        proyectoSelect.innerHTML = '';
        const opcionesFiltradas = todasLasOpciones.filter(opt => opt.getAttribute('data-cliente') === clienteSeleccionado);
        opcionesFiltradas.forEach(opt => proyectoSelect.appendChild(opt));
    }

    clienteSelect.addEventListener('change', filtrarProyectos);
    filtrarProyectos(); // aplicar filtro al cargar
});

console.log("Fin del archivo filtrar_proyectos.js");