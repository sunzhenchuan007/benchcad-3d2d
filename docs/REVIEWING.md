# Review checklist

## Source changes

- [ ] The case number and source links identify the intended original.
- [ ] Only STEP and SLDPRT assets are included in the source package.
- [ ] File paths, sizes, and hashes pass `python tools/verify_sources.py`.
- [ ] Alternative versions are preserved or an intentional replacement is explained.
- [ ] Readiness fields describe observed evidence, not folder names.

## Required before GT readiness

- [ ] The chosen STEP and native model describe the same geometry and units.
- [ ] The native feature tree or CQ construction provides meaningful parameters.
- [ ] Suppressed, redundant, and non-contributing history is excluded appropriately.
- [ ] Continuous independent variables and discrete structures are distinguished.
- [ ] Feature references and dependencies have been checked against the final solid.

## Verifier changes

- [ ] Equivalent dimension chains and constructions receive equivalent treatment.
- [ ] Missing depths, wrong termination conditions, and wrong geometry attachments fail appropriately.
- [ ] Hidden GT knowledge is never counted as information on the submitted drawing.
- [ ] Rank checks are not treated as proof of global uniqueness.
- [ ] Drawing output and machine-readable annotations are consistent.
- [ ] Unsupported items, aggregate scores, and whole-drawing completeness are reported separately.
