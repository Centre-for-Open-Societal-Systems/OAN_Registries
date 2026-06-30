/** @odoo-module **/

import {Component, onWillStart, onWillUpdateProps, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {ModelFieldSelector} from "@web/core/model_field_selector/model_field_selector";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

const EXCLUDED_TYPES = new Set(["binary", "html", "json", "properties", "properties_definition"]);
const IMAGE_FIELD_PREFIXES = ["avatar_", "image_"];
const EXCLUDED_PREFIXES = ["message_", "activity_", "website_"];
const EXCLUDED_NAMES = new Set([
    "__last_update",
    "active_lang_count",
    "active_test",
    "activity_exception_decoration",
    "activity_state",
    "activity_summary",
    "activity_type_icon",
    "commercial_partner_id",
    "create_date",
    "create_uid",
    "display_name",
    "id",
    "preview_partner_id",
    "preview_payload",
    "source_model_display",
    "source_path_display",
    "filter_model_display",
    "filter_path_display",
    "fallback_filter_model_display",
    "fallback_filter_path_display",
    "write_date",
    "write_uid",
]);
const RELATIONAL_TYPES = new Set(["many2one", "one2many", "many2many"]);
const MAX_RELATION_DEPTH = 4;

export class G2PFieldPathSelector extends Component {
    static template = "g2p_ati_websub.FieldPathSelector";
    static components = {ModelFieldSelector};
    static props = {
        ...standardFieldProps,
        purpose: {type: String, optional: true},
        sourceField: {type: String, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            available: true,
            ready: false,
            resModel: "res.partner",
            message: "",
        });
        onWillStart(() => this.loadSelectorContext(this.props));
        onWillUpdateProps((nextProps) => this.loadSelectorContext(nextProps));
    }

    get sourcePath() {
        return this.props.record.data[this.props.sourceField] || "";
    }

    get pathValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get selectorProps() {
        return {
            path: this.pathValue,
            resModel: this.state.resModel,
            readonly: this.props.readonly,
            update: this.onUpdate.bind(this),
            isDebugMode: !!this.env.debug,
            filter: this.filterField.bind(this),
            followRelations: true,
            showSearchInput: true,
            allowEmpty: true,
        };
    }

    async loadSelectorContext(props) {
        if (props.purpose !== "filter") {
            Object.assign(this.state, {
                available: true,
                ready: true,
                resModel: "res.partner",
                message: "",
            });
            return;
        }

        try {
            const context = await this.orm.call(
                "g2p.consent.data.field",
                "get_path_selector_context",
                [],
                {
                    purpose: "filter",
                    source_path: props.record.data[props.sourceField] || "",
                }
            );
            Object.assign(this.state, {
                available: !!context.available,
                ready: true,
                resModel: context.model_name || "res.partner",
                message: context.message || "",
            });
        } catch (error) {
            Object.assign(this.state, {
                available: false,
                ready: true,
                resModel: "res.partner",
                message: _t("Unable to load fields."),
            });
            this.notification.add(_t("Unable to load filter fields."), {type: "danger"});
            throw error;
        }
    }

    async onUpdate(path) {
        await this.props.record.update({[this.props.name]: path || false});
    }

    filterField(fieldDef, currentPath = "") {
        const fieldName = fieldDef.name || "";
        const isImageField = IMAGE_FIELD_PREFIXES.some((prefix) => fieldName.startsWith(prefix));
        if (EXCLUDED_TYPES.has(fieldDef.type) && !(fieldDef.type === "binary" && isImageField)) {
            return false;
        }
        if (EXCLUDED_NAMES.has(fieldName)) {
            return false;
        }
        if (EXCLUDED_PREFIXES.some((prefix) => fieldName.startsWith(prefix))) {
            return false;
        }
        const depth = currentPath ? currentPath.split(".").filter(Boolean).length : 0;
        if (depth >= MAX_RELATION_DEPTH && RELATIONAL_TYPES.has(fieldDef.type)) {
            return false;
        }
        return true;
    }
}

export const g2pFieldPathPickerWidget = {
    component: G2PFieldPathSelector,
    displayName: _t("Field Path Picker"),
    supportedTypes: ["char"],
    extractProps: ({options}) => ({
        purpose: options.purpose || "source",
        sourceField: options.source_field || "source_path",
    }),
};

export class G2PDataFieldPreview extends Component {
    static template = "g2p_ati_websub.DataFieldPreview";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: false,
            error: "",
            prettyJson: "",
        });
    }

    get previewPartnerId() {
        return this.props.record.data.preview_partner_id?.[0];
    }

    get previewPartnerName() {
        return this.props.record.data.preview_partner_id?.[1] || "";
    }

    get mappingLines() {
        const records = this.props.record.data.mapping_line_ids?.records || [];
        return records.map((record) => ({
            payload_key: record.data.payload_key || "",
            source_path: record.data.source_path || "",
            filter_path: record.data.filter_path || "",
            filter_operator: record.data.filter_operator || "=",
            filter_value: record.data.filter_value || "",
            fallback_filter_path: record.data.fallback_filter_path || "",
            fallback_filter_operator: record.data.fallback_filter_operator || "=",
            fallback_filter_value: record.data.fallback_filter_value || "",
        }));
    }

    get previewValues() {
        return {
            name: this.props.record.data.name || "",
            code: this.props.record.data.code || "",
            payload_key: this.props.record.data.payload_key || "",
            source_path: this.props.record.data.source_path || "",
            mapping_lines: this.mappingLines,
        };
    }

    async generatePreview() {
        if (!this.previewPartnerId) {
            this.notification.add(_t("Select a sample farmer first."), {type: "warning"});
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "g2p.consent.data.field",
                "preview_payload_from_values",
                [],
                {
                    values: this.previewValues,
                    preview_partner_id: this.previewPartnerId,
                }
            );
            this.state.prettyJson = result.pretty_json || "{}";
        } catch (error) {
            this.state.prettyJson = "";
            this.state.error = error?.message || _t("Unable to generate preview.");
        } finally {
            this.state.loading = false;
        }
    }
}

export const g2pDataFieldPreviewWidget = {
    component: G2PDataFieldPreview,
    displayName: _t("Data Field Preview"),
    supportedTypes: ["text"],
};

registry.category("fields").add("g2p_field_path_picker", g2pFieldPathPickerWidget);
registry.category("fields").add("g2p_data_field_preview", g2pDataFieldPreviewWidget);
