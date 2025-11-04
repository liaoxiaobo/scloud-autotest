pipeline {
    agent any
    parameters {
        // choice(name: 'BRANCH', choices: ["master"], description: '代码分支')
        string(name: 'HOST', defaultValue: '172.22.1.170', description: '测试环境管理VIP')
        string(name: 'USER', defaultValue: 'admin', description: '登录用户名')
        string(name: 'PWD', defaultValue: 'keystone_sugon', description: '登录用户密码')
        choice(name: 'MODULE', choices: ["all", "iaas", "paas"], description: '云服务类别（选择 all 运行所有用例）')
        string(name: 'KEY', defaultValue: '', description: '可选的用例过滤关键字（ecs、evs、vpc等）')
        booleanParam(name: 'RUN_LAST_FAILED', defaultValue: false, description: '是否只运行上次失败的测试')
        booleanParam(name: 'FEISHU_NOTIFY', defaultValue: false, description: '是否推送飞书群消息')
    }
    environment {
        // branch = "${params.BRANCH}"
        host = "${params.HOST}"
    }
    stages {
        // stage('Checkout') {
        //     steps {
        //         git branch: "${branch}",
        //         url: "git@code.mysugoncloud.com:SugonCloud_Stack_V8.0/playwright-sugon.git"
        //     }
        // }
        stage('Build Docker Image'){
          steps{
                script{
                    TIMESTAMP = sh(script: "date +%Y%m%d_%H%M", returnStdout: true).trim()
                    COMMIT_ID = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                    IMAGE_TAG = "${TIMESTAMP}_${COMMIT_ID}_${env.BUILD_ID}"
                    // stage间传递局部变量dir
                    dir = "$workspace"
                    sh "docker build -t playwright-sugon:${IMAGE_TAG} ."
                    // sh  'printenv |sort'
                }
          }
      }
        stage('Run Tests'){
            agent{
                docker{
                    image "playwright-sugon:${IMAGE_TAG}"
                    args '--rm'
                }
            }
          steps{
                script {
                    def pytestCommand = "pytest --headless=true --host=$host --username=${params.USER} --password=${params.PWD} -n 2 --dist=loadscope $dir/sugon_web/testcase/ --alluredir $dir/allure-result"

                    // 用例筛选逻辑
                    if (params.KEY) {
                        pytestCommand += " -k '${params.MODULE} and ${params.KEY}'"
                    }
                    else {
                        pytestCommand += " -k '${params.MODULE}'"
                    }

                    // 添加 RUN_LAST_FAILED 参数
                    if (params.RUN_LAST_FAILED) {
                        pytestCommand += " --lf"
                    }

                    sh pytestCommand
                //   sh "allure generate allure-result/ -o ./allure-report -c"  // -c代表overwrite报告目录内容
              }
          }
      }
    }
    post('Send Report') {
        always {
            // 生成测试历史数据和首页数据
            sh "cp -r allure-report/history allure-result/ || true"
//             sh "cp -f sugon_web/environment.properties allure-result/"

            // 生成 Allure 报告
            allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-result']]

            // 清理临时文件
            sh "rm -f allure-result/* || true"

            // 清理整个工作目录
            // deleteDir()  // clean up our workspace

            // Docker 系统清理
            sh "docker system prune -f"

            // 发送报告到飞书
            script {
                  if (params.FEISHU_NOTIFY) {
                      sendNotification(currentBuild.currentResult)
                  }
            }
        }
        // success {
        //     mail to: 'liaoxb@sugon.com',
        //     cc: 'sunrui1@sugon.com',
        //     subject: "接口自动化测试通过: ${currentBuild.fullDisplayName}",
        //     body: "测试报告地址: ${env.BUILD_URL}"
        // }
        // failure {
        //     mail to: 'liaoxb@sugon.com',
        //     cc: 'sunrui1@sugon.com',
        //     subject: "接口自动化测试失败: ${currentBuild.fullDisplayName}",
        //     body: "测试报告地址: ${env.BUILD_URL}"
        // }
    }
}

// 发送飞书通知函数
def sendNotification(String result) {
    sh """
    curl -X POST -H "Content-Type: application/json" \\
        -d '{
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "${env.JOB_NAME} #${env.BUILD_NUMBER}",
                    "content": [
                        [{
                            "tag": "text",
                            "text": "测试环境: ${params.HOST}:30000\\n测试结果: ${result}\\n执行时间: ${new Date().format("yyyy.MM.dd HH:mm:ss")}\\n"
                        }, {
                            "tag": "a",
                            "text": "查看报告",
                            "href": "${env.BUILD_URL}"
                        }]
                    ]
                }
            }
        }
    }' https://open.feishu.cn/open-apis/bot/v2/hook/6a07f306-b045-4748-bead-13ce14d9beda
    """
}