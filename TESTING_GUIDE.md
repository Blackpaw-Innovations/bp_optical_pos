# BP Optical POS - Testing Guide

**Module**: bp_optical_pos v17.0.1.0.0  
**Date**: November 2025  
**Status**: Production Ready (Stages 1-8 Complete)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Test Scenarios](#test-scenarios)
4. [Error Scenarios](#error-scenarios)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Modules
- ✅ `point_of_sale` (Odoo Community)
- ✅ `account` (Odoo Community)
- ✅ `bp_optical_core` (installed and configured)
- ✅ `bp_optical_pos` (this module)

### Database Setup
```bash
# Ensure module is installed on correct database
sudo -u odoo /opt/odoo/odoo-bin -c /etc/odoo.conf -d [YOUR_DB] -u bp_optical_pos --stop-after-init
sudo systemctl restart odoo
```

### User Permissions
- User must be in group: **Optical POS / User** (minimum)
- For configuration: **Optical POS / Manager**

---

## Initial Setup

### Step 1: Configure POS Settings

1. Navigate to: **Point of Sale → Configuration → Point of Sale**
2. Open your POS configuration
3. Scroll to **Optical Settings** section
4. Configure the following:

| Setting | Description | Required |
|---------|-------------|----------|
| **Optical Enabled** | Enable optical features | ✓ Yes |
| **Optical Branch** | Select branch from bp_optical_core | ✓ Yes |
| **Force Invoice** | Always create invoice for optical orders | Recommended |
| **Require Customer** | Customer must be selected | Recommended |
| **Insurance Journal** | Journal for insurance receivables | ✓ Yes (if using insurance) |

5. Click **Save**

### Step 2: Configure Analytic Account on Location

1. Navigate to: **Inventory → Configuration → Locations**
2. Find your POS location (e.g., "Shop" under your warehouse)
3. Set **Analytic Account** field (e.g., "Branch A Analytics")
4. Click **Save**

**Why**: Invoice lines will inherit this analytic distribution automatically.

### Step 3: Create Insurance Payment Method (Optional)

1. Navigate to: **Point of Sale → Configuration → Payment Methods**
2. Click **Create**
3. Configure:
   - **Name**: "Insurance Payment"
   - **Journal**: Select or create insurance journal
   - **☑ Insurance Payment Method**: Enable this checkbox
4. Click **Save**
5. Add to your POS Configuration:
   - Edit POS config → **Payment Methods** tab
   - Add "Insurance Payment"
   - Save

### Step 4: Verify Insurance Company Setup

1. Navigate to: **Optical → Configuration → Insurance Companies**
2. Verify at least one insurance company exists
3. Check **Partner** field - should auto-create if empty
4. Note: Partner is needed for invoice receivable split

---

## Test Scenarios

### TEST 1: Basic Order with Customer & Invoice

**Objective**: Verify basic optical POS workflow with customer requirement and auto-invoice.

**Prerequisites**:
- ✅ Optical Enabled
- ✅ Force Invoice enabled
- ✅ Require Customer enabled

**Steps**:

1. Open POS session
2. Add products to cart (e.g., Frames - KES 5,000)
3. Try to proceed to payment WITHOUT customer

**Expected Result**: Error popup: "A customer is required for optical POS orders."

4. Click **Customer** button
5. Select/Create customer
6. Click **Payment**
7. Add cash payment: KES 5,000
8. Click **Validate**

**Expected Results**:
- ✓ Order completes successfully
- ✓ Receipt prints/displays
- ✓ Invoice automatically generated
- ✓ Invoice Partner = selected customer
- ✓ Invoice State = Posted
- ✓ Payment State = Paid (full payment)

**Verification**:
```
Navigate to: Accounting → Customers → Invoices
Find latest invoice:
- Amount Total: KES 5,000
- Partner: [Selected Customer]
- Payment State: Paid
- Journal Items tab:
  * Revenue line (credit): KES 5,000
  * Receivable line (debit): KES 5,000
  * Payment line (credit): KES 5,000
  * Net Balance: 0
```

---

### TEST 2: Analytic Distribution on Invoice Lines

**Objective**: Verify invoice lines inherit analytic from POS location.

**Prerequisites**:
- ✅ POS location has Analytic Account set

**Steps**:

1. Open POS session
2. Add product to cart
3. Select customer
4. Complete payment
5. Navigate to generated invoice
6. Open invoice line
7. Click **Analytic** tab

**Expected Results**:
- ✓ Analytic Distribution shows: 100% to location's analytic account
- ✓ Format: `{"[account_id]": 100}`
- ✓ All product lines have same analytic

**Technical Verification**:
```sql
SELECT 
    aml.name,
    aml.analytic_distribution,
    aal.name as analytic_account
FROM account_move_line aml
JOIN account_move am ON aml.move_id = am.id
JOIN pos_order po ON am.id = po.account_move
LEFT JOIN account_analytic_account aal ON aal.id::text = any(string_to_array(trim(both '{}' from aml.analytic_distribution::text), ':'))
WHERE po.id = [ORDER_ID]
AND aml.display_type = false;
```

---

### TEST 3: Insurance Payment with Metadata Capture

**Objective**: Test insurance payment popup and metadata storage.

**Prerequisites**:
- ✅ Insurance payment method configured
- ✅ Insurance company exists in bp_optical_core

**Steps**:

1. Open POS session
2. Add products totaling KES 10,000
3. Select customer
4. Click **Payment**
5. Select **Insurance Payment** method
6. Enter amount: KES 7,000

**Expected Result**: Popup appears with title "Insurance Payment Details"

7. Fill in popup:
   - **Insurance Company**: Select from dropdown
   - **Policy Number**: "POL-2025-12345"
   - **Member Number**: "MEM-67890"
   - **Employer**: "ABC Corporation"
   - **Notes**: "Pre-approved claim"
8. Click **Confirm**

**Expected Result**: 
- ✓ Popup closes
- ✓ Payment line added: KES 7,000
- ✓ Insurance icon/indicator visible

9. Add Cash payment: KES 3,000
10. Click **Validate**

**Expected Results**:
- ✓ Order completes
- ✓ Invoice generated
- ✓ Payment State: Paid

**Database Verification**:
```sql
-- Check insurance payment record
SELECT 
    oip.order_id,
    oip.amount,
    oic.name as insurance_company,
    oip.policy_number,
    oip.member_number,
    oip.employer,
    oip.notes,
    oip.invoice_id
FROM optical_insurance_payment oip
JOIN optical_insurance_company oic ON oip.insurance_company_id = oic.id
JOIN pos_order po ON oip.order_id = po.id
WHERE po.id = [ORDER_ID];

-- Expected output:
-- amount: 7000.00
-- policy_number: POL-2025-12345
-- member_number: MEM-67890
-- employer: ABC Corporation
-- invoice_id: [INVOICE_ID]
```

---

### TEST 4: Invoice Receivable Split (Customer vs Insurance)

**Objective**: Verify invoice has two separate receivable lines for customer and insurance.

**Prerequisites**:
- ✅ Insurance payment method configured
- ✅ Insurance journal configured on POS

**Steps**:

1. Create order with total: KES 10,000
2. Select customer
3. Add payments:
   - Insurance: KES 7,000 (with full details)
   - Cash: KES 3,000
4. Validate order
5. Navigate to generated invoice
6. Click **Journal Items** tab

**Expected Results**:

**Revenue Lines** (Credit side):
- Product line(s): Total KES 10,000 credit

**Receivable Lines** (Debit side):
- Line 1: Customer Receivable
  - Partner: [Customer]
  - Account: Account Receivable (e.g., 1200)
  - Debit: KES 3,000
  - Reconciled: Yes (with cash payment)
  
- Line 2: Insurance Receivable
  - Partner: [Insurance Company Partner] (auto-created)
  - Account: Insurance Receivable Account
  - Debit: KES 7,000
  - Reconciled: Yes (with insurance payment)

**Payment Lines** (Credit side):
- Cash payment: KES 3,000 credit (reconciles Line 1)
- Insurance payment: KES 7,000 credit (reconciles Line 2)

**Total Balance**: 0 (fully reconciled)

**SQL Verification**:
```sql
SELECT 
    aml.name,
    aml.partner_id,
    rp.name as partner_name,
    aa.name as account_name,
    aml.debit,
    aml.credit,
    aml.amount_residual,
    CASE WHEN aml.reconciled THEN 'Yes' ELSE 'No' END as reconciled
FROM account_move_line aml
JOIN account_move am ON aml.move_id = am.id
JOIN pos_order po ON am.id = po.account_move
LEFT JOIN res_partner rp ON aml.partner_id = rp.id
JOIN account_account aa ON aml.account_id = aa.id
WHERE po.id = [ORDER_ID]
AND aa.account_type = 'asset_receivable'
ORDER BY aml.debit DESC;

-- Expected: 2 receivable lines with different partners
```

---

### TEST 5: Optical Test Creation from POS

**Objective**: Create optical test with full OD/OS measurements.

**Prerequisites**:
- ✅ Customer selected in POS
- ✅ Optical Branch configured

**Steps**:

1. Open POS session
2. Select customer
3. Click **Optical Test** button (top right header)

**Expected Result**: Popup "Optical Test" appears with:
- Patient info section at top
- Two-column layout: OD (Blue) | OS (Green)
- Fields visible for both eyes
- Notes textarea
- Valid Until date field

4. Fill measurements:

**OD (Right Eye)**:
- Sphere: -2.50
- Cylinder: -0.75
- Axis: 180
- Prism: 0.25
- Add: 1.50
- Visual Acuity: 20/20
- PD: 32.0

**OS (Left Eye)**:
- Sphere: -2.25
- Cylinder: -1.00
- Axis: 175
- Prism: 0.00
- Add: 1.50
- Visual Acuity: 20/25
- PD: 31.5

5. Enter **Notes**: "Patient reports slight headache. Recommended progressive lenses."
6. Click **Create Test**

**Expected Result**: Success popup with test ID (e.g., "OT/2025/00123")

**Verification**:
```
Navigate to: Optical → Tests
Filter: Latest first
Open latest test:
- Patient: [Selected customer]
- Test Date: Today
- Optometrist: [Current user]
- Branch: [POS Branch]
- Sphere OD: -2.50
- Cylinder OD: -0.75
- Axis OD: 180
- ... (all values match)
- Notes: Contains entered text
- Validity Until: Auto-calculated (2 years from test date)
```

**SQL Verification**:
```sql
SELECT 
    ot.name as test_number,
    rp.name as patient,
    ot.test_date,
    ot.sphere_od, ot.cylinder_od, ot.axis_od,
    ot.sphere_os, ot.cylinder_os, ot.axis_os,
    ot.va_od, ot.va_os,
    ot.pd_od, ot.pd_os,
    ot.notes,
    ot.validity_until
FROM optical_test ot
JOIN res_partner rp ON ot.patient_id = rp.id
WHERE ot.id = [TEST_ID];
```

---

### TEST 6: Deposit Scenario (Partial Payment)

**Objective**: Process order with partial payment, invoice remains open.

**Prerequisites**:
- ✅ Force Invoice enabled

**Steps**:

1. Open POS session
2. Add products totaling KES 10,000
3. Select customer
4. Click **Payment**
5. Add cash payment: KES 3,000 (30% deposit)
6. Click **Validate**

**Expected Results**:
- ✓ Order completes successfully
- ✓ Invoice generated immediately
- ✓ Invoice Amount Total: KES 10,000
- ✓ Invoice Payment State: **Partial**
- ✓ Invoice Amount Due: KES 7,000

**Verification**:
```
Navigate to invoice:
- Payment State badge: "Partial" (orange/yellow)
- Amount Total: KES 10,000
- Amount Due: KES 7,000
- Journal Items:
  * Receivable (debit): KES 10,000
  * Payment (credit): KES 3,000
  * Balance: KES 7,000 unreconciled
```

**Test Balance Settlement** (Continue from above):

7. Use RPC method to settle balance (or use Odoo UI to register payment)

**Via Developer Console** (F12):
```javascript
await odoo.__DEBUG__.services['rpc']({
    model: 'pos.order',
    method: 'optical_register_balance_payment',
    args: [[INVOICE_ID], {
        amount: 7000,
        journal_id: [CASH_JOURNAL_ID],
        payment_date: '2025-11-17',
        ref: 'Balance settlement'
    }]
});
```

**Expected Response**:
```json
{
    "success": true,
    "payment_id": [NEW_PAYMENT_ID],
    "payment_name": "BNK1/2025/00XXX",
    "invoice_payment_state": "paid",
    "invoice_amount_residual": 0.0
}
```

8. Refresh invoice

**Expected Results**:
- ✓ Payment State: **Paid** (green)
- ✓ Amount Due: KES 0
- ✓ All receivable lines reconciled

---

### TEST 7: Mixed Payment Types

**Objective**: Test multiple payment methods in single order.

**Steps**:

1. Create order totaling KES 15,000
2. Select customer
3. Add multiple payments:
   - Cash: KES 5,000
   - Card (M-Pesa): KES 4,000
   - Insurance: KES 6,000 (with metadata)
4. Validate order

**Expected Results**:
- ✓ Order completes
- ✓ Invoice has 3 receivable lines:
  - Customer receivable: KES 9,000 (cash + card)
  - Insurance receivable: KES 6,000
- ✓ All reconciled correctly
- ✓ Payment state: Paid

**Verification**: Check invoice journal items show all 3 payments with proper reconciliation.

---

### TEST 8: Finalize Payments RPC

**Objective**: Retrieve payment summary after order completion.

**Steps**:

1. Complete order with mixed payments (Test 7)
2. Note the POS order reference (e.g., "Order 00001-001-0001")
3. Call RPC method:

```javascript
await odoo.__DEBUG__.services['rpc']({
    model: 'pos.order',
    method: 'optical_finalize_payments',
    args: ['Order 00001-001-0001']
});
```

**Expected Response**:
```json
{
    "success": true,
    "has_invoice": true,
    "invoice_id": 123,
    "invoice_number": "INV/2025/00456",
    "invoice_state": "posted",
    "payment_state": "paid",
    "invoice_total": 15000.0,
    "amount_residual": 0.0,
    "customer_due": 0.0,
    "insurance_due": 0.0,
    "customer_payments": 9000.0,
    "insurance_payments": 6000.0,
    "payment_count": 3,
    "insurance_payment_count": 1
}
```

**Validation**:
- ✓ All totals match order
- ✓ Payment breakdown correct
- ✓ No residual amounts

---

## Error Scenarios

### ERROR 1: Missing Customer with Require Customer

**Trigger**: Try to validate order without customer when "Require Customer" is enabled.

**Expected Error**: 
```
UserError: A customer is required for optical POS orders.
```

**Resolution**: Select customer before validating.

---

### ERROR 2: Insurance Without Journal Configuration

**Setup**:
1. Add insurance payment to order
2. Insurance Journal NOT configured on POS

**Expected Error**:
```
UserError: Insurance payments require an Insurance Journal to be configured on the POS Configuration.
```

**Resolution**: 
1. Navigate to POS Configuration
2. Set **Insurance Journal** field
3. Save and retry

---

### ERROR 3: Insurance Amount Exceeds Order Total

**Setup**:
1. Order total: KES 5,000
2. Try to add insurance payment: KES 7,000

**Expected Error**:
```
UserError: Insurance payment amount (7000.00) cannot exceed the order total (5000.00).
```

**Resolution**: Reduce insurance payment to ≤ order total.

---

### ERROR 4: Missing Insurance Company

**Setup**:
1. Insurance payment method used
2. Insurance company not selected in popup

**Expected Error**:
```
UserError: All insurance payments must have an insurance company specified.
```

**Resolution**: Select insurance company in popup before confirming.

---

### ERROR 5: No Customer for Optical Test

**Trigger**: Click Optical Test button without customer selected.

**Expected Error Popup**: 
```
No Customer Selected
Please select a customer before creating an optical test.
```

**Resolution**: Select customer first, then click Optical Test.

---

### ERROR 6: Balance Payment on Paid Invoice

**Setup**: Try to register balance payment on already fully paid invoice.

**Expected Response**:
```json
{
    "error": "Invoice is already fully paid.",
    "success": false,
    "payment_state": "paid"
}
```

**Resolution**: This is expected behavior - invoice doesn't need additional payment.

---

### ERROR 7: Optical Test Validation

**Setup**: Try to create optical test with NO measurements.

**Expected Error Popup**:
```
Validation Error
Please enter at least one measurement for OD or OS.
```

**Resolution**: Enter at least one field for OD or OS before submitting.

---

## Troubleshooting

### Issue: Column `is_insurance_method` does not exist

**Cause**: Module not upgraded on correct database.

**Solution**:
```bash
# Verify your database name (check URL or login screen)
# Upgrade module on correct database
sudo -u odoo /opt/odoo/odoo-bin -c /etc/odoo.conf -d [YOUR_DATABASE] -u bp_optical_pos --stop-after-init
sudo systemctl restart odoo

# Clear browser cache
# Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R)
```

**Verification**:
```sql
-- Check if column exists
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'pos_payment_method' 
AND column_name = 'is_insurance_method';
```

---

### Issue: Insurance Popup Not Appearing

**Checks**:
1. ✓ Payment method has "Insurance Payment Method" checkbox enabled
2. ✓ JavaScript assets loaded (check Network tab in browser dev tools)
3. ✓ Browser cache cleared
4. ✓ No JS errors in console (F12)

**Solution**:
```bash
# Force asset rebuild
sudo -u odoo /opt/odoo/odoo-bin -c /etc/odoo.conf -d [DB] --stop-after-init
sudo systemctl restart odoo
```

Then clear browser cache completely.

---

### Issue: Invoice Not Splitting Receivables

**Checks**:
1. ✓ Insurance journal configured on POS config
2. ✓ Insurance payment properly marked (is_insurance = True)
3. ✓ Insurance company has partner_id (auto-created)

**Debug**:
```sql
-- Check POS payment flags
SELECT 
    pp.id,
    pp.amount,
    pp.is_insurance,
    pp.insurance_data_id,
    ppm.name as payment_method
FROM pos_payment pp
JOIN pos_payment_method ppm ON pp.payment_method_id = ppm.id
WHERE pp.pos_order_id = [ORDER_ID];

-- Check if insurance payment record exists
SELECT * FROM optical_insurance_payment 
WHERE order_id = [ORDER_ID];
```

**Solution**: Check Odoo logs for errors during `_split_invoice_receivable`:
```bash
sudo journalctl -u odoo -n 100 | grep -i "split\|insurance"
```

---

### Issue: Optical Test Not Created

**Checks**:
1. ✓ Customer selected in POS
2. ✓ At least one measurement entered
3. ✓ No browser console errors

**Debug**: Check RPC response in Network tab (F12):
```json
// Successful response
{
    "test_id": 123,
    "test_name": "OT/2025/00123",
    "success": true
}

// Error response
{
    "error": "[Error message]",
    "success": false
}
```

**Solution**: Check backend logs:
```bash
sudo journalctl -u odoo -n 50 | grep "optical_create_test"
```

---

### Issue: Analytic Not Applied to Invoice

**Checks**:
1. ✓ POS location has analytic_account_id set
2. ✓ Invoice generated through POS (not manual)
3. ✓ Product lines (not tax/note lines)

**Debug**:
```sql
SELECT 
    sl.name as location,
    sl.analytic_account_id,
    aaa.name as analytic_name
FROM stock_location sl
LEFT JOIN account_analytic_account aaa ON sl.analytic_account_id = aaa.id
WHERE sl.usage = 'internal';
```

**Solution**: Set analytic on location and regenerate invoice.

---

## Performance Notes

**Module Load Time**: ~0.8-1.0 seconds  
**Registry Load Time**: ~6-8 seconds  
**Database Queries**: 233-272 queries on upgrade  

**Recommended Configuration**:
- Workers: 4+ for production
- Database pooling: max_cron_threads = 2
- Log level: info (warning for production)

---

## Support

**Module Version**: 17.0.1.0.0  
**Odoo Version**: 17.0 Community  
**Author**: Risolto Limited  
**License**: LGPL-3  

For issues or questions:
1. Check module logs: `sudo journalctl -u odoo -n 100`
2. Verify module status: Navigate to Apps → bp_optical_pos
3. Check dependencies installed: bp_optical_core, point_of_sale, account

---

## Appendix: Quick Reference

### RPC Methods Available

| Method | Purpose | Args |
|--------|---------|------|
| `optical_create_test` | Create optical test from POS | order_uid, partner_id, test_vals |
| `optical_register_balance_payment` | Settle invoice balance | invoice_id, payment_vals |
| `optical_finalize_payments` | Get payment summary | order_uid |

### Key Models Extended

| Model | Fields Added | Purpose |
|-------|-------------|---------|
| `pos.config` | optical_enabled, optical_branch_id, optical_force_invoice, optical_require_customer, optical_insurance_journal_id | POS configuration |
| `pos.order` | Multiple methods | Business logic |
| `pos.payment` | is_insurance, insurance_data_id | Payment tracking |
| `pos.payment.method` | is_insurance_method | Method configuration |
| `stock.location` | analytic_account_id | Analytic inheritance |
| `optical.insurance.company` | partner_id | Invoice splitting |

### New Models Created

| Model | Purpose | Key Fields |
|-------|---------|-----------|
| `optical.insurance.payment` | Store insurance metadata | order_id, invoice_id, insurance_company_id, policy_number, member_number, employer, amount, notes |

---

**End of Testing Guide**
