# Public_Data publishing

Publishing is not scheduled and was not used by the shadow validation run. It requires the compatibility report, validates non-empty output, clones and rebases Public_Data before copying only PASS domains, commits atomically, and pushes without force. The checkpoint is written only after push succeeds.

Required credential:

- Secret: `PUBLIC_DATA_TOKEN`
- Configure in: `alien0077/TWStockDataPipeline` Actions secrets
- Minimum permission: fine-grained token restricted to `alien0077/Public_Data`, Contents: Read and write; no issues, administration, workflow, or organization permissions.
