// =============================================================================
//  Jenkinsfile — OAN_Registries (OpenG2P / Odoo 17 addons). Single pipeline for
//  the `oan-package` GitHub Organization folder (multibranch).
//
//  Per branch (same shape as oan_a2c / OAN-Access-To-Credit-System):
//    develop -> build + push to ECR (legacy `openg2p-at`) + ci/deploy-dev.sh
//               (kubectl set image on the in-cluster dev Odoo deployment — UNCHANGED
//                target; just extracted out of the pipeline into a script)
//    staging -> build + push to ECR (`oan/registries`) + ci/update-kustomize.sh
//               (GitOps: bump the oan-kustomize `staging` overlay; ArgoCD on node 41 syncs)
//
//  develop intentionally still targets the LEGACY `openg2p-at` repo (its dev
//  deployment pulls that image). Migrating develop to `oan/registries` is a follow-up.
//
//  PREREQUISITE for the staging stage: the oan-kustomize repo does NOT yet have an
//  `apps/registries` app. The staging → GitOps stage is wired to the target layout
//  (apps/registries/overlays/staging) and will no-op/fail until that overlay exists.
//  Until then, promote this file to `staging` only after the kustomize app is added.
//
//  The previous monolithic pipeline (direct kubectl deploys + mock-OTP exec) is
//  retained verbatim as Jenkinsfile.main for reference/fallback.
//
//  Tags:  <branch>-<build>   immutable, pinned by oan-kustomize / the dev deploy
//         <branch>-latest    moving alias (convenience)
//
//  Agent needs: docker(+buildx), aws cli v2, git, kustomize, kubectl.
//  Credentials: AWS_ACCOUNT_ID (string), oan-deployer (GitHub App), dev-kubeconfig (file).
//  NOTE: `aws ecr get-login-password` uses the agent's ambient AWS identity, which
//        must have ECR push on both `openg2p-at` and `oan/*`.
// =============================================================================
pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '30'))
    timeout(time: 60, unit: 'MINUTES')
  }

  environment {
    AWS_REGION      = 'ap-south-1'
    // Odoo image build (OpenG2P upstream refs pulled by the Dockerfile).
    OPENG2P_REGISTRY_REF        = 'v1.5.10'
    OPENG2P_SOCIAL_REGISTRY_REF = 'v1.5.8'
    OPENG2P_COMMUNITY_REF       = '6ab9227081f12d6b7a836aef4e193a37813bd22c'
    // in-cluster dev deploy target (develop branch).
    DEV_NAMESPACE   = 'dev'
    DEV_DEPLOYMENT  = 'oan-sr-odoo'
    DEV_CONTAINER   = 'odoo'
  }

  stages {
    stage('Resolve') {
      steps {
        script {
          // staging -> new namespaced repo; everything else -> legacy repo (unchanged).
          env.ECR_REPO      = (env.BRANCH_NAME == 'staging') ? 'oan/registries' : 'openg2p-at'
          env.OPENG2P_ATI_REF = env.BRANCH_NAME          // this repo's addons ref = the built branch
          env.IMMUTABLE_TAG = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"
          env.MOVING_TAG    = "${env.BRANCH_NAME}-latest"
          echo "branch=${env.BRANCH_NAME}  repo=${env.ECR_REPO}  tag=${env.IMMUTABLE_TAG}  ati_ref=${env.OPENG2P_ATI_REF}"
        }
      }
    }

    stage('Build image') {
      when { anyOf { branch 'develop'; branch 'staging' } }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

            DOCKER_BUILDKIT=1 docker buildx build \
              --build-arg OPENG2P_REGISTRY_REF=${OPENG2P_REGISTRY_REF} \
              --build-arg OPENG2P_SOCIAL_REGISTRY_REF=${OPENG2P_SOCIAL_REGISTRY_REF} \
              --build-arg OPENG2P_COMMUNITY_REF=${OPENG2P_COMMUNITY_REF} \
              --build-arg OPENG2P_ATI_REF=${OPENG2P_ATI_REF} \
              --tag ${IMAGE_URI}:${IMMUTABLE_TAG} \
              --tag ${IMAGE_URI}:${MOVING_TAG} \
              --network=host --load .
            echo "Built ${IMAGE_URI}:${IMMUTABLE_TAG}"
          '''
        }
      }
    }

    stage('Push to ECR') {
      when { anyOf { branch 'develop'; branch 'staging' } }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
            IMAGE_URI="${REGISTRY}/${ECR_REPO}"

            aws ecr get-login-password --region ${AWS_REGION} \
              | docker login --username AWS --password-stdin "${REGISTRY}"

            docker push ${IMAGE_URI}:${IMMUTABLE_TAG}
            docker push ${IMAGE_URI}:${MOVING_TAG}       # same digest -> ECR dedups

            # Scoped cleanup ONLY. Never `docker system prune -f` on a shared agent.
            docker rmi ${IMAGE_URI}:${IMMUTABLE_TAG} ${IMAGE_URI}:${MOVING_TAG} || true
            echo "Pushed ${IMAGE_URI}:${IMMUTABLE_TAG} (+ ${MOVING_TAG})"
          '''
        }
      }
    }

    // ---------------------- per-branch deploy ----------------------

    // develop -> in-cluster dev Odoo deployment (kubectl set image). Same target as
    // before the restructure; logic lives in ci/deploy-dev.sh.
    stage('develop → dev (k8s)') {
      when { branch 'develop' }
      steps {
        withCredentials([
          string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID'),
          file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')
        ]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            chmod +x ci/deploy-dev.sh
            IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMMUTABLE_TAG}" \
            NAMESPACE=${DEV_NAMESPACE} DEPLOYMENT=${DEV_DEPLOYMENT} CONTAINER=${DEV_CONTAINER} \
            bash ci/deploy-dev.sh
          '''
        }
      }
    }

    // staging -> GitOps: bump the oan-kustomize `staging` overlay to the new image.
    // Auth is the `oan-deployer` GitHub App (contents:write on oan-kustomize only).
    // NOTE: requires apps/registries/overlays/staging to exist in oan-kustomize.
    stage('staging → GitOps (ArgoCD@41)') {
      when { branch 'staging' }
      steps {
        withCredentials([
          string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID'),
          gitUsernamePassword(credentialsId: 'oan-deployer', gitToolName: 'Default')
        ]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            chmod +x ci/update-kustomize.sh
            # args: <overlay> <kustomize image match-name> <new image ref>
            ci/update-kustomize.sh staging registries \
              "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMMUTABLE_TAG}"
          '''
        }
      }
    }
  }

  post {
    success { echo "OK  ${env.BRANCH_NAME} #${env.BUILD_NUMBER} -> ${env.IMMUTABLE_TAG}" }
    failure { echo "FAIL ${env.BRANCH_NAME} #${env.BUILD_NUMBER}" }
  }
}
