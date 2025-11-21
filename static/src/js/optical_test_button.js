/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OpticalTestPopup } from "./optical_test_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

export class OpticalTestButton extends Component {
    static template = "bp_optical_pos.OpticalTestButton";

    setup() {
        this.pos = usePos();
        console.log('[OpticalTestButton] setup - optical_enabled:', this.pos?.config?.optical_enabled);
    }

    mounted() {
        console.log('[OpticalTestButton] mounted component');
    }

    async onClick() {
        console.log('[OpticalTestButton] Click detected');
        const order = this.pos.get_order();
        const client = order ? order.get_partner() : null;

        // Use env.services directly to avoid component destruction protection
        const popup = this.env.services.popup;
        const orm = this.env.services.orm;

        if (!client) {
            console.warn('[OpticalTestButton] No customer selected');
            await popup.add(ErrorPopup, {
                title: _t("No Customer Selected"),
                body: _t("Please select a customer before creating an optical test."),
            });
            return;
        }

        // Open the full Optical Test Popup
        let confirmed, payload;
        try {
            console.log('[OpticalTestButton] Opening OpticalTestPopup for customer', client.id);
            ({ confirmed, payload } = await popup.add(OpticalTestPopup, {
                customer: client,
            }));
            console.log('[OpticalTestButton] Popup closed - confirmed:', confirmed, 'payload:', payload);
        } catch (e) {
            console.error('[OpticalTestButton] Failed to open popup', e);
            await popup.add(ErrorPopup, {
                title: _t("Popup Error"),
                body: _t("Failed to open Optical Test popup."),
            });
            return;
        }

        if (confirmed && payload) {
            try {
                // Call backend RPC with full test data
                console.log('[OpticalTestButton] Sending RPC optical_create_test payload', payload);
                const result = await orm.call(
                    "pos.order",
                    "optical_create_test",
                    [order.uid, client.id, payload]
                );
                console.log('[OpticalTestButton] RPC result', result);

                if (result.error) {
                    await popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: _t("Failed to create optical test: %s", result.error),
                    });
                } else {
                    await popup.add(ConfirmPopup, {
                        title: _t("Success"),
                        body: _t("Optical test created successfully!\n\nTest ID: %s\nPatient: %s", result.test_id, client.name),
                    });
                }
            } catch (error) {
                console.error("Error creating optical test:", error);
                await popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("An error occurred while creating the optical test.\n\n%s", error.message || error),
                });
            }
        }
    }
}

ProductScreen.addControlButton({
    component: OpticalTestButton,
    condition: function () {
        return this.pos.config.optical_enabled;
    },
});
