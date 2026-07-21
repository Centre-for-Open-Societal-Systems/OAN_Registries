pipeline {
    agent any

    environment {
        IMAGE_NAME     = "openg2p-at"
        AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}"
        AWS_REGION     = "ap-south-1"
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

        OPENG2P_REGISTRY_REF        = "v1.3.0"
        OPENG2P_SOCIAL_REGISTRY_REF = "v1.3.0"
        OPENG2P_COMMUNITY_REF       = "v1.2.5"
    }

    
    stages {
        stage('Determine Environment') {
            steps {
                script {
                    if (env.BRANCH_NAME == 'staging') {
                        env.IMAGE_TAG       = 'staging'
                        env.DEPLOY_ENV      = 'staging'
                        env.DEPLOYMENT_NAME = 'oan-sr-odoo-staging'
                    } else {
                        env.IMAGE_TAG       = 'dev'
                        env.DEPLOY_ENV      = 'dev'
                        env.DEPLOYMENT_NAME = 'oan-sr-odoo'
                    }
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

        stage('Deploy to Dev') {
            when { branch 'develop' }
            agent { label 'vpn-agent' }
            steps {
                withCredentials([file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl set image deployment/${DEPLOYMENT_NAME} \
                            odoo=${FULL_IMAGE} \
                            -n dev

                        kubectl rollout status deployment/${DEPLOYMENT_NAME} -n dev --timeout=120s
                    """
                }
            }
        }

        stage('Deploy to Staging') {
            when { branch 'staging' }
            agent { label 'vpn-agent' }
            steps {
                withCredentials([file(credentialsId: 'dev-kubeconfig', variable: 'KUBECONFIG')]) {
                    input message: "Approve deploy of openg2p-at:${IMAGE_TAG} to staging (oan-sr-odoo-staging)?"
                    sh """
                        kubectl set image deployment/${DEPLOYMENT_NAME} \
                            odoo=${FULL_IMAGE} \
                            -n dev

                        kubectl rollout status deployment/${DEPLOYMENT_NAME} -n dev --timeout=120s
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