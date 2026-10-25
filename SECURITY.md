# Security

Please report vulnerabilities privately through GitHub: **Security → Report a vulnerability** on this repository. Don't open a public issue.

## How secrets are handled

- Model and speech keys live only in `.env` (git-ignored) or in Azure Container Apps secrets. The browser never receives them; speech is proxied by the server.
- Secret scanning and push protection are enabled on this repository.
- All match data is synthetic. The app stores no personal data; viewer questions are not persisted.
