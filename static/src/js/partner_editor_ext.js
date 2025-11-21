/** @odoo-module */

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { InsurancePopup } from "@bp_optical_pos/js/insurance_popup";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup(...arguments);

        this.insuranceCompanies = [];
        this.existingInsurance = null;

        onWillStart(async () => {
            if (this.opticalEnabled) {
                await this.loadInsuranceCompanies();
                await this.loadExistingInsurance();
            }
        });

        // Initialize optical fields from existing partner data
        if (!this.changes.date_of_birth) {
            this.changes.date_of_birth = this.props.partner.date_of_birth || "";
        }

        // Pre-check has_insurance if partner has active insurance
        if (this.changes.has_insurance === undefined) {
            this.changes.has_insurance = false; // Will be updated after loadExistingInsurance
        }

        // Initialize insurance data object - will be populated after loadExistingInsurance
        this.changes.insuranceData = {
            insurance_company_id: "",
            policy_number: "",
            insurance_expiry_date: "",
            patient_company: "",
            insurance_invoice_number: "",
            coverage_details: "",
        };
    },

    async loadExistingInsurance() {
        if (!this.props.partner.id) return;

        try {
            // Load active insurance for this partner
            const insurances = await this.env.services.orm.searchRead(
                "optical.patient.insurance",
                [['patient_id', '=', this.props.partner.id], ['active', '=', true]],
                ["insurance_company_id", "name", "expiry_date", "patient_company_id", "invoice_number", "coverage_details"],
                { order: "date desc", limit: 1 }
            );

            if (insurances && insurances.length > 0) {
                this.existingInsurance = insurances[0];

                // Pre-populate insurance data
                this.changes.has_insurance = true;
                this.changes.insuranceData = {
                    insurance_company_id: this.existingInsurance.insurance_company_id?.[0] || "",
                    policy_number: this.existingInsurance.name || "",
                    insurance_expiry_date: this.existingInsurance.expiry_date || "",
                    patient_company: this.existingInsurance.patient_company_id || "",
                    insurance_invoice_number: this.existingInsurance.invoice_number || "",
                    coverage_details: this.existingInsurance.coverage_details || "",
                };

                // Also set individual fields
                this.changes.insurance_company_id = this.existingInsurance.insurance_company_id?.[0];
                this.changes.policy_number = this.existingInsurance.name;
                this.changes.insurance_expiry_date = this.existingInsurance.expiry_date;
                this.changes.patient_company = this.existingInsurance.patient_company_id;
                this.changes.insurance_invoice_number = this.existingInsurance.invoice_number;
                this.changes.coverage_details = this.existingInsurance.coverage_details;
            }
        } catch (error) {
            console.error("Failed to load existing insurance:", error);
        }
    },

    async loadInsuranceCompanies() {
        try {
            const companies = await this.env.services.orm.searchRead(
                "optical.insurance.company",
                [],
                ["id", "name"],
                { order: "name" }
            );
            this.insuranceCompanies = companies;
        } catch (error) {
            console.error("Failed to load insurance companies:", error);
            this.insuranceCompanies = [];
        }
    },

    onInsuranceCheckChange(ev) {
        this.changes.has_insurance = ev.target.checked;
        if (!this.changes.has_insurance) {
            // Clear insurance data if unchecked
            this.changes.insuranceData = {
                insurance_company_id: "",
                policy_number: "",
                insurance_expiry_date: "",
                patient_company: "",
                insurance_invoice_number: "",
                coverage_details: "",
            };
        }
    },

    async openInsurancePopup() {
        const { confirmed, payload } = await this.env.services.popup.add(InsurancePopup, {
            title: "Insurance Details",
            insuranceCompanies: this.insuranceCompanies,
            insuranceData: this.changes.insuranceData,
        });

        if (confirmed && payload) {
            // Store insurance data
            this.changes.insuranceData = payload;

            // Also set individual fields for backend compatibility
            this.changes.insurance_company_id = payload.insurance_company_id;
            this.changes.policy_number = payload.policy_number;
            this.changes.insurance_expiry_date = payload.insurance_expiry_date;
            this.changes.patient_company = payload.patient_company;
            this.changes.insurance_invoice_number = payload.insurance_invoice_number;
            this.changes.coverage_details = payload.coverage_details;
        }
    },

    get hasInsuranceData() {
        return this.changes.insuranceData &&
            this.changes.insuranceData.insurance_company_id &&
            this.changes.insuranceData.policy_number;
    },

    getInsuranceSummary() {
        if (!this.hasInsuranceData) return "";

        const company = this.insuranceCompanies.find(
            c => c.id == this.changes.insuranceData.insurance_company_id
        );
        const companyName = company ? company.name : "Unknown";
        return `${companyName} - ${this.changes.insuranceData.policy_number}`;
    },

    get opticalEnabled() {
        return this.pos.config.optical_enabled;
    }
});
