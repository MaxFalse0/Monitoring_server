let chart1, chart2;

function initializeCharts() {
    // Первый график: CPU, RAM, DISK
    const ctx1 = document.getElementById("metricsChart1");
    if (ctx1) {
        chart1 = new Chart(ctx1, {
            type: "bar",
            data: {
                labels: ["CPU(%)", "RAM(%)", "Disk(%)"],
                datasets: [{
                    label: "Server Stats",
                    data: [0, 0, 0],
                    backgroundColor: ["#ff6384", "#36a2eb", "#ffce56"],
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "CPU / RAM / DISK" }
                }
            }
        });
    }

    // Второй график: Net RX / TX (в MB)
    const ctx2 = document.getElementById("metricsChart2");
    if (ctx2) {
        chart2 = new Chart(ctx2, {
            type: "bar",
            data: {
                labels: ["Net RX (MB)", "Net TX (MB)"],
                datasets: [{
                    label: "Network",
                    data: [0, 0],
                    backgroundColor: ["#4bc0c0", "#9966ff"],
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "Network Traffic" }
                }
            }
        });
    }
}

function updateCharts(data) {
    if (!chart1 || !chart2) {
        initializeCharts();
    }
    if (data && data.metrics) {
        const { cpu, ram, disk, net_rx, net_tx } = data.metrics;
        // CPU, RAM, DISK => chart1
        chart1.data.datasets[0].data = [
            cpu || 0,
            ram || 0,
            disk || 0
        ];
        chart1.update();

        // NET => делим на MB
        const rxMB = (net_rx || 0)/(1024*1024);
        const txMB = (net_tx || 0)/(1024*1024);
        chart2.data.datasets[0].data = [
            rxMB,
            txMB
        ];
        chart2.update();
    }
}

function populateTextFields(data) {
    if (!data || !data.metrics) return;
    const { cpu, ram, disk, net_rx, net_tx } = data.metrics;
    document.getElementById("cpu").textContent = cpu !== undefined ? `${cpu}%` : "--";
    document.getElementById("ram").textContent = ram !== undefined ? `${ram}%` : "--";
    document.getElementById("disk").textContent = disk !== undefined ? `${disk}%` : "--";
    document.getElementById("net-rx").textContent = net_rx !== undefined ? `${net_rx} bytes` : "--";
    document.getElementById("net-tx").textContent = net_tx !== undefined ? `${net_tx} bytes` : "--";

    // Подсветка если >80%
    const values = [cpu, ram, disk];
    const elements = [
        document.getElementById("cpu"),
        document.getElementById("ram"),
        document.getElementById("disk")
    ];
    values.forEach((val, i) => {
        if (val > 80) {
            elements[i].classList.add("high");
        } else {
            elements[i].classList.remove("high");
        }
    });

    const now = new Date().toLocaleTimeString();
    document.getElementById("last-update").textContent = now;
}

function fetchMetrics() {
    fetch("/data")
        .then(res => {
            if (!res.ok) throw new Error("HTTP error " + res.status);
            return res.json();
        })
        .then(data => {
            populateTextFields(data);
            updateCharts(data);
            if (data.status) {
                const msgEl = document.querySelector(".message");
                if (msgEl && data.status.status) {
                    msgEl.textContent = data.status.status;
                }
                const errEl = document.querySelector(".error");
                if (errEl && data.status.error) {
                    errEl.textContent = data.status.error;
                }
            }
        })
        .catch(err => {
            console.error("Error fetching /data:", err);
        });
}

document.addEventListener("DOMContentLoaded", () => {
    initializeCharts();
    fetchMetrics();
    setInterval(fetchMetrics, 3000);
});
