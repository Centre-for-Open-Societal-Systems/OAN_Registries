/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Widgetpreview} from "@g2p_documents/js/preview_document";

export class DocumentPreview extends Widgetpreview {
    clickPreview() {
        const recordData = this.props.record.data;
        const mimetype = recordData.document_mimetype;
        if (typeof mimetype === "string" && mimetype) {
            const file = {
                id: recordData.document_id,
                displayName: recordData.document_name,
                downloadUrl: recordData.document_url,
                isViewable: mimetype.includes("image") || mimetype.includes("pdf"),

                defaultSource: recordData.document_url,
                isImage: mimetype.includes("image"),
                isPdf: mimetype.includes("pdf"),
            };
            if (file.isViewable) {
                this.fileViewer.open(file);
            } else {
                window.open(recordData.document_url, "_blank");
            }
        } else {
            window.open(recordData.document_url, "_blank");
        }
    }
}

DocumentPreview.template = "g2p_ati.DocumentPreview";

registry.category("view_widgets").add("g2p_ati_document_preview", {component: DocumentPreview});
