# Go Gateway

The dedicated AuthClaw gateway runtime lives in:

- `../../gateway-go/`

It is the mandatory entry point for LLM traffic and owns gateway routing,
streaming response interception, and streaming redaction before responses reach
clients.
