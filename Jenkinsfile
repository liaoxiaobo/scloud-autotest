pipeline {
    agent any
    parameters {
//         string(name: 'BRANCH', defaultValue: 'develop', description: '请输入正确Git分支名（如main、develop)', trim: true)
        string(name: 'HOST', defaultValue: '172.22.1.190', description: '请输入环境的管理VIP')
        choice(name: 'STOR', choices: ["xstor", "zbs", "ceph", "xbd", "ustor", "usan", "local", "nfs"], description: '请选择存储池类型')
        string(name: 'USER', defaultValue: 'admin', description: '登录用户名')
        string(name: 'PWD', defaultValue: 'keystone_sugon', description: '登录用户密码')
        text(name: 'MODULE_OVERRIDES', defaultValue: '''security|172.22.3.140|xstor|4||
bigdata|||1||
compute_non_bms|||2||
network|||1||
iam|||4||
bms|||1||''', description: '''模块特殊配置，一行一个覆盖；空字段继承上方通用配置。
格式：模块|host|stor|并行度|user|pwd
示例：
security|172.22.3.140|xstor|4||
container|172.22.3.150|xstor|2|admin|keystone_sugon
database|||2||''')
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
                    env.IMAGE_TAG = "${TIMESTAMP}_${COMMIT_ID}_${env.BUILD_ID}" // 镜像标签（唯一标识：时间戳+提交ID+构建ID）
                    env.WORKSPACE_DIR = "${env.WORKSPACE}"
                    sh "rm -rf allure-result allure-merged-result allure-report"
                    sh "docker build -t playwright-sugon:${env.IMAGE_TAG} ."
//                     sh  'printenv |sort'
                }
          }
      }
        stage('Run Tests'){
            agent{
                docker{
                    image "playwright-sugon:${env.IMAGE_TAG}"
                    args '--rm'
                    reuseNode true
                }
            }
          steps{
                script {
                    def defaultRunConfig = [
                        host: params.HOST,
                        stor: params.STOR,
                        user: params.USER,
                        pwd : params.PWD,
                        parallel: (params.PARALLEL_COUNT ?: '2').trim()
                    ]

                    def parseModuleOverrides = { String value ->
                        def result = [:]
                        value?.split('\n')?.eachWithIndex { rawLine, index ->
                            def line = rawLine.trim()
                            if (!line || line.startsWith('#')) {
                                return
                            }
                            def parts = line.split('\\|', -1).collect { it.trim() }
                            if (parts.size() != 6 || !parts[0]) {
                                error "MODULE_OVERRIDES 第 ${index + 1} 行格式错误，正确格式：模块|host|stor|并行度|user|pwd"
                            }
                            result[parts[0]] = [
                                host: parts[1],
                                stor: parts[2],
                                parallel: parts[3],
                                user: parts[4],
                                pwd: parts[5]
                            ]
                        }
                        return result
                    }

                    def moduleOverrides = parseModuleOverrides(params.MODULE_OVERRIDES)
                    def modules = []
                    def failedModules = []
                    def baseWorkspace = env.WORKSPACE_DIR ?: env.WORKSPACE
                    def markFilter = (params.MARK ?: '').trim().toLowerCase()
                    def jobName = (env.JOB_NAME ?: '').toLowerCase()
                    def isBmsRun = markFilter.contains('bms') || jobName.contains('bms')

                    if (isBmsRun && defaultRunConfig.parallel != '1') {
                        echo "BMS用例依赖同一裸金属资源，Jenkins执行时强制串行，避免资源争抢。"
                    }
                    if (!isBmsRun) {
                        def moduleText = sh(
                            script: "find '${baseWorkspace}/sugon_web/testcase' -mindepth 2 -maxdepth 2 -name 'test_*.py' -print | awk -F/ '{print \$(NF-1)}' | sort -u",
                            returnStdout: true
                        ).trim()
                        modules = moduleText ? moduleText.split('\n').collect { it.trim() }.findAll { it } : []
                        if (modules.contains('compute')) {
                            modules.remove('compute')
                            modules.add('compute_non_bms')
                            modules.add('bms')
                        }
                        if (markFilter) {
                            def markParts = markFilter.split(/[^a-zA-Z0-9_]+/).findAll { it }
                            def moduleNames = modules as Set
                            def selectedModules = markParts.findAll { moduleNames.contains(it) }
                            if (selectedModules) {
                                def overrideModules = moduleOverrides.keySet().findAll { moduleNames.contains(it) }
                                def requestedModules = (selectedModules + overrideModules).unique()
                                modules = modules.findAll { requestedModules.contains(it) }
                            }
                        }
                        echo "自动生成运行单元: ${modules.join(', ')}"
                    }

                    def resolveModuleConfig = { String moduleName ->
                        def override = moduleOverrides[moduleName] ?: [:]
                        return [
                            host: override.host ?: defaultRunConfig.host,
                            stor: override.stor ?: defaultRunConfig.stor,
                            user: override.user ?: defaultRunConfig.user,
                            pwd : override.pwd ?: defaultRunConfig.pwd,
                            parallel: moduleName == 'bms' ? '1' : (override.parallel ?: defaultRunConfig.parallel)
                        ]
                    }

                    def runPytest = { String casePath, Map runCfg, String resultName, String markExpr ->
                        def pytestCommand = "pytest --headless=true " +
                            "--host=${runCfg.host} " +
                            "--stor=${runCfg.stor} " +
                            "--username=${runCfg.user} " +
                            "--password=${runCfg.pwd} " +
                            "-n ${runCfg.parallel} --dist=loadscope " +
                            "${casePath} " +
                            "--alluredir ${baseWorkspace}/allure-result/${resultName}"

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
                        if (markExpr) {
                            pytestCommand += " -m '${markExpr}'"
                        }
                        if (params.RUN_LAST_FAILED) {
                            pytestCommand += " --lf"
                        }

                        echo "Pytest command: ${pytestCommand}"
                        sh pytestCommand
                    }

                    if (modules) {
                        modules.each { moduleName ->
                            def casePath = moduleName in ['compute_non_bms', 'bms'] ?
                                "${baseWorkspace}/sugon_web/testcase/compute" :
                                "${baseWorkspace}/sugon_web/testcase/${moduleName}"
                            sh "test -d '${casePath}'"
                            def runCfg = resolveModuleConfig(moduleName)
                            def markExpr = params.MARK
                            if (moduleName == 'compute_non_bms') {
                                markExpr = markExpr ? "(${markExpr}) and not bms" : "not bms"
                            }
                            if (moduleName == 'bms') {
                                markExpr = markExpr ? "(${markExpr}) and bms" : "bms"
                            }
                            echo "Resolved module ${moduleName}: host=${runCfg.host}, stor=${runCfg.stor}, user=${runCfg.user}, parallel=${runCfg.parallel}, mark=${markExpr ?: 'default'}"
                            try {
                                runPytest(casePath, runCfg, moduleName, markExpr)
                            } catch (err) {
                                failedModules.add(moduleName)
                                currentBuild.result = 'FAILURE'
                                echo "模块 ${moduleName} 执行失败，继续执行后续模块: ${err}"
                            }
                        }
                        if (failedModules) {
                            error "以下模块执行失败: ${failedModules.join(', ')}"
                        }
                    } else {
                        def runCfg = resolveModuleConfig('bms')
                        echo "Resolved bms: host=${runCfg.host}, stor=${runCfg.stor}, user=${runCfg.user}, parallel=${runCfg.parallel}, mark=${params.MARK ?: 'default'}"
                        def testTarget = isBmsRun ? "${baseWorkspace}/sugon_web/testcase/compute/test_bms_*.py" : "${baseWorkspace}/sugon_web/testcase/"
                        runPytest(testTarget, runCfg, "all", params.MARK)
                    }
                //   sh "allure generate allure-result/ -o ./allure-report -c"  // -c代表overwrite报告目录内容
              }
          }
      }
    }
    post('Send Report') {
        always {
            sh "mkdir -p allure-result allure-merged-result"
            // 保留allure历史数据
            sh "cp -r allure-report/history allure-merged-result/ || true" // 忽略复制失败（首次构建无 history 目录）
//             sh "cp -f sugon_web/environment.properties allure-result/"

            // 多模块会分别写入 allure-result/<module>/，发布前合并为单个结果目录
            sh "find allure-result -maxdepth 3 -type f -exec cp {} allure-merged-result/ \\; || true"

            // Jenkins Allure 插件发布报告；失败时继续归档结果，避免报告完全不可看
            script {
                try {
                    allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-merged-result']]
                } catch (err) {
                    echo "Allure 插件发布失败: ${err}"
                }
            }

            archiveArtifacts artifacts: 'allure-result/**, allure-merged-result/**, screenshots/**/*.png', allowEmptyArchive: true, fingerprint: true

            // 清理整个工作目录
            // deleteDir()  // clean up our workspace

            // Docker 系统清理
            sh "docker rmi playwright-sugon:${env.IMAGE_TAG} || true" // 删除本次构建的临时镜像
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
