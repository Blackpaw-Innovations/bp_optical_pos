/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class StageChangePopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.StageChangePopup";

    setup() {
        super.setup();
        this.state = useState({
            selectedStageId: this.props.currentStage?.id || "",
            loading: false,
        });
    }

    get currentStageName() {
        return this.props.currentStage?.name || "Unknown";
    }

    get availableStages() {
        return this.props.stages || [];
    }

    async confirm() {
        if (!this.state.selectedStageId) {
            alert(_t("Please select a stage"));
            return;
        }

        // Find selected stage
        const selectedStage = this.availableStages.find(
            s => s.id === parseInt(this.state.selectedStageId)
        );

        if (!selectedStage) {
            alert(_t("Invalid stage selection"));
            return;
        }

        this.props.close({
            confirmed: true,
            payload: {
                stageId: selectedStage.id,
                stageName: selectedStage.name,
            }
        });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }
}
