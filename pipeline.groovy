

pipeline {
    stages {
        stage('Running Inter-Capability E2E Tests') {
            stages {
                stage('BDD Orchestration') {
                    stage('Customer E2E BDD') {
                        when { expression { return stageimpl.contains('ep-cus-customer-common') } }
                        steps {
                            script {
                                def repos = TAG["$params.git_repo"].customer_bdd_repo.split(',')
                                def custIndex = 1
                                for (repo in repos) {
                                    epCustomerCommon(stageimpl, "${TAGS}", "${environCustomer}",
                                        "${mstrBranch}", "${releaseTag}", "$params.git_repo", "${repo}", "CustomerE2E${custIndex}")
                                    custIndex = custIndex + 1
                                }
                            }
                        }
                    }
                    stage('Customer Baseline BDD') {
                        when { expression { return stageimpl.contains('ep-cus-customer-baseline') } }
                        steps {
                            epCustomerCommon(stageimpl, "${TAGS}", "${environCustomer}", branchConfig["ep-cus-customer-service"], branchConfig["ep-cus-customer-service"], "${releaseTag}", "${params.git_repo}", "CustomerBaseline")
                        }
                    }
                }
            }
        }
    }
}


def call(String stageimpl, String TAGS, String environ, String mstrbranch, String releaseTag, String repo, String checkoutRepo, String reportFileName) {
    stage("${checkoutRepo}") {
        container('gradle') {
            script {
                if ("${repo}".contains("${checkoutRepo}")){
                    branch = "${releaseTag}"
                } else {
                    branch = "${mstrbranch}"
                }
                repoUrl = 'https://github.com/lbg-gcp-foundation/' + checkoutRepo

                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "${branch}"]],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'CustomerE2E']],
                    submoduleCfg: [],
                    userRemoteConfigs: [[credentialsId: 'jenkinsPAT', url: "${repoUrl}"]]
                ])

                dir('CustomerE2E') {
                    dir('bdd') {
                        script {
                            try {
                                sh """
                                echo "******************** Customers BDD Execution ********************"
                                pwd
                                cp -Rf ../../testData/testdata.json ./testdata.json
                                gradle cucumber -Dtags="${TAGS}" -Denv.type="${environ}_apigee"
                                cp -Rf ./target/cucumber.json ../../Cucumber_Report/"${reportFileName}"
                                cp -Rf ./testdata.json ../../testData/testdata.json
                                echo "************************** File print testdata.json **************************"
                                cat ./testdata.json
                                """
                            }
                            catch (err) {
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
