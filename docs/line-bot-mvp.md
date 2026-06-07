# LINE Bot MVP Setup

ByteBites uses two different LINE integrations:

- LINE Login: web login for ByteBites accounts.
- LINE Messaging API: chatbot webhook for restaurant recommendations.

The bot needs a LINE Developers Messaging API channel.

## Required LINE Channel Values

Add these values to `ai-service-python/.env`:

```env
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_SIGNATURE_VERIFY=true
LINE_REPLY_ENABLED=true
LINE_PUBLIC_WEB_URL=https://your-public-web-url.example.com
```

`LINE_PUBLIC_WEB_URL` must be a public HTTPS URL for Flex card buttons and
images. For local demos, use an HTTPS tunnel that forwards to
`http://localhost:3000`.

## Webhook URL

Set the Messaging API webhook URL to:

```text
https://your-public-ai-url.example.com/api/line/webhook
```

For local demos, expose the AI service (`http://localhost:8000`) with an HTTPS
tunnel and use:

```text
https://your-ai-tunnel.example.com/api/line/webhook
```

## Current MVP Behavior

Supported:

- follow event: returns a welcome text.
- text message: runs the existing ByteBites AI agent and replies with text plus
  a Top 3 LINE Flex carousel when shop recommendations are available.
- location message: acknowledges the location and asks for dining intent.
- local preview: set `LINE_REPLY_ENABLED=false` to return `messages_preview`
  without sending to LINE.

Next recommended iteration:

- persist LINE location context in Redis;
- add background job + Push Message for slow recommendations;
- add LIFF booking flow from Flex card buttons;
- bind Messaging API `userId` to ByteBites LINE Login users.
