let chart;

function initializeChart() {
    const ctx = document.getElementById("metricsChart");
    if (!ctx) {
        console.error("Элемент canvas с id 'metricsChart' не найден!");
        return;
    }

    chart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["CPU", "RAM", "Disk"],
            datasets: [{
                label: "Usage Percentage",
                data: [0, 0, 0],
                backgroundColor: ["#ff6384", "#36a2eb", "#ffce56"],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: "Usage (%)"
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: "Metrics"
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: "top"
                },
                title: {
                    display: true,
                    text: "Server Metrics"
                }
            },
            animation: {
                duration: 1000,
                easing: "easeInOutQuad"
            }
        }
    });
    console.log("Chart successfully initialized");
}

function updateChart(data) {
    console.log("Received data for chart:", data);
    if (!chart) {
        initializeChart();
    }
    if (data && data.metrics) {
        const { cpu, ram, disk } = data.metrics;
        const now = new Date().toLocaleTimeString();
        document.getElementById("last-update").textContent = now;

        chart.data.datasets[0].data = [cpu || 0, ram || 0, disk || 0];
        chart.update();
        console.log("Chart updated with data:", chart.data.datasets[0].data);

        const cpuElement = document.getElementById("cpu");
        const ramElement = document.getElementById("ram");
        const diskElement = document.getElementById("disk");

        [cpuElement, ramElement, diskElement].forEach((element, index) => {
            element.textContent = data.metrics[Object.keys(data.metrics)[index]] !== undefined
                ? `${data.metrics[Object.keys(data.metrics)[index]]}%`
                : "Waiting for data...";
            if (data.metrics[Object.keys(data.metrics)[index]] > 80) {
                element.classList.add("high");
            } else {
                element.classList.remove("high");
            }
        });
    } else {
        console.log("No metrics data to update");
        document.getElementById("last-update").textContent = "Never";
    }
}

function fetchMetrics() {
    fetch("/data")
        .then(response => {
            if (!response.ok) {
                throw new Error("HTTP Error: " + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log("Response from /data:", data);
            if (data.status && data.status.error) {
                document.querySelector(".error").textContent = data.status.error || "Unknown error";
                document.querySelector(".message").textContent = "";
            } else {
                document.querySelector(".message").textContent = data.status ? data.status.status : "Data received";
                if (document.querySelector(".error")) {
                    document.querySelector(".error").textContent = "";
                }
                updateChart(data);
            }
        })
        .catch(error => {
            console.error("Error fetching metrics:", error);
            document.querySelector(".message").textContent = "Error connecting to server";
            if (document.querySelector(".error")) {
                document.querySelector(".error").textContent = "Failed to load data";
            }
        });
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("Page loaded, starting to fetch metrics");
    initializeChart();
    fetchMetrics();
    setInterval(fetchMetrics, 2000);
});