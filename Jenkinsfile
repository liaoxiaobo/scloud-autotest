pipeline {
    agent any
    parameters {
//         string(name: 'BRANCH', defaultValue: 'develop', description: '请输入正确Git分支名（如main、develop)', trim: true)
        string(name: 'HOST', defaultValue: '172.22.1.190', description: '请输入环境的管理VIP')
        choice(name: 'STOR', choices: ["xstor", "zbs", "ceph", "xbd", "ustor", "usan", "local", "nfs"], description: '请选择存储池类型')
        booleanParam(name: 'STORAGE_DEDICATED_ENV', defaultValue: true, description: 'storage 模块是否使用独立环境')
        string(name: 'STORAGE_HOST', defaultValue: '172.22.3.150', description: 'storage 模块专用管理 VIP')
        choice(name: 'STORAGE_STOR', choices: ["zbs", "xstor", "ceph", "xbd", "ustor", "usan", "local", "nfs"], description: 'storage 模块专用存储池类型')
        booleanParam(name: 'SECURITY_DEDICATED_ENV', defaultValue: true, description: 'security 模块是否使用独立环境')
        string(name: 'SECURITY_HOST', defaultValue: '172.22.3.140', description: 'security 模块专用管理 VIP')
        string(name: 'MODULES', defaultValue: '', description: '要运行的模块目录名，逗号分隔。如：database,middleware,bigdata。支持虚拟模块 compute_non_bms、bms；填写后覆盖 RUN_PLAN。')
        text(name: 'ENV_CONFIGS', defaultValue: '''database_env|172.22.1.190|ceph
middleware_env|172.22.1.189|usan''', description: '''页面维护的环境池，一行一个环境，不依赖 Jenkins 插件。
格式：环境别名|host|stor。兼容旧格式：环境别名|host|stor|user|pwd''')
        text(name: 'MODULE_ENV_MAP', defaultValue: '''database=database_env
middleware=middleware_env''', description: '''模块绑定环境别名，一行一个映射，不依赖 Jenkins 插件。
示例：
database=database_env
middleware=middleware_env''')
        text(name: 'MODULE_MARK_MAP', defaultValue: '', description: '''模块绑定 pytest mark，一行一个映射。优先级高于全局 MARK。
示例：
database=mysql
middleware=redis''')
        string(name: 'MARK', defaultValue: '', description: '标签筛选用例。模块级：container/compute/storage/network 等；服务级：cce/ecs/evs/obs/vpc 等；常用组合：storage and obs、compute and ecs、container and smoke、not slow')
        string(name: 'BMS_INSTANCE_NAME', defaultValue: '', description: 'BMS复用实例名称（留空使用配置文件）')
        string(name: 'BMS_BMC_IP', defaultValue: '', description: 'BMS带外IP（留空使用配置文件）')
        string(name: 'BMS_PREFERRED_NODE', defaultValue: '', description: 'BMS优先物理节点（留空使用配置文件）')
        string(name: 'BMS_NETWORK_NAME', defaultValue: '', description: 'BMS网络名称（留空使用配置文件）')
        string(name: 'BMS_PASSWORD', defaultValue: '', description: 'BMS实例登录密码（留空使用配置文件）')
        string(name: 'PARALLEL_COUNT', defaultValue: '2', description: '测试并行线程数（BMS任务会自动强制串行）')
        string(name: 'SAMPLE_PER_MODULE', defaultValue: '5', description: '每个模块按 pytest 收集顺序抽取前 N 个用例执行。0 或留空表示跑完整模块。')
        string(name: 'PRIORITY_MODULES', defaultValue: 'iam,compute_non_bms,network', description: '优先串行执行的模块，逗号分隔。执行完后再按 RUN_PLAN 并发执行其余模块。')
        text(name: 'RUN_PLAN', defaultValue: '''[
  {"lane":"bigdata","modules":["bigdata"]},
  {"lane":"database","modules":["database"]},
  {"lane":"security","modules":["security"]},
  {"lane":"middleware","modules":["middleware"]},
  {"lane":"bms","modules":["bms"]},
  {"lane":"compute","modules":["compute_non_bms"]},
  {"lane":"container","modules":["container"]},
  {"lane":"network","modules":["network"]},
  {"lane":"storage","modules":["storage"]},
  {"lane":"backup","modules":["backup"]},
  {"lane":"iam","modules":["iam"]}
]''', description: '模块并发调度计划。lane 之间并行，lane 内模块按顺序串行执行。MODULES 非空时覆盖此计划。')
        string(name: 'MODULE_PARALLEL_MAP', defaultValue: 'bigdata=1,database=2,compute_non_bms=2,container=2,backup=2,iam=1,security=4,network=1,storage=2,middleware=2,bms=1', description: '模块并发数配置，逗号分隔。BMS 会强制串行。')
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
                    def defaultUser = 'admin'
                    def defaultPwd = 'keystone'
                    def defaultEnv = [
                        host: params.HOST,
                        stor: params.STOR,
                        user: defaultUser,
                        pwd : defaultPwd
                    ]
                    def storageDedicatedEnv = (params.STORAGE_DEDICATED_ENV == null) ? true : params.STORAGE_DEDICATED_ENV
                    def storageEnv = [
                        host: params.STORAGE_HOST ?: defaultEnv.host,
                        stor: params.STORAGE_STOR ?: defaultEnv.stor,
                        user: defaultUser,
                        pwd : defaultPwd
                    ]
                    def securityDedicatedEnv = (params.SECURITY_DEDICATED_ENV == null) ? true : params.SECURITY_DEDICATED_ENV
                    def securityEnv = [
                        host: params.SECURITY_HOST ?: defaultEnv.host,
                        stor: 'xbd',
                        user: defaultUser,
                        pwd : defaultPwd
                    ]

                    def parseEnvConfigs = { String value ->
                        def result = [:]
                        value?.split('\n')?.eachWithIndex { rawLine, index ->
                            def line = rawLine.trim()
                            if (!line || line.startsWith('#')) {
                                return
                            }
                            def parts = line.split('\\|', -1).collect { it.trim() }
                            if (!(parts.size() in [3, 5])) {
                                error "ENV_CONFIGS 第 ${index + 1} 行格式错误，正确格式：环境别名|host|stor，兼容旧格式：环境别名|host|stor|user|pwd"
                            }
                            result[parts[0]] = [
                                host: parts[1],
                                stor: parts[2],
                                user: parts.size() == 5 ? parts[3] : defaultUser,
                                pwd : parts.size() == 5 ? parts[4] : defaultPwd
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

                    def failedModules = []
                    def baseWorkspace = env.WORKSPACE_DIR ?: env.WORKSPACE
                    def markFilter = (params.MARK ?: '').trim().toLowerCase()
                    def jobName = (env.JOB_NAME ?: '').toLowerCase()
                    def isBmsRun = markFilter.contains('bms') || jobName.contains('bms')
                    def samplePerModule = (params.SAMPLE_PER_MODULE == null ? '5' : params.SAMPLE_PER_MODULE.trim())
                    if (!samplePerModule) {
                        samplePerModule = '0'
                    }
                    if (!(samplePerModule ==~ /^\d+$/)) {
                        error "SAMPLE_PER_MODULE 必须是非负整数，当前值: ${samplePerModule}"
                    }
                    def sampleLimit = samplePerModule.toInteger()

                    if (isBmsRun && (params.PARALLEL_COUNT ?: '2').trim() != '1') {
                        echo "BMS用例依赖同一裸金属资源，Jenkins执行时强制串行，避免资源争抢。"
                    }

                    def moduleParallelMap = [:]
                    (params.MODULE_PARALLEL_MAP ?: '').split(/[,\n]/).each { item ->
                        def entry = item.trim()
                        if (entry) {
                            def pair = entry.split('=', 2)
                            if (pair.size() == 2 && pair[0].trim() && pair[1].trim()) {
                                moduleParallelMap[pair[0].trim()] = pair[1].trim()
                            }
                        }
                    }

                    def sanitizeName = { value ->
                        value.toString().replaceAll('[^A-Za-z0-9_.-]', '_')
                    }

                    def resolveModuleConfig = { String moduleName ->
                        if (moduleName == 'bms') {
                            return [
                                target: "${baseWorkspace}/sugon_web/testcase/compute/test_bms_*.py",
                                check: "ls ${baseWorkspace}/sugon_web/testcase/compute/test_bms_*.py >/dev/null",
                                extra: "",
                                envKey: "compute",
                                markKey: "bms",
                                parallel: "1",
                                resultName: "bms"
                            ]
                        }
                        if (moduleName == 'compute_non_bms') {
                            return [
                                target: "${baseWorkspace}/sugon_web/testcase/compute",
                                check: "test -d '${baseWorkspace}/sugon_web/testcase/compute'",
                                extra: "--ignore-glob='*/test_bms_*.py'",
                                envKey: "compute",
                                markKey: "compute_non_bms",
                                parallel: (moduleParallelMap[moduleName] ?: params.PARALLEL_COUNT ?: '2').toString(),
                                resultName: "compute_non_bms"
                            ]
                        }
                        return [
                            target: "${baseWorkspace}/sugon_web/testcase/${moduleName}",
                            check: "test -d '${baseWorkspace}/sugon_web/testcase/${moduleName}'",
                            extra: "",
                            envKey: moduleName,
                            markKey: moduleName,
                            parallel: (moduleParallelMap[moduleName] ?: params.PARALLEL_COUNT ?: '2').toString(),
                            resultName: sanitizeName(moduleName)
                        ]
                    }

                    def resolveModuleEnv = { String moduleName ->
                        def cfg = resolveModuleConfig(moduleName)
                        if (storageDedicatedEnv && cfg.envKey == 'storage') {
                            return [
                                envName: 'storage_dedicated',
                                envCfg: defaultEnv + storageEnv
                            ]
                        }
                        if (securityDedicatedEnv && cfg.envKey == 'security') {
                            return [
                                envName: 'security_dedicated',
                                envCfg: defaultEnv + securityEnv
                            ]
                        }
                        def envName = moduleEnvMap[moduleName] ?: moduleEnvMap[cfg.envKey]
                        if (envName && !envConfigs[envName]) {
                            error "模块 ${moduleName} 指定的环境 ${envName} 不存在，请检查 ENV_CONFIGS"
                        }
                        return [
                            envName: envName,
                            envCfg: defaultEnv + (envName ? (envConfigs[envName] ?: [:]) : [:])
                        ]
                    }

                    def resolveModuleMark = { String moduleName ->
                        def cfg = resolveModuleConfig(moduleName)
                        return moduleMarkMap[moduleName] ?: moduleMarkMap[cfg.markKey] ?: params.MARK
                    }

                    def shellQuote = { String value ->
                        return "'" + value.replace("'", "'\"'\"'") + "'"
                    }

                    def buildBasePytestCommand = { String casePath, Map envCfg ->
                        return "pytest --headless=true " +
                            "--host=${envCfg.host ?: defaultEnv.host} " +
                            "--stor=${envCfg.stor ?: defaultEnv.stor} " +
                            "--username=${envCfg.user ?: defaultEnv.user} " +
                            "--password=${envCfg.pwd ?: defaultEnv.pwd} " +
                            "${casePath}"
                    }

                    def appendCommonPytestOptions = { String pytestCommand, String markExpr, String extraArgs ->
                        def cmd = pytestCommand
                        if (extraArgs) {
                            cmd += " ${extraArgs}"
                        }
                        if (markExpr) {
                            cmd += " -m '${markExpr}'"
                        }
                        if (params.RUN_LAST_FAILED) {
                            cmd += " --lf"
                        }
                        return cmd
                    }

                    def collectSampleNodeIds = { String casePath, Map envCfg, String resultName, String markExpr, String extraArgs ->
                        if (sampleLimit <= 0) {
                            return null
                        }
                        def collectCommand = appendCommonPytestOptions(buildBasePytestCommand(casePath, envCfg), markExpr, extraArgs)
                        collectCommand += " --collect-only -qq"
                        echo "Collect sample command (${resultName}, first ${sampleLimit}): ${collectCommand}"
                        def collectOutput = sh(script: collectCommand, returnStdout: true).trim()
                        def nodeIds = collectOutput.readLines()
                            .collect { it.trim() }
                            .findAll { it && it.contains('::') && !it.startsWith('=') }
                            .take(sampleLimit)
                        echo "Sampled ${nodeIds.size()} test(s) for ${resultName}: ${nodeIds.join(', ')}"
                        return nodeIds
                    }

                    def runPytest = { String casePath, Map envCfg, String resultName, String markExpr, String parallelCount, String extraArgs ->
                        def sampleNodeIds = collectSampleNodeIds(casePath, envCfg, resultName, markExpr, extraArgs)
                        if (sampleNodeIds != null && sampleNodeIds.isEmpty()) {
                            error "模块 ${resultName} 开启 SAMPLE_PER_MODULE=${sampleLimit}，但未收集到可执行用例"
                        }
                        def pytestTarget = sampleNodeIds != null ? sampleNodeIds.collect { shellQuote(it) }.join(' ') : casePath
                        def pytestCommand = buildBasePytestCommand(pytestTarget, envCfg) +
                            " --alluredir ${baseWorkspace}/allure-result/${resultName}"

                        if (extraArgs) {
                            pytestCommand += " ${extraArgs}"
                        }
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
                        if (parallelCount != '1') {
                            pytestCommand += " -n ${parallelCount} --dist=loadscope"
                        } else if (resultName == 'bms') {
                            echo "BMS 用例强制单进程执行，保证按 pytest 收集顺序执行并避免裸金属资源争抢。"
                        }

                        echo "Pytest command: ${pytestCommand}"
                        sh pytestCommand
                    }

                    def runModule = { String moduleName ->
                        stage("Module: ${moduleName}") {
                            def cfg = resolveModuleConfig(moduleName)
                            def moduleExists = sh(script: cfg.check, returnStatus: true)
                            if (moduleExists != 0) {
                                echo "模块 ${moduleName} 的测试目标不存在，跳过。check=${cfg.check}"
                                return
                            }
                            def resolvedEnv = resolveModuleEnv(moduleName)
                            def envCfg = resolvedEnv.envCfg
                            def markExpr = resolveModuleMark(moduleName)
                            echo "Resolved module ${moduleName}: host=${envCfg.host}, stor=${envCfg.stor}, user=${envCfg.user}, env=${resolvedEnv.envName ?: 'default'}, mark=${markExpr ?: 'default'}, parallel=${cfg.parallel}"
                            try {
                                runPytest(cfg.target, envCfg, cfg.resultName, markExpr, cfg.parallel, cfg.extra)
                            } catch (err) {
                                failedModules.add(moduleName)
                                currentBuild.result = 'FAILURE'
                                echo "模块 ${moduleName} 执行失败，继续执行后续模块: ${err}"
                            }
                        }
                    }

                    def buildRunPlan = {
                        if (params.MODULES?.trim()) {
                            def selectedModules = params.MODULES.split(/[,\s]+/).collect { it.trim() }.findAll { it }
                            return [[lane: 'selected', modules: selectedModules]]
                        }
                        if (isBmsRun) {
                            return [[lane: 'bms', modules: ['bms']]]
                        }
                        def planText = (params.RUN_PLAN ?: '').trim()
                        if (planText) {
                            def parsedPlan = []
                            def compactPlanText = planText.replace('\r', '').replace('\n', ' ')
                            def lanePattern = /\{\s*"lane"\s*:\s*"([^"]+)"\s*,\s*"modules"\s*:\s*\[([^\]]*)\]\s*\}/
                            def matcher = compactPlanText =~ lanePattern
                            matcher.each { match ->
                                def laneName = match[1].trim()
                                def modules = match[2].split(',').collect { rawModule ->
                                    def item = rawModule.trim()
                                    if (!(item ==~ /^"[^"]+"$/)) {
                                        error "RUN_PLAN 中 ${laneName} 的 modules 格式错误: ${item}"
                                    }
                                    return item.substring(1, item.length() - 1)
                                }.findAll { it }
                                parsedPlan.add([lane: laneName, modules: modules])
                            }
                            if (parsedPlan.isEmpty()) {
                                error 'RUN_PLAN 必须是非空 JSON 数组，格式示例：[{"lane":"database","modules":["database"]}]'
                            }
                            return parsedPlan
                        }
                        def moduleText = sh(
                            script: "find '${baseWorkspace}/sugon_web/testcase' -mindepth 2 -maxdepth 2 -name 'test_*.py' -print | awk -F/ '{print \$(NF-1)}' | sort -u",
                            returnStdout: true
                        ).trim()
                        def scannedModules = moduleText ? moduleText.split('\n').collect { it.trim() }.findAll { it } : []
                        echo "RUN_PLAN 和 MODULES 为空，自动扫描到模块: ${scannedModules.join(', ')}"
                        return [[lane: 'default', modules: scannedModules]]
                    }

                    def runPlan = buildRunPlan()
                    def parseModuleList = { String value ->
                        return value?.split(/[,\s]+/)?.collect { it.trim() }?.findAll { it } ?: []
                    }
                    def plannedModules = runPlan.collectMany { laneCfg ->
                        def laneModules = laneCfg.modules
                        return (laneModules instanceof List) ? laneModules.collect { it.toString() } : []
                    }.toSet()
                    def priorityModules = parseModuleList(params.PRIORITY_MODULES ?: '').findAll { plannedModules.contains(it) }
                    def priorityModuleSet = priorityModules.toSet()
                    if (priorityModules) {
                        echo "优先串行执行模块: ${priorityModules.join(', ')}"
                        priorityModules.each { moduleName ->
                            runModule(moduleName)
                        }
                    }

                    def branches = [:]
                    runPlan.eachWithIndex { laneCfg, index ->
                        def laneName = (laneCfg.lane ?: "lane-${index + 1}").toString()
                        def laneModules = laneCfg.modules
                        if (!(laneModules instanceof List) || laneModules.isEmpty()) {
                            error "RUN_PLAN 中 ${laneName} 缺少 modules"
                        }
                        def remainingModules = laneModules.collect { it.toString() }.findAll { !priorityModuleSet.contains(it) }
                        if (remainingModules.isEmpty()) {
                            echo "Lane ${laneName} 只包含优先模块，已在前置阶段执行，跳过并发分支。"
                        } else {
                            branches[laneName] = {
                                stage("Lane: ${laneName}") {
                                    remainingModules.each { moduleName ->
                                        runModule(moduleName)
                                    }
                                }
                            }
                        }
                    }
                    if (branches) {
                        branches.failFast = false
                        parallel branches
                    } else {
                        echo "没有剩余并发模块需要执行。"
                    }

                    if (failedModules) {
                        error "以下模块执行失败: ${failedModules.join(', ')}"
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
