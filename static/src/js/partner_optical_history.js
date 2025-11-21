/** @odoo-module */

import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";
import { patch } from "@web/core/utils/patch";
import { Component, useState } from "@odoo/owl";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";

// Patch PartnerLine to add optical test history button
patch(PartnerLine.prototype, {
    get isOpticalEnabled() {
        // Access pos from env.services.pos
        const pos = this.env.services.pos;
        return pos && pos.config && pos.config.optical_enabled;
    },
    
    async showOpticalHistory() {
        const partner = this.props.partner;
        if (!partner || !partner.id) return;
        
        // Use env.services.orm directly
        const orm = this.env.services.orm;
        
        // Fetch optical tests for this patient
        const tests = await orm.call(
            "pos.order",
            "optical_get_patient_tests",
            [partner.id, 10]
        );
        
        await this.env.services.popup.add(OpticalHistoryPopup, {
            partner: partner,
            tests: tests,
        });
    }
});

// Optical History Popup Component
export class OpticalHistoryPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.OpticalHistoryPopup";
    
    setup() {
        super.setup();
        this.state = useState({
            selectedTest: null,
        });
    }
    
    get hasTests() {
        return this.props.tests && this.props.tests.length > 0;
    }
    
    selectTest(test) {
        this.state.selectedTest = test;
    }
    
    closeDetails() {
        this.state.selectedTest = null;
    }
    
    close() {
        this.props.close();
    }
    
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString();
    }
    
    formatPrescription(eye) {
        const test = this.state.selectedTest;
        if (!test) return '';
        
        const prefix = eye === 'od' ? 'od' : 'os';
        const sphere = test[`sphere_${prefix}`] || 0;
        const cylinder = test[`cylinder_${prefix}`] || 0;
        const axis = test[`axis_${prefix}`] || 0;
        const add = test[`add_${prefix}`] || 0;
        
        let result = `SPH: ${sphere.toFixed(2)}`;
        if (cylinder) result += ` CYL: ${cylinder.toFixed(2)}`;
        if (axis) result += ` AXIS: ${axis}°`;
        if (add) result += ` ADD: ${add.toFixed(2)}`;
        
        return result;
    }
}
