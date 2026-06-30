# OpenG2P ATI: WebSub Integration

This module extends the OpenG2P WebSub functionality by automatically including ATI (Agricultural Transformation Initiative) farmer data in WebSub payloads when publishing records.

## Features

- Inherits the `g2p.datashare.config.websub` model
- Automatically extracts and includes comprehensive ATI farmer data in WebSub payloads
- No additional form fields - works transparently in the background
- Includes all ATI farmer fields in the published data:
  - Geographic information (zone, woreda, kebele)
  - Name fields in multiple languages (English, Amharic, other)
  - Personal information (phone, ID, birthdate, language, farming type)
  - Membership information (cooperatives, farmer clusters)
  - Agricultural resources (fertilizer, pesticide, improved seeds)
  - Access to resources (water sources, machinery, irrigation)
  - Socio-economic data (marital status, education, household info)
  - Land information (area, ownership, certificates)
  - Crop information (types, planting dates, diseases)
  - Livestock information (types, numbers, health)
  - Cooperative and season details
  - Registration ID information

## How It Works

When a WebSub event is published:

1. The module intercepts the `publish_event_websub` method
2. Extracts ATI farmer data from the partner record
3. Adds the ATI data to the payload under `ati_farmer_data` key
4. Calls the original WebSub publishing method with enhanced data

## Dependencies

- `g2p_registry_datashare_websub` - Base WebSub functionality
- `g2p_ati` - ATI module with farmer data models

## Installation

1. Install the module through Odoo Apps
2. The ATI data will automatically be included in all WebSub payloads
3. No additional configuration needed

## Usage

After installation, when WebSub events are published:

1. All existing WebSub functionality continues to work as before
2. ATI farmer data is automatically included in the payload
3. The data appears under the `ati_farmer_data` key in the published JSON
4. Subscribers will receive the enhanced payload with ATI information

## Example Payload Structure

```json
{
  "id": 123,
  "name": "John Doe",
  "event_type": "WEBSUB_INDIVIDUAL_CREATED",
  "ati_farmer_data": {
    "given_name": "John",
    "family_name": "Doe",
    "is_farmer": "yes",
    "farming_type": "mixed_farming",
    "zone": {"id": 1, "name": "Test Zone", "code": "TZ"},
    "land_information": [...],
    "crop_information": [...],
    "livestock_information": [...]
  }
}
```

## Security

- User access controlled by ATI user groups
- Manager group has full CRUD permissions
- User group has read/write/create permissions (no delete)

## Technical Details

The module extends the existing WebSub model using Odoo's inheritance mechanism, specifically overriding the `publish_event_websub` method to enhance the data payload with ATI information before calling the parent method. This ensures compatibility with existing WebSub functionality while adding comprehensive ATI data support.
