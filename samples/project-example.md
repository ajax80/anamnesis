---
name: project-example
description: widget-service — REST API for widgets (Go + Postgres); v2 shipped, pagination + flaky test outstanding
metadata:
  type: project
---

widget-service is the primary project: a REST API for managing widgets, written
in Go against Postgres. v2 (the redesigned auth flow) shipped and is deployed.

Outstanding: pagination on `GET /widgets`, and a flaky `test_widget_expiry`
(fails ~1 in 20 — suspected time-zone dependence in the fixture).

Related: [[user-example]]
