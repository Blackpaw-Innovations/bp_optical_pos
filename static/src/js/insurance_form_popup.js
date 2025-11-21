/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class InsuranceFormPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.InsuranceFormPopup";

    setup() {
        super.setup();

        // Get today's date in YYYY-MM-DD format
        const today = new Date().toISOString().split('T')[0];

        this.state = useState({
            policy_number: "",
            insurance_company_id: "",
            date: today,
            expiry_date: "",
            patient_company_id: "",
            invoice_number: "",
            coverage_details: "",
            note: "",
            file: null,
            filename: "",
        });
    }

    async onFileChange(event) {
        const file = event.target.files[0];
        if (!file) {
            this.state.file = null;
            this.state.filename = "";
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.file = e.target.result.split(',')[1]; // Get base64 part
            this.state.filename = file.name;
        };
        reader.readAsDataURL(file);
    }

    async confirm() {
        // Validate required fields
        if (!this.state.policy_number || !this.state.policy_number.trim()) {
            await this.env.services.popup.add("ErrorPopup", {
                title: _t("Validation Error"),
                body: _t("Policy Number is required"),
            });
            return;
        }

        if (!this.state.insurance_company_id) {
            await this.env.services.popup.add("ErrorPopup", {
                title: _t("Validation Error"),
                body: _t("Insurance Company is required"),
            });
            return;
        }

        if (!this.state.date) {
            await this.env.services.popup.add("ErrorPopup", {
                title: _t("Validation Error"),
                body: _t("Date is required"),
            });
            return;
        }

        // Return insurance data
        this.props.close({
            confirmed: true,
            payload: {
                policy_number: this.state.policy_number.trim(),
                insurance_company_id: this.state.insurance_company_id,
                date: this.state.date,
                expiry_date: this.state.expiry_date || false,
                patient_company_id: this.state.patient_company_id.trim() || false,
                invoice_number: this.state.invoice_number.trim() || false,
                coverage_details: this.state.coverage_details.trim() || false,
                note: this.state.note.trim() || false,
                file: this.state.file,
                filename: this.state.filename,
            }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}

// Register the popup
registry.category("popups").add("InsuranceFormPopup", InsuranceFormPopup);
