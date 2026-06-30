$(document).ready(function () {
    // $('.selectpicker').selectpicker();

    // Determine starting index based on existing crop_info_data
    var cropMaxIndex = 0;
    $(".crop-section-wrapper").each(function () {
        var cropIndex = parseInt($(this).attr("data-index"), 10);
        if (!isNaN(cropIndex)) {
            cropMaxIndex = Math.max(cropMaxIndex, cropIndex);
        }
    });
    var cropIndex = cropMaxIndex + 1;

    var livestockMaxIndex = 0;
    $(".livestock-section-wrapper").each(function () {
        var livestockIndex = parseInt($(this).attr("data-index"), 10);
        if (!isNaN(livestockIndex)) {
            livestockMaxIndex = Math.max(livestockMaxIndex, livestockIndex);
        }
    });
    var livestockIndex = livestockMaxIndex + 1;

    var landMaxIndex = 0;
    $(".land-section-wrapper").each(function () {
        var landIndex = parseInt($(this).attr("data-index"), 10);
        if (!isNaN(landIndex)) {
            landMaxIndex = Math.max(landMaxIndex, landIndex);
        }
    });
    var landIndex = landMaxIndex + 1;

    $("#add-crop-info").click(function () {
        var $template = $("#crop-hidden-template").html();
        var $formContainer = $("#section-content-crop");

        // Use jQuery to replace {cropIndex} placeholder in the template
        var newLineHtml = $template.replace(/\{9999\}/g, cropIndex);
        var $newLine = $(newLineHtml);
        $formContainer.append($newLine);

        // Var newSelectIdIllness = `crop_illness_types_${cropIndex}`;
        //     VirtualSelect.init({
        //         ele: `#${newSelectIdIllness}`,
        //         options: cropIllnessType,
        //         search: true,
        //         multiple: true,
        //     });
        cropIndex++;
    });

    $("#add-livestock-info").click(function () {
        var $template = $("#livestock-hidden-template").html();
        var $formContainer = $("#section-content-livestock");

        // Replace {9999} placeholder in the template
        var newLineHtml = $template.replace(/\{9999\}/g, livestockIndex);
        var $newLine = $(newLineHtml);

        // Gather already selected animal types from the first select
        const selectedAnimalTypes = [];
        $("select[id='livestock_selection']").each(function () {
            const selectedValue = $(this).val();
            if (selectedValue) {
                selectedAnimalTypes.push(selectedValue);
            }
        });

        // Get the new select element
        var newSelect = $newLine.find("select");

        // Clear existing options except the first one (the placeholder)
        newSelect.find("option").not(":first").remove();

        // Populate new select with options from the first select excluding the selected ones
        $("select[id='livestock_selection']")
            .first()
            .find("option")
            .each(function () {
                const optionValue = $(this).val();
                const optionText = $(this).text();

                // Check if the option is not already selected
                if (optionValue && !selectedAnimalTypes.includes(optionValue)) {
                    newSelect.append(`<option value="${optionValue}">${optionText}</option>`);
                }
            });

        // Append the new line to the form container
        $formContainer.append($newLine);
        livestockIndex++;
    });

    $("#add-land-info").click(function () {
        var $template = $("#land-hidden-template").html();
        var $formContainer = $("#section-content-land");

        // Use jQuery to replace {cropIndex} placeholder in the template
        var newLineHtml = $template.replace(/\{9999\}/g, landIndex);
        var $newLine = $(newLineHtml);
        $formContainer.append($newLine);

        landIndex++;
    });

    // Function to toggle display and required attribute of a field
    function toggleField(selectElementId, fieldId, inputId, yesText = "yes") {
        const selectElement = document.getElementById(selectElementId);
        const field = document.getElementById(fieldId);
        // Const input = document.getElementById(inputId);

        let selectedOptionText = null;
        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === yesText.toLowerCase()) {
            field.style.display = "block";
            // Input.setAttribute("required", "required");
        } else {
            field.style.display = "none";
            // Input.removeAttribute("required");
        }
    }

    // Function to handle changes in a select element
    // eslint-disable-next-line no-unused-vars
    function handleSelectChange(selectElementId, fieldId, inputId, otherText = "other") {
        const selectElement = document.getElementById(selectElementId);
        const field = document.getElementById(fieldId);
        const input = document.getElementById(inputId);

        let selectedOptionText = null;
        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === otherText.toLowerCase()) {
            field.style.display = "block";
            input.setAttribute("required", "required");
        } else {
            field.style.display = "none";
            input.removeAttribute("required");
        }
    }

    // Apply the function to both UID and RID inputs

    const ridInput = document.getElementById("rid_input");
    const uidInput = document.getElementById("uid_input");
    const uidError = document.getElementById("uid_error");
    const ridError = document.getElementById("rid_error");

    formatInputWithSpaces(uidInput);
    formatInputWithSpaces(ridInput);

    uidInput.addEventListener("input", function () {
        const sanitizedValue = uidInput.value.replace(/\s+/g, "");
        const isOnlyDigits = /^\d*$/.test(sanitizedValue);

        if ((sanitizedValue.length !== 12 && sanitizedValue.length !== 0) || !isOnlyDigits) {
            uidInput.classList.add("uid_error");
            uidError.style.display = "block";
            // UidInput.setAttribute("required", "required");
        } else {
            uidInput.classList.remove("uid_error");
            uidError.style.display = "none";
        }
    });

    ridInput.addEventListener("input", function () {
        const sanitizedValue = ridInput.value.replace(/\s+/g, "");
        const isOnlyDigits = /^\d*$/.test(sanitizedValue);
        if ((sanitizedValue.length !== 29 && sanitizedValue.length !== 0) || !isOnlyDigits) {
            ridInput.classList.add("rid_error");
            ridError.style.display = "block";
            // RidInput.setAttribute("required", "required");
        } else {
            ridInput.classList.remove("rid_error");
            ridError.style.display = "none";
        }
    });

    // Function handleNationalIdSelection() {
    //     const selectElement = document.getElementById("have-national-id-selection");
    //     const uidDiv = document.getElementById("uid-div");
    //     const ridDiv = document.getElementById("rid-div");

    //     const uidInput = document.getElementById("uid_input");
    //     const ridInput = document.getElementById("rid_input");
    //     const uidError = document.getElementById("uid_error");
    //     const ridError = document.getElementById("rid_error");

    //     const selectedOptionText = selectElement.options[selectElement.selectedIndex].text
    //         .trim()
    //         .toLowerCase();

    //     if (selectedOptionText === "yes") {
    //         uidDiv.style.display = "block";
    //         uidInput.setAttribute("required", "required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");

    //         // Disable the 'No' option once 'Yes' is selected
    //         const noOption = [...selectElement.options].find(option => option.text.trim().toLowerCase() === "no");
    //         if (noOption) {
    //             noOption.disabled = true;
    //         }
    //     } else if (selectedOptionText === "no") {
    //         uidDiv.style.display = "none";
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "block";
    //         ridInput.setAttribute("required", "required");
    //     } else {
    //         uidDiv.style.display = "none";
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");
    //     }

    //     uidError.style.display = "none";
    //     ridError.style.display = "none";
    // }

    // document.addEventListener("DOMContentLoaded", function () {
    //     const hasUid = "{{ has_uid }}";
    //     const selectElement = document.getElementById("have-national-id-selection");
    //     const uidDiv = document.getElementById("uid-div");
    //     const ridDiv = document.getElementById("rid-div");
    //     const uidInput = document.getElementById("uid_input");
    //     const ridInput = document.getElementById("rid_input");

    //     // Set the selection based on UID presence
    //     if (hasUid === "True") {
    //         selectElement.value = "yes";
    //         uidDiv.style.display = "block";
    //         uidInput.setAttribute("required", "required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");

    //         // Disable the 'No' option
    //         // Get the current URL

    //         const noOption = [...selectElement.options].find(option => option.text.trim().toLowerCase() === "no");
    //         if (noOption) {
    //             noOption.disabled = true;
    //         }
    //     } else {
    //         selectElement.value = "";
    //         uidDiv.style.display = "none";
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");
    //     }

    //     selectElement.addEventListener("change", handleNationalIdSelection);
    // });

    // function handleNationalIdSelection() {
    //     const selectElement = document.getElementById("have-national-id-selection");
    //     const uidDiv = document.getElementById("uid-div");
    //     const ridDiv = document.getElementById("rid-div");

    //     const uidInput = document.getElementById("uid_input");
    //     const ridInput = document.getElementById("rid_input");
    //     const uidError = document.getElementById("uid_error");
    //     const ridError = document.getElementById("rid_error");

    //     const selectedOptionText = selectElement.options[selectElement.selectedIndex].text
    //         .trim()
    //         .toLowerCase();

    //     if (selectedOptionText === "yes") {
    //         uidDiv.style.display = "block";
    //         uidInput.setAttribute("required", "required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");
    //     } else if (selectedOptionText === "no") {
    //         uidDiv.style.display = "none";
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "block";
    //         ridInput.setAttribute("required", "required");
    //     } else {
    //         uidDiv.style.display = "none";
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "none";
    //         ridInput.removeAttribute("required");
    //     }

    //     // Hide errors initially
    //     uidError.style.display = "none";
    //     ridError.style.display = "none";
    // }
    // document.addEventListener("DOMContentLoaded", function () {
    //     const hasUid = "{{ has_uid }}"; // Pass this from your template context
    //     const selectElement = document.getElementById("have-national-id-selection");
    //     const uidDiv = document.getElementById("uid-div");
    //     const ridDiv = document.getElementById("rid-div");
    //     const uidInput = document.getElementById("uid_input");
    //     const ridInput = document.getElementById("rid_input");

    //     // Get the current URL
    //     const currentUrl = window.location.href;

    //     // Debugging step: Check if the URL is captured correctly
    //     console.log("Current URL:", currentUrl);

    //     // Set the selection based on UID presence
    //     if (hasUid === "True") {
    //         selectElement.value = "yes"; // Set dropdown to "Yes" if UID exists
    //         uidDiv.style.display = "block"; // Show UID div
    //         uidInput.setAttribute("required", "required");
    //         ridDiv.style.display = "none"; // Hide RID div
    //         ridInput.removeAttribute("required");
    //     } else {
    //         selectElement.value = ""; // Reset selection
    //         uidDiv.style.display = "none"; // Hide UID div
    //         uidInput.removeAttribute("required");
    //         ridDiv.style.display = "none"; // Hide RID div
    //         ridInput.removeAttribute("required");
    //     }

    //     // If the URL includes "/individual/update/", disable the select element and make UID readonly
    //     if (currentUrl.includes("/individual/update/")) {
    //         selectElement.disabled = true;  // Disable the select element (readonly)
    //         uidInput.setAttribute("readonly", "readonly");  // Make UID input readonly

    //         // Debugging steps to confirm if selection is disabled and UID is readonly
    //         console.log("Is select disabled?", selectElement.disabled);
    //         console.log("Is UID readonly?", uidInput.readOnly);
    //     }

    //     // Attach change event listener to the select element for non-update cases
    //     selectElement.addEventListener("change", handleNationalIdSelection);
    // });

    function handleNationalIdSelection() {
        const selectElement = document.getElementById("have-national-id-selection");
        const uidDiv = document.getElementById("uid-div");
        const ridDiv = document.getElementById("rid-div");

        const uidInput = document.getElementById("uid_input");
        const ridInput = document.getElementById("rid_input");
        const uidError = document.getElementById("uid_error");
        const ridError = document.getElementById("rid_error");

        // Const ridInput = document.getElementById("rid_input");
        // Const uidInput = document.getElementById("uid_input");

        let selectedOptionText = null;
        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === "yes") {
            uidDiv.style.display = "block";
            uidInput.setAttribute("required", "required");
            ridDiv.style.display = "none";
            ridInput.removeAttribute("required");
        } else if (selectedOptionText === "no") {
            uidDiv.style.display = "none";
            uidInput.removeAttribute("required");
            ridDiv.style.display = "block";
            ridInput.setAttribute("required", "required");
        } else {
            uidDiv.style.display = "none";
            uidInput.removeAttribute("required");
            ridDiv.style.display = "none";
            ridInput.removeAttribute("required");
        }
        uidError.style.display = "none";
        ridError.style.display = "none";
    }

    document.addEventListener("DOMContentLoaded", function () {
        const hasUid = "{{ has_uid }}";
        const selectElement = document.getElementById("have-national-id-selection");

        // Set the selection based on UID presence
        if (hasUid === "True") {
            selectElement.value = "yes";
            uidDiv.style.display = "block";
            uidInput.setAttribute("required", "required");
            ridDiv.style.display = "none";
            ridInput.removeAttribute("required");
        } else {
            selectElement.value = "";
            uidDiv.style.display = "none";
            uidInput.removeAttribute("required");
            ridDiv.style.display = "none";
            ridInput.removeAttribute("required");
        }

        if (currentUrl.includes("/individual/update/")) {
            selectElement.disabled = true;
        }

        selectElement.addEventListener("change", handleNationalIdSelection);
    });

    function formatInputWithSpaces(inputElement) {
        inputElement.addEventListener("input", function () {
            const value = inputElement.value.replace(/\s+/g, "");
            const formattedValue = value.match(/.{1,4}/g)?.join(" ") || "";
            inputElement.value = formattedValue;
        });
    }

    function handleSelection(selectElementId, divElementId, inputElementId) {
        const selectElement = document.getElementById(selectElementId);
        const divElement = document.getElementById(divElementId);
        const inputElement = document.getElementById(inputElementId);

        let selectedOptionText = null;
        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === "yes") {
            divElement.style.display = "block";
            inputElement.setAttribute("required", "required");
        } else {
            divElement.style.display = "none";
            inputElement.removeAttribute("required");
        }
    }

    function handleClusterSelection() {
        const selectElement = document.getElementById("in_farmer_cluster");
        const primaryCommodityDiv = document.getElementById("commodity_div");
        const primaryCommodity = document.getElementById("primary_commodity");
        const roleDiv = document.getElementById("role_div");
        const clusterRole = document.getElementById("role_in_cluster");

        let selectedOptionText = null;
        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === "yes") {
            primaryCommodityDiv.style.display = "block";
            primaryCommodity.setAttribute("required", "required");
            roleDiv.style.display = "block";
            clusterRole.setAttribute("required", "required");
        } else if (selectedOptionText === "no") {
            primaryCommodityDiv.style.display = "none";
            primaryCommodity.removeAttribute("required");
            roleDiv.style.display = "none";
            clusterRole.removeAttribute("required");
        } else {
            primaryCommodityDiv.style.display = "none";
            primaryCommodity.removeAttribute("required");
            roleDiv.style.display = "none";
            clusterRole.removeAttribute("required");
        }
    }

    function handlePhoneNumberSelection() {
        console.log("in phone number change");

        const selectElement = document.getElementById("have-phone-no-selection");
        const primaryPhoneDiv = document.getElementById("primary-div");
        const otherPhoneDiv = document.getElementById("other-div");
        const primaryPhone = document.getElementById("primary_phone");
        const otherPhone = document.getElementById("other_phone");

        let selectedOptionText;

        if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
            selectedOptionText = selectElement.options[selectElement.selectedIndex].text.trim().toLowerCase();
        }

        if (selectedOptionText === "yes") {
            primaryPhoneDiv.style.display = "block";
            primaryPhone.setAttribute("required", "required");
            otherPhoneDiv.style.display = "none";
            otherPhone.removeAttribute("required");
        } else if (selectedOptionText === "no") {
            primaryPhoneDiv.style.display = "none";
            primaryPhone.removeAttribute("required");
            otherPhoneDiv.style.display = "block";
            otherPhone.setAttribute("required", "required");
        } else {
            primaryPhoneDiv.style.display = "none";
            primaryPhone.removeAttribute("required");
            otherPhoneDiv.style.display = "none";
            otherPhone.removeAttribute("required");
        }
    }

    // Function to update options for a select element based on an AJAX response

    function updateOptions(
        url,
        data,
        targetSelectId,
        defaultOptionText = "Select",
        originalEvent = "",
        selectdropdown = "",
        initialValue = false
    ) {
        console.log(data);
        $.ajax({
            url: url,
            method: "POST",
            dataType: "json",
            data: data,
            success: function (options) {
                var selectedvalue = " ";
                const selectElement = document.getElementById(targetSelectId);

                if (selectElement.options.length > 0 && selectElement.selectedIndex >= 0) {
                    const selectedName = selectElement.options[selectElement.selectedIndex].text;
                }

                if (
                    originalEvent !== "" &&
                    (selectdropdown === "current_region" || selectdropdown === "region")
                ) {
                    selectedvalue = " ";
                } else if (originalEvent !== "") {
                    selectedvalue = " ";
                } else if (selectElement.selectedIndex > 0) {
                    selectedvalue = selectElement.options[selectElement.selectedIndex].value;
                    // If (selectedName) {
                    //     defaultOptionText = selectedName;
                    // }
                } else if (selectElement.selectedIndex === 0 && selectedName !== "Select") {
                    selectedvalue = selectElement.options[selectElement.selectedIndex].value;
                    // If (selectedName) {
                    //     defaultOptionText = selectedName;
                    // }
                }

                selectElement.innerHTML = "";

                const defaultOption = document.createElement("option");
                defaultOption.value = selectedvalue;
                defaultOption.textContent = defaultOptionText;
                selectElement.appendChild(defaultOption);

                options.forEach((option) => {
                    const opt = document.createElement("option");
                    opt.value = option.id;
                    opt.textContent = option.name;
                    selectElement.appendChild(opt);
                });

                if (initialValue) {
                    selectElement.value = initialValue;
                }
            },
            error: function (error) {
                console.error("Error fetching options:", error);
            },
        });
    }

    const initialRegionId = $("#region_selection").val();
    const initialZoneId = $("#zon_selection").val();
    const initialWoredaId = $("#woreda_selection").val();
    const initialKebeleId = $("#kebele_selection").val();

    console.log(`Here are the initial values ${initialRegionId}, ${initialZoneId}, ${initialWoredaId}`);

    updateOptions(
        "/update_zone_options",
        {region_id: initialRegionId},
        "zon_selection",
        "Select",
        null,
        "region",
        (initialValue = initialZoneId)
    );

    updateOptions(
        "/update_woreda_options",
        {zone_id: initialZoneId},
        "woreda_selection",
        "Select",
        null,
        "zone",
        (initialValue = initialWoredaId)
    );

    updateOptions(
        "/update_kebele_options",
        {woreda_id: initialWoredaId},
        "kebele_selection",
        "Select",
        null,
        "woreda",
        (initialValue = initialKebeleId)
    );

    // Event listener for national ID selection change
    $("#have-national-id-selection").on("change", handleNationalIdSelection);

    // Event listener for phone number selection change
    $("#have-phone-no-selection").on("change", handlePhoneNumberSelection);

    $("#is_member_of_primary_coop").on("change", function () {
        handleSelection("is_member_of_primary_coop", "primary_coop_div", "name_of_primary_coop");
    });

    $("#is_member_of_coop_union").on("change", function () {
        handleSelection("is_member_of_coop_union", "coop_div", "name_of_coop_union");
    });

    $("#access-to-machinery-selection").on("change", function () {
        handleSelection("access-to-machinery-selection", "machinery_div", "machinery-types-select");
    });

    $("#access-to-finance-selection").on("change", function () {
        handleSelection("access-to-finance-selection", "financial_div", "finance-selection");
    });

    $("#in_farmer_cluster").on("change", handleClusterSelection);

    $("#access-to-machinery-selection").on("change", function () {
        toggleField("access-to-machinery-selection", "machinery-field", "machinery-types-select");
    });

    $("#access-to-finance-selection").on("change", function () {
        toggleField("access-to-finance-selection", "finance-field", "finance-selection");
    });

    $("#region_selection").on("change", function (event) {
        const regionId = this.value;
        var ev = event.originalEvent;
        updateOptions("/update_zone_options", {region_id: regionId}, "zon_selection", "Select", ev, "region");
        updateOptions("/update_woreda_options", {zone_id: 0}, "woreda_selection", "Select", ev, "region");
        updateOptions("/update_kebele_options", {woreda_id: 0}, "kebele_selection", "Select", ev, "region");
    });

    $("#zon_selection").on("change", function (event) {
        const zoneId = this.value;
        var ev = event.originalEvent;
        updateOptions("/update_woreda_options", {zone_id: zoneId}, "woreda_selection", "Select", ev);
        updateOptions("/update_kebele_options", {woreda_id: 0}, "kebele_selection", "Select", ev);
    });

    $("#woreda_selection").on("change", function (event) {
        const woredaId = this.value;
        var ev = event.originalEvent;
        updateOptions("/update_kebele_options", {woreda_id: woredaId}, "kebele_selection", "Select", ev);
    });

    // Trigger the change event on page load to handle the initial state
    $("#have-national-id-selection").trigger("change");
    $("#have-phone-no-selection").trigger("change");
    $("#access-to-machinery-selection").trigger("change");
    $("#access-to-finance-selection").trigger("change");

    // Validation for email
    const emailInput = document.getElementById("email");

    function isValidEmail(email) {
        // Basic email regex pattern
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(email);
    }

    emailInput.addEventListener("input", function () {
        if (emailInput.value.length === 0) {
            emailInput.classList.remove("is-invalid");
            // EmailError.style.display = "none";
        } else if (isValidEmail(emailInput.value)) {
            emailInput.classList.remove("is-invalid");
            // EmailError.style.display = "none";
        } else {
            emailInput.classList.add("is-invalid");
            // EmailError.style.display = "block";
        }
    });

    function expandSection(sectionId) {
        var consentSection = document.getElementById(sectionId);
        consentSection.classList.add("show");
    }

    // Function hideSection(sectionId) {
    //     var consentSection = document.getElementById(sectionId);
    //     consentSection.classList.add("hide");
    // }

    window.customvalidateForm = function (isCreateForm) {
        const requiredFields = document.querySelectorAll("[required]");
        var valid = true;

        for (let i = 0; i < requiredFields.length; i++) {
            const field = requiredFields[i];
            const isFieldValid = (field.value || "").trim();
            const fieldName = field.getAttribute("name");

            if (fieldName.includes("{9999}")) {
                continue;
            }

            valid = valid && isFieldValid;

            if (!valid) {
                field.classList.toggle("is-invalid", !isFieldValid);
                const parentDiv = field.closest(".section-container");
                if (parentDiv) {
                    var sectionRequiredFields = parentDiv.querySelectorAll("[required]");
                    sectionRequiredFields.forEach((sectionField) => {
                        const isSectionFieldValid = sectionField.value.trim();
                        sectionField.classList.toggle("is-invalid", !isSectionFieldValid);
                    });

                    const navId = parentDiv.id + "-link";
                    var navLink = document.getElementById(navId);
                    expandSection(parentDiv.id);
                    navLink.click();
                }

                break;
            }
        }

        if (valid) {
            this.validateForm(isCreateForm);
        }
    };
});

function validateSelect(selectElement) {
    const value = selectElement.value;
    const defaultValue = selectElement.options[0].value;
    if (value !== defaultValue && value !== "") {
        selectElement.classList.remove("is-invalid");
    }
}

function validateInput(inputElement) {
    if (inputElement.type === "radio") {
        // Get all radio buttons with the same name (group)
        const radioGroup = document.querySelectorAll(`input[name="${inputElement.name}"]`);

        // Remove the "is-invalid" class from all radio buttons in the group
        radioGroup.forEach((radio) => {
            radio.classList.remove("is-invalid");
        });
    } else {
        // For other input types, check the value and remove "is-invalid" if not empty
        const value = inputElement.value;
        if (value.trim() !== "") {
            inputElement.classList.remove("is-invalid");
        }
    }
}

function validateMultiSelect(selectElement) {
    const selectedOptions = $(selectElement).val();
    const isValid = selectedOptions && selectedOptions.length > 0;

    // Wrapper of the selectpicker
    const selectWrapper = $(selectElement).parent().find(".dropdown-toggle");

    // Add or remove the 'is-invalid' class based on the validation
    if (!isValid) {
        selectWrapper.addClass("is-invalid");
    } else {
        selectWrapper.removeClass("is-invalid");
    }

    // Always ensure the select element itself reflects validity
    $(selectElement).toggleClass("is-invalid", !isValid);

    return isValid;
}

// eslint-disable-next-line no-unused-vars
function validateElement(element) {
    // Check if the element is a select or an input field
    if (element.tagName === "SELECT" && element.multiple) {
        $(element).removeClass("is-invalid");
        return validateMultiSelect(element);
    } else if (element.tagName === "SELECT") {
        validateSelect(element);
    } else if (element.id === "total_land_area") {
        validateLandArea(element);
    } else if (element.id === "number_of_livestock") {
        validateLandArea(element);
    } else if (element.tagName === "INPUT") {
        validateInput(element);
    }
}

function validateUID() {
    const uid = document.getElementById("uid_input");
    const uidError = document.getElementById("uid_error");
    // Const isValid = uid.value.length === 12 && /^\d+$/.test(uid.value);
    const isValid =
        uid.value.replace(/\s+/g, "").length === 12 && /^\d+$/.test(uid.value.replace(/\s+/g, ""));
    uid.classList.toggle("is-invalid", !isValid);
    // Uid.classList.toggle("is-valid", isValid); // Add this line
    uidError.style.display = isValid ? "none" : "block";
    return isValid;
}

function validateRID() {
    const rid = document.getElementById("rid_input");
    const ridError = document.getElementById("rid_error");
    // Const isValid = rid.value.length === 29 && /^\d+$/.test(rid.value);
    const isValid =
        rid.value.replace(/\s+/g, "").length === 29 && /^\d+$/.test(rid.value.replace(/\s+/g, ""));
    rid.classList.toggle("is-invalid", !isValid);
    // Rid.classList.toggle("is-valid", isValid); // Add this line
    ridError.style.display = isValid ? "none" : "block";
    return isValid;
}

function validateRadioButtons(radioName, section) {
    const radioGroup = section.querySelectorAll(`input[name="${radioName}"]`);
    const radioChecked = Array.from(radioGroup).some((radio) => radio.checked);

    radioGroup.forEach((radio) => {
        // Add or remove the invalid-radio class based on whether any radio is checked
        if (!radioChecked) {
            radio.classList.add("invalid-radio");
        } else {
            radio.classList.remove("invalid-radio");
        }

        // Attach an event listener to each radio button to remove the invalid-radio class when checked
        radio.addEventListener("change", function () {
            radioGroup.forEach((radio) => radio.classList.remove("invalid-radio"));
        });
    });

    return radioChecked;
}

function validateLandArea(field) {
    const digitRegex = /^\d*\.?\d+$/; // Regular expression to allow only digits
    const landAreaError = document.getElementById("land_area_error");

    // Check if the input value is valid (only digits)
    const isValid = digitRegex.test(field.value);

    // Display or hide the error message based on the validation
    // landAreaError.style.display = isValid ? 'none' : 'block';

    // If the input is valid, remove the 'is-invalid' class
    // If it's not valid, add the 'is-invalid' class
    if (isValid) {
        field.classList.remove("is-invalid");
    } else {
        field.classList.add("is-invalid");
    }

    return isValid;
}

function validateFileInput(field) {
    const allowedFileTypes = ["image/jpeg", "image/png", "application/pdf"]; // Allowed types
    const maxFileSize = 5 * 1024 * 1024; // 5 MB limit

    // Get the files from the input
    const files = field.files;

    // Ensure that only one file can be uploaded
    if (files.length > 1) {
        field.classList.add("is-invalid"); // Add invalid class for UI
        return false; // More than one file uploaded
    }

    // If no files uploaded, return false
    if (files.length === 0) {
        field.classList.add("is-invalid"); // Add invalid class for UI
        return false; // No file uploaded
    }

    const file = files[0]; // Get the single file

    // Check file type
    if (!allowedFileTypes.includes(file.type)) {
        field.classList.add("is-invalid"); // Add invalid class for UI
        return false; // Invalid file type
    }

    // Check file size
    if (file.size > maxFileSize) {
        field.classList.add("is-invalid"); // Add invalid class for UI
        return false; // File too large
    }

    field.classList.remove("is-invalid"); // Remove invalid class if valid
    return true; // Valid file input
}

function validateSection(sectionId) {
    const section = document.getElementById(sectionId);
    const requiredFields = section.querySelectorAll("[required]");
    const uidError = document.getElementById("uid_error");
    const ridError = document.getElementById("rid_error");

    let valid = true;

    requiredFields.forEach((field) => {
        let isFieldValid = false; // Initialize isFieldValid to avoid pre-commit error

        // Add radio button validation logic
        if (field.type === "radio") {
            // Validate radio buttons in this section
            isFieldValid = validateRadioButtons(field.name, section);
        } else if (field.tagName === "SELECT" && field.multiple) {
            // Validate multi-select fields
            isFieldValid = validateMultiSelect(field);
        } else if (field.type === "file") {
            // Validate file input field
            isFieldValid = validateFileInput(field);
        } else if (field && field.value) {
            isFieldValid = field.value.trim() !== "";
        } else {
            // Validate non-radio fields
            isFieldValid = false;
        }

        const fieldName = field.getAttribute("name");

        if (fieldName && fieldName.includes("{9999}")) {
            return;
        }

        // Check for Total Land Area field and validate it
        if (field.id === "total_land_area") {
            isFieldValid = validateLandArea(field);
        }

        if (field.id === "number_of_livestock") {
            isFieldValid = validateLandArea(field);
        }

        // Apply 'is-invalid' class for non-radio fields
        if (field.type !== "radio" && field.type !== "file") {
            field.classList.toggle("is-invalid", !isFieldValid);
        }

        valid = valid && isFieldValid;

        // Additional UID and RID validation for 'id-section'

        if (sectionId === "id-section" && fieldName === "uid") {
            valid = valid && validateUID();
        }
        if (sectionId === "id-section" && fieldName === "rid") {
            valid = valid && validateRID();
        }
        if (sectionId === "land-information" && fieldName === "total_land_area") {
            valid = valid && validateLandArea();
        }
        if (sectionId === "livestock-information" && fieldName === "number_of_livestock") {
            valid = valid && validateLandArea();
        }
    });
    if (uidError.style.display === "block") {
        valid = false;
    }
    if (ridError.style.display === "block") {
        valid = false;
    }

    // Check for UID and RID error display
    if (uidError && uidError.style.display === "block") {
        valid = false;
    }
    if (ridError && ridError.style.display === "block") {
        valid = false;
    }

    return valid;
}

function showSection(sectionId, element, fromGroup = false) {
    // Val = validateSection(previousSection);
    var val = true;
    var isSectionValid = true;

    if (val) {
        if (fromGroup) {
            document.querySelectorAll(".section-container-group").forEach((section) => {
                section.style.display = "none";
            });
        } else {
            document.querySelectorAll(".section-container").forEach((section) => {
                if (
                    sectionId === "family-members" ||
                    sectionId === "location-details" ||
                    sectionId === "family-member-template"
                ) {
                    const locationDetailsSection = document.getElementById("location-details");

                    if (locationDetailsSection) {
                        isSectionValid = validateSection("location-details");

                        if (!isSectionValid) {
                            const farmerDetailSection = document.getElementById("family-members");
                            farmerDetailSection.style.display = "none";

                            return;
                        }
                    }

                    section.style.display = "none";
                } else {
                    const locationDetailsSection = document.getElementById("location-details");

                    if (locationDetailsSection) {
                        isSectionValid = validateSection("location-details");

                        if (!isSectionValid) {
                            const farmerDetailSection = document.getElementById("family-members");
                            farmerDetailSection.style.display = "none";
                            return;
                        }
                    }

                    section.style.display = "none";
                    const farmerDetailSection = document.getElementById("farmer-details");
                    if (farmerDetailSection) {
                        farmerDetailSection.style.display = "block";
                    }
                }
            });
        }

        if (isSectionValid) {
            document.getElementById(sectionId).style.display = "block";
            // PreviousSection = sectionId;
            // If (!fromGroup) {
            document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
                link.classList.remove("active");
            });
            // }
            if (element) {
                element.classList.add("active");
            }
        }
    }
}
// eslint-disable-next-line no-unused-vars
// function showNextSection(nextSectionId, currentSectionId, fromGroup = false) {
//     var val = validateSection(currentSectionId);

//     if (val) {
//         var activeLink = document.querySelector(".sidebar .nav-link.active");
//         var nextLink = activeLink.parentElement.nextElementSibling.querySelector(".nav-link");
//         if (nextLink) {
//             nextLink.classList.remove("disabled");
//             showSection(nextSectionId, nextLink, fromGroup);
//         }
//     }
// }

function showNextSection(nextSectionId, currentSectionId, fromGroup = false) {
    const isSectionValid = validateSection(currentSectionId);

    if (isSectionValid) {
        const activeLink = document.querySelector(".sidebar .nav-link.active");
        const nextLink = activeLink.parentElement.nextElementSibling.querySelector(".nav-link");
        if (nextLink) {
            nextLink.classList.remove("disabled");
            showSection(nextSectionId, nextLink, fromGroup); // Move to next section if valid
        }
    }
}

// Call resetFormFields() when opening the modal
$("#farmerDetailModal").on("show.bs.modal", function () {
    resetFormFields();
});

function toggleFieldBasedOnSelect(
    fieldIdToToggle,
    value,
    toggleValue = "Yes",
    otherInputIdToClear,
    selectionFieldIdToClear,
    containerId,
    containerId2
) {
    const shouldShowField = value === toggleValue;

    const selectionFieldToClear = document.getElementById(selectionFieldIdToClear);
    const otherInputToClear = document.getElementById(otherInputIdToClear);
    const container_div = document.getElementById(containerId);
    const container_div2 = document.getElementById(containerId2);

    if (!shouldShowField) {
        console.log("when false");
        if (selectionFieldToClear) {
            selectionFieldToClear.selectedIndex = 0;
        } else {
            console.warn(`Warning: Invalid selection field ID provided: ${selectionFieldIdToClear}`);
        }

        if (otherInputToClear) {
            otherInputToClear.value = "";
            if (container_div) {
                container_div.style.display = shouldShowField ? "block" : "none";
            }

            if (container_div2) {
                container_div2.style.display = shouldShowField ? "block" : "none";
            }
        } else {
            console.warn(`Warning: Invalid other input ID provided: ${otherInputIdToClear}`);
        }
    }

    const fieldToToggle = document.getElementById(fieldIdToToggle);

    console.log("fieldtotoggle, this is container_div, containerdiv2");
    console.log(container_div);

    if (fieldToToggle) {
        fieldToToggle.style.display = shouldShowField ? "block" : "none";
    } else {
        console.error(`Error: Invalid field ID provided: ${fieldIdToToggle}`);
    }
}

function getInitialSelection(selectId) {
    const selectElement = document.getElementById(selectId);
    return selectElement ? selectElement.options[selectElement.selectedIndex].text : null;
}

document.addEventListener("DOMContentLoaded", function () {
    const selectHandlers = [
        {
            selectId: "is_member_of_primary_coop",
            fieldIdsToToggle: "primary-coop-field",
            otherInputIdToClear: "other_primary_coop",
            selectionFieldIdToClear: "name_of_primary_coop",
            containerId: "otherModalPrimaryCoopField",
            containerId2: "otherPrimaryCoopField",
        },

        {
            selectId: "is_member_of_coop_union",
            fieldIdsToToggle: "coop-union-field",
            otherInputIdToClear: "other_coop_union",
            selectionFieldIdToClear: "name_of_coop_union",
            containerId: "otherModalCoopUnionField",
            containerId2: "otherCoopUnionField",
        },

        {selectId: "in_farmer_cluster", fieldIdsToToggle: "primary-commodity-field"},
        {selectId: "in_farmer_cluster", fieldIdsToToggle: "role-in-cluster-field"},
    ];

    selectHandlers.forEach((handler) => {
        const selectElement = document.getElementById(handler.selectId);
        if (selectElement) {
            selectElement.addEventListener("change", function () {
                const selectedOption = selectElement.options[selectElement.selectedIndex];
                toggleFieldBasedOnSelect(
                    handler.fieldIdsToToggle,
                    selectedOption.text,
                    "Yes",
                    handler.otherInputIdToClear,
                    handler.selectionFieldIdToClear,
                    handler.containerId,
                    handler.containerId2
                );
            });

            selectHandlers.forEach((handler) => {
                const initialSelection = getInitialSelection(handler.selectId);
                if (initialSelection) {
                    toggleFieldBasedOnSelect(
                        handler.fieldIdsToToggle,
                        initialSelection,
                        "Yes",
                        handler.otherInputIdToClear,
                        handler.selectionFieldIdToClear,
                        handler.containerId,
                        handler.containerId2
                    );
                }
            });
        } else {
            console.error(`Error: Select element not found for ID: ${handler.selectId}`);
        }
    });
});
