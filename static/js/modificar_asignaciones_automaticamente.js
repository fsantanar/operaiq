
document.addEventListener("DOMContentLoaded", function() {
    
    // Botón para establecer todas las horas trabajadas a las horas originales
    document.getElementById("set_all_horas_trabajadas").addEventListener("click", function() {
        console.log("Llamando a funcion set_all_horas_trabajadas")
        // Obtener todos los inputs de horas trabajadas
        let inputs = document.querySelectorAll("input[name^='horas_trabajadas_']");

        // Obtener todos los valores de "Horas Originales"
        // Seleccionamos las celdas con la clase hh_asignadas
        let horasOriginales = document.querySelectorAll("td.hh_asignadas");
        
        // Actualizar cada input de horas trabajadas con el valor de "Horas Originales"
        inputs.forEach(function(input, index) {
            let horasOriginal = horasOriginales[index].innerText;  // Obtener valor de la celda correspondiente
            input.value = horasOriginal;  // Asignar ese valor al campo de horas trabajadas
        });
    });

    // Función para actualizar todos los porcentajes a 100% solo en el frontend
    document.getElementById("set_all_to_100").addEventListener("click", function() {
        console.log("Llamando a funcion set_all_to_100")
        // Obtener todos los inputs de porcentaje de avance
        let inputs = document.querySelectorAll("input[name^='porcentaje_avance_']");
        
        // Actualizar cada uno a 100
        inputs.forEach(function(input) {
            input.value = 100;
        });
    });


    
});
