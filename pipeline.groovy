pipeline {
    agent any

    environment {
        GITHUB_TOKEN = credentials('github-token-id') // Replace with your credentials ID
    }
    

    stages {
        stage('Fetch PR Labels') {
            steps {
                script {
                    def prNumber = env.ghprbPullId
                    def repo = 'owner/repository'
                    def response = sh(script: "curl -s -H \"Authorization: token ${env.GITHUB_TOKEN}\" -H \"Accept: application/vnd.github.v3+json\" https://api.github.com/repos/${repo}/issues/${prNumber}/labels", returnStdout: true).trim()
                    def labels = readJSON(text: response)
                    
                    // Ensure there are exactly 4 labels
                    if (labels.size() != 4) {
                        error("Expected exactly 4 labels, but found ${labels.size()}.")
                    }
                    
                    // Extract appName and releaseName from labels
                    def appNameLabel = labels.find { it.name.startsWith('appname:') }
                    def releaseNameLabel = labels.find { it.name.startsWith('releaseName:') }
                    
                    if (!appNameLabel || !releaseNameLabel) {
                        error("Required labels not found.")
                    }
                    
                    def appName = appNameLabel.name.split(': ')[1]
                    def releaseName = releaseNameLabel.name.split(': ')[1]
                    
                    // Read the YAML file
                    def appConfig = readYaml file: 'path/to/app_config.yaml'
                    def serviceConfig = appConfig.services[appName]
                    
                    // Check if appName exists in YAML
                    if (!serviceConfig) {
                        error("Appname '${appName}' not found in YAML configuration. Stopping pipeline execution.")
                    }
                    
                    def contextPath = serviceConfig.context_path
                    
                    env.ACTUATOR_ENDPOINT = "https://your-canary-service${contextPath}"
                    env.RELEASE_NAME = releaseName
                    env.APP_NAME = appName
                    
                    echo "Labels for PR #${prNumber}: ${labels*.name.join(', ')}"
                    echo "ACTUATOR_ENDPOINT: ${env.ACTUATOR_ENDPOINT}"
                    echo "RELEASE_NAME: ${env.RELEASE_NAME}"
                }
            }
        }
        stage('Check Actuator Health') {
            when {
                expression { return env.ACTUATOR_ENDPOINT != null }
            }
            steps {
                withCredentials([
                    file(credentialsId: 'tls-crt-id', variable: 'TLS_CRT_PATH'),
                    file(credentialsId: 'tls-key-id', variable: 'TLS_KEY_PATH')
                ]) {
                    sh """
                    chmod +x path/to/your/script.sh
                    path/to/your/script.sh \$TLS_CRT_PATH \$TLS_KEY_PATH \$ACTUATOR_ENDPOINT \$RELEASE_NAME
                    """
                }
            }
        }
        stage('Run BDD Tests') {
            when {
                expression { return env.ACTUATOR_ENDPOINT != null }
            }
            steps {
                script {
                    epCustomerCommon('stageimpl', "${env.TAGS}", "${env.BRANCH}", "${env.APP_NAME}")
                }
            }
        }
    }
}

def epCustomerCommon(stageimpl, TAGS, branch, appName) {
    stage("${appName} BDD") {
        container('gradle') {
            script {
                def repoUrl = 'https://github.com/lbg-gcp-foundation/' + appName

                checkout([
                    $class: 'GitSCM',
                    branches: [[name: branch]],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${appName}-E2E"]],
                    submoduleCfg: [],
                    userRemoteConfigs: [[credentialsId: 'jenkinsPAT', url: repoUrl]]
                ])

                dir("${appName}-E2E") {
                    dir('bdd') {
                        script {
                            try {
                                sh """
                                echo "******************** Customers BDD Execution ********************"
                                pwd
                                cp -Rf ../../testData/testdata.json ./testdata.json
                                gradle cucumber -Dtags="${TAGS}" -Denv.type="${env.ENVIORN}_apigee"
                                cp -Rf ./target/cucumber.json ../../Cucumber_Report/"${reportFileName}"
                                cp -Rf ./testdata.json ../../testData/testdata.json
                                echo "************************** File print testdata.json **************************"
                                cat ./testdata.json
                                """
                            } catch (err) {
                                archive includes: 'logs/*'
                                archive includes: 'logs/**/**'
                                sh """
                                cp -Rf ./target/cucumber.json ../../Cucumber_Report/"${reportFileName}"
                                cp -Rf ./testdata.json ../../testData/testdata.json
                                exit 1
                                """
                            }
                        }
                    }
                }
            }
        }
    }
    archive includes: 'logs/*'
    archive includes: 'logs/**/**'
}
