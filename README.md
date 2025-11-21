# BP Optical POS

Odoo Point of Sale integration module for optical businesses, providing seamless management of optical tests, insurance payments, and analytics.

## Features

- **Optical Test Integration**: Create and manage optical tests directly from POS
- **Insurance Payment Processing**: Handle insurance company payments and reconciliation
- **Branch Analytics**: Generate profit & loss reports per optical branch
- **Patient History**: View patient optical history and test records in POS
- **Stage Management**: Track optical test workflow stages
- **Multi-Branch Support**: Branch-based access control and reporting

## Dependencies

- Odoo 17.0
- `bp_optical_core` - Core optical records module
- `point_of_sale` - Odoo Point of Sale
- `account` - Odoo Accounting

## Installation

1. Install the required dependency module:
   ```bash
   ./optical_core.sh <database_name>
   ```

2. Install bp_optical_pos:
   ```bash
   ./optical_pos.sh <database_name>
   ```

## Configuration

1. Navigate to **Point of Sale > Configuration > Settings**
2. Configure insurance payment methods
3. Set up optical branches and assign staff
4. Configure POS to use optical features

## Usage

### Creating Optical Tests in POS
- Open POS session
- Select or create a patient
- Click "Optical Test" button
- Fill in test details and prescription
- Link to current sale if needed

### Processing Insurance Payments
- In POS, select insurance payment method
- Choose insurance company
- Enter policy details
- System tracks pending insurance receivables

### Branch Reports
- Navigate to **Optical POS > Reporting**
- Generate branch P&L reports
- View pending insurance payments
- Analyze branch performance

## Security

Three access levels:
- **User**: View branch data, process sales
- **Manager**: Full branch access, test creation
- **Admin**: Global access, configuration

## License

LGPL-3

## Author

Risolto Limited

## Support

For issues and questions, please contact support@blackpawinnovations.com
