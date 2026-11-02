# Project governance

## Purpose

This document describes how project decisions are made and how contributors can
participate. It is intended to keep changes transparent, reviewable, and aligned
with the project's users and maintainers.

## Roles

- **Maintainers** review and merge changes, manage releases, and keep project
  policies current. Until additional maintainers are named, the project owner
  performs these responsibilities.
- **Contributors** propose changes, provide context and validation, and follow
  the project's contribution and community standards.
- **Users** can report bugs, request improvements, and provide feedback through
  the project's issue tracker or its designated support channel.

## Decision-making

Routine changes should be proposed as pull requests and discussed openly in the
associated issue or review. A proposal should explain the problem, expected
behavior, impact, and any alternatives considered. Maintainers make the final
merge decision, taking into account technical quality, security, compatibility,
and user impact.

For changes with broad or breaking impact, maintainers should seek feedback
before implementation and document the decision and migration implications in
the proposal. If discussion does not reach consensus, maintainers may decide
after allowing affected participants a reasonable opportunity to comment; the
rationale should be recorded with the proposal.

## Changes to governance

Anyone may propose a change to this policy. Changes take effect when approved
and merged by a maintainer. Policies should be reviewed when project ownership,
release practices, or the contributor community materially changes.

## Related policies

- [Contributing](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## Application audit trail

The API writes one JSON event per request to `enterprise_audit.log` in the
project directory. Events include the authenticated user and role when
available, HTTP method and path, response status, outcome, UTC timestamp, and
request duration. Unhandled exceptions are re-raised and logged with their
type. Request bodies, credentials, and query strings are not included.

Restrict access to the log file, rotate and retain it according to the
deployment's privacy and operational requirements, and avoid treating a
locally stored log as tamper-proof or as a substitute for a centralized audit
system.

## Input and output guardrails

The application limits text inputs and uploads, validates image formats and
dimensions, bounds retrieved context, and checks generated text before returning
it. Retrieved documents are treated as untrusted reference data in model
instructions. These checks reduce common risks but do not replace application
security testing, human review, or deployment-specific content policies.
