/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

/**
 * Optical Test Popup
 * 
 * Full-featured popup for capturing optical test data with OD/OS fields.
 * Collects sphere, cylinder, axis, prism, add, VA, and PD for both eyes,
 * plus notes and optional validity date.
 */
export class OpticalTestPopup extends AbstractAwaitablePopup {
    static template = "bp_optical_pos.OpticalTestPopup";
    static defaultProps = {
        title: _t("Optical Test"),
        customer: null,
    };

    setup() {
        super.setup();
        this.popup = useService("popup");
        this.orm = useService("orm");

        // Initialize state with all form fields
        this.state = useState({
            // Right Eye (OD) fields
            sphere_od: "",
            cylinder_od: "",
            axis_od: "",
            prism_od: "",
            add_od: "",
            va_od: "",
            pd_od: "",
            height_od: "",

            // Left Eye (OS) fields
            sphere_os: "",
            cylinder_os: "",
            axis_os: "",
            prism_os: "",
            add_os: "",
            va_os: "",
            pd_os: "",
            height_os: "",

            // Lens & Frame
            needs_new_lens: false,
            needs_new_frame: false,
            lens_type_id: false,
            coating_id: false,
            index_id: false,
            material_id: false,
            frame_id: false,

            // Insurance
            insurance_company_id: false,

            // Other
            workshop_order_number: "",
            follow_up_required: false,
            follow_up_date: "",
            notes: "",
            valid_until: "",
        });

        // Load dropdown options
        this.lensTypes = [];
        this.coatings = [];
        this.indexes = [];
        this.materials = [];
        this.frames = [];
        this.insuranceCompanies = [];

        this.loadOptions();
    }

    async loadOptions() {
        try {
            // Load lens types
            this.lensTypes = await this.orm.searchRead(
                "optical.lens.type",
                [],
                ["id", "name"],
                { order: "name" }
            );

            // Load coatings
            this.coatings = await this.orm.searchRead(
                "optical.coating",
                [],
                ["id", "name"],
                { order: "name" }
            );

            // Load indexes
            this.indexes = await this.orm.searchRead(
                "optical.index",
                [],
                ["id", "name"],
                { order: "name" }
            );

            // Load materials
            this.materials = await this.orm.searchRead(
                "optical.material",
                [],
                ["id", "name"],
                { order: "name" }
            );

            // Load frames (products with Frame category)
            this.frames = await this.orm.searchRead(
                "product.product",
                [["categ_id.name", "=", "Frame"]],
                ["id", "name"],
                { order: "name", limit: 100 }
            );

            // Load insurance companies
            this.insuranceCompanies = await this.orm.searchRead(
                "optical.insurance.company",
                [["active", "=", true]],
                ["id", "name"],
                { order: "name" }
            );
        } catch (error) {
            console.error("Error loading options:", error);
        }
    }

    /**
     * Validate and collect form data
     */
    getPayload() {
        const payload = {
            // Right Eye (OD)
            sphere_od: this._parseFloat(this.state.sphere_od),
            cylinder_od: this._parseFloat(this.state.cylinder_od),
            axis_od: this._parseInt(this.state.axis_od),
            prism_od: this._parseFloat(this.state.prism_od),
            add_od: this._parseFloat(this.state.add_od),
            va_od: this.state.va_od?.trim() || "",
            pd_od: this._parseFloat(this.state.pd_od),
            height_od: this._parseFloat(this.state.height_od),

            // Left Eye (OS)
            sphere_os: this._parseFloat(this.state.sphere_os),
            cylinder_os: this._parseFloat(this.state.cylinder_os),
            axis_os: this._parseInt(this.state.axis_os),
            prism_os: this._parseFloat(this.state.prism_os),
            add_os: this._parseFloat(this.state.add_os),
            va_os: this.state.va_os?.trim() || "",
            pd_os: this._parseFloat(this.state.pd_os),
            height_os: this._parseFloat(this.state.height_os),

            // Lens & Frame
            needs_new_lens: this.state.needs_new_lens || false,
            needs_new_frame: this.state.needs_new_frame || false,
            lens_type_id: this.state.lens_type_id || false,
            coating_id: this.state.coating_id || false,
            index_id: this.state.index_id || false,
            material_id: this.state.material_id || false,
            frame_id: this.state.frame_id || false,

            // Insurance
            insurance_company_id: this.state.insurance_company_id || false,

            // Other
            workshop_order_number: this.state.workshop_order_number?.trim() || "",
            follow_up_required: this.state.follow_up_required || false,
            follow_up_date: this.state.follow_up_date || false,
            notes: this.state.notes?.trim() || "",
            valid_until: this.state.valid_until || false,
        };

        return payload;
    }

    /**
     * Parse float value, return false if empty/invalid
     */
    _parseFloat(value) {
        if (value === "" || value === null || value === undefined) {
            return false;
        }
        const parsed = parseFloat(value);
        return isNaN(parsed) ? false : parsed;
    }

    /**
     * Parse integer value, return false if empty/invalid
     */
    _parseInt(value) {
        if (value === "" || value === null || value === undefined) {
            return false;
        }
        const parsed = parseInt(value, 10);
        return isNaN(parsed) ? false : parsed;
    }

    /**
     * Validate input - basic validation
     * For optical tests, we allow all fields to be optional since
     * different test scenarios may only require certain measurements
     */
    validate() {
        // Check if at least one measurement field is filled
        const hasODData = this.state.sphere_od || this.state.cylinder_od ||
            this.state.axis_od || this.state.va_od;
        const hasOSData = this.state.sphere_os || this.state.cylinder_os ||
            this.state.axis_os || this.state.va_os;

        if (!hasODData && !hasOSData) {
            return {
                valid: false,
                message: _t("Please enter at least one measurement for OD or OS.")
            };
        }

        // Validate axis range if provided
        if (this.state.axis_od && (this.state.axis_od < 0 || this.state.axis_od > 180)) {
            return {
                valid: false,
                message: _t("OD Axis must be between 0 and 180.")
            };
        }

        if (this.state.axis_os && (this.state.axis_os < 0 || this.state.axis_os > 180)) {
            return {
                valid: false,
                message: _t("OS Axis must be between 0 and 180.")
            };
        }

        return { valid: true };
    }

    /**
     * Handle confirm button click
     */
    async confirm() {
        const validation = this.validate();

        if (!validation.valid) {
            await this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: validation.message,
            });
            return;
        }

        const payload = this.getPayload();
        this.props.close({ confirmed: true, payload });
    }

    /**
     * Handle cancel button click
     */
    cancel() {
        this.props.close({ confirmed: false, payload: null });
    }
}

// Register the popup in the POS popups registry
registry.category("popups").add("OpticalTestPopup", OpticalTestPopup);
