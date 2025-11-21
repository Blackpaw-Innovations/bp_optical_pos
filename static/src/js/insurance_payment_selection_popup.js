/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { InsuranceFormPopup } from "./insurance_form_popup";
import { registry } from "@web/core/registry";

export class InsurancePaymentSelectionPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.InsurancePaymentSelectionPopup";

    setup() {
        super.setup();
        this.state = useState({
            insurances: this.props.insurances || [],
            selectedInsurance: null,
        });
    }

    selectInsurance(insurance) {
        this.state.selectedInsurance = insurance;
    }

    async createNewInsurance() {
        // Open insurance form popup to create new insurance
        const { confirmed, payload } = await this.env.services.popup.add(
            InsuranceFormPopup,
            {
                title: _t("Create New Insurance Policy"),
                customerId: this.props.customerId,
                customerName: this.props.customerName,
                insuranceCompanies: this.props.insuranceCompanies,
            }
        );

        if (confirmed && payload) {
            // Create insurance record via backend
            try {
                const insuranceVals = {
                    name: payload.policy_number,
                    patient_id: this.props.customerId,
                    insurance_company_id: parseInt(payload.insurance_company_id),
                    date: payload.date || new Date().toISOString().split('T')[0],
                    expiry_date: payload.expiry_date || false,
                    patient_company_id: payload.patient_company_id || false,
                    invoice_number: payload.invoice_number || false,
                    coverage_details: payload.coverage_details || false,
                    note: payload.note || false,
                    active: true,
                };

                // Add attachment if file is provided
                if (payload.file && payload.filename) {
                    insuranceVals.document_ids = [[0, 0, {
                        name: payload.filename,
                        datas: payload.file,
                        type: 'binary',
                        res_model: 'optical.patient.insurance',
                    }]];
                }

                const insuranceId = await this.env.services.orm.call(
                    "optical.patient.insurance",
                    "create",
                    [insuranceVals]
                );

                // Read back the created insurance with company name
                const newInsurance = await this.env.services.orm.searchRead(
                    "optical.patient.insurance",
                    [["id", "=", insuranceId]],
                    ["id", "name", "insurance_company_id", "expiry_date", "patient_company_id", "invoice_number", "coverage_details", "active"]
                );

                if (newInsurance && newInsurance.length > 0) {
                    const insurance = newInsurance[0];
                    insurance.insurance_company_name = insurance.insurance_company_id[1];

                    // Add to list and select it
                    this.state.insurances.push(insurance);
                    this.state.selectedInsurance = insurance;
                }
            } catch (error) {
                console.error("Error creating insurance:", error);
                await this.env.services.popup.add("ErrorPopup", {
                    title: _t("Error"),
                    body: _t("Failed to create insurance policy: ") + error.message,
                });
            }
        }
    }

    async confirm() {
        if (!this.state.selectedInsurance) {
            return;
        }

        this.props.close({
            confirmed: true,
            payload: {
                insurance_id: this.state.selectedInsurance.id,
                insurance_company_id: this.state.selectedInsurance.insurance_company_id[0],
                insurance_company_name: this.state.selectedInsurance.insurance_company_name || this.state.selectedInsurance.insurance_company_id[1],
                policy_number: this.state.selectedInsurance.name,
                expiry_date: this.state.selectedInsurance.expiry_date || "",
                patient_company_id: this.state.selectedInsurance.patient_company_id || "",
                invoice_number: this.state.selectedInsurance.invoice_number || "",
                coverage_details: this.state.selectedInsurance.coverage_details || "",
            }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}

// Register the popup
registry.category("popups").add("InsurancePaymentSelectionPopup", InsurancePaymentSelectionPopup);
