pipeline {
    agent any
    parameters {
//         string(name: 'BRANCH', defaultValue: 'develop', description: '请输入正确Git分支名（如main、develop)', trim: true)
        string(name: 'HOST', defaultValue: '172.22.1.190', description: '请输入环境的管理VIP')
        choice(name: 'STOR', choices: ["xstor", "zbs", "ceph", "xbd", "ustor", "usan", "local", "nfs"], description: '请选择存储池类型')
        string(name: 'USER', defaultValue: 'admin', description: '登录用户名')
        string(name: 'PWD', defaultValue: 'keystone_sugon', description: '登录用户密码')
        string(name: 'MARK', defaultValue: '', description: '标签筛选用例。模块级：container/compute/storage/network 等；服务级：cce/ecs/evs/obs/vpc 等；常用组合：storage and obs、compute and ecs、container and smoke、not slow')
        string(name: 'BMS_INSTANCE_NAME', defaultValue: '', description: 'BMS复用实例名称（留空使用配置文件）')
        string(name: 'BMS_BMC_IP', defaultValue: '', description: 'BMS带外IP（留空使用配置文件）')
        string(name: 'BMS_PREFERRED_NODE', defaultValue: '', description: 'BMS优先物理节点（留空使用配置文件）')
        string(name: 'BMS_NETWORK_NAME', defaultValue: '', description: 'BMS网络名称（留空使用配置文件）')
        string(name: 'BMS_PASSWORD', defaultValue: '', description: 'BMS实例登录密码（留空使用配置文件）')
        string(name: 'PARALLEL_COUNT', defaultValue: '2', description: '测试并行线程数（BMS任务会自动强制串行）')
        booleanParam(name: 'RUN_LAST_FAILED', defaultValue: false, description: '是否只运行上次失败的测试')
        booleanParam(name: 'FEISHU_NOTIFY', defaultValue: false, description: '是否推送飞书群消息')
    }
    environment {
        START_TIME = new Date().format("yyyy.MM.dd HH:mm:ss")
    }
    stages {
//         stage('Checkout') {
//             steps {
//                 script {
//                     def repoUrl = "git@code.mysugoncloud.com:full-stack-cloud/playwright-sugon.git"
//                     def branchName = params.BRANCH
//                     git(
//                         url: repoUrl,
//                         branch: branchName
//                         // credentialsId: 'sugon-git-ssh-key'  // 无需显式指定，SSH Key已配置Jenkins服务器公钥
//                         )
//                 }
//             }
//         }
        stage('Build Docker Image'){
          steps {
                script{
                    TIMESTAMP = sh(script: "date +%Y%m%d_%H%M", returnStdout: true).trim()
                    COMMIT_ID = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                    IMAGE_TAG = "${TIMESTAMP}_${COMMIT_ID}_${env.BUILD_ID}" // 镜像标签（唯一标识：时间戳+提交ID+构建ID）
                    sh "docker build -t playwright-sugon:${IMAGE_TAG} ."
//                     sh  'printenv |sort'
                }
          }
      }
        stage('Run Tests'){
            agent{
                docker{
                    image "playwright-sugon:${IMAGE_TAG}"
                    args '--rm'
                    reuseNode true
                }
            }
          steps{
                script {
                    def markFilter = (params.MARK ?: '').trim().toLowerCase()
                    def jobName = (env.JOB_NAME ?: '').toLowerCase()
                    def effectiveParallelCount = (params.PARALLEL_COUNT ?: '2').trim()
                    def isBmsRun = markFilter.contains('bms') || jobName.contains('bms')

                    if (isBmsRun && effectiveParallelCount != '1') {
                        echo "BMS用例依赖同一裸金属资源，Jenkins执行时强制串行，避免资源争抢。"
                        effectiveParallelCount = '1'
                    }

                    def testTarget = isBmsRun ? "sugon_web/testcase/compute/test_bms_*.py" : "sugon_web/testcase/"

                    // 构建 pytest 命令（核心测试逻辑）
                    def pytestCommand = "pytest --headless=true --host=${params.HOST} --stor=${params.STOR} --username=${params.USER} --password=${params.PWD} ${testTarget} --alluredir allure-result"
                    if (params.BMS_INSTANCE_NAME?.trim()) {
                        pytestCommand += " --bms-instance-name=${params.BMS_INSTANCE_NAME.trim()}"
                    }
                    if (params.BMS_BMC_IP?.trim()) {
                        pytestCommand += " --bms-bmc-ip=${params.BMS_BMC_IP.trim()}"
                    }
                    if (params.BMS_PREFERRED_NODE?.trim()) {
                        pytestCommand += " --bms-preferred-node=${params.BMS_PREFERRED_NODE.trim()}"
                    }
                    if (params.BMS_NETWORK_NAME?.trim()) {
                        pytestCommand += " --bms-network-name=${params.BMS_NETWORK_NAME.trim()}"
                    }
                    if (params.BMS_PASSWORD?.trim()) {
                        pytestCommand += " --bms-password=${params.BMS_PASSWORD.trim()}"
                    }
                    if (effectiveParallelCount != '1') {
                        pytestCommand += " -n ${effectiveParallelCount} --dist=loadscope"
                    }

                    // 标签筛选逻辑（-m 参数）
                    if (params.MARK) {
                        pytestCommand += " -m '${params.MARK}'"
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
            // conftest.py 会按运行目标写入 allure-result/<run_id>/，Allure 插件只读取配置目录本层文件。
            // 生成报告前汇总子目录结果，避免只展示 environment 而没有 test cases。
            sh "find allure-result -mindepth 2 -type f ! -path '*/history/*' -exec cp -n {} allure-result/ \\; || true"

            // 保留allure历史数据
            sh "cp -r allure-report/history allure-result/ || true" // 忽略复制失败（首次构建无 history 目录）
//             sh "cp -f sugon_web/environment.properties allure-result/"

            // 生成 Allure 报告
            allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-result']]

            // 清理临时文件
            sh "rm -rf allure-result/* || true"

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
                            "text": "测试环境: ${params.HOST}:30000\\n测试结果: ${result}\\n开始时间: ${env.START_TIME}\\n结束时间: ${new Date().format("yyyy.MM.dd HH:mm:ss")}\\n"
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
