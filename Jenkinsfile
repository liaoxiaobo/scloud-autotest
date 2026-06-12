pipeline {
    agent any
    parameters {
//         string(name: 'BRANCH', defaultValue: 'develop', description: '请输入正确Git分支名（如main、develop)', trim: true)
        string(name: 'HOST', defaultValue: '172.22.1.190', description: '请输入环境的管理VIP')
        choice(name: 'STOR', choices: ["xstor", "zbs", "ceph", "xbd", "ustor", "usan", "local", "nfs"], description: '请选择存储池类型')
        string(name: 'USER', defaultValue: 'admin', description: '登录用户名')
        string(name: 'PWD', defaultValue: 'keystone_sugon', description: '登录用户密码')
        string(name: 'MODULES', defaultValue: '', description: '要运行的模块目录名，逗号分隔。如：database,middleware,bigdata。为空时按原逻辑运行整个 testcase')
        text(name: 'ENV_CONFIGS', defaultValue: '''bigdata_env|172.22.1.190|ceph|admin|keystone_sugon
middleware_env|172.22.1.190|usan|admin|keystone_sugon
special_env|172.22.1.191|ceph|admin|keystone_sugon''', description: '''页面维护的环境池，一行一个环境，不依赖 Jenkins 插件。
格式：环境别名|host|stor|user|pwd''')
        text(name: 'MODULE_ENV_MAP', defaultValue: '''bigdata=bigdata_env
middleware=middleware_env''', description: '''模块绑定环境别名，一行一个映射，不依赖 Jenkins 插件。
示例：
bigdata=bigdata_env
middleware=middleware_env''')
        text(name: 'MODULE_MARK_MAP', defaultValue: '', description: '''模块绑定 pytest mark，一行一个映射。优先级高于全局 MARK。
示例：
database=mysql
middleware=redis''')
        string(name: 'MARK', defaultValue: '', description: '标签筛选用例。模块级：container/compute/storage/network 等；服务级：cce/ecs/evs/obs/vpc 等；常用组合：storage and obs、compute and ecs、container and smoke、not slow')
        string(name: 'PARALLEL_COUNT', defaultValue: '2', description: '测试并行线程数（默认值2，不能超过CPU核心数）')
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
                    dir = "$workspace"  // 记录工作目录,供后续stage使用（容器内执行测试时需知道代码路径）
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
                }
            }
          steps{
                script {
                    def defaultEnv = [
                        host: params.HOST,
                        stor: params.STOR,
                        user: params.USER,
                        pwd : params.PWD
                    ]

                    def parseEnvConfigs = { String value ->
                        def result = [:]
                        value?.split('\n')?.eachWithIndex { rawLine, index ->
                            def line = rawLine.trim()
                            if (!line || line.startsWith('#')) {
                                return
                            }
                            def parts = line.split('\\|', -1).collect { it.trim() }
                            if (parts.size() != 5) {
                                error "ENV_CONFIGS 第 ${index + 1} 行格式错误，正确格式：环境别名|host|stor|user|pwd"
                            }
                            result[parts[0]] = [
                                host: parts[1],
                                stor: parts[2],
                                user: parts[3],
                                pwd : parts[4]
                            ]
                        }
                        return result
                    }

                    def parseModuleEnvMap = { String value ->
                        def result = [:]
                        value?.split('\n')?.eachWithIndex { rawLine, index ->
                            def line = rawLine.trim()
                            if (!line || line.startsWith('#')) {
                                return
                            }
                            def parts = line.split('=', -1).collect { it.trim() }
                            if (parts.size() != 2 || !parts[0] || !parts[1]) {
                                error "MODULE_ENV_MAP 第 ${index + 1} 行格式错误，正确格式：模块名=环境别名"
                            }
                            result[parts[0]] = parts[1]
                        }
                        return result
                    }

                    def envConfigs = parseEnvConfigs(params.ENV_CONFIGS)
                    def moduleEnvMap = parseModuleEnvMap(params.MODULE_ENV_MAP)
                    def moduleMarkMap = parseModuleEnvMap(params.MODULE_MARK_MAP)

                    def modules = []
                    if (params.MODULES?.trim()) {
                        modules = params.MODULES.split(',').collect { it.trim() }.findAll { it }
                    }

                    def runPytest = { String casePath, Map envCfg, String resultName, String markExpr ->
                        def pytestCommand = "pytest --headless=true " +
                            "--host=${envCfg.host ?: defaultEnv.host} " +
                            "--stor=${envCfg.stor ?: defaultEnv.stor} " +
                            "--username=${envCfg.user ?: defaultEnv.user} " +
                            "--password=${envCfg.pwd ?: defaultEnv.pwd} " +
                            "-n ${params.PARALLEL_COUNT} --dist=loadscope " +
                            "${casePath} " +
                            "--alluredir ${dir}/allure-result/${resultName}"

                        if (markExpr) {
                            pytestCommand += " -m '${markExpr}'"
                        }
                        if (params.RUN_LAST_FAILED) {
                            pytestCommand += " --lf"
                        }

                        sh pytestCommand
                    }

                    if (modules) {
                        modules.each { moduleName ->
                            def casePath = "${dir}/sugon_web/testcase/${moduleName}"
                            sh "test -d '${casePath}'"
                            def envName = moduleEnvMap[moduleName]
                            def envCfg = defaultEnv + (envName ? (envConfigs[envName] ?: [:]) : [:])
                            if (envName && !envConfigs[envName]) {
                                error "模块 ${moduleName} 指定的环境 ${envName} 不存在，请检查 ENV_CONFIGS"
                            }
                            def markExpr = moduleMarkMap[moduleName] ?: params.MARK
                            echo "Run module ${moduleName} on ${envCfg.host}, stor=${envCfg.stor}, env=${envName ?: 'default'}, mark=${markExpr ?: 'default'}"
                            runPytest(casePath, envCfg, moduleName, markExpr)
                        }
                    } else {
                        runPytest("${dir}/sugon_web/testcase/", defaultEnv, "all", params.MARK)
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

            // Jenkins Allure 插件发布报告；失败时继续生成静态报告产物，避免报告完全不可看
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
