#!/usr/bin/env bash
# =============================================================================
#  deploy-dev.sh — develop-branch deploy for OAN_Registries (OpenG2P / Odoo).
#  Rolls the in-cluster dev Odoo deployment onto a freshly built image via
#  `kubectl set image`. Called by Jenkins on the develop branch.
#
#  Env (from Jenkins):
#    IMAGE_URI    full ECR URI:tag to deploy (e.g. .../openg2p-at:develop-42)
#    NAMESPACE    k8s namespace of the dev deployment          (default: dev)
#    DEPLOYMENT   dev deployment name                          (default: oan-sr-odoo)
#    CONTAINER    container name inside the deployment         (default: odoo)
#    KUBECONFIG   injected by withCredentials(file 'dev-kubeconfig')
#    ROLLOUT_TIMEOUT  optional, kubectl rollout wait           (default: 180s)
#  Agent prereqs: kubectl.
# =============================================================================
set -euo pipefail

: "${IMAGE_URI:?IMAGE_URI is required}"
: "${KUBECONFIG:?KUBECONFIG is required (dev-kubeconfig credential)}"
NAMESPACE="${NAMESPACE:-dev}"
DEPLOYMENT="${DEPLOYMENT:-oan-sr-odoo}"
CONTAINER="${CONTAINER:-odoo}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"

echo ">> deploy ${IMAGE_URI} -> deployment/${DEPLOYMENT} (${CONTAINER}) in ns ${NAMESPACE}"
kubectl -n "${NAMESPACE}" set image "deployment/${DEPLOYMENT}" "${CONTAINER}=${IMAGE_URI}"
kubectl -n "${NAMESPACE}" rollout status "deployment/${DEPLOYMENT}" --timeout="${ROLLOUT_TIMEOUT}"
echo ">> dev deploy complete: ${DEPLOYMENT} now on ${IMAGE_URI##*/}"
