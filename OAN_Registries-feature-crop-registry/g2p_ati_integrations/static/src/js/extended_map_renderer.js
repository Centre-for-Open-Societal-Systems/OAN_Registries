/** @odoo-module */
import {G2PLeafletMapRenderer} from "@g2p_leaflet_map/g2p_lmap_renderer";
import {useRef} from "@odoo/owl";

export class CustomLeafletMapRenderer extends G2PLeafletMapRenderer {
    setup() {
        console.log("new controller running");
        super.setup();
        this.root = useRef("map");
    }

    onMounted() {
        super.onMounted(); // Call original onMounted

        if (!this.map) {
            console.error("Map is not initialized.");
            return;
        }

        if (this.props.polygonCoords?.length) {
            this.props.polygonCoords.forEach((land, index) => {
                const polygon = L.polygon(land.polygon_data, {
                    color: "blue",
                    fillColor: "blue",
                    fillOpacity: 0.5,
                }).addTo(this.map);

                // **Add Click Event for Popup**
                polygon.on("click", (e) => {
                    const popupContent = `
                        <b>Land Information</b><br>
                        <b>Owner:</b> ${land.ownership_type || "Unknown"}<br>
                        <b>Size:</b> ${land.total_land_area || "N/A"} hectares<br>
                    `;
                    L.popup().setLatLng(e.latlng).setContent(popupContent).openOn(this.map);
                });
            });
        }
    }
}
