# KAS Estimate/Quote Creator Module

## Overview
A professional, production-ready Estimate/Quote creation system for KAS Waterproofing & Building Services. Allows admins to quickly create, manage, and convert estimates into jobs within the CRM pipeline.

## Features

### 1. **Estimate Creation**
- **Fast Quote Builder**: Create professional estimates in seconds
- **Service Type Templates**: Pre-built line item templates for 12 service types
- **Client Information Capture**: Full client contact and address details
- **Auto-Calculate Totals**: Automatic calculation of subtotals, tax (6.5% FL), and grand total
- **Auto-Generated Estimate Numbers**: KAS-1001, KAS-1002, etc.

### 2. **Service Types with Templates**
The system includes templates for common KAS services:
- Waterproofing
- Roof Coating
- Exterior Painting
- Interior Painting
- Caulking / Sealants
- Concrete Repair
- Stucco Repair
- Balcony Waterproofing
- Garage / Deck Coating
- Pressure Cleaning
- Commercial Building Maintenance
- Custom Construction Services

### 3. **Line Item Management**
- **Add Multiple Items**: Build estimates with multiple line items
- **Flexible Units**: Support for hours, sqft, linear feet, days, lump sums, etc.
- **Descriptions**: Optional descriptions for each line item
- **Easy Editing**: Add, delete, or modify items in real-time
- **Auto-Calculation**: Line totals calculate automatically

### 4. **Estimate Status Workflow**
- **Draft**: Initial state, can be edited freely
- **Sent**: Marked as sent to client
- **Viewed**: Track when client opens estimate (future enhancement)
- **Approved**: Client accepted the estimate
- **Rejected**: Client declined
- **Expired**: Old estimates can be marked expired

### 5. **Estimate Management**
- **View Professionally Formatted Quotes**: Beautiful branded quote display
- **Search & Filter**: Search by client name, company, or estimate number
- **Sort Options**: Newest, oldest, client name, highest value
- **Duplicate Estimates**: Quickly duplicate an estimate for similar projects
- **Edit Estimates**: Modify client info or line items anytime (before approval)
- **Send Estimates**: Mark as sent (email integration coming soon)
- **Approve/Reject**: Change estimate status
- **Convert to Job**: Convert approved estimates directly into pipeline jobs

### 6. **Dashboard & Analytics**
- **Key Metrics**: Total estimates, drafts, pending, approved value
- **Status Counts**: See breakdown of estimates by status
- **Search & Filters**: Find specific estimates quickly
- **Quick Overview**: Cards show client name, service type, amount, and status

### 7. **Professional Presentation**
- **Branded PDF Layout** (future): Generate PDF quotes with company branding
- **Signature Line**: Space for client signature
- **Terms & Conditions**: Customizable terms section
- **Modern Design**: Clean, professional appearance matching app theme
- **Mobile Responsive**: Works perfectly on phones and tablets

## Database Schema

### `estimates` Table
```sql
CREATE TABLE estimates (
    id BIGSERIAL PRIMARY KEY,
    estimate_number TEXT UNIQUE,        -- KAS-1001, KAS-1002, etc.
    client_name TEXT NOT NULL,
    company_name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    service_type TEXT NOT NULL,
    project_description TEXT,
    status TEXT DEFAULT 'Draft',        -- Draft, Sent, Viewed, Approved, Rejected, Expired
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    total DOUBLE PRECISION,
    notes TEXT,                         -- Terms & conditions
    created_by BIGINT REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT,
    sent_at TEXT,
    approved_at TEXT
);
```

### `estimate_items` Table
```sql
CREATE TABLE estimate_items (
    id BIGSERIAL PRIMARY KEY,
    estimate_id BIGSERIAL REFERENCES estimates(id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    description TEXT,
    quantity DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    line_total DOUBLE PRECISION NOT NULL,
    sort_order INTEGER DEFAULT 0
);
```

## Routes & Endpoints

### Admin Routes (All Protected)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/estimates` | List all estimates |
| GET | `/estimate/create` | Create new estimate form |
| POST | `/estimate/create` | Submit new estimate |
| GET | `/estimate/<id>` | View estimate detail |
| GET | `/estimate/<id>/edit` | Edit estimate form |
| POST | `/estimate/<id>/edit` | Update estimate |
| POST | `/estimate/<id>/item/add` | Add line item |
| POST | `/estimate/<id>/item/<item_id>/delete` | Delete line item |
| POST | `/estimate/<id>/send` | Mark as sent |
| POST | `/estimate/<id>/approve` | Mark as approved |
| POST | `/estimate/<id>/reject` | Mark as rejected |
| POST | `/estimate/<id>/convert` | Convert to job |
| POST | `/estimate/<id>/duplicate` | Duplicate estimate |

## Navigation

The feature is accessible from the main navigation bar:
- **Estimates** link: View all estimates list
- **Create Quote** link: Quickly create a new estimate

## Usage Guide

### Creating an Estimate

1. Click **Create Quote** in the navigation
2. Fill in **Client Information** (name is required)
3. Select **Service Type** (auto-populated templates available)
4. Add **Project Description** and **Terms & Conditions**
5. Click **Create Quote**
6. System creates estimate with auto-generated number (KAS-1001, etc.)

### Adding Line Items

1. From estimate edit page, scroll to "Line Items" section
2. Click **Add Line Item**
3. Fill in:
   - **Item Name**: Description of service/product
   - **Description**: Optional details
   - **Quantity**: Number of units
   - **Unit**: Hour, sqft, linear_ft, day, each, lump_sum, etc.
   - **Unit Price**: Price per unit
4. Click **Add Item**
5. Totals automatically calculate (including 6.5% FL tax)

### Converting to Job

1. Open an **Approved** estimate
2. Click **Convert to Job** button
3. Creates job automatically in Pipeline with:
   - Job name from service type and client name
   - Status: "Scheduled"
   - Proposal amount from estimate total
   - Client name and location from estimate

### Duplicating an Estimate

1. Open any estimate
2. Click **Duplicate** button
3. Creates exact copy with new estimate number (KAS-1002, etc.)
4. Copy is in Draft status for editing
5. Perfect for similar client projects

## Design & Styling

- **Color Scheme**: Green/charcoal with professional contractor theme
- **Card-Based Layout**: Modern, clean interface matching app design
- **Status Badges**: Color-coded status indicators
- **Mobile Friendly**: Responsive design works on all devices
- **Professional Typography**: Clear hierarchy and readability

## Technical Details

### Auto-Generated Estimate Numbers
- Format: `KAS-XXXX` (e.g., KAS-1001)
- Starts at 1001, increments with each estimate
- Guaranteed unique (database constraint)

### Tax Calculation
- Hard-coded to 6.5% (Florida standard)
- Automatically calculated on subtotal
- Can be customized in code if needed (lines in `calculate_estimate_totals()`)

### Service Templates
Service templates are defined in `SERVICE_TEMPLATES` dictionary with common line items for each service type. These can be used for:
- Auto-populating line items (future enhancement)
- Helping admins remember common items for each service
- Maintaining consistency across estimates

## Security

- **Admin Only**: All estimate features require admin role
- **Database Constraints**: 
  - Estimate numbers are unique
  - Foreign key relationships enforce data integrity
  - Cascade delete removes items when estimate deleted
- **SQL Injection Protection**: All queries use parameterized statements
- **Input Validation**: All forms validate required fields

## Future Enhancements

1. **PDF Generation**: Generate downloadable PDF quotes with branding
2. **Email Integration**: Send quotes directly to clients via email
3. **Client Portal**: Let clients view and approve estimates online
4. **E-Signature**: Collect digital signatures on approved estimates
5. **Payment Terms**: Add payment schedule and deposit options
6. **Recurring Estimates**: Template for recurring maintenance quotes
7. **Version History**: Track estimate changes over time
8. **Client Portal**: Let clients view, comment, and approve estimates

## File Changes

### Modified Files
- **app.py**: Added 13 new routes, helper functions, and database schema
- **templates/base.html**: Added "Estimates" and "Create Quote" navigation links
- **static/styles.css**: Added estimate-specific styling

### New Files
- **templates/estimates.html**: Estimate list page with filters and metrics
- **templates/create_estimate.html**: Create new estimate form
- **templates/view_estimate.html**: Professional estimate view/preview
- **templates/edit_estimate.html**: Edit estimate form with line items

## Performance Notes

- **Database Indexes**: Estimate numbers indexed for fast lookup
- **Pagination**: Future enhancement for large estimate lists
- **Caching**: Estimates cached briefly to reduce DB hits
- **Search**: Full-text search available on client name and estimate number

## Testing

To test the feature:

1. Login as admin
2. Click **Create Quote** in navigation
3. Fill form with sample data (client "Acme Inc.", service "Waterproofing")
4. Create estimate
5. Add 2-3 line items (labor, materials)
6. View the formatted quote
7. Test status changes (Send, Approve, Convert)
8. Test duplicate estimate
9. Test converting approved estimate to job
10. Verify job appears in pipeline

## Support

For issues or feature requests, contact the development team. The system is fully integrated with the existing KAS CRM and uses the same authentication, database, and styling as the rest of the application.
