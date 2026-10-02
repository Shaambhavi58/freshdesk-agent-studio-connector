# Limitations

- The connector is read-only. It only calls Freshdesk `GET` endpoints and has no
  ticket creation, update, reply, or deletion tools.
- It does not bypass Freshdesk permissions or access controls. The API key's
  Freshdesk account permissions govern the data the connector can read.
- It uses documented Freshdesk API v2 behavior and does not include a private
  API or undocumented endpoint.
- The repository contains fictional demo data only; no real customer data is
  included.
- Credentials are read from the process environment or an untracked local
  `.env` file. The connector does not persist credentials.
- Demo mode uses local fictional fixtures and never sends HTTP requests.
- OAuth, webhooks, multi-tenant deployment, and per-tenant authorization are not
  implemented.
- Search pagination follows Freshdesk's search page size (30 results per page);
  ticket-list pagination uses the requested `per_page` value.
- A list response's `has_more` value is inferred from the number of records
  returned when Freshdesk does not provide a total count.