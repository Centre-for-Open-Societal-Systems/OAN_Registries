// eslint-disable-next-line no-unused-vars
function deleteLand(button) {
    const section = button.closest(".land-section-wrapper");
    if (section) {
        section.remove();
    } else {
        console.error("Could not find the section to delete.");
    }
}
// eslint-disable-next-line no-unused-vars
function deleteCrop(button) {
    const section = button.closest(".crop-section-wrapper");
    if (section) {
        section.remove();
    } else {
        console.error("Could not find the section to delete.");
    }
}
// eslint-disable-next-line no-unused-vars
function deleteLivestock(button) {
    const section = button.closest(".livestock-section-wrapper");
    if (section) {
        section.remove();
    } else {
        console.error("Could not find the section to delete.");
    }
}
// eslint-disable-next-line no-unused-vars
function addCropInfo(button) {
    const cropContainer = document.getElementById("crop-section-content");
    const toBeCloned = document.getElementById("crop-hidden-template");
    var newNode = toBeCloned.cloneNode(true);
    newNode.removeAttribute("style");
    cropContainer.appendChild(newNode);

    $(newNode).find(".selectpicker").selectpicker();
}
