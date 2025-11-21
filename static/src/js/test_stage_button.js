/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { TestViewPopup } from "@bp_optical_pos/js/test_view_popup";

export class TestStageButton extends Component {
    static template = "bp_optical_pos.TestStageButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get selectedOrder() {
        return this.pos.get_order();
    }

    get selectedClient() {
        return this.selectedOrder?.get_partner();
    }

    get isVisible() {
        // Show button only if optical is enabled and customer is selected
        return this.pos.config.optical_enabled && this.selectedClient;
    }

    async onClick() {
        if (!this.selectedClient) {
            this.notification.add("Please select a customer first", {
                type: "warning",
            });
            return;
        }

        try {
            // Get patient tests with full details
            const tests = await this.orm.call(
                "pos.order",
                "optical_get_patient_tests_full",
                [this.selectedClient.id, 10]
            );

            if (!tests || tests.length === 0) {
                this.notification.add("No optical tests found for this customer", {
                    type: "info",
                });
                return;
            }

            // Get available stages
            const stages = await this.orm.call(
                "pos.order",
                "optical_get_stages",
                []
            );

            if (!stages || stages.length === 0) {
                this.notification.add("No stages configured", {
                    type: "warning",
                });
                return;
            }

            // Show test selection popup
            const { confirmed: testConfirmed, payload: selectedTest } = await this.popup.add(TestSelectionPopup, {
                title: "Select Optical Test",
                tests: tests,
            });

            if (!testConfirmed || !selectedTest) {
                return;
            }

            // Get full test details
            const test = tests.find(t => t.id === selectedTest.testId);

            // Show comprehensive test view popup
            const { confirmed: viewConfirmed, payload: viewData } = await this.popup.add(TestViewPopup, {
                test: test,
                stages: stages,
            });

            if (viewConfirmed && viewData) {
                this.notification.add(viewData.message || "Stage updated successfully", {
                    type: "success",
                });
            }

        } catch (error) {
            console.error("Error in TestStageButton:", error);
            this.notification.add("Error: " + error.message, {
                type: "danger",
            });
        }
    }
}

// Test selection popup
class TestSelectionPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.TestSelectionPopup";

    setup() {
        super.setup();
        this.state = useState({ selectedTestId: null });
    }

    selectTest(testId) {
        this.state.selectedTestId = testId;
    }

    confirm() {
        if (!this.state.selectedTestId) {
            alert("Please select a test");
            return;
        }
        this.props.close({
            confirmed: true,
            payload: { testId: this.state.selectedTestId }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}

ProductScreen.addControlButton({
    component: TestStageButton,
    condition: function () {
        return this.pos.config.optical_enabled;
    },
});
