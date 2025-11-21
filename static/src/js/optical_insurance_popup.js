/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";

export class OpticalInsurancePopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.OpticalInsurancePopup";
    static defaultProps = {
        confirmText: _t("Confirm"),
        cancelText: _t("Cancel"),
        title: _t("Insurance Payment Information"),
        body: "",
    };

    setup() {
        super.setup();
        this.state = useState({
            insurance_company_id: this.props.insurance_company_id || null,
            policy_number: this.props.policy_number || "",
            member_number: this.props.member_number || "",
            employer: this.props.employer || "",
            notes: this.props.notes || "",
            amount: this.props.amount || 0,
        });
        this.insuranceCompanies = this.props.insuranceCompanies || [];
    }

    getPayload() {
        return {
            insurance_company_id: parseInt(this.state.insurance_company_id),
            policy_number: this.state.policy_number,
            member_number: this.state.member_number,
            employer: this.state.employer,
            notes: this.state.notes,
            amount: this.state.amount,
        };
    }

    async confirm() {
        if (!this.state.insurance_company_id) {
            await this.env.services.popup.add("ErrorPopup", {
                title: _t("Missing Insurance Company"),
                body: _t("Please select an insurance company."),
            });
            return;
        }
        this.props.resolve({ confirmed: true, payload: this.getPayload() });
        this.props.close();
    }
}
