/** @odoo-module alias=web.window.title **/

import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

patch(WebClient.prototype, {
    setup() {
        super.setup();
        // Replaces the default "Odoo" part with "ATI"
        // The full window title will become "ATI - [Current Page/Action]" instead of "Odoo - [Current Page/Action]"
        this.title.setParts({ zopenerp: "ATI" });
    }
});
