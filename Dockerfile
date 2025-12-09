# base image
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble
LABEL maintainer="liaoxb24@gmail.com" \
      version="1.0" \
      description="Playwright test environment for SugonCloud Web testing"

# 安装JDK、vim
RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    vim \
 && rm -rf /var/lib/apt/lists/*

# 安装Allure
ADD allure-2.29.0.tgz /opt/

# 环境变量配置
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
    PATH=$JAVA_HOME/bin:$PATH \
    ALLURE_HOME=/opt/allure-2.29.0 \
    PATH=$ALLURE_HOME/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install pip requirements
COPY pip.conf /root/.pip/
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# 配置时区
RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# copy app
WORKDIR /sugon_web
COPY sugon_web /sugon_web

CMD ["bash"]
