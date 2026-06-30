/** @odoo-module */
import {FormController} from "@web/views/form/form_controller";
import {formView} from "@web/views/form/form_view";
import {registry} from "@web/core/registry";
const {useEffect} = owl;

class ResPartnerFormOtherGroupController extends FormController {
    get modelParams() {
        const params = super.modelParams;
        return {
            ...params,
            hooks: {
                ...params.hooks,
                onRecordChanged: this.onRecordChanged.bind(this),
            },
        };
    }

    setup() {
        super.setup();

        useEffect(
            () => {
                this._applyLanguageToggle();
            },
            () => [this.model.root.data.primary_Language, this.model.root.data.is_group]
        );
    }

    onRecordChanged(record, changes) {
        if (!changes || !("primary_Language" in changes)) {
            return;
        }
        this._applyLanguageToggle();
    }

    _applyLanguageToggle() {
        if (this.model.root.data.is_group) {
            return;
        }

        const primaryLanguage = this.model.root.data.primary_Language;
        const primaryLanguageText = this._getLanguageName(primaryLanguage);
        const normalizedLang = primaryLanguageText.trim().toLowerCase();
        const isAmharic = !normalizedLang || normalizedLang === "amharic";
        const showOther = !isAmharic;

        const root = this.rootRef?.el || document;
        const otherGroup = this._getOtherGroup(root);
        if (otherGroup) {
            const separators = otherGroup.querySelectorAll(".o_horizontal_separator");
            for (const sep of separators) {
                sep.innerText = showOther && primaryLanguageText ? primaryLanguageText : "Other";
            }
        }

        if (otherGroup) {
            const labels = otherGroup.querySelectorAll(".o_form_label");
            for (const label of labels) {
                const rawText = label.innerText || "";
                const baseText = rawText.replace(/\s*\([^)]*\)\s*$/, "");
                const labelText = baseText.trim().toLowerCase();
                if (
                    labelText === "first name" ||
                    labelText === "father's name" ||
                    labelText === "grand father's name"
                ) {
                    if (showOther && primaryLanguageText) {
                        label.innerText = `${baseText} (${primaryLanguageText})`;
                    } else {
                        label.innerText = baseText;
                    }
                }
            }
        }
    }

    _getLanguageName(value) {
        if (!value) {
            return "";
        }
        if (Array.isArray(value)) {
            return value[1] || "";
        }
        if (typeof value === "object") {
            return (
                value.display_name ||
                value.displayName ||
                value.name ||
                value.resName ||
                value.data?.display_name ||
                ""
            );
        }
        return String(value);
    }

    _getOtherGroup(root) {
        const selector =
            ".o_field_widget[name='first_name_other'], .o_field_widget[name='family_name_other'], .o_field_widget[name='gf_name_other']";
        const fieldEl = root.querySelector(selector);
        if (!fieldEl) {
            return null;
        }
        return fieldEl.closest(".o_inner_group, .o_group");
    }
}

const resPartnerFormOtherGroupView = {
    ...formView,
    Controller: ResPartnerFormOtherGroupController,
};

registry.category("views").add("res_partner_other_group_string", resPartnerFormOtherGroupView);

// Class ResPartnerFormController extends FormController {
//     setup(){
//       jhfhkgfhgfhjgdgfdgdg
//         super.setup()

//         useEffect(()=>{
//             // const divElement = document.querySelector('.o_horizontal_separator.mt-4.mb-3.text-uppercase.fw-bolder.small');
//                 adsf
//             // if (divElement) {
//             //     divElement.innerText = "this.model.root.data.primary_Language[1]";
//             // }
//             this.disableForm()
//         }, ()=>[this.model.root.data.state])

//         this.onNotebookPageChange = (notebookId, page) => {
//             this.disableForm()
//         };
//     }

//     disableForm(){

//         console.log(this.model.root.data)

//         const divElement = document.querySelector('.o_horizontal_separator.mt-4.mb-3.text-uppercase.fw-bolder.small');

//         if (divElement) {
//             divElement.innerText = "this.model.root.data.primary_Language[1]";

//         // if (this.model.root.data.state == 'locked'){
//         //     if (inputs) inputs.forEach(e => e.setAttribute("disabled", 1))
//         //     if (widgets) widgets.forEach(e => e.classList.add("pe-none"))
//         //     this.canEdit = false
//         // } else {
//         //     if (inputs) inputs.forEach(e => e.removeAttribute("disabled"))
//         //     if (widgets) widgets.forEach(e => e.classList.remove("pe-none"))
//         //     this.canEdit = true
//         }
//     }

//     async beforeLeave() {
//         if (this.model.root.data.primary_Language != 'locked') return
//         super.beforeLeave()
//     }

//     async beforeUnload(ev) {
//         if (this.model.root.data.primary_Language != 'locked') return
//         super.beforeUnload(ev)
//     }
// }

// const resPartnerFormView = {
//     ...formView,
//     Controller: ResPartnerFormController,
// }

// registry.category("views").add("res_partner_form_disable", resPartnerFormView)
