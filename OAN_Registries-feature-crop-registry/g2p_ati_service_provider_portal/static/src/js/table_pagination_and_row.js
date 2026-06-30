const alltable = document.getElementById("newreimbursements");
const allheadercells = alltable.querySelectorAll("th");
const allRows = Array.from(alltable.querySelectorAll("tbody tr"));
const tbody = alltable.getElementsByTagName("tbody");
const totalRow = tbody[0].children.length;
const itemsPerPage = 12;
let currentPage = 1;

const searchResultCount = document.getElementById("search-result-count");
const searchInputText = document.getElementById("search-text");
const searchClearText = document.getElementById("search-text-clear");

// Const selectedOption = selectionRegion.options[selectionRegion.selectedIndex];
// const selectedOptionText = selectedOption.textContent || selectedOption.innerText;
const SelectionRegion = document.getElementById("region_selection");
const SelectionZon = document.getElementById("zone_selection");
const SelectionWoreda = document.getElementById("woreda_selection");
const SelectionKebele = document.getElementById("kebele_selection");

const SelectionRegionGroup = document.getElementById("region_selection_group");
const SelectionZonGroup = document.getElementById("zone_selection_group");
const SelectionWoredaGroup = document.getElementById("woreda_selection_group");
const SelectionKebeleGroup = document.getElementById("kebele_selection_group");

const SelectionRegionGroupModal = document.getElementById("region_selection_group_modal");
const SelectionZonGroupModal = document.getElementById("zone_selection_group_modal");
const SelectionWoredaGroupModal = document.getElementById("woreda_selection_group_modal");
const SelectionKebeleGroupModal = document.getElementById("kebele_selection_group_modal");

const SelectionRegionModal = document.getElementById("region_selection_modal");
const SelectionZonModal = document.getElementById("zone_selection_modal");
const SelectionWoredaModal = document.getElementById("woreda_selection_modal");
const SelectionKebeleModal = document.getElementById("kebele_selection_modal");

searchClearText.style.display = "none";

function addTableSrNo() {
    for (let i = 0; i < totalRow; i++) {
        tbody[0].children[i].firstElementChild.innerText = i + 1;
    }
}

addTableSrNo();
let filteredRows = [];
function showPage(page) {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const rows = filteredRows.slice(startIndex, endIndex);
    // Hide all rows
    allRows.forEach((row) => (row.style.display = "none"));
    // Show rows for current page
    rows.forEach((row) => (row.style.display = ""));
}
function updatePaginationButtons() {
    const pageButtonsContainer = document.getElementById("page-buttons");
    const buttons = pageButtonsContainer.querySelectorAll("button");
    buttons.forEach((button) => {
        button.classList.remove("active");
        if (Number(button.textContent) === currentPage) {
            button.classList.add("active");
        }
    });

    const prevButton = pageButtonsContainer.querySelector("button:first-child");
    const nextButton = pageButtonsContainer.querySelector(".next-button");

    prevButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage === Math.ceil(filteredRows.length / itemsPerPage);
}

function applySearchFilter(searchValue) {
    filteredRows = allRows.filter((row) => {
        const cellValue1 = row.cells[1].innerText.toLowerCase();
        const cellValue2 = row.cells[2].innerText.toLowerCase();
        const cellValue3 = row.cells[3].innerText.toLowerCase();
        const cellValue4 = row.cells[4].innerText.toLowerCase();
        const cellValue5 = row.cells[5].innerText.toLowerCase();
        const cellValue6 = row.cells[6].innerText.toLowerCase();

        return (
            cellValue1.includes(searchValue) ||
            cellValue2.includes(searchValue) ||
            cellValue3.includes(searchValue) ||
            cellValue4.includes(searchValue) ||
            cellValue5.includes(searchValue) ||
            cellValue6.includes(searchValue)
        );
    });
}

function applySelectionFilter(selectionValue, isGroup) {
    filteredRows = allRows.filter((row) => {
        // Assuming each row has a data attribute or a cell with the selection value
        var cellValue2 = null;

        if (isGroup) {
            cellValue2 = row.cells[3].innerText.trim().replace(/\s/g, "");
        } else {
            cellValue2 = row.cells[2].innerText.trim().replace(/\s/g, "");
        }

        const selectedText = selectionValue.options[selectionValue.selectedIndex].text
            .trim()
            .replace(/\s/g, "");

        return cellValue2 === selectedText || selectedText === "Region";
    });
}

function applySelectionFilterZone(isGroup, modal = false) {
    filteredRows = allRows.filter((row) => {
        var cellValue2 = null;
        var text_i = null;

        if (isGroup) {
            cellValue2 = row.cells[4].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionZonGroup.options[SelectionZonGroup.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }

            if (modal) {
                text_i = SelectionZonGroupModal.options[SelectionZonGroupModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        } else {
            cellValue2 = row.cells[3].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionZon.options[SelectionZon.selectedIndex].text.trim().replace(/\s/g, "");
            }

            if (modal) {
                text_i = SelectionZonModal.options[SelectionZonModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        }

        // Const cellValue2 = row.cells[3].value
        // return cellValue2 === selectionValue;

        return cellValue2 === text_i || text_i === "Zone";
    });
}

function applySelectionFilterWoreda(selectionValue, isGroup, modal = false) {
    filteredRows = allRows.filter((row) => {
        // Const cellValue2 = row.cells[4].innerText.trim().replace(/\s/g, "");
        // const selectedText = selectionValue.options[selectionValue.selectedIndex].text;

        var cellValue2 = null;
        var text_i = null;
        if (isGroup) {
            cellValue2 = row.cells[5].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionWoredaGroup.options[SelectionWoredaGroup.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
            if (modal) {
                text_i = SelectionWoredaGroupModal.options[SelectionWoredaGroupModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        } else {
            cellValue2 = row.cells[4].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionWoreda.options[SelectionWoreda.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }

            if (modal) {
                text_i = SelectionWoredaModal.options[SelectionWoredaModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        }

        return cellValue2 === text_i || text_i === "Woreda";
    });
}

function applySelectionFilterKebele(selectionValue, isGroup, modal = false) {
    filteredRows = allRows.filter((row) => {
        var cellValue2 = null;
        var text_i = null;
        if (isGroup) {
            cellValue2 = row.cells[6].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionKebeleGroup.options[SelectionKebeleGroup.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }

            if (modal) {
                text_i = SelectionKebeleGroupModal.options[SelectionKebeleGroupModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        } else {
            cellValue2 = row.cells[5].innerText.trim().replace(/\s/g, "");

            if (!modal) {
                text_i = SelectionKebele.options[SelectionKebele.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }

            if (modal) {
                text_i = SelectionKebeleModal.options[SelectionKebeleModal.selectedIndex].text
                    .trim()
                    .replace(/\s/g, "");
            }
        }

        return cellValue2 === text_i || text_i === "Kebele";
    });
}

function applySelectionFilterAny(selectionValue, isGroup, selectElement, column_name) {
    filteredRows = allRows.filter((row) => {
        var cellValue2 = null;
        var text_i = null;
        if (isGroup) {
            cellValue2 = row.cells[6].innerText.trim().replace(/\s/g, "");
            text_i = selectElement.options[selectElement.selectedIndex].text.trim().replace(/\s/g, "");
        } else {
            cellValue2 = row.cells[5].innerText.trim().replace(/\s/g, "");
            text_i = selectElement.options[selectElement.selectedIndex].text.trim().replace(/\s/g, "");
        }

        return cellValue2 === text_i || text_i === column_name;
    });
}

function createPageButton(pageNumber) {
    const button = document.createElement("button");
    button.textContent = pageNumber;
    if (pageNumber === currentPage) {
        button.classList.add("active");
    }
    button.addEventListener("click", function () {
        currentPage = pageNumber;
        showPage(currentPage);
        // eslint-disable-next-line no-use-before-define
        renderPageButtons();
    });
    return button;
}

// eslint-disable-next-line no-use-before-define
function renderPageButtons() {
    const totalPages = Math.ceil(filteredRows.length / itemsPerPage);
    const pageButtonsContainer = document.getElementById("page-buttons");
    pageButtonsContainer.innerHTML = "";

    // Add previous page button
    const prevButton = document.createElement("button");
    prevButton.innerHTML = '<i class="fa fa-angle-left"></i>';
    prevButton.addEventListener("click", function () {
        if (currentPage > 1) {
            currentPage--;
            showPage(currentPage);
            renderPageButtons();
        }
    });
    pageButtonsContainer.appendChild(prevButton);

    // Add page buttons with ellipsis logic
    if (totalPages <= 5) {
        // If total pages are 5 or less, show all pages
        for (let i = 1; i <= totalPages; i++) {
            const button = createPageButton(i);
            pageButtonsContainer.appendChild(button);
        }
    } else {
        // Show first page, ellipsis, current page range, ellipsis, last page
        if (currentPage > 3) {
            const firstButton = createPageButton(1);
            pageButtonsContainer.appendChild(firstButton);

            const ellipsis1 = document.createElement("span");
            ellipsis1.classList.add("ellipsis");
            ellipsis1.textContent = "...";
            pageButtonsContainer.appendChild(ellipsis1);
        }

        // Show current page and nearby pages
        for (let i = Math.max(1, currentPage - 1); i <= Math.min(totalPages, currentPage + 1); i++) {
            const button = createPageButton(i);
            pageButtonsContainer.appendChild(button);
        }

        if (currentPage < totalPages - 2) {
            const ellipsis2 = document.createElement("span");
            ellipsis2.classList.add("ellipsis");
            ellipsis2.textContent = "...";
            pageButtonsContainer.appendChild(ellipsis2);

            const lastButton = createPageButton(totalPages);
            pageButtonsContainer.appendChild(lastButton);
        }
    }

    // Add next page button
    const nextButton = document.createElement("button");
    nextButton.innerHTML = '<i class="fa fa-angle-right"></i>';
    nextButton.classList.add("next-button");
    nextButton.addEventListener("click", function () {
        if (currentPage < totalPages) {
            currentPage++;
            showPage(currentPage);
            renderPageButtons();
        }
    });
    pageButtonsContainer.appendChild(nextButton);

    updatePaginationButtons();
}

function compareCellValues(rowA, rowB, columnIndex) {
    const cellA = rowA.cells[columnIndex].innerText.trim();
    const cellB = rowB.cells[columnIndex].innerText.trim();

    // Detect if the column contains date values using regex or Date parsing
    const isDateColumn = !isNaN(Date.parse(cellA)) && !isNaN(Date.parse(cellB));

    if (isDateColumn) {
        // If date column, compare dates
        const dateA = new Date(cellA);
        const dateB = new Date(cellB);
        return dateA - dateB;
    }
    // Otherwise, perform normal string or number comparison
    if (!isNaN(cellA) && !isNaN(cellB)) {
        return Number(cellA) - Number(cellB);
    }
    return cellA.localeCompare(cellB);
}

allheadercells.forEach(function (th) {
    // Default sort order
    let sortOrder = "asc";
    th.addEventListener("click", function () {
        const columnIndex = th.cellIndex;
        allRows.sort(function (a, b) {
            let comparison = compareCellValues(a, b, columnIndex);

            // Reverse comparison if descending order is selected
            if (sortOrder === "desc") {
                comparison *= -1;
            }
            return comparison;
        });

        // Toggle sort order for next click
        sortOrder = sortOrder === "asc" ? "desc" : "asc";

        // Append sorted rows back to the table
        allRows.forEach((row) => {
            alltable.tBodies[0].appendChild(row);
        });

        // Update serial numbers
        allRows.forEach((row, index) => {
            const firstCell = row.cells[0];
            firstCell.innerText = index + 1;
        });

        // Reset pagination
        currentPage = 1;
        showPage(currentPage);
        renderPageButtons();
    });
});

function updateOptions(url, data, targetSelectId, defaultOptionText) {
    return new Promise((resolve, reject) => {
        $.ajax({
            url: url,
            method: "POST",
            dataType: "json",
            data: data,
            success: function (options) {
                const selectElement = document.getElementById(targetSelectId);
                selectElement.innerHTML = "";
                const defaultOption = document.createElement("option");
                defaultOption.value = "";
                defaultOption.textContent = defaultOptionText;
                selectElement.appendChild(defaultOption);

                options.forEach((option) => {
                    const opt = document.createElement("option");
                    opt.value = option.id;
                    opt.textContent = option.name;
                    selectElement.appendChild(opt);
                });

                // Resolve the promise when the AJAX call is successful
                resolve();
            },
            error: function (error) {
                console.error("Error fetching options:", error);
                // Reject the promise in case of an error
                reject(error);
            },
        });
    });
}

function resetFilters() {
    filteredRows = allRows;
    currentPage = 1;
    showPage(currentPage);
    renderPageButtons();
    searchResultCount.textContent = "";
}

function getSelectionValues(isGroup, modal = false) {
    if (!modal) {
        return {
            SelectionRegionValue: isGroup ? SelectionRegionGroup : SelectionRegion,
            SelectionZonValue: isGroup ? SelectionZonGroup?.value : SelectionZon?.value,
            SelectionWoredaValue: isGroup ? SelectionWoredaGroup?.value : SelectionWoreda?.value,
            SelectionKebeleValue: isGroup ? SelectionKebeleGroup?.value : SelectionKebele?.value,
        };
    }
    return {
        SelectionRegionValue: isGroup ? SelectionRegionGroupModal : SelectionRegionModal,
        SelectionZonValue: isGroup ? SelectionZonGroupModal?.value : SelectionZonModal?.value,
        SelectionWoredaValue: isGroup ? SelectionWoredaGroupModal?.value : SelectionWoredaModal?.value,
        SelectionKebeleValue: isGroup ? SelectionKebeleGroupModal?.value : SelectionKebeleModal?.value,
    };
}

function handleSearch(isGroup = true, modal = false) {
    var {SelectionRegionValue, SelectionZonValue, SelectionWoredaValue, SelectionKebeleValue} =
        getSelectionValues(isGroup, modal);
    var searchValue = searchInputText.value.trim().toLowerCase();
    filteredRows = allRows;

    function applyFilters() {
        if (SelectionRegionValue?.value.trim()) {
            applySelectionFilter(SelectionRegionValue, isGroup, (modal = modal));
        }
        if (SelectionZonValue?.trim()) {
            applySelectionFilterZone(isGroup, (modal = modal));
        }
        if (SelectionWoredaValue?.trim()) {
            applySelectionFilterWoreda(SelectionWoredaValue, isGroup, (modal = modal));
        }
        if (SelectionKebeleValue?.trim()) {
            applySelectionFilterKebele(SelectionKebeleValue, isGroup, (modal = modal));
        }
        if (searchValue) {
            applySearchFilter(searchValue, isGroup);
        }
    }

    if (
        searchValue ||
        SelectionRegionValue?.value.trim() ||
        SelectionZonValue?.trim() ||
        SelectionWoredaValue?.trim() ||
        SelectionKebeleValue?.trim()
    ) {
        applyFilters();
        currentPage = 1;
        showPage(currentPage);
        renderPageButtons();
        searchResultCount.textContent = `Search found ${filteredRows.length} result(s)`;
    } else {
        resetFilters();
    }

    searchClearText.style.display = searchValue ? "block" : "none";
}

searchInputText.addEventListener("input", handleSearch);

SelectionRegion?.addEventListener("input", function () {
    const regionId = this.value;
    // Use Promise.all to wait for all updateOptions calls to complete
    Promise.all([
        updateOptions("/update_zone_options", {region_id: regionId}, "zone_selection", "Zone"),
        updateOptions("/update_woreda_options", {zone_id: null}, "woreda_selection", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection", "Kebele"),
    ])
        .then(() => {
            handleSearch(false);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionRegionGroup?.addEventListener("input", function () {
    const regionId = this.value;
    console.log("before region group call");

    Promise.all([
        updateOptions("/update_zone_options", {region_id: regionId}, "zone_selection_group", "Zone"),
        updateOptions("/update_woreda_options", {zone_id: null}, "woreda_selection_group", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_group", "Kebele"),
    ])
        .then(() => {
            handleSearch(true);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionRegionGroupModal?.addEventListener("input", function () {
    const regionId = this.value;
    console.log("before region group call");

    Promise.all([
        updateOptions("/update_zone_options", {region_id: regionId}, "zone_selection_group_modal", "Zone"),
        updateOptions("/update_woreda_options", {zone_id: null}, "woreda_selection_group_modal", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_group_modal", "Kebele"),
    ])
        .then(() => {
            handleSearch(true, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionRegionModal?.addEventListener("input", function () {
    const regionId = this.value;

    Promise.all([
        updateOptions("/update_zone_options", {region_id: regionId}, "zone_selection_modal", "Zone"),
        updateOptions("/update_woreda_options", {zone_id: null}, "woreda_selection_modal", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_modal", "Kebele"),
    ])
        .then(() => {
            handleSearch(false, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionZon?.addEventListener("input", function () {
    const zoneId = this.value;
    Promise.all([
        updateOptions("/update_woreda_options", {zone_id: zoneId}, "woreda_selection", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection", "Kebele"),
    ])
        .then(() => {
            handleSearch(false);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionZonGroup?.addEventListener("input", function () {
    const zoneId = this.value;
    Promise.all([
        updateOptions("/update_woreda_options", {zone_id: zoneId}, "woreda_selection_group", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_group", "Kebele"),
    ])
        .then(() => {
            handleSearch(true);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionZonGroupModal?.addEventListener("input", function () {
    const zoneId = this.value;
    Promise.all([
        updateOptions("/update_woreda_options", {zone_id: zoneId}, "woreda_selection_group_modal", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_group_modal", "Kebele"),
    ])
        .then(() => {
            handleSearch(true, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionZonModal?.addEventListener("input", function () {
    const zoneId = this.value;
    Promise.all([
        updateOptions("/update_woreda_options", {zone_id: zoneId}, "woreda_selection_modal", "Woreda"),
        updateOptions("/update_kebele_options", {woreda_id: null}, "kebele_selection_modal", "Kebele"),
    ])
        .then(() => {
            handleSearch(false, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionWoreda?.addEventListener("input", function () {
    const woredaId = this.value;
    Promise.all([
        updateOptions("/update_kebele_options", {woreda_id: woredaId}, "kebele_selection", "Kebele"),
    ])
        .then(() => {
            handleSearch(false);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionWoredaGroup?.addEventListener("input", function () {
    const woredaId = this.value;
    Promise.all([
        updateOptions("/update_kebele_options", {woreda_id: woredaId}, "kebele_selection_group", "Kebele"),
    ])
        .then(() => {
            handleSearch(true);
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionWoredaGroupModal?.addEventListener("input", function () {
    const woredaId = this.value;
    Promise.all([
        updateOptions(
            "/update_kebele_options",
            {woreda_id: woredaId},
            "kebele_selection_group_modal",
            "Kebele"
        ),
    ])
        .then(() => {
            handleSearch(true, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionWoredaModal?.addEventListener("input", function () {
    const woredaId = this.value;
    Promise.all([
        updateOptions("/update_kebele_options", {woreda_id: woredaId}, "kebele_selection_modal", "Kebele"),
    ])
        .then(() => {
            handleSearch(false, (modal = true));
        })
        .catch((error) => {
            console.error("Error in one of the updateOptions calls:", error);
        });
});

SelectionKebele?.addEventListener("input", function () {
    handleSearch(false);
});
SelectionKebeleGroup?.addEventListener("input", function () {
    handleSearch(true);
});
SelectionKebeleGroupModal?.addEventListener("input", function () {
    handleSearch(true, (modal = true));
});
SelectionKebeleModal?.addEventListener("input", function () {
    handleSearch(false, (modal = true));
});

// SelectionKebeleGroupModal?.addEventListener("change", handleSearch(true, modal=true));

searchClearText.addEventListener("click", function () {
    searchInputText.value = "";
    handleSearch();
});

document.addEventListener("click", function (event) {
    if (event.target !== searchInputText && event.target !== searchClearText) {
        searchClearText.style.display = searchInputText.value ? "block" : "none";
    }
});

// Initial setup
filteredRows = allRows;
showPage(currentPage);
renderPageButtons();
