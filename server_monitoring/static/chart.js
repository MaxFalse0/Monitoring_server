let chart1, chart2, chart3, chart4;

function initializeCharts() {
    const ctx1 = document.getElementById("metricsChart1");
    if (ctx1) {
        chart1 = new Chart(ctx1, {
            type: "bar",
            data: {
                labels: ["CPU(%)", "RAM(%)", "Disk(%)"],
                datasets: [{
                    label: "Server Stats",
                    data: [0, 0, 0],
                    backgroundColor: ["#ff6384", "#36a2eb", "#ffce56"]
                }]
            },
            options: {
                scales: { y: { beginAtZero: true } },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "CPU / RAM / DISK" }
                }
            }
        });
    }

    const ctx2 = document.getElementById("metricsChart2");
    if (ctx2) {
        chart2 = new Chart(ctx2, {
            type: "bar",
            data: {
                labels: ["Net RX (MB)", "Net TX (MB)"],
                datasets: [{
                    label: "Network",
                    data: [0, 0],
                    backgroundColor: ["#4bc0c0", "#9966ff"]
                }]
            },
            options: {
                scales: { y: { beginAtZero: true } },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "Network Traffic" }
                }
            }
        });
    }

    const ctx3 = document.getElementById("metricsChart3");
    if (ctx3) {
        chart3 = new Chart(ctx3, {
            type: "bar",
            data: {
                labels: ["Температура °C"],
                datasets: [{
                    label: "Temperature",
                    data: [0],
                    backgroundColor: ["#e74c3c"]
                }]
            },
            options: {
                scales: { y: { beginAtZero: true } },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "Температура" }
                }
            }
        });
    }

    const ctx4 = document.getElementById("metricsChart4");
    if (ctx4) {
        chart4 = new Chart(ctx4, {
            type: "bar",
            data: {
                labels: ["Пользователи"],
                datasets: [{
                    label: "Users",
                    data: [0],
                    backgroundColor: ["#2ecc71"]
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1  // чтобы шаг был целым
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "Пользователи онлайн" }
                }
            }
        });
    }
}

function updateCharts(data) {
    if (!chart1 || !chart2 || !chart3 || !chart4) {
        initializeCharts();
    }
    if (data && data.metrics) {
        const { cpu, ram, disk, net_rx, net_tx, temp, users } = data.metrics;
        // Заполняем диаграмму 1
        chart1.data.datasets[0].data = [cpu || 0, ram || 0, disk || 0];
        chart1.update();

        // Диаграмма 2 (сетевой трафик в MB)
        chart2.data.datasets[0].data = [
          (net_rx || 0)/(1024*1024),
          (net_tx || 0)/(1024*1024)
        ];
        chart2.update();

        // Температура
        chart3.data.datasets[0].data = [temp || 0];
        chart3.update();

        // Пользователи (целое число)
        chart4.data.datasets[0].data = [users || 0];
        chart4.update();
    }
}

function populateTextFields(data) {
    if (!data || !data.metrics) return;
    const { cpu, ram, disk, net_rx, net_tx, users, temp } = data.metrics;
    document.getElementById("cpu").textContent    = cpu  !== undefined ? `${cpu}%` : "--";
    document.getElementById("ram").textContent    = ram  !== undefined ? `${ram}%` : "--";
    document.getElementById("disk").textContent   = disk !== undefined ? `${disk}%` : "--";
    document.getElementById("net-rx").textContent = net_rx !== undefined ? `${net_rx} bytes` : "--";
    document.getElementById("net-tx").textContent = net_tx !== undefined ? `${net_tx} bytes` : "--";
    document.getElementById("users").textContent  = users !== undefined ? `${users}` : "--";
    document.getElementById("temp").textContent   = temp  !== undefined ? `${temp} °C` : "--";

    const now = new Date().toLocaleTimeString();
    document.getElementById("last-update").textContent = now;
}

function fetchMetrics() {
    fetch("/data")
        .then(res => res.json())
        .then(data => {
            populateTextFields(data);
            updateCharts(data);
        })
        .catch(err => {
            console.error("Error fetching /data:", err);
        });
}

document.addEventListener("DOMContentLoaded", () => {
    initializeCharts();
    fetchMetrics();
    // Обновление каждые 3 секунды
    setInterval(fetchMetrics, 3000);

    const socket = io();
    socket.on("new_metrics", (data) => {
        populateTextFields({ metrics: data });
        updateCharts({ metrics: data });
    });
});
