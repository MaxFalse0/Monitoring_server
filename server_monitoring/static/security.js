window.addEventListener("DOMContentLoaded", () => {
    const logoutLink = document.getElementById("logout-link");
    if (logoutLink) {
        logoutLink.addEventListener("click", function (e) {
            if (!confirm("Вы действительно хотите выйти?")) {
                e.preventDefault();
            }
        });
    }
});
