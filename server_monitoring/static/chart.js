let chart;

function initializeChart() {
    const ctx = document.getElementById("metricsChart");
    if (!ctx) {
        console.error("Canvas with id 'metricsChart' not found");
        return;
    }

    chart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["CPU(%)", "RAM(%)", "Disk(%)", "Net RX(bytes)", "Net TX(bytes)"],
            datasets: [{
                label: "Current Values",
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    "#ff6384", // CPU
                    "#36a2eb", // RAM
                    "#ffce56", // Disk
                    "#4bc0c0", // Net RX
                    "#9966ff"  // Net TX
                ],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "Value"
                    }
                }
            },
            plugins: {
                legend: { display: true },
                title: { display: true, text: "Server Metrics" }
            }
        }
    });
}

function updateChart(data) {
    if (!chart) {
        initializeChart();
    }
    if (data && data.metrics) {
        const { cpu, ram, disk, net_rx, net_tx } = data.metrics;
        const now = new Date().toLocaleTimeString();

        chart.data.datasets[0].data = [cpu || 0, ram || 0, disk || 0, net_rx || 0, net_tx || 0];
        chart.update();

        document.getElementById("cpu").textContent = cpu !== undefined ? `${cpu}%` : "--";
        document.getElementById("ram").textContent = ram !== undefined ? `${ram}%` : "--";
        document.getElementById("disk").textContent = disk !== undefined ? `${disk}%` : "--";
        document.getElementById("net-rx").textContent = net_rx !== undefined ? `${net_rx} bytes` : "--";
        document.getElementById("net-tx").textContent = net_tx !== undefined ? `${net_tx} bytes` : "--";
        document.getElementById("last-update").textContent = now;

        // Подсветка, если >80% (CPU, RAM, DISK)
        let values = [cpu, ram, disk];
        let elements = [
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
    }
}

function fetchMetrics() {
    fetch("/data")
        .then(res => {
            if (!res.ok) throw new Error("HTTP error " + res.status);
            return res.json();
        })
        .then(data => {
            updateChart(data);
            if (data.status) {
                let msgEl = document.querySelector(".message");
                if (msgEl) {
                    msgEl.textContent = data.status.status || "Monitoring...";
                }
                let errEl = document.querySelector(".error");
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
    initializeChart();
    fetchMetrics();
    setInterval(fetchMetrics, 2000);
});
