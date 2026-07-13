pipeline {
    agent any

    environment {
        IMAGE_NAME     = "openg2p-at"
        AWS_ACCOUNT_ID = "379220350808"
        AWS_REGION     = "ap-south-1"
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

        OPENG2P_REGISTRY_REF        = "v1.3.0"
        OPENG2P_SOCIAL_REGISTRY_REF = "v1.3.0"
        OPENG2P_COMMUNITY_REF       = "main"
    }

    stages {
        stage('Determine Environment') {
            steps {
                script {
                    env.DEPLOY_ENV      = (env.BRANCH_NAME == 'main') ? 'production' : 'dev'
                    env.IMAGE_TAG       = (env.BRANCH_NAME == 'main') ? 'latest' : 'dev'
                    env.OPENG2P_ATI_REF = env.BRANCH_NAME
                    env.FULL_IMAGE      = "${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                    env.BUILD_IMAGE     = "${ECR_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}"
                }
            }
        }

        stage('Checkout') {
            steps { checkout scm }
        }

        stage('ECR Login') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds']]) {
                    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                }
            }
        }

        stage('Build Image') {
            steps {
                sh """
                    docker build \
                        --build-arg OPENG2P_REGISTRY_REF=${OPENG2P_REGISTRY_REF} \
                        --build-arg OPENG2P_SOCIAL_REGISTRY_REF=${OPENG2P_SOCIAL_REGISTRY_REF} \
                        --build-arg OPENG2P_COMMUNITY_REF=${OPENG2P_COMMUNITY_REF} \
                        --build-arg OPENG2P_ATI_REF=${OPENG2P_ATI_REF} \
                        -t ${FULL_IMAGE} -t ${BUILD_IMAGE} .
                """
            }
        }

        stage('Push Image') {
            steps {
                sh """
                    docker push ${FULL_IMAGE}
                    docker push ${BUILD_IMAGE}
                """
            }
        }

        stage('Deploy to Prod') {
            when { branch 'main' }
            agent { label 'vpn-agent' }
            steps {
                withCredentials([file(credentialsId: 'prod-kubeconfig', variable: 'KUBECONFIG')]) {
                    input message: "Approve deploy of openg2p-at:${IMAGE_TAG} to production?"
                    sh """
                        helm upgrade --install openg2p-at ./chart \
                            --set image.repository=${ECR_REGISTRY}/${IMAGE_NAME} \
                            --set image.tag=${IMAGE_TAG} \
                            --set postgresql.image.repository=openg2p/postgresql \
                            --set postgresql.image.tag=16.4.0-debian-12-r14 \
                            --set redis.image.repository=openg2p/redis \
                            --set redis.image.tag=7.2.5-debian-12-r4 \
                            -n production
                    """
                }
            }
        }

        stage('Deploy to Dev') {
            when { branch 'develop' }
            agent { label 'vpn-agent' }
            steps {
                withCredentials([file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl set image deployment/oan-sr-odoo \
                            oan-sr-odoo=${FULL_IMAGE} \
                            -n dev

                        kubectl rollout status deployment/oan-sr-odoo -n dev --timeout=120s
                    """
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