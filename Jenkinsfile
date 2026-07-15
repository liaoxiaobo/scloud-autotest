pipeline {
    agent any
    parameters {
//         string(name: 'BRANCH', defaultValue: 'develop', description: '请输入正确Git分支名（如main、develop)', trim: true)
        choice(name: 'USER_ROLE', choices: ["admin", "dept_admin", "user"], description: '请选择测试用户角色')
        string(name: 'MARK', defaultValue: '', description: '标签筛选用例。模块级：container/compute/storage/network 等；服务级：cce/ecs/evs/obs/vpc 等；常用组合：storage and obs、compute and ecs、container and smoke、not slow。全局 marker 筛选，先筛选用例再分发。为空则执行所有用例')
        text(name: 'ENV_DISPATCH', defaultValue: '''- host: "172.22.1.190"
  stor: xstor
  parallel_count: 3''', description: 'JSON 或 YAML 格式环境调度配置，优先级高于 env.yaml。支持默认执行环境条目（无 modules/services/mark）和具体 dispatch 任务列表。默认执行环境用于兜底未分配的模块/服务。每项包含 host、modules/services/mark、stor，可选 parallel_count、bms。YAML 示例：\n# 默认执行环境（兜底）\n- host: "172.22.1.190"\n  stor: ceph\n  parallel_count: 3\n# 具体模块/服务调度\n- host: "172.22.3.140"\n  modules: [compute]\n  stor: xbd\n  parallel_count: 4\n- host: "172.22.1.190"\n  services: [evs, vpc]\n  stor: xstor\n  parallel_count: 2\n- host: "172.22.3.141"\n  modules: [bms]\n  stor: xbd\n  parallel_count: 1\n  bms:\n    instance_name: bms-0601\n    bmc_ip: 172.22.2.250\n    preferred_node: master03.cloud.local\n    network_name: bms-test\n    password: admin1234')
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
                    env.IMAGE_TAG = IMAGE_TAG // 写入环境变量，供 post 阶段安全读取
                    workspaceDir = "$workspace"  // 记录工作目录,供后续stage使用（容器内执行测试时需知道代码路径）
                    sh "docker build -t playwright-sugon:${IMAGE_TAG} ."
//                     sh  'printenv |sort'
                }
          }
      }

        stage('Parse Dispatch Config') {
            steps {
                script {
                    def useEnvDispatch = params.ENV_DISPATCH?.trim() ? true : false
                    if (useEnvDispatch) {
                        writeFile file: 'env-dispatch-input.yaml', text: params.ENV_DISPATCH.trim()
                    }

                    // 兜底默认值：ENV_DISPATCH 中的 default 条目优先级最高，其次为硬编码默认值
                    def fallbackHost = '172.22.1.190'
                    def fallbackStor = 'xstor'
                    def fallbackParallel = '2'

                    withEnv([
                        "DISPATCH_INPUT=${useEnvDispatch ? 'env-dispatch-input.yaml' : 'sugon_web/config/env.yaml'}",
                        "DISPATCH_USE_ENV=${useEnvDispatch ? '--use-env-dispatch' : ''}",
                        "DISPATCH_MARK=${params.MARK}",
                        "DISPATCH_HOST=${fallbackHost}",
                        "DISPATCH_STOR=${fallbackStor}",
                        "DISPATCH_PARALLEL=${fallbackParallel}",
                        "DISPATCH_HOSTS=${params.HOSTS}"
                    ]) {
                        docker.image("playwright-sugon:${IMAGE_TAG}").inside() {
                            sh 'python3 sugon_web/tools/dispatch_builder.py --input "$DISPATCH_INPUT" $DISPATCH_USE_ENV --mark "$DISPATCH_MARK" --host "$DISPATCH_HOST" --stor "$DISPATCH_STOR" --parallel "$DISPATCH_PARALLEL" --hosts "$DISPATCH_HOSTS"'
                        }
                    }

                    echo "本次调度计划（含默认兜底）: ${readFile('dispatch-jobs.json')}"
                }
            }
        }

        stage('Run Tests'){
          steps{
                script {
                    def jobs = []
                    def lines = readFile('dispatch-jobs.txt').split('\n')
                    def jobCount = lines[0].trim().toInteger()
                    for (int i = 1; i <= jobCount; i++) {
                        def parts = lines[i].split('\t', -1)
                        jobs << [host: parts[0], stor: parts[1], markExpr: parts[2], label: parts[3], parallelCount: parts.size() > 4 ? parts[4] : '', bms: parts.size() > 5 ? parts[5] : '{}']
                    }
                    def branches = [:]

                    jobs.each { job ->
                        def currentJob = job
                        branches["test-${currentJob.label}"] = {
                            docker.image("playwright-sugon:${IMAGE_TAG}").inside() {
                                def parallelCount = currentJob.parallelCount?.trim() ? currentJob.parallelCount : '2'
                                def bmsJson = currentJob.bms?.trim() ? currentJob.bms : '{}'
                                def isBmsJob = currentJob.markExpr?.trim() == 'bms'
                                def pytestTarget = isBmsJob ? "${workspaceDir}/sugon_web/testcase/compute/test_bms_*.py" : "\"${workspaceDir}/sugon_web/testcase/\""
                                def pytestCommand = "pytest --headless=true --host=${currentJob.host} --stor=${currentJob.stor} --user-role=${params.USER_ROLE} --env-label=${currentJob.label} ${pytestTarget}"

                                if (!isBmsJob) {
                                    pytestCommand += " -n ${parallelCount} --dist=loadscope"
                                } else {
                                    echo "BMS 用例强制单进程执行，按 pytest 收集顺序执行。"
                                }

                                if (currentJob.markExpr) {
                                    pytestCommand += " -m '${currentJob.markExpr}'"
                                }
                                if (params.RUN_LAST_FAILED) {
                                    pytestCommand += " --lf"
                                }

                                withEnv(['SUGON_BMS_OVERRIDE=' + bmsJson]) {
                                    def exitCode = sh(script: pytestCommand, returnStatus: true)

                                    if (exitCode != 0 && exitCode != 5) {
                                        error "pytest failed with exit code ${exitCode}"
                                    }
                                }
                            }
                        }
                    }

                    parallel branches
                }
          }
      }
    }
    post('Send Report') {
        always {
            script {
                // 合并各环境 allure-result 子目录到统一目录，并在 Docker 镜像内执行需要 Python 的步骤
                docker.image("playwright-sugon:${env.IMAGE_TAG}").inside() {
                    sh '''
                        mkdir -p allure-result
                        for d in allure-result/env-*; do
                            [ -d "$d" ] || continue
                            [ -n "$(ls -A "$d")" ] || continue
                            cp -rn "$d"/* allure-result/ || true
                        done
                        find allure-result -mindepth 2 -type d -name 'env-*' | while read -r d; do
                            [ -n "$(ls -A "$d")" ] || continue
                            cp -rn "$d"/* allure-result/ || true
                        done
                        # 合并后删除原 env-* 子目录，避免 AI/Allure 重复统计
                        rm -rf allure-result/env-* || true
                    '''

                    // 保留allure历史数据
                    sh "cp -r allure-report/history allure-result/ || true"

                    // 生成汇总 environment.properties，让总览页展示所有参与环境
                    sh "python3 sugon_web/tools/write_allure_environment.py --dispatch-json dispatch-jobs.json --output allure-result/environment.properties"

                    // 生成 AI 失败分析报告（失败不影响 Allure 报告生成）
                    script {
                        try {
                            withCredentials([
                                string(credentialsId: 'sugoncloud-api-key', variable: 'SUGON_API_KEY')
                            ]) {
                                sh '''
                                    python3 sugon_web/tools/failure_analysis_cli.py \
                                        --results-dir allure-result \
                                        --logs-dir logs \
                                        --output reports/ai-test-summary.md \
                                        --json-output reports/failure-report.json \
                                        --provider sugoncloud \
                                        --max-failures 100
                                '''
                            }
                        } catch (err) {
                            echo "AI report generation failed: ${err}"
                        }
                    }
                }
            }

            // 生成 Allure 报告
            allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-result']]

            // 归档 AI 报告等产物
            archiveArtifacts artifacts: 'reports/*.md', allowEmptyArchive: true

            // 留存 allure-result 作为 AI 分析调试输入材料
            script {
                try {
                    sh "tar -czf allure-result-build-${env.BUILD_NUMBER}.tar.gz allure-result || true"
                    archiveArtifacts artifacts: 'allure-result-build-*.tar.gz', allowEmptyArchive: true
                } catch (err) {
                    echo "Archive allure-result failed: ${err}"
                }
            }

            // 清理临时文件
            sh "rm -rf allure-result/env-* || true"
            sh "rm -rf allure-result/* || true"

            // 发送报告到飞书
            script {
                if (params.FEISHU_NOTIFY) {
                    sendNotification(currentBuild.currentResult)
                }
            }

            // 清理整个工作目录
            deleteDir()  // clean up our workspace

            // 仅清理本次构建产生的镜像，避免影响同节点其他任务
            script {
                if (env.IMAGE_TAG) {
                    sh "docker image rm playwright-sugon:${env.IMAGE_TAG} || true"
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

// 从 ENV_DISPATCH 文本中解析所有 host 并去重（支持 YAML/JSON 中的 host: "x.x.x.x" / host: x.x.x.x / "host": "x.x.x.x" 等写法）
def extractEnvHosts(String envDispatchText) {
    if (!envDispatchText?.trim()) {
        return []
    }
    def hosts = []
    def matcher = envDispatchText =~ /\bhost["']?\s*:\s*["']?([0-9.]+)["']?/
    while (matcher.find()) {
        hosts << matcher.group(1)
    }
    return hosts.unique()
}

// 发送飞书通知函数
def sendNotification(String result) {
    // 从 ENV_DISPATCH 中解析所有 host，去重后按 host:30000 格式列举
    def hosts = extractEnvHosts(params.ENV_DISPATCH)
    def envText = hosts ? hosts.collect { "${it}:30000" }.join('，') : '见 ENV_DISPATCH'

    // 读取 AI 报告执行概览并做简单转义，避免破坏 JSON
    def aiSummary = "未生成 AI 摘要"
    if (fileExists('reports/ai-test-summary.md')) {
        def rawSummary = readFile('reports/ai-test-summary.md')
            .split('## 失败分类统计')[0]
            .trim()
            .take(400)
        aiSummary = rawSummary.replaceAll('\r?\n', '\\\\n').replace('"', '\\"')
    }

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
                            "text": "测试模块: ${params.MARK ?: '（空）'}\\n测试环境：${envText}\\n测试结果: ${result}\\n开始时间: ${env.START_TIME}\\n结束时间: ${new Date().format("yyyy.MM.dd HH:mm:ss")}\\n\\n${aiSummary}\\n"
                        }, {
                            "tag": "a",
                            "text": "查看 AI 分析报告",
                            "href": "${env.BUILD_URL}artifact/reports/ai-test-summary.md/*view*/"
                        }, {
                            "tag": "text",
                            "text": "\\n"
                        }, {
                            "tag": "a",
                            "text": "查看 Allure 报告",
                            "href": "${env.BUILD_URL}allure/"
                        }]
                    ]
                }
            }
        }
    }' https://open.feishu.cn/open-apis/bot/v2/hook/6a07f306-b045-4748-bead-13ce14d9beda
    """
}
