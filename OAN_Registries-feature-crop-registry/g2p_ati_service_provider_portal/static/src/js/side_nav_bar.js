// Function toggleAccordionSection(header) {
// console.log("in here the side bar")

//     const contentWrapper = header.nextElementSibling;

//     // Toggle display of the content
//     if (contentWrapper.style.display === 'none') {
//         contentWrapper.style.display = 'block !important';
//     } else {
//         contentWrapper.style.display = 'none !important';
//     }
// }

// function toggleAccordionSection(header) {
//     const contentWrapper = header.nextElementSibling; // Get the next sibling, the content-wrapper
//     const contentHeight = contentWrapper.scrollHeight; // Get the total height of the content

//     // Check if the content is already expanded or collapsed
//     if (contentWrapper.style.maxHeight) {
//         // If maxHeight is set, reset it to collapse the content
//         contentWrapper.style.maxHeight = null;
//     } else {
//         // Set the max-height to the actual content height for expansion
//         contentWrapper.style.maxHeight = contentHeight + 'px';
//     }
// }

function toggleAccordionSection(header) {
    const contentWrapper = header.nextElementSibling; // Get the content wrapper (next sibling)

    // Check if the section is already active
    const isActive = header.classList.contains("accord-active");

    // Collapse all sections by setting maxHeight to null
    const allContentWrappers = document.querySelectorAll(".section-content-wrapper");
    const allHeaders = document.querySelectorAll(".section-header");

    allContentWrappers.forEach(function (content) {
        content.style.maxHeight = null;
    });

    allHeaders.forEach(function (otherHeader) {
        otherHeader.classList.remove("accord-active");
        otherHeader.style.setProperty("--triangle-display", "none");
    });

    if (!isActive) {
        // Expand the clicked section and add active class
        header.classList.add("accord-active");
        contentWrapper.style.maxHeight = contentWrapper.scrollHeight + "px";
        header.style.setProperty("--triangle-display", "block");
    }
}
