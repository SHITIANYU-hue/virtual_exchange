# Experiment logs

Raw per-run experiment output (`portfolio_performance.csv`, `messages.csv`,
`audit_report.json`/`audit_events.csv`, per-cycle `status/*.json`, and — for
locally-retained runs — full `prompts/`/`actions/`/`errors/`) is not stored
in this repository. The full dataset backing the analyses in
[`../experiment_analysis/`](../experiment_analysis/) is published separately:

- **Dataset**: TODO — link to the Zenodo / Hugging Face Datasets release
- **DOI**: TODO

Running `python3 experiments/run_experiment.py` yourself will regenerate
this directory structure locally, one subdirectory per run, using the
current timestamp and (optionally) the `--label` you pass in.
