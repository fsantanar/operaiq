function crearGraficoServicios(data) {
    const ctx = document.getElementById('graficoServicios').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.meses,
            datasets: [{
                label: 'Servicios mensuales',
                data: data.valores,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Servicios por mes' }
            }
        }
    });
}

