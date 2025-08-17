# base image
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble
LABEL maintainer="liaoxb24@gmail.com"

# 安装OpenJDK、Allure
RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    vim \
 && rm -rf /var/lib/apt/lists/* 
ADD allure-2.29.0.tgz /opt/

# 设置环境变量
ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64
ENV PATH $JAVA_HOME/bin:$PATH
ENV ALLURE_HOME /opt/allure-2.29.0
ENV PATH $ALLURE_HOME/bin:$PATH

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY pip.conf /root/.pip/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 配置时区
RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# copy app
WORKDIR /sugon_web
COPY sugon_web /sugon_web

CMD ["bash"]
#pytest -s --alluredir ./allure-result 
#allure generate allure-result/ -o ./allure-report -c
#allure open -h xx.xx.xx.xx -p 8888 ./allure-report
