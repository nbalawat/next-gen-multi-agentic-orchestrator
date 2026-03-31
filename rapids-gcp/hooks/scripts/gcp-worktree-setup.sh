#!/usr/bin/env bash
# gcp-worktree-setup.sh
# Called on WorktreeCreate to initialize GCP environment for the new worktree.

set -euo pipefail

echo "[rapids-gcp] Setting up GCP environment for worktree..."

# Set default GCP environment variables if not already set
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
export CLOUDSDK_COMPUTE_REGION="${CLOUDSDK_COMPUTE_REGION:-us-central1}"
export CLOUDSDK_COMPUTE_ZONE="${CLOUDSDK_COMPUTE_ZONE:-us-central1-a}"

# Terraform environment defaults
export TF_VAR_region="${TF_VAR_region:-us-central1}"
export TF_VAR_zone="${TF_VAR_zone:-us-central1-a}"

if [ -n "$GOOGLE_CLOUD_PROJECT" ]; then
  export TF_VAR_project_id="$GOOGLE_CLOUD_PROJECT"
  echo "[rapids-gcp] GCP project: $GOOGLE_CLOUD_PROJECT"
else
  echo "[rapids-gcp] WARNING: GOOGLE_CLOUD_PROJECT not set. Set it or configure project_id in plugin config."
fi

# Start Bigtable emulator if available
if command -v gcloud &> /dev/null; then
  if gcloud components list --filter="id=bigtable" --format="value(state.name)" 2>/dev/null | grep -q "Installed"; then
    echo "[rapids-gcp] Starting Bigtable emulator..."
    export BIGTABLE_EMULATOR_HOST="localhost:8086"
    gcloud beta emulators bigtable start --host-port="$BIGTABLE_EMULATOR_HOST" &
    EMULATOR_PID=$!
    echo "[rapids-gcp] Bigtable emulator started (PID: $EMULATOR_PID)"
    echo "[rapids-gcp] BIGTABLE_EMULATOR_HOST=$BIGTABLE_EMULATOR_HOST"
  else
    echo "[rapids-gcp] Bigtable emulator not installed. Skipping."
  fi
else
  echo "[rapids-gcp] gcloud CLI not found. Skipping emulator setup."
fi

# Initialize Terraform if a config exists in the worktree
if [ -f "main.tf" ] || [ -f "terraform.tf" ]; then
  echo "[rapids-gcp] Terraform config detected. Running terraform init..."
  terraform init -input=false 2>&1 || echo "[rapids-gcp] WARNING: terraform init failed. Check provider configuration."
fi

echo "[rapids-gcp] Worktree setup complete."
