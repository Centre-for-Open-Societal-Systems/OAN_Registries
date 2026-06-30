$(document).ready(function () {
    function expandSection(sectionId) {
        var consentSection = document.getElementById(sectionId);
        consentSection.classList.add("show");
    }

    window.customvalidateFormGroup = function (isCreateForm) {
        const locationDetailsSection = document.querySelector("#location-details");
        const requiredFields = locationDetailsSection.querySelectorAll("[required]");
        var valid = true;
        for (let i = 0; i < requiredFields.length; i++) {
            const field = requiredFields[i];
            const isFieldValid = field.value.trim();

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
            this.validateFormGroup(isCreateForm);
        }
    };
});

let memberCount = 0;

// eslint-disable-next-line no-unused-vars
function addFamilyMember() {
    const givenName = document.getElementById("mamber_given_name").value;
    const fathersName = document.getElementById("member_fathers_name").value;
    const grandfathersName = document.getElementById("member_grandfathers_name").value;
    const birthdate = document.getElementById("member-birthdate").value;
    const gender = document.querySelector('input[name="gender"]:checked').value;

    if (givenName && fathersName && grandfathersName && birthdate && gender) {
        const table = document.getElementById("familylist").getElementsByTagName("tbody")[0];

        const newRow = table.insertRow();
        newRow.innerHTML = `
            <td><input type="hidden" name="member_given_name_${memberCount}" value="${givenName}">${givenName}</td>
            <td><input type="hidden" name="member_fathers_name_${memberCount}" value="${fathersName}">${fathersName}</td>
            <td><input type="hidden" name="member_grandfathers_name_${memberCount}" value="${grandfathersName}">${grandfathersName}</td>
            <td><input type="hidden" name="member_birthdate_${memberCount}" value="${birthdate}">${birthdate}</td>
            <td><input type="hidden" name="gender_${memberCount}" value="${gender}">${gender}</td>
            <td><button type="button" class="btn btn-outline-secondary btn-sm" onclick="deleteMember(this)"><i class="fas fa-trash-alt"></i></button></td>
        `;

        memberCount++;

        // Clear the form fields
        document.getElementById("mamber_given_name").value = "";
        document.getElementById("member_fathers_name").value = "";
        document.getElementById("member_grandfathers_name").value = "";
        document.getElementById("member-birthdate").value = "";
        document.querySelectorAll('input[name="gender"]').forEach((el) => {
            el.checked = false;
        });

        $("#familyMemberModal").modal("hide");
    } else {
    }
}

// Function deleteMember(button) {
//     const memberId = $(button).attr("store");
//     var groupId = $("input[name='group_id']").val();

//     console.log("memberID is ", memberId);

//     if (confirm("Are you sure you want to delete this family member?")) {
//         $.ajax({
//             url: "/serviceprovider/member/delete/",
//             type: "POST",
//             data: { member_id: memberId, group_id: groupId },
//             success: function (data) {
//                 data = JSON.parse(data);
//                 if (data.success) {

//                     console.log("in the the the here")
//                     const row = $(button).closest("tr");
//                     row.remove();
//                     alert(data.message);
//                 }

//                 else {
//                     console.log("Delete failed:", data);
//                     alert("Error: " + (data.error));
//                 }
//             },
//             error: function (jqXHR, textStatus, errorThrown) {
//                 console.error("Error:", textStatus, errorThrown);
//                 alert("An error occurred while deleting the family member: " + errorThrown);
//             },
//         });
//     }
// }

const farmerCount = 0;

// eslint-disable-next-line no-unused-vars
function addFarmerMember() {
    const givenName = document.getElementById("mamber_given_name").value;
    const fathersName = document.getElementById("member_fathers_name").value;
    const grandfathersName = document.getElementById("member_grandfathers_name").value;
    const birthdate = document.getElementById("member-birthdate").value;
    const gender = document.querySelector('input[name="gender"]:checked').value;

    if (givenName && fathersName && grandfathersName && birthdate && gender) {
        const table = document.getElementById("familylist").getElementsByTagName("tbody")[0];

        const newRow = table.insertRow();
        newRow.innerHTML = `
            <td><input type="hidden" name="member_given_name_${farmerCount}" value="${givenName}">${givenName}</td>
            <td><input type="hidden" name="member_fathers_name_${farmerCount}" value="${fathersName}">${fathersName}</td>
            <td><input type="hidden" name="member_grandfathers_name_${farmerCount}" value="${grandfathersName}">${grandfathersName}</td>
            <td><input type="hidden" name="member_birthdate_${farmerCount}" value="${birthdate}">${birthdate}</td>
            <td><input type="hidden" name="gender_${farmerCount}" value="${gender}">${gender}</td>
            <td><button type="button" class="btn btn-outline-secondary btn-sm" onclick="deleteMember(this)"><i class="fas fa-trash-alt"></i></button></td>
        `;

        memberCount++;

        // Clear the form fields
        document.getElementById("mamber_given_name").value = "";
        document.getElementById("member_fathers_name").value = "";
        document.getElementById("member_grandfathers_name").value = "";
        document.getElementById("member-birthdate").value = "";
        document.querySelectorAll('input[name="gender"]').forEach((el) => {
            el.checked = false;
        });

        $("#familyMemberModal").modal("hide");
    } else {
        console.log("Please fill all the required fields");
    }
}

$(document).on("click", "#hh_member_update", function () {
    var memberId = $(this).attr("store");
    var group_id = $("input[name='group_id']").val();
    var modal = $("#editFamilyMemberModal");
    $.ajax({
        url: "/serviceprovider/member/update/",
        method: "POST",
        data: {
            member_id: memberId,
            group_id: group_id,
        },
        dataType: "json",
        success: function (response) {
            modal.find("#edit_given_name").val(response.given_name);
            modal.find("#edit_fathers_name").val(response.family_name);
            modal.find("#edit_grandfathers_name").val(response.gf_name_eng);
            modal.find("#edit_birthdate").val(response.dob);
            if (response.gender === "male") {
                modal.find("#edit_gender_male").prop("checked", true);
            } else if (response.gender === "female") {
                modal.find("#edit_gender_female").prop("checked", true);
            }

            modal.find("#edit_relation_with_hh_selection").val(response.kind);

            var ele = document.getElementById("update-member-btn");
            ele.setAttribute("store", memberId);
            // Ele.setAttribute("id", "update-member-btn");

            // $("#update_member").replaceWith(
            //     '<div id="update-member-btn" store="' +
            //         memberId +
            //         '" class="btn btn-primary create-new">Update</div>'
            // );

            modal.modal("show");
            // $("#update_member").replaceWith(
            //                 '<div id="update-member-btn" store="' +
            //                     memberId +
            //                     '" class="btn btn-primary create-new">Updatee</div>'
            //             );
        },
        error: function (error) {
            console.error("Ajax request failed");
            console.error("Error:", error);
        },
    });
});

$(document).on("click", "#update-member-btn", function () {
    var ele = document.getElementById("update-member-btn");
    var modal = $("#editFamilyMemberModal");
    var memberId = ele.getAttribute("store");

    var group_id = $("input[name='group_id']").val();
    var relationship = $("select[name='relation_with_household_head']").val();

    var data = {
        group_id: group_id,
        member_id: memberId,
        given_name: modal.find("#edit_given_name").val(),
        family_name: modal.find("#edit_fathers_name").val(),
        gf_name_eng: modal.find("#edit_grandfathers_name").val(),
        birthdate: modal.find("#edit_birthdate").val(),
        gender: modal.find("input[name='gender']:checked").val(),
        Relationship: relationship,
    };

    $.ajax({
        url: "/serviceprovider/family_member/update/submit/",
        method: "POST",
        data: data,
        dataType: "json",
        success: function (response) {
            if (response.member_list) {
                // Update the table with the new member list
                var tableBody = $("#familylist tbody");
                tableBody.empty();
                response.member_list.forEach(function (member, index) {
                    var serialNumber = index + 1;
                    var newRowHtml = `
                        <tr>
                            <td>${serialNumber}</td>
                            <td>${member.name}</td>
                            <td>${member.age}</td>
                            <td>${member.gender}</td>
                            <td>${member.kind}</td>
                            <td>
                                <button type="button" class="btn btn-icon rounded-0" id="hh_member_update" store="${member.id}" title="Edit">
                                    <i class="fa fa-pencil"></i>
                                </button>

                            </td>
                        </tr>
                    `;
                    tableBody.append(newRowHtml);
                });

                $("#editFamilyMemberModal").modal("hide");
            } else {
                showErrorModal("Failed to edit family member!");
                console.error("Failed to edit family member");
            }
        },

        error: function (error) {
            console.error("Ajax request failed");
            showErrorModal(error);

            console.error("Error:", error);
        },
    });
});

function showSuccessModal(message) {
    const imgElement = document.getElementById("successModal").querySelector(".popup_img");
    const h4Element = document.getElementById("successModal").querySelector("h4");
    const msgElement = document.getElementById("successModal").querySelector(".popup_msg");

    imgElement.src = "/g2p_ati_service_provider_portal/static/src/img/ok.png";
    h4Element.textContent = "Success!";
    msgElement.textContent = message.replace(/^"|"$/g, "");

    $("#successModal").modal("show");
}

function showErrorModal(message) {
    const imgElement = document.getElementById("successModal").querySelector(".popup_img");
    const h4Element = document.getElementById("successModal").querySelector("h4");
    const msgElement = document.getElementById("successModal").querySelector(".popup_msg");

    imgElement.src = "/g2p_ati_service_provider_portal/static/src/img/no.png";
    h4Element.textContent = "Error";
    msgElement.textContent = message.replace(/^"|"$/g, "");

    $("#successModal").modal("show");
}

$(document).on("click", "#family_member_submit", function () {
    $(this).prop("disabled", true);

    var group_id = $("input[name='group_id']").val();
    var given_name = $("#mamber_given_name").val();
    var family_name = $("#member_fathers_name").val();
    var gf_name_eng = $("#member_grandfathers_name").val();
    var birthdate = $("#member-birthdate").val();
    var gender = $("input[name='gender']:checked").val();
    var relationship = $("select[name='relation_with_household_head_add']").val();

    // Proceed with the AJAX request if the form is valid
    $.ajax({
        url: "/serviceprovider/family_member/add/submit/",
        method: "POST",
        data: {
            group_id: group_id,
            given_name: given_name,
            family_name: family_name,
            gf_name_eng: gf_name_eng,
            birthdate: birthdate,
            gender: gender,
            Relationship: relationship,
        },
        dataType: "json",
        success: function (response) {
            console.log("Response:", response);

            if (response.member_list) {
                // eslint-disable-next-line no-undef
                resetFormFieldsMember();

                // Update the table with the new member list
                var tableBody = $("#familylist tbody");
                tableBody.empty();
                response.member_list.forEach(function (member, index) {
                    var serialNumber = index + 1;

                    var newRowHtml = `
                        <tr>
                            <td>${serialNumber}</td>
                            <td>${member.name}</td>
                            <td>${member.age}</td>
                            <td>${member.gender}</td>
                            <td>${member.kind}</td>
                            <td>
                                <button type="button" class="btn btn-icon rounded-0" id="hh_member_update" store="${member.id}" title="Edit">
                                    <i class="fa fa-pencil"></i>
                                </button>

                            </td>
                        </tr>
                    `;
                    tableBody.append(newRowHtml);
                });

                // Hide the modal after successful submission
                $("#familyMemberModal").modal("hide");

                $("#family_member_submit").prop("disabled", false);
                showSuccessModal("Family member added successfully!");
            } else {
                console.error("Failed to add family member");
                $("#family_member_submit").prop("disabled", false);
                showErrorModal("Failed to add family member!");
            }
        },
        error: function (error) {
            console.error("request failed");
            console.error("Error:", error);
            $("#family_member_submit").prop("disabled", false);
            showErrorModal("Request Failed");
        },
    });
});

// eslint-disable-next-line no-unused-vars
function showNextModal(nextSectionId, currentSectionId) {
    // eslint-disable-next-line no-undef
    var val = validateSection("location-details");

    val = true;

    if (val) {
        var activeLink = document.querySelector(".sidebar .nav-link.active");

        var nextLink = activeLink.parentElement.nextElementSibling.querySelector(".nav-link");
        if (nextLink) {
            nextLink.classList.remove("disabled");
            nextLink = document.getElementById(currentSectionId + "-link");
            // eslint-disable-next-line no-undef
            showSection(nextSectionId, nextLink, true);
        }
    }
}

// eslint-disable-next-line no-unused-vars
function showModalSection(nextSectionId, currentSectionId, direction) {
    // eslint-disable-next-line no-undef
    var val = validateSection(currentSectionId);
    if (direction === "prev") {
        var val = true;
    }

    // Val = true;
    // val = true;

    if (val && (currentSectionId || direction)) {
        var activeLink = document.querySelector(".sidebar .nav-link.active");

        // eslint-disable-next-line no-undef
        showSection(nextSectionId, activeLink, true);
    }
}
