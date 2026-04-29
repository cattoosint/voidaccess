# Security Policy

## Reporting Security Vulnerabilities

We take security seriously. If you discover a security vulnerability in VoidAccess, please report it responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please use one of these methods:

1. **GitHub Private Vulnerability Reporting** (preferred):
   - Go to the "Security" tab of the repository
   - Click "Report a vulnerability"
   - Fill out the vulnerability report form

2. **Email**:
   - Email the maintainers directly (if available in the repository settings)

### What to Include

When reporting, please include:

1. **Type of vulnerability** (e.g., SQL injection, XSS, etc.)
2. **Full paths** of the source file(s) related to the vulnerability
3. **Steps to reproduce** the issue
4. **Impact** of the vulnerability (what an attacker could accomplish)
5. ** Proof of concept** or exploit code (if non-sensitive)

### Response Timeline

- **Acknowledgment**: Within 72 hours, we will confirm receipt of your report
- **Initial Response**: We aim to provide an initial assessment within 7 days
- **Resolution**: We work to release a fix as quickly as possible, depending on severity

### Severity Levels

We prioritize fixes based on severity:
- **Critical**: Patch released within 24-48 hours
- **High**: Patch released within 1-2 weeks
- **Medium**: Patch released within 2-4 weeks
- **Low**: Patch released in next regular release

### Scope

This policy applies to:
- The VoidAccess core application
- Official plugins and extensions
- Documentation and deployment configurations

### What to Expect

- We will keep you updated on our progress
- We will credit you in the security advisory (unless you prefer to remain anonymous)
- We will publicly acknowledge your contribution in the release notes once the vulnerability is fixed

Thank you for helping keep VoidAccess and its users safe!
### Known Limitations

**SSRF DNS Rebinding**
The platform employs protections against Server-Side Request Forgery (SSRF) when crawling dark web and clearnet addresses by resolving destination hostnames and rejecting internal IPs (e.g., 10.0.0.0/8, 127.0.0.1). However, this protection is performed at the application layer prior to initiating the HTTP request. It remains partially vulnerable to advanced Time-of-Check to Time-of-Use (TOCTOU) DNS Rebinding attacks. A sophisticated attacker capable of serving DNS responses with extremely short TTLs could theoretically bypass this protection if the DNS record resolves to a safe IP during validation but is subsequently rebound to an internal IP during the actual crawler connection. Administrators deploying VoidAccess on sensitive internal networks are strongly advised to enforce strict egress network policies at the firewall level to fully mitigate this vector.

