/** @odoo-module */

import { Payment } from "@point_of_sale/app/store/models";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { OpticalInsurancePopup } from "./optical_insurance_popup";
import { InsurancePaymentSelectionPopup } from "./insurance_payment_selection_popup";
import { InsuranceFormPopup } from "./insurance_form_popup";
import { registry } from "@web/core/registry";

// Register the legacy popup (keep for backwards compatibility)
registry.category("popups").add("OpticalInsurancePopup", OpticalInsurancePopup);

// Extend Payment model to store insurance data
patch(Payment.prototype, {
    setup() {
        super.setup(...arguments);
        this.is_insurance = this.is_insurance || false;
        this.insuranceData = this.insuranceData || null;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.is_insurance = this.is_insurance;
        json.insuranceData = this.insuranceData;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.is_insurance = json.is_insurance || false;
        this.insuranceData = json.insuranceData || null;
    },
});

// Extend PaymentScreen to handle insurance payments
patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.popup = useService("popup");
    },

    async addNewPaymentLine(arg) {
        // Support both Odoo event shape ({detail}) and direct object
        const paymentMethod = (arg && arg.detail !== undefined) ? arg.detail : arg;
        console.log("addNewPaymentLine called with:", paymentMethod);
        console.log("is_insurance_method:", paymentMethod?.is_insurance_method);
        if (paymentMethod && paymentMethod.is_insurance_method) {
            console.log("Handling insurance payment");
            return await this.handleInsurancePayment(paymentMethod);
        }
        return await super.addNewPaymentLine(...arguments);
    },

    async handleInsurancePayment(paymentMethod) {
        const order = this.currentOrder || this.pos.get_order();
        const dueAmount = order.get_due();

        if (dueAmount <= 0) {
            return;
        }

        // Check if customer is selected
        const customer = order.get_partner();
        if (!customer) {
            await this.popup.add("ErrorPopup", {
                title: _t("No Customer Selected"),
                body: _t("Please select a customer before using insurance payment."),
            });
            return;
        }

        // Load insurance companies from backend
        let insuranceCompanies = [];
        try {
            insuranceCompanies = await this.orm.searchRead(
                "optical.insurance.company",
                [],
                ["id", "name"],
                { limit: 100 }
            );
        } catch (error) {
            console.error("Error loading insurance companies:", error);
        }

        // Load customer's insurance policies
        let customerInsurances = [];
        try {
            customerInsurances = await this.orm.searchRead(
                "optical.patient.insurance",
                [["patient_id", "=", customer.id]],
                ["id", "name", "insurance_company_id", "expiry_date", "patient_company_id", "invoice_number", "coverage_details", "active"],
                { order: "date desc" }
            );

            // Add insurance company name to each insurance
            customerInsurances.forEach(insurance => {
                insurance.insurance_company_name = insurance.insurance_company_id[1];
            });
        } catch (error) {
            console.error("Error loading customer insurances:", error);
        }

        // Show insurance selection popup
        console.log("InsurancePaymentSelectionPopup component:", InsurancePaymentSelectionPopup);

        if (!InsurancePaymentSelectionPopup) {
            console.error("InsurancePaymentSelectionPopup is undefined!");
            await this.popup.add("ErrorPopup", {
                title: _t("System Error"),
                body: _t("Insurance Popup component failed to load."),
            });
            return;
        }

        const { confirmed, payload } = await this.popup.add(
            InsurancePaymentSelectionPopup,
            {
                customerId: customer.id,
                customerName: customer.name,
                insurances: customerInsurances,
                insuranceCompanies: insuranceCompanies,
            }
        );

        if (confirmed && payload) {
            // Create payment line
            const payment = order.add_paymentline(paymentMethod);
            if (payment) {
                payment.set_amount(dueAmount); // Set to full due amount
                payment.is_insurance = true;
                payment.insuranceData = payload;

                // Store insurance data for backend processing
                payment.insurance_id = payload.insurance_id;
                payment.insurance_company_id = payload.insurance_company_id;
                payment.insurance_company_name = payload.insurance_company_name;
                payment.policy_number = payload.policy_number;
                payment.expiry_date = payload.expiry_date;
                payment.patient_company_id = payload.patient_company_id;
                payment.invoice_number = payload.invoice_number;
                payment.coverage_details = payload.coverage_details;
            }
        }
    },
});
