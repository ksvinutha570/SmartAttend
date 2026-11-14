function toggleStudentFields() {
    const role = document.getElementById("role");
    const studentFields = document.getElementById("studentFields");
    const usn = document.getElementById("usn");

    if (!role || !studentFields) {
        return;
    }

    const isStudent = role.value === "student";

    studentFields.hidden = !isStudent;

    if (usn) {
        usn.required = isStudent;
    }
}

function validateRegister() {
    const password = document.getElementById("password");

    if (password && password.value.length < 6) {
        alert("Password must contain at least 6 characters.");
        return false;
    }

    return true;
}

document.addEventListener("DOMContentLoaded", function () {
    const dateInput = document.getElementById("date");

    if (dateInput) {
        dateInput.value = new Date().toISOString().split("T")[0];
    }

    toggleStudentFields();
});