/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { FloatField, floatField } from "@web/views/fields/float/float_field";

export class G2PTrimFloatField extends FloatField {
    get formattedValue() {
        if (
            !this.props.formatNumber ||
            (this.props.inputType === "number" && !this.props.readonly && this.value)
        ) {
            return this.value;
        }
        if (this.props.humanReadable && !this.state.hasFocus) {
            return formatFloat(this.value, {
                digits: this.digits,
                humanReadable: true,
                decimals: this.props.decimals,
                trailingZeros: false,
            });
        }
        return formatFloat(this.value, {
            digits: this.digits,
            humanReadable: false,
            trailingZeros: false,
        });
    }
}

registry.category("fields").add("g2p_trim_float", {
    ...floatField,
    component: G2PTrimFloatField,
});
