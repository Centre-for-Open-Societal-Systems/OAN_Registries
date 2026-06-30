function checkFarmingType(farmingTypeSelection, fromGroup) {
    var selectedOption = farmingTypeSelection.options[farmingTypeSelection.selectedIndex];
    var selectedFarmingType = selectedOption.textContent.trim();

    const membershipRequiredFields = document.getElementsByClassName("membership_required_field");
    const membershipAstrix = document.getElementsByClassName("membership_astrix");
    const landRequiredFields = document.getElementsByClassName("land_required_field");
    const landAstrix = document.getElementsByClassName("land_astrix");
    const livestockRequiredFields = document.getElementsByClassName("livestock_required_field");
    const cropMixedRequiredFields = document.getElementsByClassName("crop_mixed_required_field");
    const landNext = document.getElementById("land-next");
    const cropNext = document.getElementById("crop-next");
    const livestockNext = document.getElementById("livestock-next");
    const livestockPrev = document.getElementById("livestock-previous");
    const resourcePrev = document.getElementById("resource-previous");
    const agriPrev = document.getElementById("agricultural-previous");
    const addLineLivestockField = document.getElementsByClassName("addline_livestock_field");

    if (selectedFarmingType === "Crop Farming" || selectedFarmingType === "Mixed Farming") {
        // Membership
        Array.from(membershipAstrix).forEach((element) => {
            element.textContent = " *";
        });
        Array.from(membershipRequiredFields).forEach((element) => {
            element.setAttribute("required", "required");
        });
        Array.from(livestockRequiredFields).forEach((element) => {
            element.removeAttribute("required", "required");
        });

        // Land Information
        Array.from(landAstrix).forEach((element) => {
            element.textContent = " *";
        });
        Array.from(landRequiredFields).forEach((element) => {
            element.setAttribute("required", "required");
        });

        Array.from(cropMixedRequiredFields).forEach((element) => {
            element.setAttribute("required", "required");

            // Add event listener to validate when the user selects an option
            if (element.tagName === "SELECT" && element.hasAttribute("multiple")) {
                console.log("selected");
                // Apply multiselect-specific validation
                $(element).on("changed.bs.select", function () {
                    validateMultiSelect(element);
                });
                // Initial validation for multiselect
                validateMultiSelect(element);
            }
        });

        if (fromGroup) {
            landNext.setAttribute(
                "onclick",
                "showModalSection('crop-information', 'land-information',  'next')"
            );
            resourcePrev.setAttribute(
                "onclick",
                "showModalSection('agricultural-input', 'access-to-resource',  'prev')"
            );
        } else {
            const cropMixed = document.getElementsByClassName("crop-mixed-farming-type");
            Array.from(cropMixed).forEach((section) => {
                section.style.display = "block";
            });
            const errMsgCM = document.getElementsByClassName("crop-mixed-err-msg");
            Array.from(errMsgCM).forEach((section) => {
                section.style.display = "none";
            });
        }
    }

    if (selectedFarmingType === "Crop Farming") {
        Array.from(livestockRequiredFields).forEach((element) => {
            element.removeAttribute("required", "required");
        });
        Array.from(cropMixedRequiredFields).forEach((element) => {
            element.setAttribute("required", "required");

            // Add event listener to validate when the user selects an option
            if (element.tagName === "SELECT" && element.hasAttribute("multiple")) {
                console.log("selected");
                // Apply multiselect-specific validation
                $(element).on("changed.bs.select", function () {
                    validateMultiSelect(element);
                    element.removeAttribute("required", "required");
                });
                // Initial validation for multiselect
                validateMultiSelect(element);
            }
        });

        if (fromGroup) {
            cropNext.setAttribute(
                "onclick",
                "showModalSection('agricultural-input', 'crop-information',  'next')"
            );
            cropNext.setAttribute(
                "onclick",
                "showModalSection('agricultural-input', 'crop-information',  'next')"
            );
            agriPrev.setAttribute(
                "onclick",
                "showModalSection('crop-information', 'agricultural-input',  'prev')"
            );
        } else {
            const livestock = document.getElementsByClassName("livestock-farming-type");
            Array.from(livestock).forEach((section) => {
                section.style.display = "none";
            });
            const errMsg = document.getElementsByClassName("livestock-err-msg");
            Array.from(errMsg).forEach((section) => {
                section.style.display = "block";
            });
        }
    } else if (selectedFarmingType === "Livestock Farming") {
        // Membership
        Array.from(membershipAstrix).forEach((element) => {
            element.textContent = "";
        });
        Array.from(membershipRequiredFields).forEach((element) => {
            element.removeAttribute("required");
        });
        Array.from(cropMixedRequiredFields).forEach((element) => {
            element.removeAttribute("required");
            element.classList.remove("is-invalid");
        });
        Array.from(addLineLivestockField).forEach((element) => {
            element.setAttribute("required");
        });
        Array.from(livestockRequiredFields).forEach((element) => {
            element.setAttribute("required", "required");
        });

        // Land Information
        Array.from(landAstrix).forEach((element) => {
            element.textContent = "";
        });
        Array.from(landRequiredFields).forEach((element) => {
            element.removeAttribute("required");
        });

        // Hide some sections
        if (fromGroup) {
            landNext.setAttribute(
                "onclick",
                "showModalSection('livestock-information', 'land-information',  'next')"
            );
            livestockPrev.setAttribute(
                "onclick",
                "showModalSection('land-information', 'livestock-information',  'prev')"
            );
            livestockNext.setAttribute(
                "onclick",
                "showModalSection('access-to-resource', 'livestock-information',  'next')"
            );
            resourcePrev.setAttribute(
                "onclick",
                "showModalSection('livestock-information', 'access-to-resource',  'prev')"
            );
        } else {
            const cropMixed = document.getElementsByClassName("crop-mixed-farming-type");
            Array.from(cropMixed).forEach((section) => {
                section.style.display = "none";
            });
            const errMsg = document.getElementsByClassName("crop-mixed-err-msg");
            Array.from(errMsg).forEach((section) => {
                section.style.display = "block";
            });
            const livestock = document.getElementsByClassName("livestock-farming-type");
            Array.from(livestock).forEach((section) => {
                section.style.display = "block";
            });
            const errMsgLive = document.getElementsByClassName("livestock-err-msg");
            Array.from(errMsgLive).forEach((section) => {
                section.style.display = "none";
            });
        }
    } else if (selectedFarmingType === "Mixed Farming") {
        if (fromGroup) {
            cropNext.setAttribute(
                "onclick",
                "showModalSection('livestock-information', 'crop-information',  'next')"
            );
            livestockPrev.setAttribute(
                "onclick",
                "showModalSection('crop-information', 'livestock-information',  'prev')"
            );
            livestockNext.setAttribute(
                "onclick",
                "showModalSection('agricultural-input', 'livestock-information',  'next')"
            );
            agriPrev.setAttribute(
                "onclick",
                "showModalSection('livestock-information', 'agricultural-input',  'prev')"
            );
        } else {
            const livestock = document.getElementsByClassName("livestock-farming-type");
            Array.from(livestock).forEach((section) => {
                section.style.display = "block";
            });
            const errMsgLive = document.getElementsByClassName("livestock-err-msg");
            Array.from(errMsgLive).forEach((section) => {
                section.style.display = "none";
            });
        }
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Initial check on page load
    const farmingTypeInd = document.getElementById("farming-type-selection-ind");
    const farmingTypeGroup = document.getElementById("farming-type-selection");

    if (farmingTypeInd) {
        checkFarmingType(farmingTypeInd, false);
    } else if (farmingTypeGroup) {
        checkFarmingType(farmingTypeGroup, true);
    }
});
