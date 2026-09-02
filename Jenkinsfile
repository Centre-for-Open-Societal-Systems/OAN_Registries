// =============================================================================
//  Jenkinsfile — OAN_Registries (OpenG2P / Odoo 17 addons). Multibranch.
//
//  All branches publish to the namespaced ECR repo `oan/registries` (develop + staging_aws
//  migrated off legacy `openg2p-at`). Deploy target routed by branch:
//    staging_aws -> AWS staging: build `oan/registries:staging-aws-<n>`, then `kubectl set
//                   image` on the in-cluster Odoo deployment (oan-sr-odoo-staging, ns dev)
//                   via the vpn-agent (VPN to the dev cluster).
//    staging_ati -> on-prem ATI cluster (node 41) via GitOps: build `oan/registries:staging-<n>`,
//                   then ci/update-kustomize-ati.sh bumps the oan-kustomize
//                   apps/registries/overlays/staging overlay; ArgoCD syncs.
//    develop     -> dev: build `oan/registries:dev-<n>` + kubectl set image (oan-sr-odoo, ns dev).
//
//  staging_aws / staging_ati SHARE the `oan/registries` repo, so each uses a distinct tag
//  prefix (staging-aws-<n> / staging-<n>) — their build-number sequences are independent, so
//  a shared prefix could collide on the immutable tag.
//
//  PREREQUISITES:
//    - oan-kustomize has apps/registries/overlays/staging (it does; ArgoCD app exists).
//    - OPENG2P_ATI_REF = BRANCH_NAME, so the g2p_ati addon source must have a ref named
//      after the branch (`staging_ati` / `staging_aws`). Create those refs, or pin
//      OPENG2P_ATI_REF to a fixed ref, before the first build — else the image build fails.
//    - ECR push on `oan/registries` (ap-south-1) for aws-ecr-creds.
//    - The DEV CLUSTER's image-pull auth must allow `oan/registries` (develop + staging_aws
//      pull it via `kubectl set image`). Same AWS account (379220350808) as the old
//      `openg2p-at`, so an account-wide ECR pull role/secret already covers it; if a per-repo
//      IAM policy restricts pulls, add `oan/registries` before the first dev/staging_aws roll
//      (else the Odoo pod ImagePullBackOffs).
//
//  Credentials: AWS_ACCOUNT_ID (string), aws-ecr-creds (AWS), dev-kubeconfig (file),
//               oan-deployer (GitHub App, contents:write on oan-kustomize).
// =============================================================================
pipeline {
    agent any

    environment {
        AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}"
        AWS_REGION     = "ap-south-1"
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

        OPENG2P_REGISTRY_REF        = "v1.5.10"
        OPENG2P_SOCIAL_REGISTRY_REF = "v1.5.8"
        OPENG2P_COMMUNITY_REF       = "v1.2.5"
    }

    stages {
        stage('Determine Environment') {
            steps {
                script {
                    // All branches now publish to the namespaced repo `oan/registries`
                    // (develop + staging_aws migrated off legacy `openg2p-at`). Because
                    // staging_aws and staging_ati share this one repo and each branch has its
                    // OWN Jenkins build-number sequence, they MUST use distinct tag prefixes
                    // or their immutable <tag>-<build> tags could collide in ECR. Hence:
                    //   staging_ati -> staging-<n>   staging_aws -> staging-aws-<n>   develop -> dev-<n>
                    if (env.BRANCH_NAME == 'staging_ati') {
                        // on-prem ATI (41) via GitOps -> apps/registries overlay uses oan/registries
                        env.IS_ATI          = 'true'
                        env.IMAGE_NAME      = 'oan/registries'
                        env.IMAGE_TAG       = 'staging'
                    } else if (env.BRANCH_NAME == 'staging_aws') {
                        // AWS staging: imperative kubectl to the dev-ns Odoo deployment
                        env.IMAGE_NAME      = 'oan/registries'
                        env.IMAGE_TAG       = 'staging-aws'
                        env.DEPLOYMENT_NAME = 'oan-sr-odoo-staging'
                    } else if (env.BRANCH_NAME == 'develop') {
                        // dev: imperative kubectl to the dev-ns Odoo deployment
                        env.IMAGE_NAME      = 'oan/registries'
                        env.IMAGE_TAG       = 'dev'
                        env.DEPLOYMENT_NAME = 'oan-sr-odoo'
                    } else {
                        error "Determine Environment: unexpected branch '${env.BRANCH_NAME}' (expected develop, staging_aws, or staging_ati)"
                    }
                    // g2p_ati addon ref = the built branch (see PREREQUISITES in the header).
                    env.OPENG2P_ATI_REF = env.BRANCH_NAME
                    env.FULL_IMAGE      = "${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"                 // moving
                    env.BUILD_IMAGE     = "${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-${BUILD_NUMBER}" // immutable
                    echo "branch=${env.BRANCH_NAME} image=${IMAGE_NAME} tag=${IMAGE_TAG} build=${BUILD_IMAGE}"
                }
            }
        }

        stage('Checkout') {
            steps { checkout scm }
        }

        stage('ECR Login') {
            when { anyOf { branch 'develop'; branch 'staging_aws'; branch 'staging_ati' } }
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds']]) {
                    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                }
            }
        }

        stage('Build Image') {
            when { anyOf { branch 'develop'; branch 'staging_aws'; branch 'staging_ati' } }
            steps {
                sh """
                    docker build --no-cache --pull \
                        --build-arg OPENG2P_REGISTRY_REF=${OPENG2P_REGISTRY_REF} \
                        --build-arg OPENG2P_SOCIAL_REGISTRY_REF=${OPENG2P_SOCIAL_REGISTRY_REF} \
                        --build-arg OPENG2P_COMMUNITY_REF=${OPENG2P_COMMUNITY_REF} \
                        --build-arg OPENG2P_ATI_REF=${OPENG2P_ATI_REF} \
                        -t ${FULL_IMAGE} -t ${BUILD_IMAGE} .
                """
            }
        }

        stage('Push Image') {
            when { anyOf { branch 'develop'; branch 'staging_aws'; branch 'staging_ati' } }
            steps {
                sh """
                    docker push ${FULL_IMAGE}
                    docker push ${BUILD_IMAGE}
                """
            }
        }

        // ---------------------- per-branch deploy ----------------------

        stage('Deploy to Dev') {
            when { branch 'develop' }
            agent { label 'vpn-agent' }   // kubectl to the dev cluster (10.15.0.1) is reachable only via the vpn-agent's VPN
            steps {
                withCredentials([file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl set image deployment/${DEPLOYMENT_NAME} odoo=${BUILD_IMAGE} -n dev
                        kubectl rollout status deployment/${DEPLOYMENT_NAME} -n dev --timeout=120s
                    """
                }
            }
        }

        // staging_aws -> AWS staging (imperative kubectl). Registries team's existing logic,
        // re-gated from the old `staging` branch to `staging_aws`. Unchanged otherwise.
        stage('Deploy to Staging (AWS)') {
            when { branch 'staging_aws' }
            agent { label 'vpn-agent' }   // kubectl to oan-sr-odoo-staging (dev cluster) needs the vpn-agent's VPN
            steps {
                withCredentials([file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl set image deployment/${DEPLOYMENT_NAME} odoo=${BUILD_IMAGE} -n dev
                        kubectl rollout status deployment/${DEPLOYMENT_NAME} -n dev --timeout=120s
                        kubectl exec -n dev deploy/${DEPLOYMENT_NAME} -- \
                            sh -c 'nohup python3 /mnt/openg2p-ati/g2p_ati_consent_mgt/utils/mock_fayda_otp_api.py > /tmp/mock_fayda.log 2>&1 &'
                    """
                }
            }
        }

        // staging_ati -> on-prem ATI (41) via GitOps. Bumps the oan-kustomize apps/registries
        // overlay to the freshly built oan/registries image; ArgoCD syncs. Runs on the
        // built-in agent (same workspace as Checkout/Build) so ci/ is present; this only
        // pushes to GitHub. Auth: oan-deployer GitHub App.
        stage('Deploy to Staging (ATI / GitOps)') {
            when { branch 'staging_ati' }
            steps {
                withCredentials([gitUsernamePassword(credentialsId: 'oan-deployer', gitToolName: 'Default')]) {
                    sh '''#!/usr/bin/env bash
                        set -euo pipefail
                        chmod +x ci/update-kustomize-ati.sh
                        # args: <overlay> <kustomize image match-name> <new image ref>
                        ci/update-kustomize-ati.sh staging registries "${BUILD_IMAGE}"
                    '''
                }
            }
        }
    }

    post {
        always {
            sh """
                docker rmi ${FULL_IMAGE} || true
                docker rmi ${BUILD_IMAGE} || true
                docker image prune -f
            """
            sh "docker logout ${ECR_REGISTRY} || true"
        }
    }
}
