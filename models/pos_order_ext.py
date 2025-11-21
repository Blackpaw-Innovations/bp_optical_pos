# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"
    
    @api.model
    def _order_fields(self, ui_order):
        """Override to force invoice creation for optical POS."""
        order_fields = super()._order_fields(ui_order)
        
        # Get session and config
        session = self.env['pos.session'].browse(ui_order.get('pos_session_id'))
        if session and session.config_id.optical_enabled:
            # Check if order has a customer
            has_customer = bool(ui_order.get('partner_id'))
            
            # Check if order has insurance payments
            has_insurance_payment = False
            if 'statement_ids' in ui_order:
                for statement in ui_order['statement_ids']:
                    # statement is [0, 0, {values}]
                    if len(statement) == 3:
                        payment_vals = statement[2]
                        payment_method_id = payment_vals.get('payment_method_id')
                        if payment_method_id:
                            payment_method = self.env['pos.payment.method'].browse(payment_method_id)
                            if payment_method.is_insurance_method:
                                has_insurance_payment = True
                                break
            
            # Force invoice if configured globally OR if insurance payment is present
            if has_customer and (session.config_id.optical_force_invoice or has_insurance_payment):
                _logger.info('[BP Optical POS] Forcing invoice creation for order (Insurance: %s)', has_insurance_payment)
                order_fields['to_invoice'] = True
        
        return order_fields

    @api.model
    def _payment_fields(self, order, ui_paymentline):
        """Override to extract insurance data from UI payment line."""
        fields = super()._payment_fields(order, ui_paymentline)
        
        # Log the incoming UI payment line for debugging
        _logger.info('[BP Optical POS] _payment_fields UI line: %s', ui_paymentline)

        # Check for insurance data (flag OR data presence)
        if ui_paymentline.get('is_insurance') or ui_paymentline.get('insuranceData'):
            fields['is_insurance'] = True
            fields['insurance_raw_data'] = ui_paymentline.get('insuranceData')
        
        return fields

    def add_payment(self, data):
        """Override to handle insurance payment creation."""
        # Log incoming payment data for debugging
        _logger.info('[BP Optical POS] add_payment called with data keys: %s', data.keys())
        if 'insurance_raw_data' in data:
            _logger.info('[BP Optical POS] Insurance data present: %s', True)
            _logger.info('[BP Optical POS] Insurance raw data content: %s', data['insurance_raw_data'])
        
        insurance_data = data.pop('insurance_raw_data', False)
        insurance_record = False

        if insurance_data:
            # Create insurance payment record BEFORE calling super
            # This ensures validation passes if super() triggers order completion
            insurance_vals = {
                'amount': data.get('amount'),
                'insurance_company_id': insurance_data.get('insurance_company_id'),
                'policy_number': insurance_data.get('policy_number'),
                'member_number': insurance_data.get('member_number'),
                'employer': insurance_data.get('employer'),
                'notes': insurance_data.get('notes'),
            }
            
            # Create the record
            insurance_record = self._create_insurance_payment_record(insurance_vals)
            
            # Add insurance_data_id to data so it's set on the payment immediately
            data['insurance_data_id'] = insurance_record.id
            data['is_insurance'] = True # Ensure this is set too if not already

        # Call super to create the payment
        payment = super().add_payment(data)
        
        if insurance_record and payment:
            # Link back to payment (reverse link)
            insurance_record.write({'payment_id': payment.id})
            
        return payment

    def _optical_check_requirements(self):
        """
        Validate optical POS requirements before order completion.
        Raises UserError if requirements are not met.
        """
        self.ensure_one()
        
        # Skip checks if optical is not enabled
        if not self.config_id.optical_enabled:
            return
        
        # Check if customer is required
        if self.config_id.optical_require_customer and not self.partner_id:
            raise UserError(_("A customer is required for optical POS orders."))
        
        # Check if invoice is forced and customer is missing
        if self.config_id.optical_force_invoice and not self.partner_id:
            raise UserError(_(
                "This POS is configured to always create an invoice. "
                "Please select a customer before validating the order."
            ))
        
        # Check insurance payment configuration
        # Check both the line flag and the payment method configuration
        insurance_payments = self.payment_ids.filtered(
            lambda p: p.is_insurance or p.payment_method_id.is_insurance_method
        )
        
        if insurance_payments:
            # Ensure insurance journal is configured
            if not self.config_id.optical_insurance_journal_id:
                raise UserError(_(
                    "Insurance payments require an Insurance Journal to be configured "
                    "on the POS Configuration."
                ))
            
            # Ensure all insurance payments have insurance company set
            for payment in insurance_payments:
                # If the payment method is insurance, we MUST have insurance data
                if not payment.insurance_data_id or not payment.insurance_data_id.insurance_company_id:
                    raise UserError(_(
                        "Insurance details (Company, Policy, etc.) are missing for the Insurance payment. "
                        "Please edit the payment and add the required information."
                    ))
            
            # Calculate totals for validation
            insurance_total = sum(insurance_payments.mapped('amount'))
            order_total = self.amount_total
            
            # Ensure insurance total doesn't exceed order total
            if insurance_total > order_total:
                raise UserError(_(
                    "Insurance payment amount (%.2f) cannot exceed the order total (%.2f)."
                ) % (insurance_total, order_total))

    def action_pos_order_paid(self):
        """Override to add optical validation before marking order as paid."""
        # Perform optical checks for each order
        for order in self:
            order._optical_check_requirements()
        
        # Call parent method
        return super().action_pos_order_paid()

    def _apply_invoice_payments(self, is_reverse=False):
        """
        Override to prevent insurance payments from being applied to the invoice.
        This ensures the invoice remains open (unpaid) for the insurance portion.
        """
        # Strategy: Temporarily set the amount of insurance payments to 0.
        # This prevents _apply_invoice_payments from reconciling them,
        # without deleting the payment records (which causes issues due to required fields).
        
        insurance_payments_data = {}
        
        for order in self:
            if order.config_id.optical_enabled:
                # Identify insurance payments
                insurance_payments = order.payment_ids.filtered(
                    lambda p: p.is_insurance or p.payment_method_id.is_insurance_method
                )
                
                for payment in insurance_payments:
                    # Store original amount
                    insurance_payments_data[payment.id] = payment.amount
                    # Set amount to 0 to skip reconciliation
                    payment.write({'amount': 0})
        
        try:
            # Call super - it will ignore 0 amount payments
            res = super()._apply_invoice_payments(is_reverse)
        except Exception as e:
            _logger.error("Error in _apply_invoice_payments: %s", str(e))
            raise
        finally:
            # Restore original amounts
            for payment_id, amount in insurance_payments_data.items():
                payment = self.env['pos.payment'].browse(payment_id)
                if payment.exists():
                    payment.write({'amount': amount})
        
        return res

    def _generate_pos_order_invoice(self):
        """Override to ensure invoice creation for optical POS when required."""
        # Pre-validate optical requirements before invoice generation
        for order in self:
            if order.config_id.optical_enabled and order.config_id.optical_force_invoice:
                # Ensure partner exists for invoicing
                if not order.partner_id:
                    raise UserError(_(
                        "Optical POS requires invoicing. Please select a customer."
                    ))
                # Ensure the order will create an invoice
                if not order.to_invoice:
                    # Force invoice creation for optical POS
                    order.write({'to_invoice': True})
        
        # Call parent method to generate invoices
        result = super()._generate_pos_order_invoice()
        
        # Post-process invoices for insurance
        for order in self:
            if order.account_move and order.config_id.optical_enabled:
                invoice = order.account_move
                
                # Check if order has insurance payments
                insurance_payments = order.payment_ids.filtered(
                    lambda p: p.is_insurance or p.payment_method_id.is_insurance_method
                )
                
                if insurance_payments:
                    # Set insurance flags on invoice
                    invoice.write({
                        'is_insurance_invoice': True,
                        'paying_with_insurance': True,
                        'associated_patient': order.partner_id.id,
                    })
                    
                    # Link insurance payment records to this invoice
                    for payment in insurance_payments:
                        if payment.insurance_data_id:
                            payment.insurance_data_id.write({'invoice_id': invoice.id})
        
        return result
    
    def _create_insurance_payment_record(self, payment_vals):
        """
        Create an insurance payment record from POS.
        payment_vals should contain:
            - amount
            - insurance_company_id
            - policy_number (optional)
            - member_number (optional)
            - employer (optional)
            - notes (optional)
            - pos_payment_id (optional)
        """
        self.ensure_one()
        
        # Prepare values for insurance payment record
        insurance_vals = {
            'order_id': self.id,
            'amount': payment_vals.get('amount', 0.0),
            'insurance_company_id': payment_vals.get('insurance_company_id'),
            'policy_number': payment_vals.get('policy_number', ''),
            'member_number': payment_vals.get('member_number', ''),
            'employer': payment_vals.get('employer', ''),
            'notes': payment_vals.get('notes', ''),
        }
        
        # Add payment_id if provided
        if payment_vals.get('pos_payment_id'):
            insurance_vals['payment_id'] = payment_vals['pos_payment_id']
        
        # Add invoice_id if invoice already exists
        if self.account_move:
            insurance_vals['invoice_id'] = self.account_move.id
        
        # Create insurance payment record
        insurance_payment = self.env['optical.insurance.payment'].create(insurance_vals)
        
        return insurance_payment

    def _create_invoice(self, move_vals):
        """Override to apply analytic distribution and set insurance journal."""
        # Apply location analytic to invoice line values before creation
        self._apply_location_analytic_to_move_vals(move_vals)
        
        # Set branch from POS config
        if self.config_id.optical_enabled and self.config_id.optical_branch_id:
            move_vals['branch_id'] = self.config_id.optical_branch_id.id
        
        # Check for insurance payments and set specific journal if configured
        if self.config_id.optical_enabled and self.config_id.optical_insurance_journal_id:
            insurance_payments = self.payment_ids.filtered(
                lambda p: p.is_insurance or p.payment_method_id.is_insurance_method
            )
            if insurance_payments:
                move_vals['journal_id'] = self.config_id.optical_insurance_journal_id.id
        
        # Call parent method to create the invoice
        invoice = super()._create_invoice(move_vals)
        
        return invoice

    def _apply_location_analytic_to_move_vals(self, move_vals):
        """Apply the analytic account from POS config's branch or location to invoice line values."""
        # Get the analytic account from the POS config's location
        if not self.session_id or not self.session_id.config_id:
            return
        
        pos_config = self.session_id.config_id
        analytic_account = False

        # 1. Check Optical Branch Analytic Account
        if pos_config.optical_enabled and pos_config.optical_branch_id and pos_config.optical_branch_id.analytic_account_id:
            analytic_account = pos_config.optical_branch_id.analytic_account_id
        
        # 2. Fallback to Stock Location Analytic Account
        if not analytic_account:
            location = pos_config.picking_type_id.default_location_dest_id
            if location and location.analytic_account_id:
                analytic_account = location.analytic_account_id
        
        if not analytic_account:
            return
        
        analytic_distribution = {str(analytic_account.id): 100}
        
        # Apply analytic distribution to invoice line values
        if 'invoice_line_ids' in move_vals:
            for line_vals in move_vals['invoice_line_ids']:
                # line_vals is typically a tuple like (0, 0, {values})
                if isinstance(line_vals, (list, tuple)) and len(line_vals) == 3:
                    line_data = line_vals[2]
                    # Only apply to product lines (check if it has product_id)
                    if isinstance(line_data, dict) and line_data.get('product_id'):
                        line_data['analytic_distribution'] = analytic_distribution

    def _apply_location_analytic_to_invoice(self, invoice):
        """Apply the analytic account from the POS config's branch or stock location to all invoice lines."""
        # Get the analytic account from the POS config's location
        if not self.session_id or not self.session_id.config_id:
            return
        
        pos_config = self.session_id.config_id
        analytic_account = False

        # 1. Check Optical Branch Analytic Account
        if pos_config.optical_enabled and pos_config.optical_branch_id and pos_config.optical_branch_id.analytic_account_id:
            analytic_account = pos_config.optical_branch_id.analytic_account_id
        
        # 2. Fallback to Stock Location Analytic Account
        if not analytic_account:
            location = pos_config.picking_type_id.default_location_dest_id
            if location and location.analytic_account_id:
                analytic_account = location.analytic_account_id
        
        if not analytic_account:
            return
        
        # Apply analytic distribution to invoice lines
        for move_line in invoice.invoice_line_ids:
            # Only apply to product lines (not tax, section, or note lines)
            if move_line.display_type is False and move_line.product_id:
                # In Odoo 17, analytic_distribution is a JSON field with format {account_id: percentage}
                move_line.analytic_distribution = {str(analytic_account.id): 100}

    @api.model
    def optical_create_test(self, order_uid, partner_id, test_vals):
        """
        Create a full optical.test record from POS popup.
        
        Args:
            order_uid: POS order UID (for reference/logging)
            partner_id: Patient partner ID (required)
            test_vals: Dictionary containing all test fields:
                - sphere_od, cylinder_od, axis_od, prism_od, add_od, va_od, pd_od
                - sphere_os, cylinder_os, axis_os, prism_os, add_os, va_os, pd_os
                - notes, valid_until (optional)
        
        Returns:
            Dictionary with test_id on success, or error message
        """
        if not partner_id:
            return {"error": "No customer specified.", "success": False}
        
        try:
            # Verify patient exists
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {"error": "Invalid customer ID.", "success": False}
            
            # Get current user as optometrist
            current_user = self.env.user
            
            # Get branch from POS config if available
            branch_id = False
            if order_uid:
                order = self.search([('pos_reference', '=', order_uid)], limit=1)
                if order and order.config_id and order.config_id.optical_branch_id:
                    branch_id = order.config_id.optical_branch_id.id
            
            # Prepare values for optical.test creation
            vals = {
                'patient_id': partner_id,
                'test_date': fields.Datetime.now(),
                'optometrist_id': current_user.id,
                'company_id': self.env.company.id,
            }
            
            # Add branch if available
            if branch_id:
                vals['branch_id'] = branch_id
            
            # Map OD (Right Eye) fields
            if test_vals.get('sphere_od') is not False:
                vals['sphere_od'] = test_vals['sphere_od']
            if test_vals.get('cylinder_od') is not False:
                vals['cylinder_od'] = test_vals['cylinder_od']
            if test_vals.get('axis_od') is not False:
                vals['axis_od'] = test_vals['axis_od']
            if test_vals.get('prism_od') is not False:
                vals['prism_od'] = test_vals['prism_od']
            if test_vals.get('add_od') is not False:
                vals['add_od'] = test_vals['add_od']
            if test_vals.get('va_od'):
                vals['va_od'] = test_vals['va_od']
            if test_vals.get('pd_od') is not False:
                vals['pd_od'] = test_vals['pd_od']
            
            # Map OS (Left Eye) fields
            if test_vals.get('sphere_os') is not False:
                vals['sphere_os'] = test_vals['sphere_os']
            if test_vals.get('cylinder_os') is not False:
                vals['cylinder_os'] = test_vals['cylinder_os']
            if test_vals.get('axis_os') is not False:
                vals['axis_os'] = test_vals['axis_os']
            if test_vals.get('prism_os') is not False:
                vals['prism_os'] = test_vals['prism_os']
            if test_vals.get('add_os') is not False:
                vals['add_os'] = test_vals['add_od']
            if test_vals.get('va_os'):
                vals['va_os'] = test_vals['va_os']
            if test_vals.get('pd_os') is not False:
                vals['pd_os'] = test_vals['pd_os']
            
            # Map additional fields
            if test_vals.get('notes'):
                vals['notes'] = test_vals['notes']
            
            # Handle valid_until if provided (otherwise computed field will handle it)
            if test_vals.get('valid_until'):
                # Note: validity_until is computed from test_date by default,
                # but we can still set it if a custom value is provided
                pass  # Let the computed field handle it
            
            # Create the optical test record
            test = self.env['optical.test'].sudo().create(vals)
            
            return {
                "test_id": test.id,
                "test_name": test.name,
                "success": True
            }
            
        except Exception as e:
            _logger.error("Error creating optical test from POS: %s", str(e))
            return {
                "error": str(e),
                "success": False
            }
    
    @api.model
    def optical_get_patient_tests(self, partner_id, limit=10):
        """
        Retrieve optical test history for a patient to display in POS.
        
        Args:
            partner_id: Patient partner ID
            limit: Maximum number of tests to return (default 10)
        
        Returns:
            List of dictionaries with test summary data
        """
        if not partner_id:
            return []
        
        try:
            tests = self.env['optical.test'].search(
                [('patient_id', '=', partner_id)],
                order='test_date desc',
                limit=limit
            )
            
            result = []
            for test in tests:
                result.append({
                    'id': test.id,
                    'name': test.name,
                    'test_date': test.test_date.strftime('%Y-%m-%d %H:%M') if test.test_date else '',
                    'optometrist': test.optometrist_id.name if test.optometrist_id else '',
                    'branch': test.branch_id.name if test.branch_id else '',
                    'stage_id': test.stage_id.id if test.stage_id else False,
                    'stage_name': test.stage_id.name if test.stage_id else 'Draft',
                    # Right Eye (OD)
                    'sphere_od': test.sphere_od if test.sphere_od else 0,
                    'cylinder_od': test.cylinder_od if test.cylinder_od else 0,
                    'axis_od': test.axis_od if test.axis_od else 0,
                    'add_od': test.add_od if test.add_od else 0,
                    'va_od': test.va_od or '',
                    'pd_od': test.pd_od if test.pd_od else 0,
                    # Left Eye (OS)
                    'sphere_os': test.sphere_os if test.sphere_os else 0,
                    'cylinder_os': test.cylinder_os if test.cylinder_os else 0,
                    'axis_os': test.axis_os if test.axis_os else 0,
                    'add_os': test.add_os if test.add_os else 0,
                    'va_os': test.va_os or '',
                    'pd_os': test.pd_os if test.pd_os else 0,
                    # Additional
                    'notes': test.notes or '',
                    'validity_until': test.validity_until.strftime('%Y-%m-%d') if test.validity_until else '',
                })
            
            return result
            
        except Exception as e:
            _logger.error("Error fetching optical tests for patient %s: %s", partner_id, str(e))
            return []
    
    @api.model
    def optical_get_patient_tests_full(self, partner_id, limit=10):
        """
        Retrieve full optical test details for a patient (for comprehensive view in POS).
        
        Args:
            partner_id: Patient partner ID
            limit: Maximum number of tests to return (default 10)
        
        Returns:
            List of dictionaries with complete test data
        """
        if not partner_id:
            return []
        
        try:
            tests = self.env['optical.test'].search(
                [('patient_id', '=', partner_id)],
                order='test_date desc',
                limit=limit
            )
            
            result = []
            for test in tests:
                result.append({
                    'id': test.id,
                    'name': test.name,
                    'patient_name': test.patient_id.name if test.patient_id else '',
                    'test_date': test.test_date.strftime('%Y-%m-%d %H:%M') if test.test_date else '',
                    'optometrist_name': test.optometrist_id.name if test.optometrist_id else '',
                    'optician_name': test.optician_id.name if test.optician_id else '',
                    'branch': test.branch_id.name if test.branch_id else '',
                    'stage_id': test.stage_id.id if test.stage_id else False,
                    'stage_name': test.stage_id.name if test.stage_id else 'Draft',
                    'validity_until': test.validity_until.strftime('%Y-%m-%d') if test.validity_until else '',
                    'age': test.age or 0,
                    'phone_number': test.phone_number or '',
                    # Right Eye (OD) - Complete
                    'sphere_od': test.sphere_od if test.sphere_od else 0,
                    'cylinder_od': test.cylinder_od if test.cylinder_od else 0,
                    'axis_od': test.axis_od if test.axis_od else 0,
                    'prism_od': test.prism_od if test.prism_od else 0,
                    'add_od': test.add_od if test.add_od else 0,
                    'va_od': test.va_od or '',
                    'pd_od': test.pd_od if test.pd_od else 0,
                    'height_od': test.height_od if test.height_od else 0,
                    # Left Eye (OS) - Complete
                    'sphere_os': test.sphere_os if test.sphere_os else 0,
                    'cylinder_os': test.cylinder_os if test.cylinder_os else 0,
                    'axis_os': test.axis_os if test.axis_os else 0,
                    'prism_os': test.prism_os if test.prism_os else 0,
                    'add_os': test.add_os if test.add_os else 0,
                    'va_os': test.va_os or '',
                    'pd_os': test.pd_os if test.pd_os else 0,
                    'height_os': test.height_os if test.height_os else 0,
                    # Lens & Frame Details
                    'lens_type': test.lens_type_id.name if test.lens_type_id else '',
                    'coating': test.coating_id.name if test.coating_id else '',
                    'index': test.index_id.name if test.index_id else '',
                    'material': test.material_id.name if test.material_id else '',
                    'frame': test.frame_id.name if test.frame_id else '',
                    'needs_new_lens': test.needs_new_lens or False,
                    'needs_new_frame': test.needs_new_frame or False,
                    # Insurance
                    'insurance_company': test.insurance_company_id.name if test.insurance_company_id else '',
                    # Notes & Follow-up
                    'notes': test.notes or '',
                    'follow_up_required': test.follow_up_required or False,
                    'follow_up_date': test.follow_up_date.strftime('%Y-%m-%d') if test.follow_up_date else '',
                    'workshop_order_number': test.workshop_order_number or '',
                })
            
            return result
            
        except Exception as e:
            _logger.error("Error fetching full optical tests for patient %s: %s", partner_id, str(e))
            return []
    
    @api.model
    def optical_change_test_stage(self, test_id, stage_name):
        """
        Change the stage of an optical test from POS.
        
        Args:
            test_id: Optical test ID
            stage_name: Name of the target stage (e.g., 'Test Room', 'Fitting', 'Ready For collection', 'Completed')
        
        Returns:
            Dictionary with success status and new stage info
        """
        if not test_id:
            return {"error": "No test specified.", "success": False}
        
        if not stage_name:
            return {"error": "No stage specified.", "success": False}
        
        try:
            # Get the test
            test = self.env['optical.test'].browse(test_id)
            if not test.exists():
                return {"error": "Test not found.", "success": False}
            
            # Find the target stage
            stage = self.env['optical.prescription.stage'].search([
                ('name', '=', stage_name)
            ], limit=1)
            
            if not stage:
                return {"error": f"Stage '{stage_name}' not found.", "success": False}
            
            # Update the stage
            test.write({'stage_id': stage.id})
            
            return {
                "success": True,
                "test_id": test.id,
                "test_name": test.name,
                "stage_id": stage.id,
                "stage_name": stage.name,
                "message": f"Test {test.name} moved to {stage.name}"
            }
            
        except Exception as e:
            _logger.error("Error changing test stage: %s", str(e))
            return {"error": str(e), "success": False}
    
    @api.model
    def optical_get_stages(self):
        """
        Get list of available optical prescription stages for POS.
        
        Returns:
            List of dictionaries with stage info
        """
        try:
            stages = self.env['optical.prescription.stage'].search([], order='sequence asc')
            return [{
                'id': stage.id,
                'name': stage.name,
                'sequence': stage.sequence,
                'is_final': stage.is_final,
            } for stage in stages]
        except Exception as e:
            _logger.error("Error fetching optical stages: %s", str(e))
            return []
    
    @api.model
    def optical_register_balance_payment(self, invoice_id, payment_vals):
        """
        Register a balance settlement payment for an optical POS invoice.
        
        This method allows registering additional payments against an invoice
        after the initial POS order was completed (e.g., deposit scenario).
        
        Args:
            invoice_id: ID of the invoice to settle
            payment_vals: Dictionary containing:
                - amount: Payment amount (required)
                - journal_id: Payment journal ID (required)
                - payment_date: Payment date (optional, defaults to today)
                - ref: Payment reference (optional)
        
        Returns:
            Dictionary with payment info on success, or error message
        """
        if not invoice_id:
            return {"error": "No invoice specified.", "success": False}
        
        if not payment_vals.get('amount') or payment_vals['amount'] <= 0:
            return {"error": "Invalid payment amount.", "success": False}
        
        if not payment_vals.get('journal_id'):
            return {"error": "Payment journal is required.", "success": False}
        
        try:
            # Get invoice
            invoice = self.env['account.move'].browse(invoice_id)
            if not invoice.exists():
                return {"error": "Invoice not found.", "success": False}
            
            if invoice.state != 'posted':
                return {"error": "Invoice is not posted.", "success": False}
            
            if invoice.payment_state == 'paid':
                return {
                    "error": "Invoice is already fully paid.",
                    "success": False,
                    "payment_state": "paid"
                }
            
            # Get payment journal
            journal = self.env['account.journal'].browse(payment_vals['journal_id'])
            if not journal.exists():
                return {"error": "Payment journal not found.", "success": False}
            
            # Determine payment date
            payment_date = payment_vals.get('payment_date', fields.Date.today())
            if isinstance(payment_date, str):
                payment_date = fields.Date.from_string(payment_date)
            
            # Create payment record
            payment_obj_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice.partner_id.id,
                'amount': payment_vals['amount'],
                'currency_id': invoice.currency_id.id,
                'journal_id': journal.id,
                'date': payment_date,
                'ref': payment_vals.get('ref', _('Balance Payment - %s') % invoice.name),
                'payment_method_line_id': journal.inbound_payment_method_line_ids[0].id if journal.inbound_payment_method_line_ids else False,
            }
            
            payment = self.env['account.payment'].sudo().create(payment_obj_vals)
            payment.action_post()
            
            # Reconcile with invoice
            payment_line = payment.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable' and l.credit > 0
            )
            
            invoice_line = invoice.line_ids.filtered(
                lambda l: (
                    l.account_id.account_type == 'asset_receivable' and 
                    l.debit > 0 and
                    not l.reconciled
                )
            )
            
            if payment_line and invoice_line:
                (payment_line + invoice_line).reconcile()
            
            # Refresh invoice to get updated payment state
            invoice.invalidate_recordset(['payment_state', 'amount_residual'])
            
            return {
                "success": True,
                "payment_id": payment.id,
                "payment_name": payment.name,
                "invoice_payment_state": invoice.payment_state,
                "invoice_amount_residual": invoice.amount_residual,
            }
            
        except Exception as e:
            _logger.error("Error registering balance payment: %s", str(e))
            return {
                "error": str(e),
                "success": False
            }
    
    @api.model
    def optical_finalize_payments(self, order_uid):
        """
        Finalize payments for an optical POS order.
        
        This method is called after order completion to:
        1. Update all insurance payment records with invoice reference
        2. Calculate and return payment summary
        3. Verify invoice state
        
        Args:
            order_uid: POS order UID (pos_reference)
        
        Returns:
            Dictionary with payment summary and invoice details
        """
        if not order_uid:
            return {"error": "No order specified.", "success": False}
        
        try:
            # Find order by reference
            order = self.search([('pos_reference', '=', order_uid)], limit=1)
            if not order:
                return {"error": "Order not found.", "success": False}
            
            invoice = order.account_move
            if not invoice:
                return {
                    "error": "No invoice found for this order.",
                    "success": False,
                    "has_invoice": False
                }
            
            # Update insurance payment records
            insurance_payments = order.payment_ids.filtered(lambda p: p.is_insurance)
            for payment in insurance_payments:
                if payment.insurance_data_id and not payment.insurance_data_id.invoice_id:
                    payment.insurance_data_id.write({'invoice_id': invoice.id})
            
            # Calculate payment breakdown
            customer_payments = order.payment_ids.filtered(lambda p: not p.is_insurance)
            insurance_payments_total = sum(insurance_payments.mapped('amount'))
            customer_payments_total = sum(customer_payments.mapped('amount'))
            
            # Get receivable amounts from invoice
            customer_receivables = invoice.line_ids.filtered(
                lambda l: (
                    l.account_id.account_type == 'asset_receivable' and
                    l.partner_id == order.partner_id and
                    l.debit > 0
                )
            )
            customer_due = sum(customer_receivables.mapped('amount_residual'))
            
            insurance_receivables = invoice.line_ids.filtered(
                lambda l: (
                    l.account_id.account_type == 'asset_receivable' and
                    l.partner_id != order.partner_id and
                    l.debit > 0
                )
            )
            insurance_due = sum(insurance_receivables.mapped('amount_residual'))
            
            return {
                "success": True,
                "has_invoice": True,
                "invoice_id": invoice.id,
                "invoice_number": invoice.name,
                "invoice_state": invoice.state,
                "payment_state": invoice.payment_state,
                "invoice_total": invoice.amount_total,
                "amount_residual": invoice.amount_residual,
                "customer_due": customer_due,
                "insurance_due": insurance_due,
                "customer_payments": customer_payments_total,
                "insurance_payments": insurance_payments_total,
                "payment_count": len(order.payment_ids),
                "insurance_payment_count": len(insurance_payments),
            }
            
        except Exception as e:
            _logger.error("Error finalizing payments for order %s: %s", order_uid, str(e))
            return {
                "error": str(e),
                "success": False
            }

