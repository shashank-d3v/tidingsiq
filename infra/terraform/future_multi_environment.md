# Future Terraform Multi-Environment Notes

This project currently uses a single active environment. This note exists only as future reference in case the infrastructure later needs both `dev` and `prod`.

## Core Idea

Using one repo for multiple environments is normal. The important separation is not the codebase, it is:

- different input variables per environment
- different Terraform state per environment
- different resource naming where collisions are possible

## Recommended Shape

If this repo ever manages both environments, a clean structure is:

```text
infra/terraform/
  env/
    dev/
      terraform.tfvars
      backend.hcl
    prod/
      terraform.tfvars
      backend.hcl
```

## Separate Variable Files

Each environment should have its own variable file.

Typical difference:

- `project_id = "<DEV_GCP_PROJECT_ID>"` for dev
- `project_id = "<PROD_GCP_PROJECT_ID>"` for prod

If both environments ever share one GCP project, dataset names would need environment-specific prefixes such as:

- `dev_bronze`, `dev_silver`, `dev_gold`
- `prod_bronze`, `prod_silver`, `prod_gold`

## Most Important Rule: Separate State

`dev` and `prod` must never share the same Terraform state.

Why:

- `terraform plan` compares code against the current state
- if `dev` and `prod` share state, each environment can appear to Terraform as drift from the other
- that leads to dangerous plans and accidental changes

## Best Practice: Remote Backend With Separate Keys

The safest approach is a remote backend, typically a GCS bucket, with a separate path for each environment.

Mental model:

```text
GCS bucket: gs://<TERRAFORM_STATE_BUCKET>

dev state:  gs://<TERRAFORM_STATE_BUCKET>/<STATE_PREFIX>/dev/terraform.tfstate
prod state: gs://<TERRAFORM_STATE_BUCKET>/<STATE_PREFIX>/prod/terraform.tfstate
```

This means:

- `dev` reads and writes only dev state
- `prod` reads and writes only prod state
- the same Terraform code can safely manage both environments

## Example Backend Files

`env/dev/backend.hcl`

```hcl
bucket = "<TERRAFORM_STATE_BUCKET>"
prefix = "<STATE_PREFIX>/dev"
```

`env/prod/backend.hcl`

```hcl
bucket = "<TERRAFORM_STATE_BUCKET>"
prefix = "<STATE_PREFIX>/prod"
```

## Example Commands

Initialize dev:

```bash
terraform init -backend-config=env/dev/backend.hcl
terraform plan -var-file=env/dev/terraform.tfvars
terraform apply -var-file=env/dev/terraform.tfvars
```

Initialize prod:

```bash
terraform init -backend-config=env/prod/backend.hcl
terraform plan -var-file=env/prod/terraform.tfvars
terraform apply -var-file=env/prod/terraform.tfvars
```

When switching environments in the same working directory, re-run `terraform init` with the correct backend config before planning or applying.

## If Remote Backend Is Not Ready Yet

Temporary alternatives exist, but they are weaker:

1. Separate Terraform workspaces
2. Separate local state files

Both are more error-prone than separate remote backend keys.

## Practical Recommendation

If this project remains single-environment, keep the current simpler setup.

If multi-environment support becomes necessary later:

1. add environment-specific variable files
2. move state to a remote backend
3. separate state paths by environment
4. introduce environment-specific resource naming only where required
