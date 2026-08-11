Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and UX inventory

- [ ] 0.1 Audit current Android/web screens and real V2 read contracts; create
  an observable state/action matrix and minimal navigation strategy without
  changing UI

## 1. Shared models and navigation

- [ ] 1.1 Add contract fixtures/tests for projects, change lists/details,
  blockers, permissions, primary actions, unknown values and durable recovery
- [ ] 1.2 Implement read-only Project → Changes → Change detail on web and
  Android behind disabled flags, reusing existing styles/components

## 2. Focused module surfaces

- [ ] 2.1 Add conversation/editing and protected validation state/actions with
  clear capacity/transport/validation/policy/ownership presentation
- [ ] 2.2 Add artifact/review environment/decision surfaces with private
  preview and evidence visibility
- [ ] 2.3 Add integration/release plans, step-up confirmation and operation
  recovery without exposing internal selectors

## 3. Visual and parity proof

- [ ] 3.1 Validate every critical state in data/persistence, DOM and real
  1440x900/390x844 screenshots; inspect hierarchy, first viewport, clipping,
  overflow, long messages, permissions and accessibility
- [ ] 3.2 Validate equivalent Android rendered states, rotation/restart/offline
  recovery and exact one-primary-action behavior on the real build
- [ ] 3.3 Seal separate web/backend and protected Android APK rollouts; stop
  independently for H3 and H8
- [ ] 3.4 After exact authorizations, roll out Atenea-only clients, observe
  parity, strict-validate, seal and archive
