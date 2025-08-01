document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('.formulario-servicio');  // Asegúrate de que tu formulario tiene la clase correcta
    const fechaSolicitudInput = document.querySelector('input[name="fecha_solicitud"]');
    const fechaEsperadaInput = document.querySelector('input[name="fecha_esperada"]');
    const errorMessage = document.getElementById('error-message');  // El div donde se mostrará el error

    form.addEventListener('submit', function (event) {
        // Verifica que ambos campos de fecha no estén vacíos
        if (!fechaSolicitudInput.value || !fechaEsperadaInput.value) {
            errorMessage.textContent = "Por favor, complete ambas fechas."; // Muestra el mensaje en el div
            errorMessage.style.display = 'block'; // Hace visible el mensaje de error
            event.preventDefault();  // Evita que el formulario se envíe si no están completas

            // Hacer scroll hacia el mensaje de error
            errorMessage.scrollIntoView({ behavior: 'smooth' });
            return;
        }

        const fechaSolicitud = new Date(fechaSolicitudInput.value);
        const fechaEsperada = new Date(fechaEsperadaInput.value);

        // Validar que la fecha de solicitud no sea mayor que la fecha esperada
        if (fechaSolicitud > fechaEsperada) {
            errorMessage.textContent = "Ojo: La fecha de solicitud no puede ser mayor que la esperada."; // Muestra el mensaje en el div
            errorMessage.style.display = 'block'; // Hace visible el mensaje de error
            event.preventDefault();  // Evita que el formulario se envíe si la validación falla

            // Hacer scroll hacia el mensaje de error
            errorMessage.scrollIntoView({ behavior: 'smooth' });
        }
    });
});
console.log("Fin del archivo validaciones.js");
