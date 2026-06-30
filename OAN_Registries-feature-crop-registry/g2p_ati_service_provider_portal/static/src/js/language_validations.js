var primaryLang = null;

$(document).ready(function () {
    // eslint-disable-next-line no-undef
    primaryLang = primaryLanguageData;
});

function updateLanguage(langElement) {
    const selectedValue = langElement.value;
    const nameRow = document.getElementById("other-lang-names");

    const givenName = document.getElementById("other-given-name");
    const fatherName = document.getElementById("other-father-name");
    const gfName = document.getElementById("other-gf-name");

    const givenNameOther = document.getElementById("first_name_other");
    const fatherNameOther = document.getElementById("family_name_other");
    const gfNameOther = document.getElementById("gf_name_other");

    const givenNameAmh = document.getElementById("first_name_amh");
    const fatherNameAmh = document.getElementById("family_name_amh");
    const gfNameAmh = document.getElementById("gf_name_amh");
    const amhNamesReq = document.getElementsByClassName("amh_names_required");

    const selectedLang = primaryLang.find((lang) => parseInt(lang.value, 10) === parseInt(selectedValue, 10));

    const allowedLanguages = ["Afaan Oromoo", "Afar", "Tigrinya", "Somali"];

    const placeholders = {
        "Afaan Oromoo": {
            givenName: "Maqaa Galchi",
            fatherName: "Maqaa Galchi",
            gfName: "Maqaa Galchi",
        },
        Afar: {
            givenName: "Migaq Culus",
            fatherName: "Migaq Culus",
            gfName: "Migaq Culus",
        },
        Tigrinya: {
            givenName: "ስም ኣእትዉ",
            fatherName: "ስም ኣእትዉ",
            gfName: "ስም ኣእትዉ",
        },
        Somali: {
            givenName: "Geli Magaca",
            fatherName: "Geli Magaca",
            gfName: "Geli Magaca",
        },
    };

    if (selectedLang) {
        if (allowedLanguages.includes(selectedLang.label)) {
            if (givenName) {
                givenName.textContent = `(${selectedLang.label})`;
            }
            if (fatherName) {
                fatherName.textContent = `(${selectedLang.label})`;
            }
            if (gfName) {
                gfName.textContent = `(${selectedLang.label})`;
            }

            givenNameAmh.removeAttribute("required");
            fatherNameAmh.removeAttribute("required");
            gfNameAmh.removeAttribute("required");
            Array.from(amhNamesReq).forEach((element) => {
                element.textContent = "";
            });
            // Set placeholders based on selected language
            givenNameOther.setAttribute("placeholder", placeholders[selectedLang.label]?.givenName);
            fatherNameOther.setAttribute("placeholder", placeholders[selectedLang.label]?.fatherName);
            gfNameOther.setAttribute("placeholder", placeholders[selectedLang.label]?.gfName);
        } else {
            givenNameAmh.setAttribute("required", "required");
            fatherNameAmh.setAttribute("required", "required");
            gfNameAmh.setAttribute("required", "required");
            givenNameOther.removeAttribute("required");
            fatherNameOther.removeAttribute("required");
            gfNameOther.removeAttribute("required");
            Array.from(amhNamesReq).forEach((element) => {
                element.textContent = " *";
            });
        }
    } else {
        return;
    }

    const defaultValue = langElement.options[0].value;
    if (
        selectedValue !== defaultValue &&
        selectedValue !== "" &&
        allowedLanguages.includes(selectedLang?.label)
    ) {
        nameRow.style.display = "flex";
    } else {
        nameRow.style.display = "none";
    }
}

// eslint-disable-next-line no-unused-vars
function validateLang(element) {
    if (element.getAttribute("name") === "primary_language") {
        updateLanguage(element);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // eslint-disable-next-line no-undef
    primaryLang = primaryLanguageData;
    // Initial check on page load
    const langSelect = document.getElementById("primary_language");
    updateLanguage(langSelect);
});
