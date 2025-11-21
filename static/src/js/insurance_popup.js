/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class InsurancePopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.InsurancePopup";

    setup() {
        super.setup();
        this.state = useState({
            insurance_company_id: this.props.insuranceData?.insurance_company_id || "",
            policy_number: this.props.insuranceData?.policy_number || "",
            insurance_expiry_date: this.props.insuranceData?.insurance_expiry_date || "",
            patient_company: this.props.insuranceData?.patient_company || "",
            insurance_invoice_number: this.props.insuranceData?.insurance_invoice_number || "",
            coverage_details: this.props.insuranceData?.coverage_details || "",
            document: null,
            fileName: "",
        });
    }

    onFileChange(event) {
        const file = event.target.files[0];
        if (file) {
            // Validate file size (5MB limit)
            if (file.size > 5 * 1024 * 1024) {
                alert(_t("File size must be less than 5MB"));
                event.target.value = "";
                return;
            }

            // Read file as base64
            const reader = new FileReader();
            reader.onload = (e) => {
                this.state.document = e.target.result.split(',')[1]; // Get base64 part
                this.state.fileName = file.name;
            };
            reader.readAsDataURL(file);
        }
    }

    confirm() {
        // Validate required fields
        if (!this.state.insurance_company_id || !this.state.policy_number) {
            alert(_t("Please fill in Insurance Company and Policy Number"));
            return;
        }

        // Return insurance data with document
        this.props.close({
            confirmed: true,
            payload: {
                insurance_company_id: this.state.insurance_company_id,
                policy_number: this.state.policy_number,
                insurance_expiry_date: this.state.insurance_expiry_date || "",
                patient_company: this.state.patient_company || "",
                insurance_invoice_number: this.state.insurance_invoice_number || "",
                coverage_details: this.state.coverage_details || "",
                document: this.state.document || null,
                document_name: this.state.fileName || "",
            }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}
