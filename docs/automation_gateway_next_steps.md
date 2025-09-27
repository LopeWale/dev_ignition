# Automation Gateway Integration – Next Actions

## Immediate Priorities (Sprint 1)
1. **Security Hardening Baseline**  
   - Implement credential validation and token lifetime enforcement for the GraphQL admin service in the fork prior to any control plane exposure.  
   - Add HTTPS and configurable CORS defaults that align with the platform's API Gateway requirements described in the architecture plan (SSO-backed auth, RBAC, and audit logging expectations).  
   - Ship a minimal threat model covering attack surfaces created by MQTT, OPC UA, and GraphQL listeners so security controls can be validated against the unified control plane vision.
2. **Container Packaging & CI**  
   - Stand up a GitHub Actions workflow that builds, scans, and publishes forked images targeting Java 17, mirroring the platform's container-first delivery model.  
   - Embed health/readiness endpoints that the Environment Orchestrator can probe when orchestrating sidecars alongside Ignition gateways.  
   - Capture SBOM output for the image to satisfy the compliance and audit objectives documented in the architecture.
3. **Configuration Schema Alignment**  
   - Document a curated subset of drivers, loggers, and servers that will ship as opinionated defaults for Ignition-centric environments.  
   - Produce JSON Schema definitions for the selected options so the SPA and FastAPI backend can validate user input before rendering YAML.  
   - Map secrets required by each component (certificates, broker passwords, JDBC credentials) to the central Secrets Service interfaces outlined in the architecture plan.

## Near-Term (Sprint 2)
1. **Compose/Kubernetes Template Integration**  
   - Extend the Docker Compose and Helm templates to declare the Automation Gateway sidecar, including shared volumes for configuration, certificates, and telemetry sinks.  
   - Model startup dependencies so Ignition gateways expose OPC UA endpoints before the sidecar attempts to connect.  
   - Provide resource recommendations (CPU/RAM) to prevent contention with Ignition in constrained sandboxes.
2. **Control Plane Surface Area**  
   - Add FastAPI endpoints and SPA workflows that collect Automation Gateway settings, leveraging the architecture's unified web interface and API Gateway patterns.  
   - Expose template selectors and preview endpoints (already implemented) within the SPA to help users choose the right configuration package.  
   - Instrument telemetry hooks so the Monitoring & Telemetry pillar can track sidecar health, connector status, and sink delivery metrics.
3. **Documentation & Runbooks**  
   - Produce operator runbooks that describe how to troubleshoot driver connectivity, credential rotation, and logger failures when running the combined Ignition + Automation Gateway stack.  
   - Update the architecture plan with security guardrails, configuration boundaries, and rollout sequencing once the fork hardening tasks land.  
   - Capture quick-start guides for the most common use cases (telemetry streaming, GraphQL browsing, MQTT bridging) to align with the "one-stop shop" goal.

## Longer-Term (Post-MVP)
1. **Advanced Connectors & Pipelines**  
   - Expand logger support to additional sinks (Kafka, OpenSearch) and integrate with the CI/CD orchestrator for automated pipeline triggers.  
   - Investigate event-driven scaling or pausing of connectors based on environment lifecycle hooks emitted by the platform.
2. **Compliance & Observability Enhancements**  
   - Add structured logging, distributed tracing, and metrics export from the fork to meet the platform's observability standards.  
   - Align fork release cadence with the control plane's delivery roadmap to guarantee security patches and dependency updates are applied promptly.  
   - Formalize backup and restore procedures for gateway configuration and state handled by the sidecar.
3. **Ecosystem Alignment**  
   - Coordinate with future multi-tenant and federation features to ensure Automation Gateway deployments respect tenancy boundaries.  
   - Evaluate opportunities to expose curated GraphQL schemas or MQTT topics through the central API Gateway while preserving isolation between environments.

This plan builds directly on the architecture pillars documented in `docs/architecture_plan.md`, ensuring Automation Gateway becomes a secure, observable, and user-friendly extension of the Ignition DevOps control plane.
