# Automation Gateway Fork Plan

## Current Status
- The upstream project at https://github.com/vogler75/automation-gateway has been evaluated but **a fork has not yet been created** under the dev_ignition organization.
- Before forking, we must align the repository structure and governance model with the control plane architecture documented in `docs/architecture_plan.md`.

## Recommended Fork Process
Following the GitHub guidance on forking workflows, ensure the fork remains in sync with upstream changes and that contribution history is preserved.

1. **Establish the fork**
   - Create the fork within the dev_ignition GitHub organization and restrict direct pushes to the `main` branch.
   - Configure branch protection and enable required status checks for Gradle builds and tests.

2. **Prepare automation**
   - Mirror upstream tags and releases to maintain version traceability.
   - Configure a scheduled workflow that fetches upstream changes and opens pull requests for review when divergences occur.

3. **Security and compliance hardening**
   - Prioritize fixing the GraphQL admin authentication gap before exposing the service in dev_ignition-managed environments.
   - Review third-party dependencies for CVEs during the fork initialization.

4. **Integration roadmap**
   - Publish hardened Docker images that align with the dev_ignition release cadence.
   - Document configuration contracts so the automation sidecar can be provisioned by the compose generator and API schemas already in this repository.

## Next Steps
- [ ] Create the fork and bootstrap repository settings.
- [ ] Implement CI workflows (Gradle build, vulnerability scanning).
- [ ] Begin security hardening tasks, focusing on authentication and configuration validation.

