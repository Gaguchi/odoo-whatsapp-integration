# WhatsApp Integration for Odoo 18 Community Edition

A custom module that integrates WhatsApp Business API with Odoo Community Edition.

## Features

- ✅ Send text messages via WhatsApp Business API
- ✅ Send template messages
- ✅ Receive incoming messages via webhooks
- ✅ Track message status (sent, delivered, read)
- ✅ Auto-link messages to Odoo contacts
- ✅ Sync message templates from WhatsApp

## Prerequisites

1. **Meta Business Account** - [business.facebook.com](https://business.facebook.com)
2. **Meta Developer Account** - [developers.facebook.com](https://developers.facebook.com)
3. **WhatsApp Business App** with API access

### Required API Credentials

- Phone Number ID
- Access Token (permanent)
- WhatsApp Business Account ID (WABA ID)
- App ID
- App Secret
- Verify Token (you create this)

## Installation on Dokploy

### 1. Add to extra-addons volume

Copy the `whatsapp_integration` folder to your Odoo's extra-addons directory:

```yaml
services:
  odoo:
    image: odoo:18
    volumes:
      - ./extra-addons:/mnt/extra-addons
```

### 2. Restart Odoo

```bash
docker-compose restart odoo
```

### 3. Install the Module

1. Enable Developer Mode in Odoo
2. Go to **Apps** → **Update Apps List**
3. Search for "WhatsApp Integration"
4. Click **Install**

## Configuration

### 1. Add WhatsApp Account

Navigate to **WhatsApp → Configuration → Accounts** and create a new account with your API credentials.

### 2. Configure Webhook in Meta

In Meta Developer Console:
- **Callback URL:** `https://YOUR_ODOO_DOMAIN/whatsapp/webhook`
- **Verify Token:** Same as configured in Odoo
- **Subscribe to:** `messages` field

### 3. Test Connection

Click "Test Connection" on your WhatsApp account to verify API connectivity.

## Usage

### Sending Messages

1. Go to **WhatsApp → Messages**
2. Click action to open Send Message wizard
3. Enter phone number and message
4. Click Send

### Viewing Messages

All incoming and outgoing messages appear in **WhatsApp → Messages** with:
- Direction indicator
- Status tracking
- Partner auto-linking

### Using Templates

1. **WhatsApp → Configuration → Accounts** → Click "Sync Templates"
2. Templates are synced from your WhatsApp Business account
3. Use templates in the Send Message wizard

## Webhook URL

Your webhook endpoint is:
```
https://YOUR_DOMAIN/whatsapp/webhook
```

Make sure this URL is accessible from the internet with valid SSL.

## Support

This is a community module. For issues, check the Odoo logs or the Meta Developer Console for API errors.

## License

LGPL-3
