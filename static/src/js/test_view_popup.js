/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class TestViewPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.TestViewPopup";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            selectedStageId: this.props.test.stage_id || null,
            loading: false,
        });
    }

    get test() {
        return this.props.test;
    }

    get stages() {
        return this.props.stages || [];
    }

    get currentStage() {
        return this.stages.find(s => s.id === this.state.selectedStageId);
    }

    selectStage(stageId) {
        this.state.selectedStageId = stageId;
    }

    async saveStage() {
        if (!this.state.selectedStageId) {
            return;
        }

        if (this.state.selectedStageId === this.test.stage_id) {
            // No change
            this.props.close({ confirmed: false });
            return;
        }

        this.state.loading = true;
        try {
            const stage = this.stages.find(s => s.id === this.state.selectedStageId);
            const result = await this.orm.call(
                "pos.order",
                "optical_change_test_stage",
                [this.test.id, stage.name]
            );

            if (result.success) {
                this.props.close({
                    confirmed: true,
                    payload: {
                        testId: this.test.id,
                        stageId: this.state.selectedStageId,
                        stageName: stage.name,
                        message: result.message,
                    }
                });
            } else {
                alert(result.error || "Failed to change stage");
                this.state.loading = false;
            }
        } catch (error) {
            console.error("Error changing stage:", error);
            alert("Error: " + error.message);
            this.state.loading = false;
        }
    }

    async printTest() {
        try {
            // Generate PDF URL and open in new window
            const url = `/report/pdf/bp_optical_core.report_optical_prescription/${this.test.id}`;
            window.open(url, '_blank');
        } catch (error) {
            console.error("Error printing test:", error);
            alert("Error printing test: " + error.message);
        }
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}
